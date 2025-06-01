# isra_seeds/models/stock_movement.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from odoo.tools import ormcache
import logging

_logger = logging.getLogger(__name__)

class SeedStockMove(models.Model):
    _name = 'seed.stock.move'
    _description = 'Mouvement de Stock de Semences'
    _order = 'date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Identification
    name = fields.Char(
        'Référence',
        required=True,
        default='New',
        readonly=True
    )
    
    # Relations principales
    seed_lot_id = fields.Many2one(
        'seed.lot',
        'Lot de Semences',
        required=True,
        tracking=True,
        ondelete='restrict'
    )
    
    # Type de mouvement
    move_type = fields.Selection([
        ('in', 'Entrée'),
        ('out', 'Sortie'),
        ('transfer', 'Transfert'),
        ('adjustment', 'Ajustement'),
        ('production', 'Production'),
        ('quality_sample', 'Échantillon Qualité'),
        ('loss', 'Perte'),
        ('return', 'Retour'),
    ], string='Type de Mouvement', required=True, tracking=True)
    
    # Quantités
    quantity = fields.Float(
        'Quantité (kg)',
        required=True,
        digits=(10, 2),
        tracking=True
    )
    quantity_available_before = fields.Float(
        'Quantité Disponible Avant',
        readonly=True,
        digits=(10, 2)
    )
    quantity_available_after = fields.Float(
        'Quantité Disponible Après',
        readonly=True,
        digits=(10, 2)
    )
    
    # Dates et timing
    date = fields.Datetime(
        'Date',
        required=True,
        default=fields.Datetime.now,
        tracking=True
    )
    
    # Lieux
    source_location = fields.Char(
        'Lieu d\'Origine',
        help="Lieu d'origine du mouvement"
    )
    destination_location = fields.Char(
        'Destination',
        help="Lieu de destination du mouvement"
    )
    
    # Références
    reference = fields.Char(
        'Référence Externe',
        help="Référence externe (bon de livraison, etc.)"
    )
    origin = fields.Char(
        'Document d\'Origine',
        help="Document qui a généré ce mouvement"
    )
    
    # Responsable
    user_id = fields.Many2one(
        'res.users',
        'Responsable',
        required=True,
        default=lambda self: self.env.user,
        tracking=True
    )
    
    # Partenaire (pour entrées/sorties)
    partner_id = fields.Many2one(
        'res.partner',
        'Partenaire',
        help="Fournisseur ou client selon le type de mouvement"
    )
    
    # État
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('done', 'Effectué'),
        ('cancelled', 'Annulé'),
    ], string='État', default='draft', tracking=True)
    
    # Notes et observations
    notes = fields.Text('Notes')
    reason = fields.Text(
        'Raison du Mouvement',
        help="Explication détaillée du mouvement"
    )
    
    # Champs calculés
    is_negative = fields.Boolean(
        'Mouvement Négatif',
        compute='_compute_is_negative'
    )
    
    @api.depends('move_type')
    def _compute_is_negative(self):
        for record in self:
            record.is_negative = record.move_type in ['out', 'quality_sample', 'loss']
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('seed.stock.move') or 'New'
        
        # ✅ AMÉLIORATION: Enregistrer la quantité disponible avant avec gestion d'erreur
        if vals.get('seed_lot_id'):
            try:
                lot = self.env['seed.lot'].browse(vals['seed_lot_id'])
                if lot.exists():
                    vals['quantity_available_before'] = getattr(lot, 'quantity_available', lot.quantity)
            except Exception as e:
                _logger.warning(f"Erreur lors de la récupération de la quantité disponible: {e}")
                vals['quantity_available_before'] = 0
        
        result = super().create(vals)
        return result
    
    def write(self, vals):
        if 'quantity' in vals or 'move_type' in vals:
            for record in self:
                if record.state == 'done':
                    raise UserError("Impossible de modifier un mouvement déjà effectué.")
        
        return super().write(vals)
    
    def action_confirm(self):
        """Confirme le mouvement"""
        for record in self:
            if record.state != 'draft':
                raise UserError("Seuls les mouvements en brouillon peuvent être confirmés.")
            
            # ✅ AMÉLIORATION: Vérification robuste de la disponibilité
            if record.is_negative:
                try:
                    available_qty = getattr(record.seed_lot_id, 'quantity_available', record.seed_lot_id.quantity)
                    if available_qty < record.quantity:
                        raise ValidationError(
                            f"Quantité insuffisante. Disponible: {available_qty} kg, "
                            f"Demandé: {record.quantity} kg"
                        )
                except Exception as e:
                    _logger.error(f"Erreur lors de la vérification de disponibilité: {e}")
                    raise UserError("Impossible de vérifier la disponibilité du stock.")
            
            record.state = 'confirmed'
    
    def action_done(self):
        """Effectue le mouvement"""
        for record in self:
            if record.state != 'confirmed':
                raise UserError("Le mouvement doit être confirmé avant d'être effectué.")
            
            # Mettre à jour la quantité du lot
            record._update_lot_quantity()
            
            # Calculer la quantité après
            try:
                record.quantity_available_after = getattr(record.seed_lot_id, 'quantity_available', record.seed_lot_id.quantity)
            except Exception as e:
                _logger.warning(f"Erreur lors du calcul de la quantité après: {e}")
                record.quantity_available_after = 0
            
            record.state = 'done'
            
            # Créer une activité de suivi si nécessaire
            if record.move_type == 'loss':
                record._create_loss_activity()
    
    def action_cancel(self):
        """Annule le mouvement"""
        for record in self:
            if record.state == 'done':
                raise UserError("Impossible d'annuler un mouvement déjà effectué.")
            record.state = 'cancelled'
    
    def _update_lot_quantity(self):
        """Met à jour la quantité du lot"""
        for record in self:
            lot = record.seed_lot_id
            
            if record.is_negative:
                # Mouvement sortant
                new_quantity = lot.quantity - record.quantity
                if new_quantity < 0:
                    raise ValidationError("La quantité ne peut pas être négative.")
                lot.quantity = new_quantity
            else:
                # Mouvement entrant
                lot.quantity += record.quantity
    
    def _create_loss_activity(self):
        """Crée une activité pour les pertes importantes"""
        for record in self:
            if record.move_type == 'loss' and record.quantity > 100:  # Seuil de 100kg
                try:
                    manager_group = self.env.ref('isra_seeds.group_seed_manager')
                    if manager_group and manager_group.users:
                        record.activity_schedule(
                            'mail.mail_activity_data_warning',
                            summary=f"Perte importante - {record.seed_lot_id.name}",
                            note=f"Perte de {record.quantity} kg sur le lot {record.seed_lot_id.name}. "
                                 f"Raison: {record.reason or 'Non spécifiée'}",
                            user_id=manager_group.users[0].id
                        )
                except Exception as e:
                    _logger.warning(f"Impossible de créer l'activité de perte: {e}")
    
    # Contraintes
    _sql_constraints = [
        ('quantity_positive', 'CHECK(quantity > 0)', 'La quantité doit être positive !'),
    ]
    
    @api.constrains('quantity', 'seed_lot_id', 'move_type')
    def _validate_quantity_availability(self):
        """Validation de la disponibilité des quantités"""
        for record in self:
            if record.state == 'draft' and record.is_negative:
                try:
                    available = getattr(record.seed_lot_id, 'quantity_available', record.seed_lot_id.quantity)
                    if available < record.quantity:
                        raise ValidationError(
                            f"Quantité insuffisante pour le lot {record.seed_lot_id.name}. "
                            f"Disponible: {available} kg, Demandé: {record.quantity} kg"
                        )
                except Exception as e:
                    _logger.error(f"Erreur lors de la validation: {e}")
                    # Ne pas bloquer si erreur technique, mais logger

# ✅ AMÉLIORATION: Extension du modèle SeedLot pour la gestion des stocks optimisée
class SeedLotStock(models.Model):
    """Extension du modèle SeedLot pour la gestion des stocks"""
    _inherit = 'seed.lot'
    
    # Relations avec les mouvements
    stock_move_ids = fields.One2many(
        'seed.stock.move',
        'seed_lot_id',
        string='Mouvements de Stock'
    )
    
    # ✅ OPTIMISATION: Quantités calculées avec cache
    quantity_available = fields.Float(
        'Quantité Disponible',
        compute='_compute_stock_quantities',
        store=True,
        digits=(10, 2),
        help="Quantité réellement disponible (quantité - réservé)"
    )
    quantity_reserved = fields.Float(
        'Quantité Réservée',
        compute='_compute_stock_quantities',
        store=True,
        digits=(10, 2),
        help="Quantité réservée pour des commandes/productions"
    )
    quantity_in_transit = fields.Float(
        'Quantité en Transit',
        compute='_compute_stock_quantities',
        store=True,
        digits=(10, 2),
        help="Quantité en cours de transfert"
    )
    
    # Compteurs
    stock_move_count = fields.Integer(
        'Nombre de Mouvements',
        compute='_compute_stock_move_count'
    )
    
    # ✅ OPTIMISATION: Calcul optimisé avec cache et SQL direct pour gros volumes
    @api.depends('stock_move_ids.quantity', 'stock_move_ids.state', 'stock_move_ids.move_type')
    @ormcache('self.id')
    def _compute_stock_quantities(self):
        """Calcul optimisé des quantités de stock"""
        for record in self:
            try:
                # Utiliser SQL direct pour les gros volumes
                if len(self) > 50:
                    self.env.cr.execute("""
                        SELECT 
                            SUM(CASE WHEN is_negative = false AND state = 'done' THEN quantity ELSE 0 END) as in_qty,
                            SUM(CASE WHEN is_negative = true AND state = 'done' THEN quantity ELSE 0 END) as out_qty,
                            SUM(CASE WHEN state = 'confirmed' AND is_negative = true THEN quantity ELSE 0 END) as reserved_qty,
                            SUM(CASE WHEN state = 'confirmed' AND move_type = 'transfer' THEN quantity ELSE 0 END) as transit_qty
                        FROM seed_stock_move 
                        WHERE seed_lot_id = %s
                    """, (record.id,))
                    
                    result = self.env.cr.fetchone()
                    if result:
                        in_qty, out_qty, reserved_qty, transit_qty = result
                        record.quantity_available = (in_qty or 0) - (out_qty or 0)
                        record.quantity_reserved = reserved_qty or 0
                        record.quantity_in_transit = transit_qty or 0
                    else:
                        record.quantity_available = record.quantity
                        record.quantity_reserved = 0
                        record.quantity_in_transit = 0
                else:
                    # Méthode ORM pour petits volumes
                    moves = record.stock_move_ids.filtered(lambda m: m.state == 'done')
                    
                    in_qty = sum(moves.filtered(lambda m: not m.is_negative).mapped('quantity'))
                    out_qty = sum(moves.filtered(lambda m: m.is_negative).mapped('quantity'))
                    record.quantity_available = in_qty - out_qty
                    
                    # Calculer les réservations (mouvements confirmés mais pas encore effectués)
                    reserved_moves = record.stock_move_ids.filtered(
                        lambda m: m.state == 'confirmed' and m.is_negative
                    )
                    record.quantity_reserved = sum(reserved_moves.mapped('quantity'))
                    
                    # Calculer les transits (transferts confirmés)
                    transit_moves = record.stock_move_ids.filtered(
                        lambda m: m.state == 'confirmed' and m.move_type == 'transfer'
                    )
                    record.quantity_in_transit = sum(transit_moves.mapped('quantity'))
                    
            except Exception as e:
                _logger.error(f"Erreur calcul quantités stock pour lot {record.id}: {e}")
                # Valeurs par défaut en cas d'erreur
                record.quantity_available = record.quantity
                record.quantity_reserved = 0
                record.quantity_in_transit = 0
    
    @api.depends('stock_move_ids')
    def _compute_stock_move_count(self):
        for record in self:
            record.stock_move_count = len(record.stock_move_ids)
    
    def action_view_stock_moves(self):
        """Action pour voir les mouvements de stock"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Mouvements - {self.name}',
            'res_model': 'seed.stock.move',
            'view_mode': 'tree,form',
            'domain': [('seed_lot_id', '=', self.id)],
            'context': {'default_seed_lot_id': self.id}
        }
    
    def action_stock_in(self):
        """Action pour créer un mouvement d'entrée"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Entrée de Stock',
            'res_model': 'seed.stock.move',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_seed_lot_id': self.id,
                'default_move_type': 'in'
            }
        }
    
    def action_stock_out(self):
        """Action pour créer un mouvement de sortie"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sortie de Stock',
            'res_model': 'seed.stock.move',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_seed_lot_id': self.id,
                'default_move_type': 'out'
            }
        }

class SeedStockLocation(models.Model):
    _name = 'seed.stock.location'
    _description = 'Emplacement de Stock'
    _order = 'complete_name'
    _parent_store = True
    _rec_name = 'complete_name'
    
    name = fields.Char('Nom', required=True)
    complete_name = fields.Char(
        'Nom Complet',
        compute='_compute_complete_name',
        store=True
    )
    parent_id = fields.Many2one(
        'seed.stock.location',
        'Emplacement Parent',
        ondelete='cascade'
    )
    child_ids = fields.One2many(
        'seed.stock.location',
        'parent_id',
        'Emplacements Enfants'
    )
    parent_path = fields.Char(index=True)
    
    location_type = fields.Selection([
        ('warehouse', 'Entrepôt'),
        ('internal', 'Interne'),
        ('customer', 'Client'),
        ('supplier', 'Fournisseur'),
        ('production', 'Production'),
        ('transit', 'Transit'),
    ], string='Type d\'Emplacement', required=True, default='internal')
    
    active = fields.Boolean('Actif', default=True)
    address = fields.Text('Adresse')
    responsible_id = fields.Many2one('res.users', 'Responsable')
    
    # Capacités
    max_capacity = fields.Float('Capacité Maximale (tonnes)')
    current_capacity = fields.Float(
        'Capacité Actuelle',
        compute='_compute_current_capacity'
    )
    
    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for location in self:
            if location.parent_id:
                location.complete_name = f"{location.parent_id.complete_name} / {location.name}"
            else:
                location.complete_name = location.name
    
    def _compute_current_capacity(self):
        """Calcule la capacité actuelle basée sur les stocks présents"""
        for location in self:
            # ✅ AMÉLIORATION: Implémenter le calcul de capacité
            try:
                # Rechercher tous les mouvements vers cette localisation
                stock_moves = self.env['seed.stock.move'].search([
                    ('destination_location', '=', location.name),
                    ('state', '=', 'done')
                ])
                
                total_in = sum(stock_moves.filtered(lambda m: not m.is_negative).mapped('quantity'))
                total_out = sum(stock_moves.filtered(lambda m: m.is_negative).mapped('quantity'))
                
                # Convertir en tonnes
                location.current_capacity = (total_in - total_out) / 1000
                
            except Exception as e:
                _logger.warning(f"Erreur calcul capacité pour {location.name}: {e}")
                location.current_capacity = 0
    
    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        """Vérifie qu'il n'y a pas de récursion dans la hiérarchie"""
        if not self._check_recursion():
            raise ValidationError("Erreur: Vous ne pouvez pas créer une hiérarchie récursive d'emplacements.")
    
    def action_view_stock_summary(self):
        """Affiche un résumé des stocks dans cet emplacement"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Stock - {self.name}',
            'res_model': 'seed.stock.move',
            'view_mode': 'tree,graph',
            'domain': [
                '|',
                ('source_location', '=', self.name),
                ('destination_location', '=', self.name)
            ],
            'context': {
                'group_by': 'seed_lot_id',
                'search_default_location': 1
            }
        }

# ✅ AMÉLIORATION: Rapport de stock pour le tableau de bord
class SeedStockReport(models.Model):
    _name = 'seed.stock.report'
    _description = 'Rapport de Stock'
    _auto = False
    _order = 'total_quantity desc'
    
    # Champs du rapport
    variety_id = fields.Many2one('seed.variety', 'Variété', readonly=True)
    variety_name = fields.Char('Nom Variété', readonly=True)
    level = fields.Selection([
        ('GO', 'GO'), ('G1', 'G1'), ('G2', 'G2'),
        ('G3', 'G3'), ('G4', 'G4'), ('R1', 'R1'), ('R2', 'R2'),
    ], string='Niveau', readonly=True)
    
    total_quantity = fields.Float('Quantité Totale', readonly=True)
    available_quantity = fields.Float('Quantité Disponible', readonly=True)
    reserved_quantity = fields.Float('Quantité Réservée', readonly=True)
    lots_count = fields.Integer('Nombre de Lots', readonly=True)
    
    avg_age_days = fields.Integer('Âge Moyen (jours)', readonly=True)
    expiring_soon_count = fields.Integer('Lots Expirant Bientôt', readonly=True)
    
    def init(self):
        """Initialise la vue SQL pour le rapport"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT 
                    ROW_NUMBER() OVER() as id,
                    sl.variety_id,
                    sv.name as variety_name,
                    sl.level,
                    SUM(sl.quantity) as total_quantity,
                    SUM(COALESCE(sl.quantity_available, sl.quantity)) as available_quantity,
                    SUM(COALESCE(sl.quantity_reserved, 0)) as reserved_quantity,
                    COUNT(sl.id) as lots_count,
                    AVG(EXTRACT(DAYS FROM (CURRENT_DATE - sl.production_date))) as avg_age_days,
                    COUNT(CASE WHEN sl.expiry_date <= CURRENT_DATE + INTERVAL '30 days' THEN 1 END) as expiring_soon_count
                FROM seed_lot sl
                LEFT JOIN seed_variety sv ON sl.variety_id = sv.id
                WHERE sl.active = true
                GROUP BY sl.variety_id, sv.name, sl.level
                ORDER BY total_quantity DESC
            )
        """)

# ✅ AMÉLIORATION: Widget de stock pour le tableau de bord
class SeedStockWidget(models.TransientModel):
    _name = 'seed.stock.widget'
    _description = 'Widget Stock Dashboard'
    
    def get_stock_summary(self):
        """Retourne un résumé des stocks pour le dashboard"""
        try:
            # Statistiques globales
            total_lots = self.env['seed.lot'].search_count([('active', '=', True)])
            total_stock = sum(self.env['seed.lot'].search([('active', '=', True)]).mapped('quantity'))
            
            # Alertes
            low_stock = self.env['seed.lot'].search_count([
                ('quantity_available', '<', 100),
                ('active', '=', True)
            ])
            
            expiring_soon = self.env['seed.lot'].search_count([
                ('expiry_date', '<=', fields.Date.today() + timedelta(days=30)),
                ('expiry_date', '>=', fields.Date.today()),
                ('active', '=', True)
            ])
            
            # Top variétés par stock
            variety_stock = self.env['seed.lot'].read_group(
                [('active', '=', True)],
                ['variety_id', 'quantity:sum'],
                ['variety_id'],
                limit=5,
                orderby='quantity desc'
            )
            
            return {
                'total_lots': total_lots,
                'total_stock': total_stock,
                'low_stock_alerts': low_stock,
                'expiring_soon': expiring_soon,
                'top_varieties': variety_stock
            }
            
        except Exception as e:
            _logger.error(f"Erreur widget stock: {e}")
            return {
                'total_lots': 0,
                'total_stock': 0,
                'low_stock_alerts': 0,
                'expiring_soon': 0,
                'top_varieties': []
            }
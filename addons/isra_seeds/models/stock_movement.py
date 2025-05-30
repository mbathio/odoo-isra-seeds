# isra_seeds/models/stock_movement.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

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
        
        # Enregistrer la quantité disponible avant
        if vals.get('seed_lot_id'):
            lot = self.env['seed.lot'].browse(vals['seed_lot_id'])
            vals['quantity_available_before'] = lot.quantity_available
        
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
            
            # Vérifier la disponibilité pour les mouvements sortants
            if record.is_negative:
                available_qty = record.seed_lot_id.quantity_available
                if available_qty < record.quantity:
                    raise ValidationError(
                        f"Quantité insuffisante. Disponible: {available_qty} kg, "
                        f"Demandé: {record.quantity} kg"
                    )
            
            record.state = 'confirmed'
    
    def action_done(self):
        """Effectue le mouvement"""
        for record in self:
            if record.state != 'confirmed':
                raise UserError("Le mouvement doit être confirmé avant d'être effectué.")
            
            # Mettre à jour la quantité du lot
            record._update_lot_quantity()
            
            # Calculer la quantité après
            record.quantity_available_after = record.seed_lot_id.quantity_available
            
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
                record.activity_schedule(
                    'mail.mail_activity_data_warning',
                    summary=f"Perte importante - {record.seed_lot_id.name}",
                    note=f"Perte de {record.quantity} kg sur le lot {record.seed_lot_id.name}. "
                         f"Raison: {record.reason or 'Non spécifiée'}",
                    user_id=self.env.ref('isra_seeds.group_seed_manager').users[:1].id
                )
    
    # Contraintes
    _sql_constraints = [
        ('quantity_positive', 'CHECK(quantity > 0)', 'La quantité doit être positive !'),
    ]
    
    @api.constrains('quantity', 'seed_lot_id', 'move_type')
    def _check_quantity_availability(self):
        for record in self:
            if record.state == 'draft' and record.is_negative:
                available = record.seed_lot_id.quantity_available
                if available < record.quantity:
                    raise ValidationError(
                        f"Quantité insuffisante pour le lot {record.seed_lot_id.name}. "
                        f"Disponible: {available} kg, Demandé: {record.quantity} kg"
                    )

class SeedLotStock(models.Model):
    """Extension du modèle SeedLot pour la gestion des stocks"""
    _inherit = 'seed.lot'
    
    # Relations avec les mouvements
    stock_move_ids = fields.One2many(
        'seed.stock.move',
        'seed_lot_id',
        string='Mouvements de Stock'
    )
    
    # Quantités calculées
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
    
    @api.depends('stock_move_ids.quantity', 'stock_move_ids.state', 'stock_move_ids.move_type')
    def _compute_stock_quantities(self):
        for record in self:
            moves = record.stock_move_ids.filtered(lambda m: m.state == 'done')
            
            # Calculer la quantité disponible
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
        # Calculer la capacité actuelle basée sur les stocks présents
        for location in self:
            # Cette méthode devra être implémentée selon les besoins spécifiques
            location.current_capacity = 0
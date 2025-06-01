# models/seed_lot.py
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import json
import base64
from datetime import datetime, timedelta

class SeedLot(models.Model):
    _name = 'isra.seed.lot'
    _description = 'Lot de Semences'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'production_date desc, name'
    
    # === CHAMPS IDENTIFIANTS ===
    
    name = fields.Char(
        string='ID Lot',
        required=True,
        copy=False,
        readonly=True,
        default='/',  # Sera généré automatiquement
        help='Identifiant unique du lot (ex: SL-G1-2024-001)'
    )
    
    # === INFORMATIONS PRINCIPALES ===
    
    # Many2one = relation plusieurs vers 1 (comme varietyId dans Prisma)
    variety_id = fields.Many2one(
        comodel_name='isra.seed.variety',
        string='Variété',
        required=True,
        ondelete='restrict',  # Empêche la suppression si des lots existent
        tracking=True
    )
    
    level = fields.Selection([
        ('GO', 'GO - Semence de Base'),
        ('G1', 'G1 - Première Génération'),
        ('G2', 'G2 - Deuxième Génération'),
        ('G3', 'G3 - Troisième Génération'),
        ('G4', 'G4 - Quatrième Génération'),
        ('R1', 'R1 - Première Reproduction'),
        ('R2', 'R2 - Deuxième Reproduction')
    ], string='Niveau', required=True, tracking=True)
    
    quantity = fields.Float(
        string='Quantité (kg)',
        required=True,
        tracking=True,
        digits=(10, 2)
    )
    
    # Date = date seule (sans heure)
    production_date = fields.Date(
        string='Date de Production',
        required=True,
        default=fields.Date.today,
        tracking=True
    )
    
    expiry_date = fields.Date(
        string='Date d\'Expiration',
        compute='_compute_expiry_date',
        store=True,  # Stocké en base pour pouvoir filtrer dessus
        help='Calculée automatiquement selon le niveau'
    )
    
    # === RELATIONS ===
    
    multiplier_id = fields.Many2one(
        'isra.multiplier',
        string='Multiplicateur',
        tracking=True
    )
    
    parcel_id = fields.Many2one(
        'isra.parcel',
        string='Parcelle de Production'
    )
    
    # Auto-relation (parent/enfant)
    parent_lot_id = fields.Many2one(
        'isra.seed.lot',
        string='Lot Parent',
        help='Lot utilisé pour produire ce lot'
    )
    
    child_lot_ids = fields.One2many(
        'isra.seed.lot',
        'parent_lot_id',
        string='Lots Dérivés'
    )
    
    # === STATUT ET SUIVI ===
    
    status = fields.Selection([
        ('draft', 'Brouillon'),
        ('pending', 'En Attente de Certification'),
        ('certified', 'Certifié'),
        ('rejected', 'Rejeté'),
        ('in_stock', 'En Stock'),
        ('distributed', 'Distribué'),
        ('expired', 'Expiré')
    ], string='Statut', default='draft', tracking=True)
    
    # === QR CODE ===
    
    qr_code_data = fields.Text('Données QR Code')
    
    # Binary = fichier binaire (image, PDF, etc.)
    qr_code_image = fields.Binary(
        string='Image QR Code',
        attachment=True  # Stocké comme pièce jointe
    )
    
    # === NOTES ET OBSERVATIONS ===
    
    notes = fields.Text('Notes et Observations')
    
    batch_number = fields.Char('Numéro de Lot')
    
    is_active = fields.Boolean('Actif', default=True)
    
    # === CHAMPS CALCULÉS ===
    
    # Related = raccourci vers un champ d'une relation
    variety_code = fields.Char(
        related='variety_id.code',
        string='Code Variété',
        store=True  # Copié en base pour les recherches
    )
    
    days_to_expiry = fields.Integer(
        string='Jours avant Expiration',
        compute='_compute_days_to_expiry'
    )
    
    is_expired = fields.Boolean(
        string='Expiré',
        compute='_compute_is_expired'
    )
    
    quality_status = fields.Selection(
        related='latest_quality_control_id.result',
        string='Dernier Contrôle Qualité'
    )
    
    # === RELATIONS CALCULÉES ===
    
    quality_control_ids = fields.One2many(
        'isra.quality.control',
        'lot_id',
        string='Contrôles Qualité'
    )
    
    latest_quality_control_id = fields.Many2one(
        'isra.quality.control',
        compute='_compute_latest_quality_control',
        string='Dernier Contrôle'
    )
    
    quality_control_count = fields.Integer(
        compute='_compute_quality_control_count',
        string='Nb Contrôles'
    )
    
    # === CONTRAINTES ===
    
    _sql_constraints = [
        ('positive_quantity', 'CHECK(quantity > 0)', 'La quantité doit être positive'),
        ('unique_name', 'UNIQUE(name)', 'L\'identifiant du lot doit être unique'),
    ]
    
    # === MÉTHODES CALCULÉES ===
    
    @api.depends('production_date', 'level')
    def _compute_expiry_date(self):
        """Calcule la date d'expiration selon le niveau"""
        # Durées de validité par niveau (en années)
        validity_periods = {
            'GO': 2,
            'G1': 2,
            'G2': 2,
            'G3': 1,
            'G4': 1,
            'R1': 1,
            'R2': 1
        }
        
        for lot in self:
            if lot.production_date and lot.level:
                years = validity_periods.get(lot.level, 1)
                lot.expiry_date = lot.production_date + timedelta(days=365 * years)
            else:
                lot.expiry_date = False
    
    @api.depends('expiry_date')
    def _compute_days_to_expiry(self):
        """Calcule les jours restants avant expiration"""
        today = fields.Date.today()
        for lot in self:
            if lot.expiry_date:
                delta = lot.expiry_date - today
                lot.days_to_expiry = delta.days
            else:
                lot.days_to_expiry = 0
    
    @api.depends('days_to_expiry')
    def _compute_is_expired(self):
        """Détermine si le lot est expiré"""
        for lot in self:
            lot.is_expired = lot.days_to_expiry < 0
    
    @api.depends('quality_control_ids')
    def _compute_latest_quality_control(self):
        """Trouve le dernier contrôle qualité"""
        for lot in self:
            if lot.quality_control_ids:
                lot.latest_quality_control_id = lot.quality_control_ids.sorted('control_date', reverse=True)[0]
            else:
                lot.latest_quality_control_id = False
    
    @api.depends('quality_control_ids')
    def _compute_quality_control_count(self):
        """Compte les contrôles qualité"""
        for lot in self:
            lot.quality_control_count = len(lot.quality_control_ids)
    
    # === MÉTHODES CRUD ===
    
    @api.model
    def create(self, vals):
        """Création d'un nouveau lot"""
        # Générer l'ID automatiquement
        if vals.get('name', '/') == '/':
            vals['name'] = self._generate_lot_id(vals.get('level'))
        
        # Créer le lot
        lot = super().create(vals)
        
        # Générer le QR code
        lot._generate_qr_code()
        
        return lot
    
    def write(self, vals):
        """Modification d'un lot"""
        result = super().write(vals)
        
        # Régénérer le QR code si nécessaire
        if any(field in vals for field in ['variety_id', 'level', 'production_date']):
            self._generate_qr_code()
        
        return result
    
    # === MÉTHODES UTILITAIRES ===
    
    def _generate_lot_id(self, level):
        """Génère un ID unique pour le lot"""
        year = datetime.now().year
        sequence = self.env['ir.sequence'].next_by_code('isra.seed.lot.sequence') or '001'
        return f"SL-{level}-{year}-{sequence}"
    
    def _generate_qr_code(self):
        """Génère le QR code du lot"""
        for lot in self:
            # Données à encoder dans le QR code
            qr_data = {
                'lot_id': lot.name,
                'variety_name': lot.variety_id.name,
                'variety_code': lot.variety_id.code,
                'level': lot.level,
                'production_date': str(lot.production_date),
                'multiplier': lot.multiplier_id.name if lot.multiplier_id else '',
                'verification_url': f"https://isra.sn/verify/{lot.name}",
                'timestamp': datetime.now().isoformat()
            }
            
            # Encoder en JSON
            lot.qr_code_data = json.dumps(qr_data, ensure_ascii=False, indent=2)
            
            # Générer l'image QR (nécessite la librairie qrcode)
            try:
                import qrcode
                from io import BytesIO
                
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_M,
                    box_size=10,
                    border=4,
                )
                qr.add_data(lot.qr_code_data)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                
                lot.qr_code_image = base64.b64encode(buffer.getvalue())
            except ImportError:
                # Si qrcode n'est pas installé
                pass
    
    # === ACTIONS UTILISATEUR ===
    
    def action_certify(self):
        """Certifier le lot après contrôle qualité"""
        for lot in self:
            if not lot.quality_control_ids:
                raise UserError("Impossible de certifier sans contrôle qualité")
            
            latest_control = lot.latest_quality_control_id
            if latest_control.result != 'pass':
                raise UserError("Impossible de certifier un lot qui a échoué au contrôle qualité")
            
            lot.status = 'certified'
            
            # Envoyer notification
            lot.message_post(
                body=f"Le lot {lot.name} a été certifié avec succès.",
                message_type='notification'
            )
    
    def action_reject(self):
        """Rejeter le lot"""
        for lot in self:
            lot.status = 'rejected'
            lot.message_post(
                body=f"Le lot {lot.name} a été rejeté.",
                message_type='notification'
            )
    
    def action_view_genealogy(self):
        """Ouvrir la vue généalogique"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Généalogie - {self.name}',
            'res_model': 'isra.lot.genealogy.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_lot_id': self.id}
        }
    
    def action_print_qr_label(self):
        """Imprimer l'étiquette QR"""
        return self.env.ref('isra_seed_traceability.report_lot_qr_label').report_action(self)
    
    # === VALIDATIONS ===
    
    @api.constrains('parent_lot_id')
    def _check_parent_lot(self):
        """Vérifier la cohérence du lot parent"""
        for lot in self:
            if lot.parent_lot_id:
                # Le parent doit être d'un niveau inférieur
                parent_levels = ['GO', 'G1', 'G2', 'G3', 'G4', 'R1', 'R2']
                current_levels = ['G1', 'G2', 'G3', 'G4', 'R1', 'R2', 'R2']
                
                if lot.level in current_levels:
                    expected_parent_index = current_levels.index(lot.level)
                    if lot.parent_lot_id.level != parent_levels[expected_parent_index]:
                        raise ValidationError(
                            f"Un lot {lot.level} ne peut pas dériver d'un lot {lot.parent_lot_id.level}"
                        )
                
                # Même variété
                if lot.variety_id != lot.parent_lot_id.variety_id:
                    raise ValidationError("Le lot parent doit être de la même variété")
    
    @api.constrains('quantity')
    def _check_quantity(self):
        """Vérifier que la quantité est cohérente"""
        for lot in self:
            if lot.quantity <= 0:
                raise ValidationError("La quantité doit être positive")
            
            if lot.quantity > 50000:  # 50 tonnes max
                raise ValidationError("La quantité ne peut pas dépasser 50 tonnes")
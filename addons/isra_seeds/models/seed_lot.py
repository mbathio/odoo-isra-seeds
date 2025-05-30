# isra_seeds/models/seed_lot.py  
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import qrcode
import base64
from io import BytesIO
import json

class SeedLot(models.Model):
    _name = 'seed.lot'
    _description = 'Lot de Semences'
    _order = 'production_date desc, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'

    # Identification
    name = fields.Char(
        'Référence',
        required=True,
        default='New',
        readonly=True,
        tracking=True,
        help="Référence unique du lot"
    )
    display_name = fields.Char(
        'Nom d\'affichage',
        compute='_compute_display_name',
        store=True
    )
    
    # Relations principales
    variety_id = fields.Many2one(
        'seed.variety',
        'Variété',
        required=True,
        tracking=True,
        ondelete='restrict'
    )
    multiplier_id = fields.Many2one(
        'res.partner',
        'Multiplicateur',
        domain=[('is_multiplier', '=', True)],
        tracking=True
    )
    parcel_id = fields.Many2one(
        'agricultural.parcel',
        'Parcelle',
        tracking=True
    )
    
    # Niveau et hiérarchie
    level = fields.Selection([
        ('GO', 'GO - Semence de Pré-base'),
        ('G1', 'G1 - Semence de Base'),
        ('G2', 'G2 - Semence Certifiée R1'),
        ('G3', 'G3 - Semence Certifiée R2'),
        ('G4', 'G4 - Semence Certifiée R3'),
        ('R1', 'R1 - Semence Commerciale'),
        ('R2', 'R2 - Semence Commerciale'),
    ], string='Niveau', required=True, tracking=True)
    
    parent_lot_id = fields.Many2one(
        'seed.lot',
        'Lot Parent',
        tracking=True,
        help="Lot dont provient ce lot"
    )
    child_lot_ids = fields.One2many(
        'seed.lot',
        'parent_lot_id',
        string='Lots Descendants'
    )
    
    # Quantités et dates
    quantity = fields.Float(
        'Quantité (kg)',
        required=True,
        tracking=True,
        digits=(10, 2)
    )
    production_date = fields.Date(
        'Date de Production',
        required=True,
        tracking=True,
        default=fields.Date.today
    )
    expiry_date = fields.Date(
        'Date d\'Expiration',
        compute='_compute_expiry_date',
        store=True,
        help="Calculée automatiquement selon le type de semence"
    )
    
    # Statut et état
    status = fields.Selection([
        ('pending', 'En Attente'),
        ('certified', 'Certifié'),
        ('rejected', 'Rejeté'),
        ('in_stock', 'En Stock'),
        ('distributed', 'Distribué'),
        ('expired', 'Expiré'),
    ], string='Statut', default='pending', tracking=True)
    
    active = fields.Boolean('Actif', default=True)
    
    # Informations supplémentaires
    batch_number = fields.Char(
        'Numéro de Lot',
        tracking=True,
        help="Numéro de lot de production"
    )
    notes = fields.Text('Notes')
    
    # QR Code
    qr_code = fields.Text('Données QR Code')
    qr_code_image = fields.Binary(
        'Image QR Code',
        compute='_compute_qr_code_image'
    )
    
    # Relations
    quality_control_ids = fields.One2many(
        'seed.quality.control',
        'seed_lot_id',
        string='Contrôles Qualité'
    )
    production_ids = fields.One2many(
        'seed.production',
        'seed_lot_id',
        string='Productions'
    )
    
    # Champs calculés
    child_lot_count = fields.Integer(
        'Nombre de Lots Descendants',
        compute='_compute_child_lot_count'
    )
    quality_control_count = fields.Integer(
        'Nombre de Contrôles',
        compute='_compute_quality_control_count'
    )
    last_quality_result = fields.Selection([
        ('pass', 'Réussi'),
        ('fail', 'Échec'),
    ], string='Dernier Contrôle', compute='_compute_last_quality_result')
    
    is_expired = fields.Boolean(
        'Expiré',
        compute='_compute_is_expired'
    )
    
    @api.depends('name', 'variety_id.name', 'level')
    def _compute_display_name(self):
        for record in self:
            if record.variety_id:
                record.display_name = f"{record.name} - {record.variety_id.name} ({record.level})"
            else:
                record.display_name = record.name or 'Nouveau Lot'
    
    @api.depends('production_date', 'variety_id.crop_type')
    def _compute_expiry_date(self):
        for record in self:
            if record.production_date:
                # Durée de validité selon le type de culture (en mois)
                validity_months = {
                    'rice': 18,
                    'maize': 12,
                    'peanut': 12,
                    'sorghum': 24,
                    'cowpea': 18,
                    'millet': 24,
                }
                months = validity_months.get(record.variety_id.crop_type, 12)
                
                # Ajouter les mois à la date de production
                from dateutil.relativedelta import relativedelta
                record.expiry_date = record.production_date + relativedelta(months=months)
    
    @api.depends('child_lot_ids')
    def _compute_child_lot_count(self):
        for record in self:
            record.child_lot_count = len(record.child_lot_ids)
    
    @api.depends('quality_control_ids')
    def _compute_quality_control_count(self):
        for record in self:
            record.quality_control_count = len(record.quality_control_ids)
    
    @api.depends('quality_control_ids.result')
    def _compute_last_quality_result(self):
        for record in self:
            if record.quality_control_ids:
                last_control = record.quality_control_ids.sorted('control_date', reverse=True)[0]
                record.last_quality_result = last_control.result
            else:
                record.last_quality_result = False
    
    @api.depends('expiry_date')
    def _compute_is_expired(self):
        today = fields.Date.today()
        for record in self:
            record.is_expired = record.expiry_date and record.expiry_date < today
    
    def _compute_qr_code_image(self):
        for record in self:
            if record.qr_code:
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(record.qr_code)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                record.qr_code_image = base64.b64encode(buffer.getvalue())
            else:
                record.qr_code_image = False
    
    @api.model
    def create(self, vals):
        # Générer la référence automatiquement
        if vals.get('name', 'New') == 'New':
            level = vals.get('level', 'R1')
            sequence_code = f'seed.lot.{level.lower()}'
            vals['name'] = self.env['ir.sequence'].next_by_code(sequence_code) or 'New'
        
        lot = super().create(vals)
        
        # Générer le QR code
        lot._generate_qr_code()
        
        return lot
    
    def _generate_qr_code(self):
        """Génère le QR code pour le lot"""
        for record in self:
            qr_data = {
                'lot_id': record.name,
                'variety': record.variety_id.name,
                'level': record.level,
                'production_date': record.production_date.isoformat() if record.production_date else None,
                'multiplier': record.multiplier_id.name if record.multiplier_id else None,
                'verification_url': f'/seed-lot/{record.id}/verify'
            }
            record.qr_code = json.dumps(qr_data)
    
    def action_certify(self):
        """Certifie le lot"""
        self.write({'status': 'certified'})
        self.message_post(body="Lot certifié")
    
    def action_reject(self):
        """Rejette le lot"""
        self.write({'status': 'rejected'})
        self.message_post(body="Lot rejeté")
    
    def action_view_genealogy(self):
        """Affiche l'arbre généalogique"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Généalogie du Lot',
            'res_model': 'seed.lot',
            'view_mode': 'tree,form',
            'domain': [
                '|', 
                ('id', 'in', self._get_genealogy_ids()),
                ('parent_lot_id', 'in', self._get_genealogy_ids())
            ],
            'context': {'default_parent_lot_id': self.id}
        }
    
    def _get_genealogy_ids(self):
        """Récupère tous les IDs de la généalogie"""
        ids = [self.id]
        
        # Ancêtres
        current = self
        while current.parent_lot_id:
            ids.append(current.parent_lot_id.id)
            current = current.parent_lot_id
        
        # Descendants
        def get_children(lot):
            child_ids = []
            for child in lot.child_lot_ids:
                child_ids.append(child.id)
                child_ids.extend(get_children(child))
            return child_ids
        
        ids.extend(get_children(self))
        return ids
    
    # Contraintes
    _sql_constraints = [
        ('quantity_positive', 'CHECK(quantity > 0)', 'La quantité doit être positive !'),
    ]
    
    @api.constrains('parent_lot_id')
    def _check_parent_lot(self):
        for record in self:
            if record.parent_lot_id == record:
                raise ValidationError("Un lot ne peut pas être son propre parent !")
            
            # Vérifier les boucles dans la hiérarchie
            current = record.parent_lot_id
            while current:
                if current == record:
                    raise ValidationError("Boucle détectée dans la hiérarchie des lots !")
                current = current.parent_lot_id
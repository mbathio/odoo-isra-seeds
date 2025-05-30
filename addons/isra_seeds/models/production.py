# isra_seeds/models/production.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SeedProduction(models.Model):
    _name = 'seed.production'
    _description = 'Production de Semences'
    _order = 'start_date desc'
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
    multiplier_id = fields.Many2one(
        'res.partner',
        'Multiplicateur',
        domain=[('is_multiplier', '=', True)],
        required=True,
        tracking=True
    )
    parcel_id = fields.Many2one(
        'agricultural.parcel',
        'Parcelle',
        required=True,
        tracking=True
    )
    
    # Dates de production
    start_date = fields.Date(
        'Date de Début',
        required=True,
        tracking=True
    )
    end_date = fields.Date(
        'Date de Fin',
        tracking=True
    )
    sowing_date = fields.Date(
        'Date de Semis',
        tracking=True
    )
    harvest_date = fields.Date(
        'Date de Récolte',
        tracking=True
    )
    
    # Quantités et rendement
    planned_quantity = fields.Float(
        'Quantité Prévue (kg)',
        digits=(10, 2),
        help="Quantité de semences prévue à produire"
    )
    actual_yield = fields.Float(
        'Rendement Réel (kg)',
        digits=(10, 2),
        tracking=True,
        help="Quantité réellement produite"
    )
    yield_per_hectare = fields.Float(
        'Rendement/Ha (kg/ha)',
        compute='_compute_yield_per_hectare',
        store=True,
        help="Rendement par hectare"
    )
    
    # Statut
    status = fields.Selection([
        ('planned', 'Planifiée'),
        ('in_progress', 'En Cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée'),
    ], string='Statut', default='planned', tracking=True)
    
    # Conditions et pratiques
    weather_conditions = fields.Text(
        'Conditions Météorologiques',
        help="Description des conditions météo pendant la production"
    )
    cultural_practices = fields.Text(
        'Pratiques Culturales',
        help="Description des pratiques culturales utilisées"
    )
    
    # Notes et observations
    notes = fields.Text('Notes')
    problems_encountered = fields.Text('Problèmes Rencontrés')
    
    # Relations
    activity_ids = fields.One2many(
        'seed.production.activity',
        'production_id',
        string='Activités'
    )
    issue_ids = fields.One2many(
        'seed.production.issue',
        'production_id',
        string='Problèmes'
    )
    
    # Champs calculés
    activity_count = fields.Integer(
        'Nombre d\'Activités',
        compute='_compute_activity_count'
    )
    issue_count = fields.Integer(
        'Nombre de Problèmes',
        compute='_compute_issue_count'
    )
    open_issue_count = fields.Integer(
        'Problèmes Non Résolus',
        compute='_compute_open_issue_count'
    )
    duration_days = fields.Integer(
        'Durée (jours)',
        compute='_compute_duration_days'
    )
    
    @api.depends('actual_yield', 'parcel_id.area')
    def _compute_yield_per_hectare(self):
        for record in self:
            if record.actual_yield and record.parcel_id.area:
                record.yield_per_hectare = record.actual_yield / record.parcel_id.area
            else:
                record.yield_per_hectare = 0
    
    @api.depends('activity_ids')
    def _compute_activity_count(self):
        for record in self:
            record.activity_count = len(record.activity_ids)
    
    @api.depends('issue_ids')
    def _compute_issue_count(self):
        for record in self:
            record.issue_count = len(record.issue_ids)
    
    @api.depends('issue_ids.resolved')
    def _compute_open_issue_count(self):
        for record in self:
            record.open_issue_count = len(record.issue_ids.filtered(lambda x: not x.resolved))
    
    @api.depends('start_date', 'end_date')
    def _compute_duration_days(self):
        for record in self:
            if record.start_date and record.end_date:
                delta = record.end_date - record.start_date
                record.duration_days = delta.days
            else:
                record.duration_days = 0
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('seed.production') or 'New'
        return super().create(vals)
    
    def action_start_production(self):
        """Démarre la production"""
        self.write({
            'status': 'in_progress',
            'start_date': fields.Date.today()
        })
    
    def action_complete_production(self):
        """Termine la production"""
        self.write({
            'status': 'completed',
            'end_date': fields.Date.today()
        })
        
        # Créer automatiquement un nouveau lot si du rendement est obtenu
        if self.actual_yield:
            self._create_child_lot()
    
    def _create_child_lot(self):
        """Crée un lot enfant basé sur cette production"""
        next_level_map = {
            'GO': 'G1',
            'G1': 'G2',
            'G2': 'G3',
            'G3': 'G4',
            'G4': 'R1',
            'R1': 'R2',
        }
        
        parent_level = self.seed_lot_id.level
        child_level = next_level_map.get(parent_level, 'R2')
        
        child_lot = self.env['seed.lot'].create({
            'variety_id': self.seed_lot_id.variety_id.id,
            'level': child_level,
            'quantity': self.actual_yield,
            'production_date': self.harvest_date or fields.Date.today(),
            'multiplier_id': self.multiplier_id.id,
            'parcel_id': self.parcel_id.id,
            'parent_lot_id': self.seed_lot_id.id,
            'notes': f'Produit à partir de {self.seed_lot_id.name} - Production {self.name}',
        })
        
        self.message_post(
            body=f"Lot enfant créé automatiquement : {child_lot.name}"
        )
    
    # Contraintes
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.end_date < record.start_date:
                raise ValidationError("La date de fin doit être postérieure à la date de début !")
    
    @api.constrains('sowing_date', 'harvest_date')
    def _check_sowing_harvest_dates(self):
        for record in self:
            if record.sowing_date and record.harvest_date and record.harvest_date < record.sowing_date:
                raise ValidationError("La date de récolte doit être postérieure à la date de semis !")

class SeedProductionActivity(models.Model):
    _name = 'seed.production.activity'
    _description = 'Activité de Production'
    _order = 'activity_date desc'
    
    production_id = fields.Many2one(
        'seed.production',
        'Production',
        required=True,
        ondelete='cascade'
    )
    
    activity_type = fields.Selection([
        ('soil_preparation', 'Préparation du Sol'),
        ('sowing', 'Semis'),
        ('fertilization', 'Fertilisation'),
        ('irrigation', 'Irrigation'),
        ('weeding', 'Désherbage'),
        ('pest_control', 'Lutte Phytosanitaire'),
        ('harvest', 'Récolte'),
        ('other', 'Autre'),
    ], string='Type d\'Activité', required=True)
    
    activity_date = fields.Date(
        'Date d\'Activité',
        required=True,
        default=fields.Date.today
    )
    description = fields.Text('Description', required=True)
    
    # Personnel
    responsible_user_id = fields.Many2one(
        'res.users',
        'Responsable',
        default=lambda self: self.env.user
    )
    personnel = fields.Text(
        'Personnel Impliqué',
        help="Liste du personnel qui a participé à l'activité"
    )
    
    # Coûts et intrants
    cost = fields.Float('Coût (FCFA)', digits=(12, 2))
    input_ids = fields.One2many(
        'seed.production.input',
        'activity_id',
        string='Intrants Utilisés'
    )
    
    notes = fields.Text('Notes')

class SeedProductionInput(models.Model):
    _name = 'seed.production.input'
    _description = 'Intrant de Production'
    
    activity_id = fields.Many2one(
        'seed.production.activity',
        'Activité',
        required=True,
        ondelete='cascade'
    )
    
    name = fields.Char('Nom de l\'Intrant', required=True)
    quantity = fields.Float('Quantité', required=True)
    unit = fields.Char('Unité', required=True)
    unit_cost = fields.Float('Coût Unitaire (FCFA)')
    total_cost = fields.Float(
        'Coût Total (FCFA)',
        compute='_compute_total_cost',
        store=True
    )
    
    @api.depends('quantity', 'unit_cost')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = record.quantity * record.unit_cost

class SeedProductionIssue(models.Model):
    _name = 'seed.production.issue'
    _description = 'Problème de Production'
    _order = 'issue_date desc'
    
    production_id = fields.Many2one(
        'seed.production',
        'Production',
        required=True,
        ondelete='cascade'
    )
    
    issue_date = fields.Date(
        'Date du Problème',
        required=True,
        default=fields.Date.today
    )
    
    issue_type = fields.Selection([
        ('disease', 'Maladie'),
        ('pest', 'Ravageur'),
        ('weather', 'Conditions Météorologiques'),
        ('management', 'Gestion'),
        ('equipment', 'Équipement'),
        ('other', 'Autre'),
    ], string='Type de Problème', required=True)
    
    severity = fields.Selection([
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé'),
        ('critical', 'Critique'),
    ], string='Gravité', required=True, default='medium')
    
    description = fields.Text('Description', required=True)
    actions_taken = fields.Text('Actions Entreprises')
    
    # Résolution
    resolved = fields.Boolean('Résolu', default=False)
    resolved_date = fields.Date('Date de Résolution')
    resolution_notes = fields.Text('Notes de Résolution')
    
    # Coût et impact
    estimated_cost = fields.Float('Coût Estimé (FCFA)')
    actual_cost = fields.Float('Coût Réel (FCFA)')
    yield_impact = fields.Float(
        'Impact sur Rendement (%)',
        help="Pourcentage de perte de rendement estimée"
    )
    
    # Responsable
    reported_by = fields.Many2one(
        'res.users',
        'Signalé par',
        default=lambda self: self.env.user
    )
    
    def action_resolve(self):
        """Marque le problème comme résolu"""
        self.write({
            'resolved': True,
            'resolved_date': fields.Date.today()
        })

# Modèle pour les contrats de multiplication
class SeedContract(models.Model):
    _name = 'seed.contract'
    _description = 'Contrat de Multiplication'
    _order = 'start_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(
        'Référence',
        required=True,
        default='New',
        readonly=True
    )
    
    # Relations
    multiplier_id = fields.Many2one(
        'res.partner',
        'Multiplicateur',
        domain=[('is_multiplier', '=', True)],
        required=True,
        tracking=True
    )
    variety_id = fields.Many2one(
        'seed.variety',
        'Variété',
        required=True,
        tracking=True
    )
    
    # Dates
    start_date = fields.Date(
        'Date de Début',
        required=True,
        tracking=True
    )
    end_date = fields.Date(
        'Date de Fin',
        required=True,
        tracking=True
    )
    
    # Détails du contrat
    seed_level = fields.Selection([
        ('GO', 'GO'),
        ('G1', 'G1'),
        ('G2', 'G2'),
        ('G3', 'G3'),
        ('G4', 'G4'),
        ('R1', 'R1'),
        ('R2', 'R2'),
    ], string='Niveau de Semence', required=True)
    
    expected_quantity = fields.Float(
        'Quantité Attendue (kg)',
        required=True,
        digits=(10, 2)
    )
    actual_quantity = fields.Float(
        'Quantité Réelle (kg)',
        digits=(10, 2),
        tracking=True
    )
    
    # Termes financiers
    unit_price = fields.Float('Prix Unitaire (FCFA/kg)')
    total_amount = fields.Float(
        'Montant Total (FCFA)',
        compute='_compute_total_amount',
        store=True
    )
    advance_payment = fields.Float('Acompte (FCFA)')
    
    # Statut
    status = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé'),
    ], string='Statut', default='draft', tracking=True)
    
    # Termes et conditions
    payment_terms = fields.Text('Conditions de Paiement')
    quality_requirements = fields.Text('Exigences Qualité')
    delivery_terms = fields.Text('Conditions de Livraison')
    
    notes = fields.Text('Notes')
    
    @api.depends('expected_quantity', 'unit_price')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = record.expected_quantity * record.unit_price
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('seed.contract') or 'New'
        return super().create(vals)
    
    def action_activate(self):
        """Active le contrat"""
        self.write({'status': 'active'})
    
    def action_complete(self):
        """Termine le contrat"""
        self.write({'status': 'completed'})
    
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.end_date <= record.start_date:
                raise ValidationError("La date de fin doit être postérieure à la date de début !")
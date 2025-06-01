# isra_seeds/models/multiplier.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # Champ pour identifier les multiplicateurs
    is_multiplier = fields.Boolean('Est Multiplicateur', default=False)
    
    # Champs spécifiques aux multiplicateurs
    years_experience = fields.Integer(
        'Années d\'Expérience',
        help="Nombre d'années d'expérience en multiplication de semences"
    )
    certification_level = fields.Selection([
        ('beginner', 'Débutant'),
        ('intermediate', 'Intermédiaire'),
        ('expert', 'Expert'),
    ], string='Niveau de Certification')
    
    specialization = fields.Many2many(
        'seed.variety',
        'multiplier_variety_rel',
        'multiplier_id',
        'variety_id',
        string='Spécialisations',
        help="Variétés de semences dans lesquelles le multiplicateur est spécialisé"
    )
    
    multiplier_status = fields.Selection([
        ('active', 'Actif'),
        ('inactive', 'Inactif'),
        ('suspended', 'Suspendu'),
    ], string='Statut Multiplicateur', default='active')
    
    # Relations avec les semences
    seed_lot_ids = fields.One2many(
        'seed.lot',
        'multiplier_id',
        string='Lots de Semences'
    )
    parcel_ids = fields.One2many(
        'agricultural.parcel',
        'multiplier_id',
        string='Parcelles'
    )
    contract_ids = fields.One2many(
        'seed.contract',
        'multiplier_id',
        string='Contrats'
    )
    production_ids = fields.One2many(
        'seed.production',
        'multiplier_id',
        string='Productions'
    )
    
    # Champs calculés
    seed_lot_count = fields.Integer(
        'Nombre de Lots',
        compute='_compute_seed_lot_count'
    )
    parcel_count = fields.Integer(
        'Nombre de Parcelles',
        compute='_compute_parcel_count'
    )
    total_area = fields.Float(
        'Surface Totale (ha)',
        compute='_compute_total_area'
    )
    
    @api.depends('seed_lot_ids')
    def _compute_seed_lot_count(self):
        for record in self:
            record.seed_lot_count = len(record.seed_lot_ids)
    
    @api.depends('parcel_ids')
    def _compute_parcel_count(self):
        for record in self:
            record.parcel_count = len(record.parcel_ids)
    
    @api.depends('parcel_ids.area')
    def _compute_total_area(self):
        for record in self:
            record.total_area = sum(record.parcel_ids.mapped('area'))
    
    @api.constrains('years_experience')
    def _check_years_experience(self):
        for record in self:
            if record.is_multiplier and record.years_experience < 0:
                raise ValidationError("L'expérience ne peut pas être négative !")
# isra_seeds/models/seed_variety.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SeedVariety(models.Model):
    _name = 'seed.variety'
    _description = 'Variété de Semences'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Champs de base
    code = fields.Char(
        'Code', 
        required=True, 
        tracking=True,
        help="Code unique de la variété (ex: sahel108)"
    )
    name = fields.Char(
        'Nom', 
        required=True, 
        tracking=True,
        help="Nom de la variété"
    )
    crop_type = fields.Selection([
        ('rice', 'Riz'),
        ('maize', 'Maïs'), 
        ('peanut', 'Arachide'),
        ('sorghum', 'Sorgho'),
        ('cowpea', 'Niébé'),
        ('millet', 'Mil'),
    ], string='Type de Culture', required=True, tracking=True)
    
    # Caractéristiques techniques
    description = fields.Text('Description')
    maturity_days = fields.Integer(
        'Jours de Maturité', 
        help="Nombre de jours pour arriver à maturité"
    )
    yield_potential = fields.Float(
        'Potentiel de Rendement (t/ha)',
        digits=(5, 2),
        help="Rendement potentiel en tonnes par hectare"
    )
    resistances = fields.Text(
        'Résistances',
        help="Résistances aux maladies et parasites"
    )
    origin = fields.Char(
        'Origine',
        help="Origine de la variété (ex: AfricaRice, ISRA)"
    )
    release_year = fields.Integer(
        'Année de Release',
        help="Année de mise en circulation"
    )
    
    # Statut
    active = fields.Boolean('Actif', default=True)
    
    # Relations
    seed_lot_ids = fields.One2many(
        'seed.lot', 
        'variety_id', 
        string='Lots de Semences'
    )
    contract_ids = fields.One2many(
        'seed.contract',
        'variety_id',
        string='Contrats'
    )
    
    # Champs calculés
    seed_lot_count = fields.Integer(
        'Nombre de Lots',
        compute='_compute_seed_lot_count'
    )
    total_quantity = fields.Float(
        'Quantité Totale (kg)',
        compute='_compute_total_quantity'
    )
    
    @api.depends('seed_lot_ids')
    def _compute_seed_lot_count(self):
        for record in self:
            record.seed_lot_count = len(record.seed_lot_ids)
    
    @api.depends('seed_lot_ids.quantity')
    def _compute_total_quantity(self):
        for record in self:
            record.total_quantity = sum(record.seed_lot_ids.mapped('quantity'))
    
    # Contraintes
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Le code de la variété doit être unique !'),
    ]
    
    @api.constrains('release_year')
    def _check_release_year(self):
        current_year = fields.Date.today().year
        for record in self:
            if record.release_year and record.release_year > current_year:
                raise ValidationError("L'année de release ne peut pas être dans le futur !")
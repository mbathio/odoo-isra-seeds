# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SeedProduction(models.Model):
    _name = 'seed.production'
    _description = 'Production de Semences'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char('Référence', required=True, default='New')
    seed_lot_id = fields.Many2one('seed.lot', 'Lot de Semences', required=True)
    multiplier_id = fields.Many2one('res.partner', 'Multiplicateur')
    parcel_id = fields.Many2one('agricultural.parcel', 'Parcelle')
    
    start_date = fields.Date('Date de Début')
    end_date = fields.Date('Date de Fin')
    sowing_date = fields.Date('Date de Semis')
    harvest_date = fields.Date('Date de Récolte')
    
    planned_quantity = fields.Float('Quantité Prévue (kg)')
    actual_yield = fields.Float('Rendement Réel (kg)')
    
    status = fields.Selection([
        ('planned', 'Planifié'),
        ('in_progress', 'En Cours'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé'),
    ], string='Statut', default='planned')
    
    notes = fields.Text('Notes')
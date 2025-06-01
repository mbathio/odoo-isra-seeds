# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SeedContract(models.Model):
    _name = 'seed.contract'
    _description = 'Contrat de Multiplication'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char('Référence', required=True, default='New')
    multiplier_id = fields.Many2one('res.partner', 'Multiplicateur', required=True)
    variety_id = fields.Many2one('seed.variety', 'Variété', required=True)
    
    start_date = fields.Date('Date de Début')
    end_date = fields.Date('Date de Fin')
    
    expected_quantity = fields.Float('Quantité Attendue (kg)')
    seed_level = fields.Selection([
        ('GO', 'GO'), ('G1', 'G1'), ('G2', 'G2'),
        ('G3', 'G3'), ('G4', 'G4'), ('R1', 'R1'), ('R2', 'R2'),
    ], string='Niveau de Semence')
    
    status = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé'),
    ], string='Statut', default='draft')
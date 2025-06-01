# models/dashboard.py
from odoo import models, fields, api
from datetime import datetime, timedelta

class ISRADashboard(models.Model):
    _name = 'isra.dashboard'
    _description = 'Tableau de Bord ISRA'
    
    name = fields.Char('Nom', default='Tableau de Bord ISRA')
    
    # Statistiques générales
    total_varieties = fields.Integer('Total Variétés', compute='_compute_stats')
    total_lots = fields.Integer('Total Lots', compute='_compute_stats')
    total_multipliers = fields.Integer('Total Multiplicateurs', compute='_compute_stats')
    active_productions = fields.Integer('Productions Actives', compute='_compute_stats')
    
    # Statistiques qualité
    quality_pass_rate = fields.Float('Taux de Réussite Qualité (%)', compute='_compute_quality_stats')
    pending_certifications = fields.Integer('Certifications en Attente', compute='_compute_quality_stats')
    
    # Alertes
    expiring_lots_count = fields.Integer('Lots Expirant Bientôt', compute='_compute_alerts')
    rejected_lots_count = fields.Integer('Lots Rejetés ce Mois', compute='_compute_alerts')
    
    @api.depends()
    def _compute_stats(self):
        for dashboard in self:
            dashboard.total_varieties = self.env['isra.seed.variety'].search_count([('is_active', '=', True)])
            dashboard.total_lots = self.env['isra.seed.lot'].search_count([('is_active', '=', True)])
            dashboard.total_multipliers = self.env['isra.multiplier'].search_count([('is_active', '=', True)])
            dashboard.active_productions = self.env['isra.production'].search_count([('status', '=', 'in_progress')])
    
    @api.depends()
    def _compute_quality_stats(self):
        for dashboard in self:
            # Contrôles qualité du mois
            start_month = datetime.now().replace(day=1)
            quality_controls = self.env['isra.quality.control'].search([
                ('control_date', '>=', start_month)
            ])
            
            if quality_controls:
                passed = quality_controls.filtered(lambda qc: qc.result == 'pass')
                dashboard.quality_pass_rate = (len(passed) / len(quality_controls)) * 100
            else:
                dashboard.quality_pass_rate = 0.0
            
            dashboard.pending_certifications = self.env['isra.seed.lot'].search_count([
                ('status', '=', 'pending')
            ])
    
    @api.depends()
    def _compute_alerts(self):
        for dashboard in self:
            # Lots expirant dans 30 jours
            thirty_days_from_now = datetime.now().date() + timedelta(days=30)
            dashboard.expiring_lots_count = self.env['isra.seed.lot'].search_count([
                ('expiry_date', '<=', thirty_days_from_now),
                ('expiry_date', '>=', datetime.now().date()),
                ('status', 'in', ['certified', 'in_stock'])
            ])
            
            # Lots rejetés ce mois
            start_month = datetime.now().replace(day=1).date()
            dashboard.rejected_lots_count = self.env['isra.seed.lot'].search_count([
                ('status', '=', 'rejected'),
                ('write_date', '>=', start_month)
            ])
    
    def action_view_expiring_lots(self):
        """Action pour voir les lots qui expirent bientôt"""
        thirty_days_from_now = datetime.now().date() + timedelta(days=30)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Lots Expirant Bientôt',
            'res_model': 'isra.seed.lot',
            'view_mode': 'tree,form',
            'domain': [
                ('expiry_date', '<=', thirty_days_from_now),
                ('expiry_date', '>=', datetime.now().date()),
                ('status', 'in', ['certified', 'in_stock'])
            ],
            'context': {'search_default_group_expiry_date': 1}
        }
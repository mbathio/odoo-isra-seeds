# isra_seeds/models/alert_system.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class SeedAlert(models.Model):
    _name = 'seed.alert'
    _description = 'Système d\'Alertes'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Identification
    name = fields.Char('Référence', required=True, default='New', readonly=True)
    
    # Type d'alerte
    alert_type = fields.Selection([
        ('expiry', 'Expiration de Lot'),
        ('quality_failure', 'Échec Contrôle Qualité'),
        ('low_stock', 'Stock Faible'),
        ('production_delay', 'Retard de Production'),
        ('weather_warning', 'Alerte Météo'),
        ('contract_expiry', 'Expiration de Contrat'),
        ('certification_expiry', 'Expiration de Certification'),
        ('maintenance', 'Maintenance Requise'),
        ('custom', 'Personnalisée'),
    ], string='Type d\'Alerte', required=True)
    
    # Niveau de priorité
    priority = fields.Selection([
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé'),
        ('critical', 'Critique'),
    ], string='Priorité', required=True, default='medium')
    
    # Contenu de l'alerte
    title = fields.Char('Titre', required=True)
    message = fields.Text('Message', required=True)
    
    # Références
    seed_lot_id = fields.Many2one('seed.lot', 'Lot de Semences')
    quality_control_id = fields.Many2one('seed.quality.control', 'Contrôle Qualité')
    production_id = fields.Many2one('seed.production', 'Production')
    contract_id = fields.Many2one('seed.contract', 'Contrat')
    
    # Gestion des alertes
    status = fields.Selection([
        ('active', 'Active'),
        ('acknowledged', 'Acquittée'),
        ('resolved', 'Résolue'),
        ('dismissed', 'Ignorée'),
    ], string='Statut', default='active', tracking=True)
    
    # Utilisateurs concernés
    assigned_user_ids = fields.Many2many(
        'res.users',
        'seed_alert_user_rel',
        'alert_id',
        'user_id',
        string='Utilisateurs Assignés'
    )
    
    # Dates importantes
    trigger_date = fields.Datetime('Date de Déclenchement', default=fields.Datetime.now)
    due_date = fields.Datetime('Date d\'Échéance')
    acknowledged_date = fields.Datetime('Date d\'Acquittement')
    resolved_date = fields.Datetime('Date de Résolution')
    
    # Actions
    action_taken = fields.Text('Actions Entreprises')
    resolution_notes = fields.Text('Notes de Résolution')
    
    # Métadonnées
    auto_generated = fields.Boolean('Générée Automatiquement', default=True)
    recurring = fields.Boolean('Récurrente')
    next_alert_date = fields.Datetime('Prochaine Alerte')
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('seed.alert') or 'New'
        
        alert = super().create(vals)
        alert._send_notifications()
        return alert
    
    def action_acknowledge(self):
        """Acquitte l'alerte"""
        self.write({
            'status': 'acknowledged',
            'acknowledged_date': fields.Datetime.now()
        })
        self.message_post(body=f"Alerte acquittée par {self.env.user.name}")
    
    def action_resolve(self):
        """Marque l'alerte comme résolue"""
        self.write({
            'status': 'resolved',
            'resolved_date': fields.Datetime.now()
        })
        self.message_post(body=f"Alerte résolue par {self.env.user.name}")
    
    def action_dismiss(self):
        """Ignore l'alerte"""
        self.write({'status': 'dismissed'})
        self.message_post(body=f"Alerte ignorée par {self.env.user.name}")
    
    def _send_notifications(self):
        """Envoie les notifications aux utilisateurs concernés"""
        for alert in self:
            users = alert.assigned_user_ids
            if not users:
                # Si aucun utilisateur assigné, notifier les managers
                users = self.env.ref('isra_seeds.group_seed_manager').users
            
            for user in users:
                alert.activity_schedule(
                    'mail.mail_activity_data_warning',
                    user_id=user.id,
                    summary=alert.title,
                    note=alert.message,
                    date_deadline=alert.due_date.date() if alert.due_date else fields.Date.today()
                )
    
    @api.model
    def check_all_alerts(self):
        """Méthode appelée par le cron pour vérifier toutes les alertes"""
        self._check_expiry_alerts()
        self._check_quality_alerts()
        self._check_stock_alerts()
        self._check_production_alerts()
        self._check_contract_alerts()
    
    @api.model
    def _check_expiry_alerts(self):
        """Vérifie les lots qui expirent bientôt"""
        days_threshold = int(self.env['ir.config_parameter'].sudo().get_param(
            'seed.expiry_alert_days', 30
        ))
        
        alert_date = fields.Date.today() + timedelta(days=days_threshold)
        
        lots_expiring = self.env['seed.lot'].search([
            ('expiry_date', '<=', alert_date),
            ('expiry_date', '>=', fields.Date.today()),
            ('status', 'in', ['certified', 'in_stock']),
            ('active', '=', True)
        ])
        
        for lot in lots_expiring:
            # Vérifier si une alerte existe déjà
            existing_alert = self.search([
                ('alert_type', '=', 'expiry'),
                ('seed_lot_id', '=', lot.id),
                ('status', 'in', ['active', 'acknowledged'])
            ])
            
            if not existing_alert:
                days_until_expiry = (lot.expiry_date - fields.Date.today()).days
                
                if days_until_expiry <= 7:
                    priority = 'critical'
                elif days_until_expiry <= 15:
                    priority = 'high'
                else:
                    priority = 'medium'
                
                self.create({
                    'alert_type': 'expiry',
                    'priority': priority,
                    'title': f'Lot {lot.name} expire bientôt',
                    'message': f'Le lot {lot.name} ({lot.variety_id.name}) '
                              f'expire le {lot.expiry_date} (dans {days_until_expiry} jours)',
                    'seed_lot_id': lot.id,
                    'due_date': lot.expiry_date
                })
    
    @api.model
    def _check_quality_alerts(self):
        """Vérifie les échecs de contrôle qualité récents"""
        recent_date = fields.Date.today() - timedelta(days=7)
        
        failed_controls = self.env['seed.quality.control'].search([
            ('result', '=', 'fail'),
            ('control_date', '>=', recent_date),
            ('status', '=', 'completed')
        ])
        
        for control in failed_controls:
            existing_alert = self.search([
                ('alert_type', '=', 'quality_failure'),
                ('quality_control_id', '=', control.id),
                ('status', 'in', ['active', 'acknowledged'])
            ])
            
            if not existing_alert:
                self.create({
                    'alert_type': 'quality_failure',
                    'priority': 'high',
                    'title': f'Échec contrôle qualité - {control.seed_lot_id.name}',
                    'message': f'Le contrôle qualité {control.name} a échoué. '
                              f'Germination: {control.germination_rate}%, '
                              f'Pureté: {control.variety_purity}%',
                    'seed_lot_id': control.seed_lot_id.id,
                    'quality_control_id': control.id
                })
    
    @api.model
    def _check_stock_alerts(self):
        """Vérifie les stocks faibles"""
        # Seuil minimum configurable
        min_stock_threshold = float(self.env['ir.config_parameter'].sudo().get_param(
            'seed.min_stock_threshold', 100.0
        ))
        
        lots_low_stock = self.env['seed.lot'].search([
            ('quantity_available', '<', min_stock_threshold),
            ('quantity_available', '>', 0),
            ('status', 'in', ['certified', 'in_stock']),
            ('active', '=', True)
        ])
        
        for lot in lots_low_stock:
            existing_alert = self.search([
                ('alert_type', '=', 'low_stock'),
                ('seed_lot_id', '=', lot.id),
                ('status', 'in', ['active', 'acknowledged'])
            ])
            
            if not existing_alert:
                if lot.quantity_available <= 10:
                    priority = 'critical'
                elif lot.quantity_available <= 50:
                    priority = 'high'
                else:
                    priority = 'medium'
                
                self.create({
                    'alert_type': 'low_stock',
                    'priority': priority,
                    'title': f'Stock faible - {lot.name}',
                    'message': f'Le lot {lot.name} a un stock faible: '
                              f'{lot.quantity_available} kg disponibles',
                    'seed_lot_id': lot.id
                })
    
    @api.model
    def _check_production_alerts(self):
        """Vérifie les retards de production"""
        today = fields.Date.today()
        
        delayed_productions = self.env['seed.production'].search([
            ('status', '=', 'in_progress'),
            ('end_date', '<', today)
        ])
        
        for production in delayed_productions:
            existing_alert = self.search([
                ('alert_type', '=', 'production_delay'),
                ('production_id', '=', production.id),
                ('status', 'in', ['active', 'acknowledged'])
            ])
            
            if not existing_alert:
                delay_days = (today - production.end_date).days
                
                if delay_days > 30:
                    priority = 'critical'
                elif delay_days > 14:
                    priority = 'high'
                else:
                    priority = 'medium'
                
                self.create({
                    'alert_type': 'production_delay',
                    'priority': priority,
                    'title': f'Retard production - {production.name}',
                    'message': f'La production {production.name} est en retard de {delay_days} jours. '
                              f'Date de fin prévue: {production.end_date}',
                    'production_id': production.id
                })
    
    @api.model
    def _check_contract_alerts(self):
        """Vérifie les contrats qui expirent"""
        alert_date = fields.Date.today() + timedelta(days=30)
        
        expiring_contracts = self.env['seed.contract'].search([
            ('end_date', '<=', alert_date),
            ('end_date', '>=', fields.Date.today()),
            ('status', '=', 'active')
        ])
        
        for contract in expiring_contracts:
            existing_alert = self.search([
                ('alert_type', '=', 'contract_expiry'),
                ('contract_id', '=', contract.id),
                ('status', 'in', ['active', 'acknowledged'])
            ])
            
            if not existing_alert:
                days_until_expiry = (contract.end_date - fields.Date.today()).days
                
                if days_until_expiry <= 7:
                    priority = 'high'
                elif days_until_expiry <= 15:
                    priority = 'medium'
                else:
                    priority = 'low'
                
                self.create({
                    'alert_type': 'contract_expiry',
                    'priority': priority,
                    'title': f'Contrat {contract.name} expire bientôt',
                    'message': f'Le contrat {contract.name} avec {contract.multiplier_id.name} '
                              f'expire le {contract.end_date} (dans {days_until_expiry} jours)',
                    'contract_id': contract.id,
                    'due_date': contract.end_date
                })

class SeedNotificationSettings(models.Model):
    _name = 'seed.notification.settings'
    _description = 'Paramètres de Notification'
    
    user_id = fields.Many2one('res.users', 'Utilisateur', required=True)
    
    # Types d'alertes à recevoir
    receive_expiry_alerts = fields.Boolean('Alertes d\'Expiration', default=True)
    receive_quality_alerts = fields.Boolean('Alertes Qualité', default=True)
    receive_stock_alerts = fields.Boolean('Alertes Stock', default=True)
    receive_production_alerts = fields.Boolean('Alertes Production', default=True)
    receive_contract_alerts = fields.Boolean('Alertes Contrats', default=True)
    
    # Méthodes de notification
    email_notifications = fields.Boolean('Notifications Email', default=True)
    in_app_notifications = fields.Boolean('Notifications In-App', default=True)
    sms_notifications = fields.Boolean('Notifications SMS', default=False)
    
    # Fréquence
    notification_frequency = fields.Selection([
        ('immediate', 'Immédiate'),
        ('daily', 'Quotidienne'),
        ('weekly', 'Hebdomadaire'),
    ], string='Fréquence', default='immediate')
    
    # Horaires préférés
    preferred_time = fields.Float('Heure Préférée', default=9.0)  # 9h00
    
    @api.model
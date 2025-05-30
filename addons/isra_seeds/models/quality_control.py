# isra_seeds/models/quality_control.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SeedQualityControl(models.Model):
    _name = 'seed.quality.control'
    _description = 'Contrôle Qualité des Semences'
    _order = 'control_date desc'
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
    inspector_id = fields.Many2one(
        'res.users',
        'Inspecteur',
        required=True,
        default=lambda self: self.env.user,
        tracking=True
    )
    
    # Dates et timing
    control_date = fields.Date(
        'Date de Contrôle',
        required=True,
        default=fields.Date.today,
        tracking=True
    )
    sample_date = fields.Date(
        'Date d\'Échantillonnage',
        help="Date de prélèvement de l'échantillon"
    )
    
    # Tests principaux
    germination_rate = fields.Float(
        'Taux de Germination (%)',
        required=True,
        digits=(5, 2),
        tracking=True,
        help="Pourcentage de graines qui germent"
    )
    variety_purity = fields.Float(
        'Pureté Variétale (%)',
        required=True,
        digits=(5, 2),
        tracking=True,
        help="Pourcentage de pureté de la variété"
    )
    
    # Tests optionnels
    moisture_content = fields.Float(
        'Taux d\'Humidité (%)',
        digits=(5, 2),
        help="Taux d'humidité des semences"
    )
    seed_health = fields.Float(
        'Santé des Semences (%)',
        digits=(5, 2),
        help="Pourcentage de semences saines"
    )
    thousand_grain_weight = fields.Float(
        'Poids de 1000 Grains (g)',
        digits=(8, 2),
        help="Poids de 1000 graines en grammes"
    )
    
    # Tests spécialisés
    protein_content = fields.Float(
        'Teneur en Protéines (%)',
        digits=(5, 2)
    )
    oil_content = fields.Float(
        'Teneur en Huile (%)',
        digits=(5, 2)
    )
    
    # Impuretés
    other_seeds = fields.Float(
        'Autres Semences (%)',
        digits=(5, 2),
        help="Pourcentage d'autres espèces de semences"
    )
    inert_matter = fields.Float(
        'Matières Inertes (%)',
        digits=(5, 2),
        help="Pourcentage de matières inertes"
    )
    
    # Résultat et statut
    result = fields.Selection([
        ('pass', 'RÉUSSI'),
        ('fail', 'ÉCHEC'),
        ('pending', 'EN COURS'),
    ], string='Résultat', compute='_compute_result', store=True, tracking=True)
    
    status = fields.Selection([
        ('draft', 'Brouillon'),
        ('in_progress', 'En Cours'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé'),
    ], string='Statut', default='draft', tracking=True)
    
    # Informations méthodologiques
    test_method = fields.Selection([
        ('ista', 'Méthode ISTA'),
        ('aosa', 'Méthode AOSA'),
        ('national', 'Méthode Nationale'),
        ('custom', 'Méthode Personnalisée'),
    ], string='Méthode de Test', default='ista')
    
    sample_size = fields.Integer(
        'Taille de l\'Échantillon',
        help="Nombre de graines testées"
    )
    
    # Laboratoire et certification
    laboratory = fields.Char(
        'Laboratoire',
        help="Nom du laboratoire qui a effectué l'analyse"
    )
    laboratory_ref = fields.Char(
        'Référence Laboratoire',
        help="Référence du laboratoire pour ce test"
    )
    certificate_number = fields.Char(
        'Numéro de Certificat',
        help="Numéro du certificat de qualité"
    )
    
    # Observations et notes
    observations = fields.Text('Observations')
    recommendations = fields.Text('Recommandations')
    
    # Fichiers joints
    certificate_file = fields.Binary('Certificat PDF')
    certificate_filename = fields.Char('Nom du Certificat')
    test_report_file = fields.Binary('Rapport de Test')
    test_report_filename = fields.Char('Nom du Rapport')
    
    # Champs calculés
    total_impurities = fields.Float(
        'Total Impuretés (%)',
        compute='_compute_total_impurities'
    )
    
    @api.depends('germination_rate', 'variety_purity', 'seed_lot_id.level')
    def _compute_result(self):
        for record in self:
            if not record.germination_rate or not record.variety_purity:
                record.result = 'pending'
                continue
            
            # Seuils selon le niveau de semence
            thresholds = {
                'GO': {'germination': 98, 'purity': 99.9},
                'G1': {'germination': 95, 'purity': 99.5},
                'G2': {'germination': 90, 'purity': 99.0},
                'G3': {'germination': 85, 'purity': 98.0},
                'G4': {'germination': 80, 'purity': 97.0},
                'R1': {'germination': 80, 'purity': 97.0},
                'R2': {'germination': 80, 'purity': 95.0},
            }
            
            level = record.seed_lot_id.level
            threshold = thresholds.get(level, thresholds['R2'])
            
            if (record.germination_rate >= threshold['germination'] and 
                record.variety_purity >= threshold['purity']):
                record.result = 'pass'
            else:
                record.result = 'fail'
    
    @api.depends('other_seeds', 'inert_matter')
    def _compute_total_impurities(self):
        for record in self:
            record.total_impurities = (record.other_seeds or 0) + (record.inert_matter or 0)
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('seed.quality.control') or 'New'
        
        result = super().create(vals)
        
        # Mettre à jour le statut du lot selon le résultat
        result._update_lot_status()
        
        return result
    
    def write(self, vals):
        result = super().write(vals)
        
        # Mettre à jour le statut du lot si le résultat change
        if 'result' in vals:
            self._update_lot_status()
        
        return result
    
    def _update_lot_status(self):
        """Met à jour le statut du lot selon le résultat du contrôle"""
        for record in self:
            if record.result == 'pass':
                record.seed_lot_id.status = 'certified'
                record.seed_lot_id.message_post(
                    body=f"Lot certifié suite au contrôle qualité {record.name}"
                )
            elif record.result == 'fail':
                record.seed_lot_id.status = 'rejected'
                record.seed_lot_id.message_post(
                    body=f"Lot rejeté suite au contrôle qualité {record.name}"
                )
    
    def action_start_test(self):
        """Démarre le test"""
        self.write({'status': 'in_progress'})
    
    def action_complete_test(self):
        """Termine le test"""
        self.write({'status': 'completed'})
        
        # Envoyer une notification si le test échoue
        if self.result == 'fail':
            self._send_failure_notification()
    
    def _send_failure_notification(self):
        """Envoie une notification en cas d'échec"""
        # Trouver les utilisateurs à notifier (managers, admins)
        users_to_notify = self.env['res.users'].search([
            ('groups_id', 'in', [
                self.env.ref('isra_seeds.group_seed_manager').id,
                self.env.ref('base.group_system').id
            ])
        ])
        
        for user in users_to_notify:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                summary=f"Échec contrôle qualité - {self.seed_lot_id.name}",
                note=f"Le contrôle qualité du lot {self.seed_lot_id.name} a échoué. "
                     f"Taux de germination: {self.germination_rate}%, "
                     f"Pureté: {self.variety_purity}%"
            )
    
    # Contraintes
    _sql_constraints = [
        ('germination_rate_range', 'CHECK(germination_rate >= 0 AND germination_rate <= 100)', 
         'Le taux de germination doit être entre 0 et 100% !'),
        ('variety_purity_range', 'CHECK(variety_purity >= 0 AND variety_purity <= 100)', 
         'La pureté variétale doit être entre 0 et 100% !'),
        ('moisture_content_range', 'CHECK(moisture_content >= 0 AND moisture_content <= 100)', 
         'Le taux d\'humidité doit être entre 0 et 100% !'),
    ]
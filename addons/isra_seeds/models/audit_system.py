# isra_seeds/models/audit_system.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import json
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)

class SeedAuditLog(models.Model):
    _name = 'seed.audit.log'
    _description = 'Journal d\'Audit des Semences'
    _order = 'timestamp desc'
    _rec_name = 'display_name'

    # Identification
    display_name = fields.Char('Nom d\'affichage', compute='_compute_display_name', store=True)
    
    # Métadonnées de l'action
    user_id = fields.Many2one('res.users', 'Utilisateur', required=True)
    action = fields.Char('Action', required=True, size=100)
    model = fields.Char('Modèle', required=True, size=100)
    record_id = fields.Integer('ID Enregistrement', required=True)
    record_name = fields.Char('Nom de l\'Enregistrement', size=200)
    
    # Données de l'audit
    old_values = fields.Text('Anciennes Valeurs')
    new_values = fields.Text('Nouvelles Valeurs')
    changes_summary = fields.Text('Résumé des Changements')
    
    # Contexte
    timestamp = fields.Datetime('Horodatage', default=fields.Datetime.now, required=True)
    ip_address = fields.Char('Adresse IP', size=45)
    user_agent = fields.Char('User Agent', size=500)
    
    # Catégorisation
    category = fields.Selection([
        ('creation', 'Création'),
        ('modification', 'Modification'),
        ('deletion', 'Suppression'),
        ('access', 'Accès'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('approval', 'Approbation'),
        ('certification', 'Certification'),
    ], string='Catégorie', required=True)
    
    # Niveau de criticité
    criticality = fields.Selection([
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé'),
        ('critical', 'Critique'),
    ], string='Criticité', default='medium')
    
    # Relations pour traçabilité
    seed_lot_id = fields.Many2one('seed.lot', 'Lot de Semences')
    quality_control_id = fields.Many2one('seed.quality.control', 'Contrôle Qualité')
    production_id = fields.Many2one('seed.production', 'Production')
    
    @api.depends('action', 'model', 'record_name', 'user_id.name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.action} - {record.model}"
            if record.record_name:
                record.display_name += f" ({record.record_name})"
            record.display_name += f" par {record.user_id.name}"
    
    @api.model
    def log_action(self, model_name, record_id, action, old_values=None, new_values=None, 
                   category='modification', criticality='medium'):
        """Enregistre une action dans le journal d'audit"""
        try:
            # Récupérer des informations sur l'enregistrement
            record_name = None
            seed_lot_id = None
            quality_control_id = None
            production_id = None
            
            if model_name and record_id:
                try:
                    record_obj = self.env[model_name].browse(record_id)
                    if record_obj.exists():
                        record_name = record_obj.name_get()[0][1] if hasattr(record_obj, 'name_get') else str(record_obj.id)
                        
                        # Liens avec les entités principales
                        if model_name == 'seed.lot':
                            seed_lot_id = record_id
                        elif model_name == 'seed.quality.control':
                            quality_control_id = record_id
                            if hasattr(record_obj, 'seed_lot_id'):
                                seed_lot_id = record_obj.seed_lot_id.id
                        elif model_name == 'seed.production':
                            production_id = record_id
                            if hasattr(record_obj, 'seed_lot_id'):
                                seed_lot_id = record_obj.seed_lot_id.id
                except Exception as e:
                    _logger.warning(f"Erreur lors de la récupération des infos de l'enregistrement: {e}")
            
            # Générer le résumé des changements
            changes_summary = self._generate_changes_summary(old_values, new_values)
            
            # Créer l'entrée d'audit
            audit_entry = self.create({
                'user_id': self.env.user.id,
                'action': action,
                'model': model_name,
                'record_id': record_id,
                'record_name': record_name,
                'old_values': json.dumps(old_values, default=str) if old_values else None,
                'new_values': json.dumps(new_values, default=str) if new_values else None,
                'changes_summary': changes_summary,
                'category': category,
                'criticality': criticality,
                'seed_lot_id': seed_lot_id,
                'quality_control_id': quality_control_id,
                'production_id': production_id,
                'ip_address': self._get_client_ip(),
                'user_agent': self._get_user_agent(),
            })
            
            # Alertes pour actions critiques
            if criticality == 'critical':
                self._send_critical_action_alert(audit_entry)
            
            return audit_entry
            
        except Exception as e:
            _logger.error(f"Erreur lors de l'enregistrement de l'audit: {e}")
            return False
    
    def _generate_changes_summary(self, old_values, new_values):
        """Génère un résumé lisible des changements"""
        if not old_values or not new_values:
            return None
        
        try:
            old_dict = old_values if isinstance(old_values, dict) else {}
            new_dict = new_values if isinstance(new_values, dict) else {}
            
            changes = []
            
            # Champs modifiés
            for field, new_value in new_dict.items():
                old_value = old_dict.get(field)
                if old_value != new_value:
                    changes.append(f"{field}: '{old_value}' → '{new_value}'")
            
            # Nouveaux champs
            for field, value in new_dict.items():
                if field not in old_dict:
                    changes.append(f"Nouveau {field}: '{value}'")
            
            return '; '.join(changes) if changes else None
            
        except Exception as e:
            _logger.warning(f"Erreur lors de la génération du résumé: {e}")
            return "Changements non analysables"
    
    def _get_client_ip(self):
        """Récupère l'adresse IP du client"""
        try:
            request = self.env.context.get('request')
            if request:
                return request.httprequest.environ.get('REMOTE_ADDR')
        except:
            pass
        return None
    
    def _get_user_agent(self):
        """Récupère le User Agent du client"""
        try:
            request = self.env.context.get('request')
            if request:
                return request.httprequest.environ.get('HTTP_USER_AGENT')
        except:
            pass
        return None
    
    def _send_critical_action_alert(self, audit_entry):
        """Envoie une alerte pour les actions critiques"""
        try:
            # Notifier les administrateurs
            admin_users = self.env.ref('isra_seeds.group_seed_admin').users
            
            for admin in admin_users:
                audit_entry.activity_schedule(
                    'mail.mail_activity_data_warning',
                    user_id=admin.id,
                    summary=f"Action critique: {audit_entry.action}",
                    note=f"Action critique effectuée par {audit_entry.user_id.name}\n"
                         f"Modèle: {audit_entry.model}\n"
                         f"Changements: {audit_entry.changes_summary or 'N/A'}"
                )
        except Exception as e:
            _logger.error(f"Erreur lors de l'envoi d'alerte critique: {e}")
    
    @api.model
    def cleanup_old_logs(self, days_to_keep=365):
        """Nettoie les anciens logs d'audit"""
        cutoff_date = fields.Datetime.now() - timedelta(days=days_to_keep)
        old_logs = self.search([
            ('timestamp', '<', cutoff_date),
            ('criticality', '!=', 'critical')  # Garder les actions critiques plus longtemps
        ])
        
        count = len(old_logs)
        old_logs.unlink()
        
        _logger.info(f"Nettoyage des logs d'audit: {count} entrées supprimées")
        return count
    
    def action_view_related_logs(self):
        """Affiche les logs liés à cet enregistrement"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Logs d\'Audit Liés',
            'res_model': 'seed.audit.log',
            'view_mode': 'tree,form',
            'domain': [
                '|', '|',
                ('seed_lot_id', '=', self.seed_lot_id.id if self.seed_lot_id else False),
                ('quality_control_id', '=', self.quality_control_id.id if self.quality_control_id else False),
                ('production_id', '=', self.production_id.id if self.production_id else False)
            ]
        }

# ✅ CORRECTION: Mixin pour ajouter l'audit automatique aux modèles
class AuditMixin(models.AbstractModel):
    _name = 'seed.audit.mixin'
    _description = 'Mixin pour Audit Automatique'
    
    @api.model
    def create(self, vals):
        """Override create pour logger la création"""
        result = super().create(vals)
        
        if self._should_audit():
            self.env['seed.audit.log'].log_action(
                model_name=self._name,
                record_id=result.id,
                action='Création',
                new_values=vals,
                category='creation',
                criticality=self._get_audit_criticality('create')
            )
        
        return result
    
    def write(self, vals):
        """Override write pour logger les modifications"""
        old_values = {}
        if self._should_audit():
            # Capturer les anciennes valeurs
            for record in self:
                old_values[record.id] = {
                    field: getattr(record, field, None) 
                    for field in vals.keys() 
                    if hasattr(record, field)
                }
        
        result = super().write(vals)
        
        if self._should_audit():
            for record in self:
                self.env['seed.audit.log'].log_action(
                    model_name=self._name,
                    record_id=record.id,
                    action='Modification',
                    old_values=old_values.get(record.id),
                    new_values=vals,
                    category='modification',
                    criticality=self._get_audit_criticality('write')
                )
        
        return result
    
    def unlink(self):
        """Override unlink pour logger les suppressions"""
        if self._should_audit():
            for record in self:
                # Capturer les valeurs avant suppression
                values = {}
                for field in record._fields.values():
                    if not field.compute and hasattr(record, field.name):
                        try:
                            values[field.name] = getattr(record, field.name)
                        except:
                            pass  # Ignorer les erreurs d'accès
                
                self.env['seed.audit.log'].log_action(
                    model_name=self._name,
                    record_id=record.id,
                    action='Suppression',
                    old_values=values,
                    category='deletion',
                    criticality=self._get_audit_criticality('unlink')
                )
        
        return super().unlink()
    
    def _should_audit(self):
        """Détermine si ce modèle doit être audité"""
        # Par défaut, auditer tous les modèles qui héritent de ce mixin
        audit_enabled = self.env['ir.config_parameter'].sudo().get_param('seed.enable_audit_log', True)
        return audit_enabled and self._name.startswith('seed.')
    
    def _get_audit_criticality(self, operation):
        """Détermine la criticité selon l'opération"""
        criticality_map = {
            'create': 'medium',
            'write': 'medium',
            'unlink': 'high'
        }
        
        # Criticité spécifique par modèle
        if self._name == 'seed.quality.control' and operation in ['write', 'unlink']:
            return 'high'
        elif self._name == 'seed.lot' and operation == 'unlink':
            return 'critical'
        
        return criticality_map.get(operation, 'medium')

# ✅ CORRECTION: Extension des modèles existants pour l'audit - Héritage propre
class SeedLot(models.Model):
    _inherit = ['seed.lot', 'seed.audit.mixin']

class SeedQualityControl(models.Model):
    _inherit = ['seed.quality.control', 'seed.audit.mixin']

class SeedProduction(models.Model):
    _inherit = ['seed.production', 'seed.audit.mixin']

class SeedVariety(models.Model):
    _inherit = ['seed.variety', 'seed.audit.mixin']

# Signature électronique pour certificats
class SeedDigitalSignature(models.Model):
    _name = 'seed.digital.signature'
    _description = 'Signature Électronique'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # Identification
    name = fields.Char('Référence', required=True, default='New')
    
    # Document signé
    document_type = fields.Selection([
        ('quality_certificate', 'Certificat Qualité'),
        ('production_report', 'Rapport Production'),
        ('contract', 'Contrat'),
        ('audit_report', 'Rapport Audit'),
    ], string='Type de Document', required=True)
    
    # Relations
    quality_control_id = fields.Many2one('seed.quality.control', 'Contrôle Qualité')
    production_id = fields.Many2one('seed.production', 'Production')
    contract_id = fields.Many2one('seed.contract', 'Contrat')
    
    # Signataire
    signer_id = fields.Many2one('res.users', 'Signataire', required=True)
    signer_role = fields.Char('Rôle du Signataire')
    
    # Signature
    signature_date = fields.Datetime('Date de Signature', default=fields.Datetime.now)
    signature_hash = fields.Char('Hash de Signature', readonly=True)
    certificate_serial = fields.Char('Numéro de Certificat')
    
    # Validation
    is_valid = fields.Boolean('Signature Valide', default=True)
    validation_date = fields.Datetime('Date de Validation')
    validation_method = fields.Selection([
        ('internal', 'Validation Interne'),
        ('external', 'Service Externe'),
        ('manual', 'Validation Manuelle'),
    ], string='Méthode de Validation')
    
    # Métadonnées
    document_content_hash = fields.Char('Hash du Contenu')
    signature_algorithm = fields.Char('Algorithme', default='SHA-256')
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('seed.digital.signature') or 'New'
        
        signature = super().create(vals)
        signature._generate_signature_hash()
        return signature
    
    def _generate_signature_hash(self):
        """Génère le hash de signature"""
        import hashlib
        
        for record in self:
            # Créer une chaîne unique basée sur les données
            signature_string = f"{record.signer_id.id}{record.signature_date}{record.document_type}"
            if record.quality_control_id:
                signature_string += str(record.quality_control_id.id)
            
            # Générer le hash
            record.signature_hash = hashlib.sha256(signature_string.encode()).hexdigest()
    
    def sign_certificate(self, quality_control_id):
        """Signe électroniquement un certificat qualité"""
        quality_control = self.env['seed.quality.control'].browse(quality_control_id)
        if not quality_control.exists():
            raise ValidationError("Contrôle qualité introuvable")
        
        # Vérifier les permissions
        if not self.env.user.has_group('isra_seeds.group_seed_inspector'):
            raise ValidationError("Seuls les inspecteurs peuvent signer les certificats")
        
        # Créer la signature
        signature = self.create({
            'document_type': 'quality_certificate',
            'quality_control_id': quality_control_id,
            'signer_id': self.env.user.id,
            'signer_role': 'Inspecteur Qualité',
            'document_content_hash': self._calculate_document_hash(quality_control)
        })
        
        # Mettre à jour le statut du contrôle
        quality_control.write({
            'status': 'completed',
            'certificate_number': signature.name
        })
        
        # Logger l'action
        self.env['seed.audit.log'].log_action(
            model_name='seed.quality.control',
            record_id=quality_control_id,
            action='Signature Électronique',
            new_values={'certificate_signed': True, 'signature_id': signature.id},
            category='certification',
            criticality='high'
        )
        
        return signature
    
    def _calculate_document_hash(self, document):
        """Calcule le hash du contenu du document"""
        import hashlib
        
        # Créer une représentation du document
        content = ""
        if hasattr(document, 'name'):
            content += str(document.name)
        if hasattr(document, 'germination_rate'):
            content += str(document.germination_rate)
        if hasattr(document, 'variety_purity'):
            content += str(document.variety_purity)
        
        return hashlib.sha256(content.encode()).hexdigest()
    
    def validate_signature(self):
        """Valide la signature électronique"""
        for record in self:
            # Vérifications de base
            if not record.signature_hash:
                record.is_valid = False
                continue
            
            # Vérifier l'intégrité du document
            if record.quality_control_id:
                current_hash = record._calculate_document_hash(record.quality_control_id)
                if current_hash != record.document_content_hash:
                    record.is_valid = False
                    record.message_post(
                        body="⚠️ Signature invalidée: le document a été modifié après signature"
                    )
                    continue
            
            # Vérifier la validité temporelle (ex: signature pas trop ancienne)
            if record.signature_date:
                days_old = (fields.Datetime.now() - record.signature_date).days
                if days_old > 365:  # Signature de plus d'un an
                    record.message_post(
                        body="⚠️ Attention: signature de plus d'un an"
                    )
            
            record.validation_date = fields.Datetime.now()
            record.validation_method = 'internal'
    
    def action_invalidate_signature(self):
        """Invalide une signature"""
        for record in self:
            record.is_valid = False
            record.message_post(
                body=f"Signature invalidée par {self.env.user.name}"
            )
            
            # Logger l'action critique
            self.env['seed.audit.log'].log_action(
                model_name='seed.digital.signature',
                record_id=record.id,
                action='Invalidation Signature',
                old_values={'is_valid': True},
                new_values={'is_valid': False},
                category='modification',
                criticality='critical'
            )

class SeedComplianceCheck(models.Model):
    _name = 'seed.compliance.check'
    _description = 'Vérification de Conformité'
    
    name = fields.Char('Référence', required=True, default='New')
    
    # Type de vérification
    check_type = fields.Selection([
        ('regulatory', 'Conformité Réglementaire'),
        ('quality_standard', 'Standard Qualité'),
        ('traceability', 'Traçabilité'),
        ('documentation', 'Documentation'),
        ('storage', 'Conditions de Stockage'),
    ], string='Type de Vérification', required=True)
    
    # Cible de la vérification
    target_type = fields.Selection([
        ('lot', 'Lot de Semences'),
        ('production', 'Production'),
        ('facility', 'Installation'),
        ('process', 'Processus'),
    ], string='Cible', required=True)
    
    seed_lot_id = fields.Many2one('seed.lot', 'Lot de Semences')
    production_id = fields.Many2one('seed.production', 'Production')
    
    # Résultats
    check_date = fields.Date('Date de Vérification', default=fields.Date.today)
    inspector_id = fields.Many2one('res.users', 'Inspecteur', default=lambda self: self.env.user)
    
    result = fields.Selection([
        ('compliant', 'Conforme'),
        ('non_compliant', 'Non Conforme'),
        ('partial', 'Partiellement Conforme'),
        ('pending', 'En Attente'),
    ], string='Résultat', default='pending')
    
    score = fields.Float('Score (%)', digits=(5, 2))
    
    # Détails
    checklist_items = fields.One2many(
        'seed.compliance.item',
        'check_id',
        string='Éléments de Vérification'
    )
    
    non_conformities = fields.Text('Non-Conformités Identifiées')
    corrective_actions = fields.Text('Actions Correctives Requises')
    
    # Suivi
    status = fields.Selection([
        ('draft', 'Brouillon'),
        ('in_progress', 'En Cours'),
        ('completed', 'Terminé'),
        ('reviewed', 'Révisé'),
    ], string='Statut', default='draft')
    
    next_check_date = fields.Date('Prochaine Vérification')
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('seed.compliance.check') or 'New'
        return super().create(vals)
    
    def action_start_check(self):
        """Démarre la vérification"""
        self.write({'status': 'in_progress'})
        self._populate_checklist()
    
    def action_complete_check(self):
        """Termine la vérification"""
        self._calculate_score()
        self._determine_result()
        self.write({'status': 'completed'})
        
        if self.result == 'non_compliant':
            self._create_corrective_actions()
    
    def _populate_checklist(self):
        """Remplit la checklist selon le type de vérification"""
        items_data = []
        
        if self.check_type == 'quality_standard':
            items_data = [
                {'name': 'Taux de germination conforme', 'requirement': 'Selon standards ISTA'},
                {'name': 'Pureté variétale respectée', 'requirement': 'Minimum 95%'},
                {'name': 'Humidité acceptable', 'requirement': 'Maximum 14%'},
                {'name': 'Absence de contaminants', 'requirement': 'Contrôle visuel'},
            ]
        elif self.check_type == 'traceability':
            items_data = [
                {'name': 'Généalogie documentée', 'requirement': 'Traçabilité complète'},
                {'name': 'QR codes présents', 'requirement': 'Tous les lots'},
                {'name': 'Données de production', 'requirement': 'Complètes et exactes'},
                {'name': 'Contrôles qualité', 'requirement': 'Documentés et valides'},
            ]
        
        for item_data in items_data:
            self.env['seed.compliance.item'].create({
                'check_id': self.id,
                'name': item_data['name'],
                'requirement': item_data['requirement'],
                'status': 'pending'
            })
    
    def _calculate_score(self):
        """Calcule le score de conformité"""
        items = self.checklist_items
        if not items:
            self.score = 0
            return
        
        compliant_items = items.filtered(lambda i: i.status == 'compliant')
        self.score = (len(compliant_items) / len(items)) * 100
    
    def _determine_result(self):
        """Détermine le résultat global"""
        if self.score >= 95:
            self.result = 'compliant'
        elif self.score >= 70:
            self.result = 'partial'
        else:
            self.result = 'non_compliant'
    
    def _create_corrective_actions(self):
        """Crée des actions correctives pour les non-conformités"""
        non_compliant_items = self.checklist_items.filtered(lambda i: i.status == 'non_compliant')
        
        for item in non_compliant_items:
            self.env['seed.corrective.action'].create({
                'name': f"Corriger: {item.name}",
                'compliance_check_id': self.id,
                'description': item.comment or 'Non-conformité détectée',
                'responsible_id': self.inspector_id.id,
                'due_date': fields.Date.today() + timedelta(days=30),
                'priority': 'high' if self.result == 'non_compliant' else 'medium'
            })

class SeedComplianceItem(models.Model):
    _name = 'seed.compliance.item'
    _description = 'Élément de Vérification de Conformité'
    
    check_id = fields.Many2one('seed.compliance.check', 'Vérification', required=True, ondelete='cascade')
    name = fields.Char('Élément à Vérifier', required=True)
    requirement = fields.Text('Exigence')
    
    status = fields.Selection([
        ('pending', 'En Attente'),
        ('compliant', 'Conforme'),
        ('non_compliant', 'Non Conforme'),
        ('not_applicable', 'Non Applicable'),
    ], string='Statut', default='pending')
    
    comment = fields.Text('Commentaire')
    evidence = fields.Binary('Preuve/Photo')
    evidence_filename = fields.Char('Nom du Fichier')

class SeedCorrectiveAction(models.Model):
    _name = 'seed.corrective.action'
    _description = 'Action Corrective'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char('Action', required=True)
    compliance_check_id = fields.Many2one('seed.compliance.check', 'Vérification de Conformité')
    
    description = fields.Text('Description')
    responsible_id = fields.Many2one('res.users', 'Responsable', required=True)
    due_date = fields.Date('Date d\'Échéance', required=True)
    
    priority = fields.Selection([
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé'),
        ('urgent', 'Urgent'),
    ], string='Priorité', default='medium')
    
    status = fields.Selection([
        ('open', 'Ouverte'),
        ('in_progress', 'En Cours'),
        ('completed', 'Terminée'),
        ('verified', 'Vérifiée'),
        ('closed', 'Fermée'),
    ], string='Statut', default='open', tracking=True)
    
    completion_date = fields.Date('Date de Réalisation')
    verification_date = fields.Date('Date de Vérification')
    verification_notes = fields.Text('Notes de Vérification')
    
    def action_start(self):
        """Démarre l'action corrective"""
        self.write({'status': 'in_progress'})
    
    def action_complete(self):
        """Marque l'action comme terminée"""
        self.write({
            'status': 'completed',
            'completion_date': fields.Date.today()
        })
    
    def action_verify(self):
        """Vérifie l'efficacité de l'action"""
        self.write({
            'status': 'verified',
            'verification_date': fields.Date.today()
        })
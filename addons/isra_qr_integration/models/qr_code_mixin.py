# models/qr_code_mixin.py
from odoo import models, fields, api
import qrcode
import base64
import json
from io import BytesIO
import logging

_logger = logging.getLogger(__name__)

class QRCodeMixin(models.AbstractModel):
    """
    Mixin pour ajouter facilement des fonctionnalités QR Code à n'importe quel modèle
    
    Usage:
    class MonModele(models.Model):
        _name = 'mon.modele'
        _inherit = ['isra.qr.mixin']
        
        def _get_qr_data(self):
            return {'id': self.id, 'name': self.name}
    """
    _name = 'isra.qr.mixin'
    _description = 'Mixin QR Code pour ISRA'
    
    # Champs QR Code
    qr_code_data = fields.Text(
        string='Données QR Code',
        help='Données JSON encodées dans le QR code'
    )
    
    qr_code_image = fields.Binary(
        string='Image QR Code',
        attachment=True,
        help='Image du QR code générée automatiquement'
    )
    
    qr_code_filename = fields.Char(
        string='Nom fichier QR',
        compute='_compute_qr_filename',
        help='Nom du fichier pour téléchargement'
    )
    
    def _compute_qr_filename(self):
        """Génère un nom de fichier pour le QR code"""
        for record in self:
            if hasattr(record, 'name') and record.name:
                filename = f"QR_{record.name.replace('/', '_')}.png"
            else:
                filename = f"QR_{record._name}_{record.id}.png"
            record.qr_code_filename = filename
    
    def _get_qr_data(self):
        """
        Méthode à surcharger dans les modèles héritiers
        Doit retourner un dictionnaire avec les données à encoder
        """
        return {
            'model': self._name,
            'id': self.id,
            'timestamp': fields.Datetime.now().isoformat()
        }
    
    def _get_qr_config(self):
        """
        Configuration du QR code
        Peut être surchargée pour personnaliser l'apparence
        """
        return {
            'version': 1,
            'error_correction': qrcode.constants.ERROR_CORRECT_M,
            'box_size': 10,
            'border': 4,
            'fill_color': "black",
            'back_color': "white"
        }
    
    def generate_qr_code(self):
        """Génère le QR code pour cet enregistrement"""
        for record in self:
            try:
                # Obtenir les données à encoder
                qr_data = record._get_qr_data()
                
                if not qr_data:
                    _logger.warning(f"Aucune donnée QR pour {record._name} ID {record.id}")
                    continue
                
                # Encoder en JSON
                json_data = json.dumps(qr_data, ensure_ascii=False, separators=(',', ':'))
                record.qr_code_data = json_data
                
                # Générer l'image QR
                config = record._get_qr_config()
                qr = qrcode.QRCode(
                    version=config['version'],
                    error_correction=config['error_correction'],
                    box_size=config['box_size'],
                    border=config['border'],
                )
                qr.add_data(json_data)
                qr.make(fit=True)
                
                # Créer l'image
                img = qr.make_image(
                    fill_color=config['fill_color'],
                    back_color=config['back_color']
                )
                
                # Convertir en base64
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                record.qr_code_image = base64.b64encode(buffer.getvalue())
                
                _logger.info(f"QR code généré pour {record._name} ID {record.id}")
                
            except Exception as e:
                _logger.error(f"Erreur génération QR pour {record._name} ID {record.id}: {e}")
                record.qr_code_data = False
                record.qr_code_image = False
    
    def action_generate_qr_code(self):
        """Action pour régénérer le QR code manuellement"""
        self.generate_qr_code()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'QR Code Généré',
                'message': f'Le QR code a été généré avec succès pour {len(self)} enregistrement(s)',
                'type': 'success',
            }
        }
    
    def action_download_qr_code(self):
        """Action pour télécharger le QR code"""
        self.ensure_one()
        if not self.qr_code_image:
            self.generate_qr_code()
        
        if self.qr_code_image:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content?model={self._name}&id={self.id}&field=qr_code_image&filename={self.qr_code_filename}&download=true',
                'target': 'self',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Erreur',
                    'message': 'Impossible de générer le QR code',
                    'type': 'danger',
                }
            }
    
    def action_print_qr_label(self):
        """Action pour imprimer l'étiquette QR"""
        if not self.qr_code_image:
            self.generate_qr_code()
        
        # Retourner l'action du rapport (à définir dans le module principal)
        return {
            'type': 'ir.actions.report',
            'report_name': 'isra_qr_integration.qr_label_report',
            'report_type': 'qweb-pdf',
            'data': {'ids': self.ids},
            'context': self.env.context,
        }
    
    @api.model
    def create(self, vals):
        """Génère automatiquement le QR code à la création"""
        record = super().create(vals)
        record.generate_qr_code()
        return record
    
    def write(self, vals):
        """Régénère le QR code si les données importantes changent"""
        result = super().write(vals)
        
        # Obtenir les champs qui déclenchent une régénération
        trigger_fields = self._get_qr_trigger_fields()
        
        if any(field in vals for field in trigger_fields):
            self.generate_qr_code()
        
        return result
    
    def _get_qr_trigger_fields(self):
        """
        Champs qui déclenchent une régénération du QR code
        À surcharger dans les modèles héritiers
        """
        return ['name']  # Par défaut, régénérer si le nom change


class QRVerificationLog(models.Model):
    """Journal des vérifications de QR codes"""
    _name = 'isra.qr.verification.log'
    _description = 'Journal des Vérifications QR'
    _order = 'verification_date desc'
    
    verification_date = fields.Datetime(
        string='Date de Vérification',
        default=fields.Datetime.now,
        required=True
    )
    
    qr_data = fields.Text(
        string='Données QR Scannées',
        required=True
    )
    
    result = fields.Selection([
        ('success', 'Succès'),
        ('not_found', 'Non Trouvé'),
        ('invalid', 'Invalide'),
        ('error', 'Erreur')
    ], string='Résultat', required=True)
    
    model_name = fields.Char(string='Modèle')
    record_id = fields.Integer(string='ID Enregistrement')
    
    user_id = fields.Many2one(
        'res.users',
        string='Utilisateur',
        default=lambda self: self.env.user
    )
    
    ip_address = fields.Char(string='Adresse IP')
    user_agent = fields.Text(string='User Agent')
    
    error_message = fields.Text(string='Message d\'Erreur')
    
    def name_get(self):
        result = []
        for record in self:
            name = f"Vérification {record.verification_date.strftime('%d/%m/%Y %H:%M')} - {record.result}"
            result.append((record.id, name))
        return result
# controllers/qr_verification.py
from odoo import http
from odoo.http import request
import json

class QRVerificationController(http.Controller):
    
    @http.route('/isra/verify/<string:lot_id>', type='http', auth='public', website=True)
    def verify_lot_public(self, lot_id, **kwargs):
        """Page publique de vérification d'un lot via QR code"""
        
        lot = request.env['isra.seed.lot'].sudo().search([
            ('name', '=', lot_id),
            ('is_active', '=', True)
        ], limit=1)
        
        if not lot:
            return request.render('isra_qr_integration.lot_not_found', {
                'lot_id': lot_id
            })
        
        # Données à afficher publiquement (sans infos sensibles)
        lot_data = {
            'name': lot.name,
            'variety_name': lot.variety_id.name,
            'variety_code': lot.variety_id.code,
            'level': lot.level,
            'production_date': lot.production_date,
            'status': lot.status,
            'multiplier_name': lot.multiplier_id.name if lot.multiplier_id else '',
            'latest_quality_result': lot.latest_quality_control_id.result if lot.latest_quality_control_id else None,
            'qr_code_image': lot.qr_code_image
        }
        
        return request.render('isra_qr_integration.lot_verification', {
            'lot': lot_data
        })
    
    @http.route('/isra/api/verify', type='json', auth='user', methods=['POST'])
    def verify_lot_api(self, qr_data):
        """API pour vérification depuis l'app mobile"""
        
        try:
            # Décoder les données QR
            if isinstance(qr_data, str):
                qr_info = json.loads(qr_data)
            else:
                qr_info = qr_data
            
            lot_id = qr_info.get('lot_id')
            if not lot_id:
                return {'error': 'ID de lot manquant dans le QR code'}
            
            # Rechercher le lot
            lot = request.env['isra.seed.lot'].search([
                ('name', '=', lot_id),
                ('is_active', '=', True)
            ], limit=1)
            
            if not lot:
                return {'error': f'Lot {lot_id} non trouvé'}
            
            # Vérifier l'authenticité
            authentic = self._verify_qr_authenticity(lot, qr_info)
            
            return {
                'success': True,
                'authentic': authentic,
                'lot': {
                    'name': lot.name,
                    'variety': lot.variety_id.name,
                    'level': lot.level,
                    'status': lot.status,
                    'production_date': lot.production_date.strftime('%d/%m/%Y'),
                    'multiplier': lot.multiplier_id.name if lot.multiplier_id else None,
                    'quality_status': lot.latest_quality_control_id.result if lot.latest_quality_control_id else None,
                    'days_to_expiry': lot.days_to_expiry,
                    'is_expired': lot.is_expired
                }
            }
            
        except Exception as e:
            return {'error': f'Erreur de vérification: {str(e)}'}
    
    def _verify_qr_authenticity(self, lot, qr_info):
        """Vérifier l'authenticité du QR code"""
        
        # Vérifications de base
        checks = [
            qr_info.get('variety_name') == lot.variety_id.name,
            qr_info.get('level') == lot.level,
            qr_info.get('production_date') == str(lot.production_date),
        ]
        
        return all(checks)
    
    @http.route('/isra/scanner', type='http', auth='user', website=True)
    def qr_scanner_page(self):
        """Page du scanner QR pour les utilisateurs connectés"""
        return request.render('isra_qr_integration.qr_scanner_page')
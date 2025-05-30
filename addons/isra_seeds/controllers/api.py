# isra_seeds/controllers/api.py
# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class SeedLotAPI(http.Controller):
    
    @http.route('/api/seed-lots', type='http', auth='user', methods=['GET'], csrf=False)
    def get_seed_lots(self, **kwargs):
        """API pour récupérer les lots de semences"""
        try:
            # Paramètres de pagination et filtres
            page = int(kwargs.get('page', 1))
            page_size = int(kwargs.get('pageSize', 10))
            search = kwargs.get('search', '')
            level = kwargs.get('level', '')
            status = kwargs.get('status', '')
            variety_id = kwargs.get('varietyId', '')
            multiplier_id = kwargs.get('multiplierId', '')
            sort_by = kwargs.get('sortBy', 'production_date')
            sort_order = kwargs.get('sortOrder', 'desc')
            
            # Construction du domaine de recherche
            domain = [('active', '=', True)]
            
            if search:
                domain.extend([
                    '|', '|', '|',
                    ('name', 'ilike', search),
                    ('variety_id.name', 'ilike', search),
                    ('multiplier_id.name', 'ilike', search),
                    ('notes', 'ilike', search)
                ])
            
            if level:
                domain.append(('level', '=', level))
            
            if status:
                domain.append(('status', '=', status))
            
            if variety_id:
                domain.append(('variety_id', '=', int(variety_id)))
            
            if multiplier_id:
                domain.append(('multiplier_id', '=', int(multiplier_id)))
            
            # Récupération des lots
            SeedLot = request.env['seed.lot']
            
            # Total pour pagination
            total = SeedLot.search_count(domain)
            
            # Lots avec pagination
            offset = (page - 1) * page_size
            lots = SeedLot.search(
                domain,
                limit=page_size,
                offset=offset,
                order=f'{sort_by} {sort_order}'
            )
            
            # Formatage des données
            data = []
            for lot in lots:
                # Dernière qualité control
                last_quality = None
                if lot.quality_control_ids:
                    qc = lot.quality_control_ids.sorted('control_date', reverse=True)[0]
                    last_quality = {
                        'id': qc.id,
                        'result': qc.result,
                        'germination_rate': qc.germination_rate,
                        'variety_purity': qc.variety_purity,
                        'control_date': qc.control_date.isoformat() if qc.control_date else None
                    }
                
                lot_data = {
                    'id': lot.id,
                    'name': lot.name,
                    'variety': {
                        'id': lot.variety_id.id,
                        'name': lot.variety_id.name,
                        'code': lot.variety_id.code,
                        'crop_type': lot.variety_id.crop_type
                    } if lot.variety_id else None,
                    'level': lot.level,
                    'quantity': lot.quantity,
                    'production_date': lot.production_date.isoformat() if lot.production_date else None,
                    'expiry_date': lot.expiry_date.isoformat() if lot.expiry_date else None,
                    'status': lot.status,
                    'multiplier': {
                        'id': lot.multiplier_id.id,
                        'name': lot.multiplier_id.name,
                    } if lot.multiplier_id else None,
                    'parcel': {
                        'id': lot.parcel_id.id,
                        'name': lot.parcel_id.name,
                    } if lot.parcel_id else None,
                    'parent_lot_id': lot.parent_lot_id.name if lot.parent_lot_id else None,
                    'child_lot_count': lot.child_lot_count,
                    'quality_control_count': lot.quality_control_count,
                    'last_quality_result': lot.last_quality_result,
                    'is_expired': lot.is_expired,
                    'qr_code': lot.qr_code,
                    'notes': lot.notes,
                    'last_quality_control': last_quality
                }
                data.append(lot_data)
            
            # Métadonnées de pagination
            total_pages = (total + page_size - 1) // page_size
            
            response = {
                'success': True,
                'data': data,
                'meta': {
                    'page': page,
                    'pageSize': page_size,
                    'totalCount': total,
                    'totalPages': total_pages
                }
            }
            
            return request.make_response(
                json.dumps(response),
                headers={'Content-Type': 'application/json'}
            )
            
        except Exception as e:
            _logger.error(f"Erreur API get_seed_lots: {str(e)}")
            return request.make_response(
                json.dumps({
                    'success': False,
                    'message': 'Erreur lors de la récupération des lots',
                    'error': str(e)
                }),
                status=500,
                headers={'Content-Type': 'application/json'}
            )
    
    @http.route('/api/seed-lots/<int:lot_id>', type='http', auth='user', methods=['GET'], csrf=False)
    def get_seed_lot_by_id(self, lot_id, **kwargs):
        """API pour récupérer un lot spécifique"""
        try:
            lot = request.env['seed.lot'].browse(lot_id)
            
            if not lot.exists():
                return request.make_response(
                    json.dumps({
                        'success': False,
                        'message': 'Lot non trouvé'
                    }),
                    status=404,
                    headers={'Content-Type': 'application/json'}
                )
            
            # Contrôles qualité
            quality_controls = []
            for qc in lot.quality_control_ids.sorted('control_date', reverse=True):
                quality_controls.append({
                    'id': qc.id,
                    'control_date': qc.control_date.isoformat() if qc.control_date else None,
                    'germination_rate': qc.germination_rate,
                    'variety_purity': qc.variety_purity,
                    'moisture_content': qc.moisture_content,
                    'seed_health': qc.seed_health,
                    'result': qc.result,
                    'observations': qc.observations,
                    'inspector': {
                        'id': qc.inspector_id.id,
                        'name': qc.inspector_id.name
                    } if qc.inspector_id else None
                })
            
            # Productions
            productions = []
            for prod in lot.production_ids.sorted('start_date', reverse=True):
                productions.append({
                    'id': prod.id,
                    'name': prod.name,
                    'start_date': prod.start_date.isoformat() if prod.start_date else None,
                    'end_date': prod.end_date.isoformat() if prod.end_date else None,
                    'status': prod.status,
                    'planned_quantity': prod.planned_quantity,
                    'actual_yield': prod.actual_yield,
                    'multiplier': {
                        'id': prod.multiplier_id.id,
                        'name': prod.multiplier_id.name
                    } if prod.multiplier_id else None
                })
            
            # Généalogie
            genealogy = {
                'parent': None,
                'children': []
            }
            
            if lot.parent_lot_id:
                genealogy['parent'] = {
                    'id': lot.parent_lot_id.id,
                    'name': lot.parent_lot_id.name,
                    'level': lot.parent_lot_id.level,
                    'variety': lot.parent_lot_id.variety_id.name
                }
            
            for child in lot.child_lot_ids:
                genealogy['children'].append({
                    'id': child.id,
                    'name': child.name,
                    'level': child.level,
                    'quantity': child.quantity,
                    'status': child.status
                })
            
            lot_data = {
                'id': lot.id,
                'name': lot.name,
                'display_name': lot.display_name,
                'variety': {
                    'id': lot.variety_id.id,
                    'name': lot.variety_id.name,
                    'code': lot.variety_id.code,
                    'crop_type': lot.variety_id.crop_type,
                    'description': lot.variety_id.description
                } if lot.variety_id else None,
                'level': lot.level,
                'quantity': lot.quantity,
                'production_date': lot.production_date.isoformat() if lot.production_date else None,
                'expiry_date': lot.expiry_date.isoformat() if lot.expiry_date else None,
                'status': lot.status,
                'batch_number': lot.batch_number,
                'multiplier': {
                    'id': lot.multiplier_id.id,
                    'name': lot.multiplier_id.name,
                    'phone': lot.multiplier_id.phone,
                    'email': lot.multiplier_id.email
                } if lot.multiplier_id else None,
                'parcel': {
                    'id': lot.parcel_id.id,
                    'name': lot.parcel_id.name,
                    'area': lot.parcel_id.area,
                    'soil_type': lot.parcel_id.soil_type
                } if lot.parcel_id else None,
                'qr_code': lot.qr_code,
                'notes': lot.notes,
                'is_expired': lot.is_expired,
                'quality_controls': quality_controls,
                'productions': productions,
                'genealogy': genealogy
            }
            
            return request.make_response(
                json.dumps({
                    'success': True,
                    'data': lot_data
                }),
                headers={'Content-Type': 'application/json'}
            )
            
        except Exception as e:
            _logger.error(f"Erreur API get_seed_lot_by_id: {str(e)}")
            return request.make_response(
                json.dumps({
                    'success': False,
                    'message': 'Erreur lors de la récupération du lot',
                    'error': str(e)
                }),
                status=500,
                headers={'Content-Type': 'application/json'}
            )
    
    @http.route('/api/seed-lots', type='json', auth='user', methods=['POST'], csrf=False)
    def create_seed_lot(self, **kwargs):
        """API pour créer un nouveau lot"""
        try:
            data = request.jsonrequest
            
            # Validation des données requises
            required_fields = ['variety_id', 'level', 'quantity', 'production_date']
            for field in required_fields:
                if field not in data:
                    return {
                        'success': False,
                        'message': f'Champ requis manquant: {field}'
                    }
            
            # Création du lot
            lot_vals = {
                'variety_id': data['variety_id'],
                'level': data['level'],
                'quantity': data['quantity'],
                'production_date': data['production_date'],
                'multiplier_id': data.get('multiplier_id'),
                'parcel_id': data.get('parcel_id'),
                'parent_lot_id': data.get('parent_lot_id'),
                'batch_number': data.get('batch_number'),
                'notes': data.get('notes')
            }
            
            lot = request.env['seed.lot'].create(lot_vals)
            
            return {
                'success': True,
                'message': 'Lot créé avec succès',
                'data': {
                    'id': lot.id,
                    'name': lot.name,
                    'qr_code': lot.qr_code
                }
            }
            
        except Exception as e:
            _logger.error(f"Erreur API create_seed_lot: {str(e)}")
            return {
                'success': False,
                'message': 'Erreur lors de la création du lot',
                'error': str(e)
            }

class VarietyAPI(http.Controller):
    
    @http.route('/api/varieties', type='http', auth='user', methods=['GET'], csrf=False)
    def get_varieties(self, **kwargs):
        """API pour récupérer les variétés"""
        try:
            search = kwargs.get('search', '')
            crop_type = kwargs.get('crop_type', '')
            
            domain = [('active', '=', True)]
            
            if search:
                domain.extend([
                    '|', '|', '|',
                    ('name', 'ilike', search),
                    ('code', 'ilike', search),
                    ('description', 'ilike', search),
                    ('origin', 'ilike', search)
                ])
            
            if crop_type:
                domain.append(('crop_type', '=', crop_type))
            
            varieties = request.env['seed.variety'].search(domain, order='name asc')
            
            data = []
            for variety in varieties:
                data.append({
                    'id': variety.id,
                    'code': variety.code,
                    'name': variety.name,
                    'crop_type': variety.crop_type,
                    'description': variety.description,
                    'maturity_days': variety.maturity_days,
                    'yield_potential': variety.yield_potential,
                    'resistances': variety.resistances,
                    'origin': variety.origin,
                    'release_year': variety.release_year,
                    'seed_lot_count': variety.seed_lot_count,
                    'total_quantity': variety.total_quantity
                })
            
            return request.make_response(
                json.dumps({
                    'success': True,
                    'data': data
                }),
                headers={'Content-Type': 'application/json'}
            )
            
        except Exception as e:
            _logger.error(f"Erreur API get_varieties: {str(e)}")
            return request.make_response(
                json.dumps({
                    'success': False,
                    'message': 'Erreur lors de la récupération des variétés',
                    'error': str(e)
                }),
                status=500,
                headers={'Content-Type': 'application/json'}
            )

class MultiplierAPI(http.Controller):
    
    @http.route('/api/multipliers', type='http', auth='user', methods=['GET'], csrf=False)
    def get_multipliers(self, **kwargs):
        """API pour récupérer les multiplicateurs"""
        try:
            domain = [('is_multiplier', '=', True), ('active', '=', True)]
            
            search = kwargs.get('search', '')
            if search:
                domain.extend([
                    '|', '|',
                    ('name', 'ilike', search),
                    ('email', 'ilike', search),
                    ('phone', 'ilike', search)
                ])
            
            multipliers = request.env['res.partner'].search(domain, order='name asc')
            
            data = []
            for mult in multipliers:
                data.append({
                    'id': mult.id,
                    'name': mult.name,
                    'email': mult.email,
                    'phone': mult.phone,
                    'street': mult.street,
                    'city': mult.city,
                    'years_experience': mult.years_experience,
                    'certification_level': mult.certification_level,
                    'multiplier_status': mult.multiplier_status,
                    'seed_lot_count': mult.seed_lot_count,
                    'parcel_count': mult.parcel_count,
                    'total_area': mult.total_area
                })
            
            return request.make_response(
                json.dumps({
                    'success': True,
                    'data': data
                }),
                headers={'Content-Type': 'application/json'}
            )
            
        except Exception as e:
            _logger.error(f"Erreur API get_multipliers: {str(e)}")
            return request.make_response(
                json.dumps({
                    'success': False,
                    'message': 'Erreur lors de la récupération des multiplicateurs',
                    'error': str(e)
                }),
                status=500,
                headers={'Content-Type': 'application/json'}
            )

class AuthAPI(http.Controller):
    
    @http.route('/api/auth/me', type='json', auth='user', methods=['POST'], csrf=False)
    def get_current_user(self):
        """API pour récupérer l'utilisateur connecté"""
        try:
            user = request.env.user
            
            return {
                'success': True,
                'data': {
                    'id': user.id,
                    'name': user.name,
                    'email': user.login,
                    'role': user.groups_id.mapped('name'),
                    'avatar': None,  # À implémenter si nécessaire
                    'company': user.company_id.name if user.company_id else None
                }
            }
            
        except Exception as e:
            _logger.error(f"Erreur API get_current_user: {str(e)}")
            return {
                'success': False,
                'message': 'Erreur lors de la récupération de l\'utilisateur',
                'error': str(e)
            }

class QualityControlAPI(http.Controller):
    
    @http.route('/api/quality-controls', type='json', auth='user', methods=['POST'], csrf=False)
    def create_quality_control(self):
        """API pour créer un contrôle qualité"""
        try:
            data = request.jsonrequest
            
            # Validation
            required_fields = ['lot_id', 'control_date', 'germination_rate', 'variety_purity']
            for field in required_fields:
                if field not in data:
                    return {
                        'success': False,
                        'message': f'Champ requis manquant: {field}'
                    }
            
            # Vérifier que le lot existe
            lot = request.env['seed.lot'].browse(int(data['lot_id']))
            if not lot.exists():
                return {
                    'success': False,
                    'message': 'Lot de semences non trouvé'
                }
            
            # Création du contrôle qualité
            qc_vals = {
                'seed_lot_id': int(data['lot_id']),
                'control_date': data['control_date'],
                'germination_rate': data['germination_rate'],
                'variety_purity': data['variety_purity'],
                'moisture_content': data.get('moisture_content'),
                'seed_health': data.get('seed_health'),
                'observations': data.get('observations'),
                'test_method': data.get('test_method', 'ista'),
                'laboratory': data.get('laboratory'),
                'inspector_id': request.env.user.id
            }
            
            qc = request.env['seed.quality.control'].create(qc_vals)
            
            return {
                'success': True,
                'message': 'Contrôle qualité créé avec succès',
                'data': {
                    'id': qc.id,
                    'name': qc.name,
                    'result': qc.result
                }
            }
            
        except Exception as e:
            _logger.error(f"Erreur API create_quality_control: {str(e)}")
            return {
                'success': False,
                'message': 'Erreur lors de la création du contrôle qualité',
                'error': str(e)
            }

class StatisticsAPI(http.Controller):
    
    @http.route('/api/statistics/dashboard', type='http', auth='user', methods=['GET'], csrf=False)
    def get_dashboard_stats(self, **kwargs):
        """API pour les statistiques du tableau de bord"""
        try:
            # Statistiques générales
            seed_lots_count = request.env['seed.lot'].search_count([('active', '=', True)])
            varieties_count = request.env['seed.variety'].search_count([('active', '=', True)])
            multipliers_count = request.env['res.partner'].search_count([
                ('is_multiplier', '=', True), 
                ('active', '=', True)
            ])
            quality_controls_count = request.env['seed.quality.control'].search_count([])
            
            # Statistiques par niveau
            levels_stats = {}
            for level in ['GO', 'G1', 'G2', 'G3', 'G4', 'R1', 'R2']:
                count = request.env['seed.lot'].search_count([
                    ('level', '=', level),
                    ('active', '=', True)
                ])
                total_quantity = sum(request.env['seed.lot'].search([
                    ('level', '=', level),
                    ('active', '=', True)
                ]).mapped('quantity'))
                
                levels_stats[level] = {
                    'count': count,
                    'total_quantity': total_quantity
                }
            
            # Contrôles qualité récents
            recent_qc = request.env['seed.quality.control'].search([
                ('control_date', '>=', fields.Date.today() - relativedelta(days=30))
            ])
            
            passed_qc = recent_qc.filtered(lambda x: x.result == 'pass')
            quality_pass_rate = (len(passed_qc) / len(recent_qc) * 100) if recent_qc else 0
            
            # Lots expirant bientôt
            expiring_soon = request.env['seed.lot'].search_count([
                ('expiry_date', '<=', fields.Date.today() + relativedelta(days=30)),
                ('expiry_date', '>=', fields.Date.today()),
                ('active', '=', True)
            ])
            
            data = {
                'overview': {
                    'total_seed_lots': seed_lots_count,
                    'total_varieties': varieties_count,  
                    'total_multipliers': multipliers_count,
                    'total_quality_controls': quality_controls_count,
                    'quality_pass_rate': round(quality_pass_rate, 1),
                    'lots_expiring_soon': expiring_soon
                },
                'levels_distribution': levels_stats,
                'recent_activity': {
                    'new_lots_this_month': request.env['seed.lot'].search_count([
                        ('create_date', '>=', fields.Date.today().replace(day=1)),
                        ('active', '=', True)
                    ]),
                    'quality_controls_this_month': len(recent_qc)
                }
            }
            
            return request.make_response(
                json.dumps({
                    'success': True,
                    'data': data
                }),
                headers={'Content-Type': 'application/json'}
            )
            
        except Exception as e:
            _logger.error(f"Erreur API get_dashboard_stats: {str(e)}")
            return request.make_response(
                json.dumps({
                    'success': False,
                    'message': 'Erreur lors de la récupération des statistiques',
                    'error': str(e)
                }),
                status=500,
                headers={'Content-Type': 'application/json'}
            )
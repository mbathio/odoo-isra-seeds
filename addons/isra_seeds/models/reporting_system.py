# isra_seeds/models/reporting_system.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import json
from datetime import datetime, timedelta
import base64
import io

class SeedReport(models.Model):
    _name = 'seed.report'
    _description = 'Rapport de Traçabilité'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Identification
    name = fields.Char('Référence', required=True, default='New', readonly=True)
    title = fields.Char('Titre du Rapport', required=True)
    
    # Type de rapport
    report_type = fields.Selection([
        ('traceability', 'Traçabilité Complète'),
        ('quality_summary', 'Résumé Qualité'),
        ('production_summary', 'Résumé Production'),
        ('stock_status', 'État des Stocks'),
        ('variety_performance', 'Performance Variétés'),
        ('multiplier_performance', 'Performance Multiplicateurs'),
        ('financial_summary', 'Résumé Financier'),
        ('regulatory_compliance', 'Conformité Réglementaire'),
        ('custom', 'Personnalisé'),
    ], string='Type de Rapport', required=True)
    
    # Période du rapport
    date_from = fields.Date('Date de Début', required=True)
    date_to = fields.Date('Date de Fin', required=True)
    
    # Filtres
    variety_ids = fields.Many2many(
        'seed.variety',
        'seed_report_variety_rel',
        'report_id',
        'variety_id',
        string='Variétés'
    )
    multiplier_ids = fields.Many2many(
        'res.partner',
        'seed_report_multiplier_rel',
        'report_id',
        'multiplier_id',
        string='Multiplicateurs',
        domain=[('is_multiplier', '=', True)]
    )
    level_filter = fields.Selection([
        ('GO', 'GO'),
        ('G1', 'G1'),
        ('G2', 'G2'),
        ('G3', 'G3'),
        ('G4', 'G4'),
        ('R1', 'R1'),
        ('R2', 'R2'),
    ], string='Niveau de Semence')
    
    # Contenu du rapport
    content = fields.Html('Contenu du Rapport')
    data_json = fields.Text('Données JSON')
    
    # Fichiers générés
    pdf_file = fields.Binary('Rapport PDF')
    pdf_filename = fields.Char('Nom du fichier PDF')
    excel_file = fields.Binary('Rapport Excel')
    excel_filename = fields.Char('Nom du fichier Excel')
    
    # Métadonnées
    generated_by = fields.Many2one('res.users', 'Généré par', default=lambda self: self.env.user)
    generation_date = fields.Datetime('Date de Génération', default=fields.Datetime.now)
    auto_generated = fields.Boolean('Généré Automatiquement', default=False)
    
    # Statut
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('generating', 'En Cours de Génération'),
        ('ready', 'Prêt'),
        ('error', 'Erreur'),
    ], string='État', default='draft', tracking=True)
    
    error_message = fields.Text('Message d\'Erreur')
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('seed.report') or 'New'
        return super().create(vals)
    
    def action_generate_report(self):
        """Génère le rapport selon le type sélectionné"""
        self.write({'state': 'generating'})
        
        try:
            if self.report_type == 'traceability':
                self._generate_traceability_report()
            elif self.report_type == 'quality_summary':
                self._generate_quality_summary()
            elif self.report_type == 'production_summary':
                self._generate_production_summary()
            elif self.report_type == 'stock_status':
                self._generate_stock_status()
            elif self.report_type == 'variety_performance':
                self._generate_variety_performance()
            elif self.report_type == 'multiplier_performance':
                self._generate_multiplier_performance()
            elif self.report_type == 'financial_summary':
                self._generate_financial_summary()
            elif self.report_type == 'regulatory_compliance':
                self._generate_regulatory_compliance()
            
            self.write({'state': 'ready'})
            
        except Exception as e:
            self.write({
                'state': 'error',
                'error_message': str(e)
            })
            raise UserError(f"Erreur lors de la génération du rapport: {e}")
    
    def _generate_traceability_report(self):
        """Génère un rapport de traçabilité complète"""
        # Récupérer les lots selon les filtres
        domain = [
            ('production_date', '>=', self.date_from),
            ('production_date', '<=', self.date_to),
            ('active', '=', True)
        ]
        
        if self.variety_ids:
            domain.append(('variety_id', 'in', self.variety_ids.ids))
        if self.multiplier_ids:
            domain.append(('multiplier_id', 'in', self.multiplier_ids.ids))
        if self.level_filter:
            domain.append(('level', '=', self.level_filter))
        
        lots = self.env['seed.lot'].search(domain)
        
        # Construire les données
        data = {
            'lots': [],
            'summary': {
                'total_lots': len(lots),
                'total_quantity': sum(lots.mapped('quantity')),
                'varieties_count': len(lots.mapped('variety_id')),
                'multipliers_count': len(lots.mapped('multiplier_id')),
            }
        }
        
        for lot in lots:
            lot_data = {
                'name': lot.name,
                'variety': lot.variety_id.name,
                'level': lot.level,
                'quantity': lot.quantity,
                'production_date': lot.production_date.isoformat() if lot.production_date else None,
                'multiplier': lot.multiplier_id.name if lot.multiplier_id else None,
                'status': lot.status,
                'genealogy': self._get_full_genealogy(lot),
                'quality_controls': self._get_quality_data(lot),
                'productions': self._get_production_data(lot),
                'stock_movements': self._get_stock_movements(lot)
            }
            data['lots'].append(lot_data)
        
        self.data_json = json.dumps(data, indent=2, default=str)
        self._generate_content_html(data)
    
    def _generate_quality_summary(self):
        """Génère un résumé des contrôles qualité"""
        domain = [
            ('control_date', '>=', self.date_from),
            ('control_date', '<=', self.date_to)
        ]
        
        if self.variety_ids:
            domain.append(('seed_lot_id.variety_id', 'in', self.variety_ids.ids))
        
        controls = self.env['seed.quality.control'].search(domain)
        
        # Calculs statistiques
        total_controls = len(controls)
        passed_controls = len(controls.filtered(lambda c: c.result == 'pass'))
        failed_controls = len(controls.filtered(lambda c: c.result == 'fail'))
        
        avg_germination = sum(controls.mapped('germination_rate')) / total_controls if total_controls else 0
        avg_purity = sum(controls.mapped('variety_purity')) / total_controls if total_controls else 0
        
        # Données par variété
        variety_stats = {}
        for variety in self.variety_ids or controls.mapped('seed_lot_id.variety_id'):
            variety_controls = controls.filtered(lambda c: c.seed_lot_id.variety_id == variety)
            if variety_controls:
                variety_stats[variety.name] = {
                    'total': len(variety_controls),
                    'passed': len(variety_controls.filtered(lambda c: c.result == 'pass')),
                    'avg_germination': sum(variety_controls.mapped('germination_rate')) / len(variety_controls),
                    'avg_purity': sum(variety_controls.mapped('variety_purity')) / len(variety_controls),
                }
        
        data = {
            'summary': {
                'total_controls': total_controls,
                'passed_controls': passed_controls,
                'failed_controls': failed_controls,
                'pass_rate': (passed_controls / total_controls * 100) if total_controls else 0,
                'avg_germination': avg_germination,
                'avg_purity': avg_purity,
            },
            'variety_stats': variety_stats,
            'controls': [self._format_control_data(c) for c in controls]
        }
        
        self.data_json = json.dumps(data, indent=2, default=str)
        self._generate_content_html(data)
    
    def _generate_production_summary(self):
        """Génère un résumé des productions"""
        domain = [
            ('start_date', '>=', self.date_from),
            ('start_date', '<=', self.date_to)
        ]
        
        if self.multiplier_ids:
            domain.append(('multiplier_id', 'in', self.multiplier_ids.ids))
        
        productions = self.env['seed.production'].search(domain)
        
        # Calculs
        total_productions = len(productions)
        completed_productions = len(productions.filtered(lambda p: p.status == 'completed'))
        total_planned = sum(productions.mapped('planned_quantity'))
        total_actual = sum(productions.mapped('actual_yield'))
        
        # Données par multiplicateur
        multiplier_stats = {}
        for multiplier in self.multiplier_ids or productions.mapped('multiplier_id'):
            mult_productions = productions.filtered(lambda p: p.multiplier_id == multiplier)
            if mult_productions:
                multiplier_stats[multiplier.name] = {
                    'total_productions': len(mult_productions),
                    'completed': len(mult_productions.filtered(lambda p: p.status == 'completed')),
                    'total_yield': sum(mult_productions.mapped('actual_yield')),
                    'avg_yield_per_ha': sum(mult_productions.mapped('yield_per_hectare')) / len(mult_productions) if mult_productions else 0,
                }
        
        data = {
            'summary': {
                'total_productions': total_productions,
                'completed_productions': completed_productions,
                'completion_rate': (completed_productions / total_productions * 100) if total_productions else 0,
                'total_planned': total_planned,
                'total_actual': total_actual,
                'efficiency_rate': (total_actual / total_planned * 100) if total_planned else 0,
            },
            'multiplier_stats': multiplier_stats,
            'productions': [self._format_production_data(p) for p in productions]
        }
        
        self.data_json = json.dumps(data, indent=2, default=str)
        self._generate_content_html(data)
    
    def _generate_stock_status(self):
        """Génère un rapport d'état des stocks"""
        domain = [('active', '=', True)]
        
        if self.variety_ids:
            domain.append(('variety_id', 'in', self.variety_ids.ids))
        if self.level_filter:
            domain.append(('level', '=', self.level_filter))
        
        lots = self.env['seed.lot'].search(domain)
        
        # Calculs par variété et niveau
        stock_by_variety = {}
        stock_by_level = {}
        
        for lot in lots:
            # Par variété
            variety_name = lot.variety_id.name
            if variety_name not in stock_by_variety:
                stock_by_variety[variety_name] = {
                    'total_quantity': 0,
                    'available_quantity': 0,
                    'lots_count': 0,
                    'certified_lots': 0
                }
            
            stock_by_variety[variety_name]['total_quantity'] += lot.quantity
            stock_by_variety[variety_name]['available_quantity'] += lot.quantity_available
            stock_by_variety[variety_name]['lots_count'] += 1
            if lot.status == 'certified':
                stock_by_variety[variety_name]['certified_lots'] += 1
            
            # Par niveau
            level = lot.level
            if level not in stock_by_level:
                stock_by_level[level] = {
                    'total_quantity': 0,
                    'available_quantity': 0,
                    'lots_count': 0
                }
            
            stock_by_level[level]['total_quantity'] += lot.quantity
            stock_by_level[level]['available_quantity'] += lot.quantity_available
            stock_by_level[level]['lots_count'] += 1
        
        # Alertes de stock
        low_stock_lots = lots.filtered(lambda l: l.quantity_available < 100)
        expiring_lots = lots.filtered(lambda l: l.expiry_date and 
                                     (l.expiry_date - fields.Date.today()).days <= 30)
        
        data = {
            'summary': {
                'total_lots': len(lots),
                'total_stock': sum(lots.mapped('quantity')),
                'available_stock': sum(lots.mapped('quantity_available')),
                'varieties_count': len(stock_by_variety),
                'low_stock_alerts': len(low_stock_lots),
                'expiring_soon': len(expiring_lots),
            },
            'stock_by_variety': stock_by_variety,
            'stock_by_level': stock_by_level,
            'alerts': {
                'low_stock': [{'name': l.name, 'quantity': l.quantity_available} for l in low_stock_lots],
                'expiring': [{'name': l.name, 'expiry_date': l.expiry_date.isoformat()} for l in expiring_lots],
            }
        }
        
        self.data_json = json.dumps(data, indent=2, default=str)
        self._generate_content_html(data)
    
    def _get_full_genealogy(self, lot):
        """Récupère la généalogie complète d'un lot"""
        genealogy = {
            'ancestors': [],
            'descendants': []
        }
        
        # Ancêtres
        current = lot
        while current.parent_lot_id:
            parent_data = {
                'name': current.parent_lot_id.name,
                'level': current.parent_lot_id.level,
                'variety': current.parent_lot_id.variety_id.name,
                'production_date': current.parent_lot_id.production_date.isoformat() if current.parent_lot_id.production_date else None
            }
            genealogy['ancestors'].append(parent_data)
            current = current.parent_lot_id
        
        # Descendants
        def get_children_recursive(parent_lot):
            children = []
            for child in parent_lot.child_lot_ids:
                child_data = {
                    'name': child.name,
                    'level': child.level,
                    'quantity': child.quantity,
                    'status': child.status,
                    'children': get_children_recursive(child)
                }
                children.append(child_data)
            return children
        
        genealogy['descendants'] = get_children_recursive(lot)
        return genealogy
    
    def _get_quality_data(self, lot):
        """Récupère les données de contrôle qualité d'un lot"""
        controls = lot.quality_control_ids.sorted('control_date', reverse=True)
        return [{
            'name': c.name,
            'control_date': c.control_date.isoformat() if c.control_date else None,
            'germination_rate': c.germination_rate,
            'variety_purity': c.variety_purity,
            'result': c.result,
            'inspector': c.inspector_id.name if c.inspector_id else None
        } for c in controls]
    
    def _get_production_data(self, lot):
        """Récupère les données de production d'un lot"""
        productions = lot.production_ids.sorted('start_date', reverse=True)
        return [{
            'name': p.name,
            'start_date': p.start_date.isoformat() if p.start_date else None,
            'end_date': p.end_date.isoformat() if p.end_date else None,
            'status': p.status,
            'actual_yield': p.actual_yield,
            'multiplier': p.multiplier_id.name if p.multiplier_id else None
        } for p in productions]
    
    def _get_stock_movements(self, lot):
        """Récupère les mouvements de stock d'un lot"""
        movements = lot.stock_move_ids.sorted('date', reverse=True)
        return [{
            'name': m.name,
            'date': m.date.isoformat() if m.date else None,
            'move_type': m.move_type,
            'quantity': m.quantity,
            'state': m.state
        } for m in movements]
    
    def _format_control_data(self, control):
        """Formate les données d'un contrôle qualité"""
        return {
            'name': control.name,
            'lot_name': control.seed_lot_id.name,
            'variety': control.seed_lot_id.variety_id.name,
            'control_date': control.control_date.isoformat() if control.control_date else None,
            'germination_rate': control.germination_rate,
            'variety_purity': control.variety_purity,
            'result': control.result,
            'inspector': control.inspector_id.name if control.inspector_id else None
        }
    
    def _format_production_data(self, production):
        """Formate les données d'une production"""
        return {
            'name': production.name,
            'lot_name': production.seed_lot_id.name,
            'multiplier': production.multiplier_id.name if production.multiplier_id else None,
            'start_date': production.start_date.isoformat() if production.start_date else None,
            'end_date': production.end_date.isoformat() if production.end_date else None,
            'status': production.status,
            'planned_quantity': production.planned_quantity,
            'actual_yield': production.actual_yield,
            'yield_per_hectare': production.yield_per_hectare
        }
    
    def _generate_content_html(self, data):
        """Génère le contenu HTML du rapport"""
        if self.report_type == 'traceability':
            self.content = self._render_traceability_html(data)
        elif self.report_type == 'quality_summary':
            self.content = self._render_quality_html(data)
        elif self.report_type == 'production_summary':
            self.content = self._render_production_html(data)
        elif self.report_type == 'stock_status':
            self.content = self._render_stock_html(data)
    
    def _render_traceability_html(self, data):
        """Rend le HTML pour le rapport de traçabilité"""
        html = f"""
        <div class="seed-report">
            <h1>Rapport de Traçabilité</h1>
            <div class="report-period">
                Période: {self.date_from} - {self.date_to}
            </div>
            
            <div class="summary">
                <h2>Résumé</h2>
                <ul>
                    <li>Total lots: {data['summary']['total_lots']}</li>
                    <li>Quantité totale: {data['summary']['total_quantity']} kg</li>
                    <li>Variétés: {data['summary']['varieties_count']}</li>
                    <li>Multiplicateurs: {data['summary']['multipliers_count']}</li>
                </ul>
            </div>
            
            <div class="lots-detail">
                <h2>Détail des Lots</h2>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Lot</th>
                            <th>Variété</th>
                            <th>Niveau</th>
                            <th>Quantité</th>
                            <th>Statut</th>
                            <th>Multiplicateur</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for lot in data['lots']:
            html += f"""
                        <tr>
                            <td>{lot['name']}</td>
                            <td>{lot['variety']}</td>
                            <td>{lot['level']}</td>
                            <td>{lot['quantity']} kg</td>
                            <td>{lot['status']}</td>
                            <td>{lot['multiplier'] or '-'}</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
            </div>
        </div>
        """
        
        return html
    
    def _render_quality_html(self, data):
        """Rend le HTML pour le rapport qualité"""
        html = f"""
        <div class="seed-report">
            <h1>Résumé des Contrôles Qualité</h1>
            <div class="report-period">
                Période: {self.date_from} - {self.date_to}
            </div>
            
            <div class="summary">
                <h2>Statistiques Générales</h2>
                <ul>
                    <li>Total contrôles: {data['summary']['total_controls']}</li>
                    <li>Contrôles réussis: {data['summary']['passed_controls']}</li>
                    <li>Taux de réussite: {data['summary']['pass_rate']:.1f}%</li>
                    <li>Germination moyenne: {data['summary']['avg_germination']:.1f}%</li>
                    <li>Pureté moyenne: {data['summary']['avg_purity']:.1f}%</li>
                </ul>
            </div>
            
            <div class="variety-stats">
                <h2>Statistiques par Variété</h2>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Variété</th>
                            <th>Total</th>
                            <th>Réussis</th>
                            <th>Taux</th>
                            <th>Germination Moy.</th>
                            <th>Pureté Moy.</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for variety, stats in data['variety_stats'].items():
            success_rate = (stats['passed'] / stats['total'] * 100) if stats['total'] else 0
            html += f"""
                        <tr>
                            <td>{variety}</td>
                            <td>{stats['total']}</td>
                            <td>{stats['passed']}</td>
                            <td>{success_rate:.1f}%</td>
                            <td>{stats['avg_germination']:.1f}%</td>
                            <td>{stats['avg_purity']:.1f}%</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
            </div>
        </div>
        """
        
        return html
    
    def _render_production_html(self, data):
        """Rend le HTML pour le rapport de production"""
        # Implémentation similaire pour les autres types de rapports
        return f"<h1>Résumé des Productions</h1><p>Données: {len(data.get('productions', []))} productions</p>"
    
    def _render_stock_html(self, data):
        """Rend le HTML pour le rapport de stock"""
        # Implémentation similaire pour les autres types de rapports
        return f"<h1>État des Stocks</h1><p>Total: {data['summary']['total_stock']} kg</p>"

class SeedKPI(models.Model):
    _name = 'seed.kpi'
    _description = 'Indicateurs de Performance'
    
    name = fields.Char('Nom', required=True)
    kpi_type = fields.Selection([
        ('quality_rate', 'Taux de Qualité'),
        ('production_efficiency', 'Efficacité Production'),
        ('stock_turnover', 'Rotation Stock'),
        ('multiplier_performance', 'Performance Multiplicateur'),
        ('variety_yield', 'Rendement Variété'),
        ('financial_performance', 'Performance Financière'),
    ], string='Type d\'Indicateur', required=True)
    
    value = fields.Float('Valeur')
    target_value = fields.Float('Valeur Cible')
    unit = fields.Char('Unité')
    
    period_start = fields.Date('Début Période')
    period_end = fields.Date('Fin Période')
    
    # Relations
    variety_id = fields.Many2one('seed.variety', 'Variété')
    multiplier_id = fields.Many2one('res.partner', 'Multiplicateur')
    
    # Calculs automatiques
    performance_rate = fields.Float(
        'Taux de Performance (%)',
        compute='_compute_performance_rate'
    )
    
    @api.depends('value', 'target_value')
    def _compute_performance_rate(self):
        for record in self:
            if record.target_value:
                record.performance_rate = (record.value / record.target_value) * 100
            else:
                record.performance_rate = 0
    
    @api.model
    def compute_quality_trends(self, variety_id, period='month'):
        """Calcule les tendances qualité par variété"""
        if period == 'month':
            start_date = fields.Date.today().replace(day=1)
        elif period == 'quarter':
            start_date = fields.Date.today() - timedelta(days=90)
        else:
            start_date = fields.Date.today() - timedelta(days=365)
        
        controls = self.env['seed.quality.control'].search([
            ('seed_lot_id.variety_id', '=', variety_id),
            ('control_date', '>=', start_date),
            ('status', '=', 'completed')
        ])
        
        if not controls:
            return {
                'avg_germination': 0,
                'pass_rate': 0,
                'trend': 'stable',
                'total_controls': 0
            }
        
        avg_germination = sum(controls.mapped('germination_rate')) / len(controls)
        pass_rate = len(controls.filtered(lambda x: x.result == 'pass')) / len(controls) * 100
        
        # Calculer la tendance (simple comparaison avec période précédente)
        prev_start = start_date - (fields.Date.today() - start_date)
        prev_controls = self.env['seed.quality.control'].search([
            ('seed_lot_id.variety_id', '=', variety_id),
            ('control_date', '>=', prev_start),
            ('control_date', '<', start_date),
            ('status', '=', 'completed')
        ])
        
        trend = 'stable'
        if prev_controls:
            prev_pass_rate = len(prev_controls.filtered(lambda x: x.result == 'pass')) / len(prev_controls) * 100
            if pass_rate > prev_pass_rate + 5:
                trend = 'improving'
            elif pass_rate < prev_pass_rate - 5:
                trend = 'declining'
        
        return {
            'avg_germination': avg_germination,
            'pass_rate': pass_rate,
            'trend': trend,
            'total_controls': len(controls)
        }
    
    @api.model
    def compute_production_efficiency(self, multiplier_id=None, period='month'):
        """Calcule l'efficacité de production"""
        domain = [('status', '=', 'completed')]
        
        if multiplier_id:
            domain.append(('multiplier_id', '=', multiplier_id))
        
        if period == 'month':
            start_date = fields.Date.today().replace(day=1)
        elif period == 'quarter':
            start_date = fields.Date.today() - timedelta(days=90)
        else:
            start_date = fields.Date.today() - timedelta(days=365)
        
        domain.append(('start_date', '>=', start_date))
        
        productions = self.env['seed.production'].search(domain)
        
        if not productions:
            return {
                'efficiency_rate': 0,
                'avg_yield_per_ha': 0,
                'total_productions': 0,
                'total_yield': 0
            }
        
        total_planned = sum(productions.mapped('planned_quantity'))
        total_actual = sum(productions.mapped('actual_yield'))
        efficiency_rate = (total_actual / total_planned * 100) if total_planned else 0
        
        avg_yield_per_ha = sum(productions.mapped('yield_per_hectare')) / len(productions)
        
        return {
            'efficiency_rate': efficiency_rate,
            'avg_yield_per_ha': avg_yield_per_ha,
            'total_productions': len(productions),
            'total_yield': total_actual
        }
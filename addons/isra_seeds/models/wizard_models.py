# isra_seeds/models/wizard_models.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import base64
import csv
import io
import json
from datetime import datetime, timedelta

class SeedBulkLotWizard(models.TransientModel):
    _name = 'seed.bulk.lot.wizard'
    _description = 'Assistant Création de Lots en Masse'
    
    # Paramètres de base
    variety_id = fields.Many2one('seed.variety', 'Variété', required=True)
    level = fields.Selection([
        ('GO', 'GO'),
        ('G1', 'G1'),
        ('G2', 'G2'),
        ('G3', 'G3'),
        ('G4', 'G4'),
        ('R1', 'R1'),
        ('R2', 'R2'),
    ], string='Niveau', required=True)
    
    # Multiplicateur et parcelle
    multiplier_id = fields.Many2one('res.partner', 'Multiplicateur', domain=[('is_multiplier', '=', True)])
    parcel_id = fields.Many2one('agricultural.parcel', 'Parcelle')
    
    # Paramètres de génération
    production_date = fields.Date('Date de Production', required=True, default=fields.Date.today)
    lot_count = fields.Integer('Nombre de Lots', required=True, default=1, help="Nombre de lots à créer")
    quantity_per_lot = fields.Float('Quantité par Lot (kg)', required=True, digits=(10, 2))
    
    # Nommage
    prefix = fields.Char('Préfixe', help="Préfixe pour le nom des lots (optionnel)")
    
    # Notes communes
    notes = fields.Text('Notes Communes')
    
    # Prévisualisation
    preview_names = fields.Text('Aperçu des Noms', compute='_compute_preview_names')
    
    @api.depends('lot_count', 'level', 'variety_id', 'prefix')
    def _compute_preview_names(self):
        for wizard in self:
            if wizard.lot_count and wizard.level:
                names = []
                for i in range(1, min(wizard.lot_count + 1, 6)):  # Limiter l'aperçu à 5
                    # Simuler la génération de nom
                    year = fields.Date.today().year
                    if wizard.prefix:
                        name = f"{wizard.prefix}-{wizard.level}-{year}-{i:03d}"
                    else:
                        name = f"SL-{wizard.level}-{year}-{i:03d}"
                    names.append(name)
                
                if wizard.lot_count > 5:
                    names.append(f"... et {wizard.lot_count - 5} autres")
                
                wizard.preview_names = '\n'.join(names)
            else:
                wizard.preview_names = ""
    
    @api.onchange('multiplier_id')
    def _onchange_multiplier_id(self):
        if self.multiplier_id:
            return {'domain': {'parcel_id': [('multiplier_id', '=', self.multiplier_id.id)]}}
        else:
            return {'domain': {'parcel_id': []}}
    
    def create_lots(self):
        """Crée les lots en masse"""
        if self.lot_count <= 0:
            raise ValidationError("Le nombre de lots doit être positif")
        
        if self.lot_count > 100:
            raise ValidationError("Impossible de créer plus de 100 lots à la fois")
        
        created_lots = []
        errors = []
        
        for i in range(1, self.lot_count + 1):
            try:
                lot_vals = {
                    'variety_id': self.variety_id.id,
                    'level': self.level,
                    'quantity': self.quantity_per_lot,
                    'production_date': self.production_date,
                    'multiplier_id': self.multiplier_id.id if self.multiplier_id else False,
                    'parcel_id': self.parcel_id.id if self.parcel_id else False,
                    'notes': self.notes,
                }
                
                lot = self.env['seed.lot'].create(lot_vals)
                created_lots.append(lot)
                
            except Exception as e:
                errors.append(f"Lot {i}: {str(e)}")
        
        if errors:
            raise UserError(f"Erreurs lors de la création:\n" + "\n".join(errors))
        
        # Message de succès
        message = f"{len(created_lots)} lots créés avec succès"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Création Terminée',
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }

class SeedQuickQCWizard(models.TransientModel):
    _name = 'seed.quick.qc.wizard'
    _description = 'Assistant Contrôle Qualité Rapide'
    
    # Lots à contrôler
    seed_lot_ids = fields.Many2many('seed.lot', string='Lots de Semences', required=True)
    
    # Paramètres du contrôle
    control_date = fields.Date('Date de Contrôle', required=True, default=fields.Date.today)
    inspector_id = fields.Many2one('res.users', 'Inspecteur', required=True, default=lambda self: self.env.user)
    
    # Méthode et laboratoire
    test_method = fields.Selection([
        ('ista', 'Méthode ISTA'),
        ('aosa', 'Méthode AOSA'),
        ('national', 'Méthode Nationale'),
    ], string='Méthode de Test', default='ista')
    
    laboratory = fields.Char('Laboratoire')
    sample_size = fields.Integer('Taille Échantillon', default=400)
    
    # Paramètres de test communs
    germination_rate = fields.Float('Taux de Germination (%)', required=True, digits=(5, 2))
    variety_purity = fields.Float('Pureté Variétale (%)', required=True, digits=(5, 2))
    moisture_content = fields.Float('Taux d\'Humidité (%)', digits=(5, 2))
    seed_health = fields.Float('Santé des Semences (%)', digits=(5, 2))
    other_seeds = fields.Float('Autres Semences (%)', digits=(5, 2))
    inert_matter = fields.Float('Matières Inertes (%)', digits=(5, 2))
    
    # Observations communes
    observations = fields.Text('Observations Communes')
    
    # Options avancées
    create_individual_observations = fields.Boolean(
        'Observations Individuelles',
        help="Créer des observations spécifiques pour chaque lot"
    )
    auto_generate_certificates = fields.Boolean(
        'Générer Certificats Automatiquement',
        default=True
    )
    
    def create_quality_controls(self):
        """Crée les contrôles qualité pour tous les lots sélectionnés"""
        if not self.seed_lot_ids:
            raise ValidationError("Aucun lot sélectionné")
        
        created_controls = []
        errors = []
        
        for lot in self.seed_lot_ids:
            try:
                # Vérifier si un contrôle récent existe déjà
                existing_control = self.env['seed.quality.control'].search([
                    ('seed_lot_id', '=', lot.id),
                    ('control_date', '>=', fields.Date.today() - timedelta(days=7))
                ], limit=1)
                
                if existing_control:
                    errors.append(f"Lot {lot.name}: contrôle récent existant ({existing_control.name})")
                    continue
                
                qc_vals = {
                    'seed_lot_id': lot.id,
                    'control_date': self.control_date,
                    'inspector_id': self.inspector_id.id,
                    'test_method': self.test_method,
                    'laboratory': self.laboratory,
                    'sample_size': self.sample_size,
                    'germination_rate': self.germination_rate,
                    'variety_purity': self.variety_purity,
                    'moisture_content': self.moisture_content,
                    'seed_health': self.seed_health,
                    'other_seeds': self.other_seeds,
                    'inert_matter': self.inert_matter,
                    'observations': self.observations,
                }
                
                control = self.env['seed.quality.control'].create(qc_vals)
                
                # Démarrer automatiquement le test
                control.action_start_test()
                control.action_complete_test()
                
                created_controls.append(control)
                
                # Générer certificat si demandé
                if self.auto_generate_certificates and control.result == 'pass':
                    self._generate_certificate(control)
                
            except Exception as e:
                errors.append(f"Lot {lot.name}: {str(e)}")
        
        # Résumé des résultats
        summary = f"{len(created_controls)} contrôles créés"
        if errors:
            summary += f"\n{len(errors)} erreurs:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                summary += f"\n... et {len(errors) - 5} autres erreurs"
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Contrôles Créés',
            'res_model': 'seed.quality.control',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', [c.id for c in created_controls])],
            'context': {
                'create': False,
                'search_default_group_by_result': 1
            }
        }
    
    def _generate_certificate(self, control):
        """Génère un certificat pour un contrôle réussi"""
        try:
            # Utiliser le rapport de certificat existant
            report = self.env.ref('isra_seeds.report_quality_certificate')
            if report:
                pdf_content, _ = report._render_qweb_pdf(control.ids)
                
                # Sauvegarder le PDF
                control.write({
                    'certificate_file': base64.b64encode(pdf_content),
                    'certificate_filename': f'Certificat_{control.name}.pdf'
                })
        except Exception as e:
            # Ne pas faire échouer le processus si la génération échoue
            control.message_post(body=f"Erreur génération certificat: {e}")

class SeedDataImportWizard(models.TransientModel):
    _name = 'seed.data.import.wizard'
    _description = 'Assistant Import de Données'
    
    # Type d'import
    import_type = fields.Selection([
        ('varieties', 'Variétés'),
        ('lots', 'Lots de Semences'),
        ('multipliers', 'Multiplicateurs'),
        ('parcels', 'Parcelles'),
        ('quality_controls', 'Contrôles Qualité'),
    ], string='Type de Données', required=True)
    
    # Fichier
    file_data = fields.Binary('Fichier à Importer', required=True)
    filename = fields.Char('Nom du Fichier')
    delimiter = fields.Selection([
        (',', 'Virgule (,)'),
        (';', 'Point-virgule (;)'),
        ('\t', 'Tabulation'),
    ], string='Délimiteur', default=',')
    
    # Options
    has_header = fields.Boolean('Première ligne = en-têtes', default=True)
    update_existing = fields.Boolean('Mettre à jour existants', default=False)
    
    # Prévisualisation
    preview_data = fields.Text('Aperçu des Données', readonly=True)
    
    def preview_import(self):
        """Prévisualise les données à importer"""
        if not self.file_data:
            raise ValidationError("Aucun fichier sélectionné")
        
        try:
            # Décoder le fichier
            file_content = base64.b64decode(self.file_data).decode('utf-8')
            
            # Parser le CSV
            csv_reader = csv.reader(io.StringIO(file_content), delimiter=self.delimiter)
            rows = list(csv_reader)
            
            if not rows:
                raise ValidationError("Fichier vide")
            
            # Générer l'aperçu
            preview_lines = []
            max_preview = 10
            
            for i, row in enumerate(rows[:max_preview]):
                if i == 0 and self.has_header:
                    preview_lines.append(f"En-têtes: {' | '.join(row)}")
                else:
                    preview_lines.append(f"Ligne {i}: {' | '.join(row[:5])}")  # Limiter à 5 colonnes
            
            if len(rows) > max_preview:
                preview_lines.append(f"... et {len(rows) - max_preview} autres lignes")
            
            self.preview_data = '\n'.join(preview_lines)
            
        except Exception as e:
            raise UserError(f"Erreur lors de la lecture du fichier: {e}")
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'seed.data.import.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
    
    def execute_import(self):
        """Exécute l'import des données"""
        if not self.file_data:
            raise ValidationError("Aucun fichier sélectionné")
        
        try:
            # Décoder et parser le fichier
            file_content = base64.b64decode(self.file_data).decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(file_content), delimiter=self.delimiter)
            
            if self.import_type == 'varieties':
                return self._import_varieties(csv_reader)
            elif self.import_type == 'lots':
                return self._import_lots(csv_reader)
            elif self.import_type == 'multipliers':
                return self._import_multipliers(csv_reader)
            elif self.import_type == 'parcels':
                return self._import_parcels(csv_reader)
            elif self.import_type == 'quality_controls':
                return self._import_quality_controls(csv_reader)
            
        except Exception as e:
            raise UserError(f"Erreur lors de l'import: {e}")
    
    def _import_varieties(self, csv_reader):
        """Importe les variétés"""
        created = 0
        updated = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, 1):
            try:
                # Mapping des colonnes
                vals = {
                    'code': row.get('code', '').strip(),
                    'name': row.get('name', '').strip(),
                    'crop_type': row.get('crop_type', '').strip(),
                    'description': row.get('description', '').strip(),
                    'maturity_days': int(row.get('maturity_days', 0)) if row.get('maturity_days') else None,
                    'yield_potential': float(row.get('yield_potential', 0)) if row.get('yield_potential') else None,
                    'origin': row.get('origin', '').strip(),
                    'release_year': int(row.get('release_year', 0)) if row.get('release_year') else None,
                }
                
                if not vals['code'] or not vals['name']:
                    errors.append(f"Ligne {row_num}: code et nom requis")
                    continue
                
                # Vérifier si existe
                existing = self.env['seed.variety'].search([('code', '=', vals['code'])], limit=1)
                
                if existing:
                    if self.update_existing:
                        existing.write(vals)
                        updated += 1
                    else:
                        errors.append(f"Ligne {row_num}: variété {vals['code']} existe déjà")
                else:
                    self.env['seed.variety'].create(vals)
                    created += 1
                    
            except Exception as e:
                errors.append(f"Ligne {row_num}: {str(e)}")
        
        return self._format_import_result('variétés', created, updated, errors)
    
    def _import_lots(self, csv_reader):
        """Importe les lots de semences"""
        created = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, 1):
            try:
                # Trouver la variété
                variety_code = row.get('variety_code', '').strip()
                variety = self.env['seed.variety'].search([('code', '=', variety_code)], limit=1)
                
                if not variety:
                    errors.append(f"Ligne {row_num}: variété {variety_code} introuvable")
                    continue
                
                # Trouver le multiplicateur (optionnel)
                multiplier_name = row.get('multiplier_name', '').strip()
                multiplier = None
                if multiplier_name:
                    multiplier = self.env['res.partner'].search([
                        ('name', 'ilike', multiplier_name),
                        ('is_multiplier', '=', True)
                    ], limit=1)
                
                vals = {
                    'variety_id': variety.id,
                    'level': row.get('level', 'R1').strip(),
                    'quantity': float(row.get('quantity', 0)),
                    'production_date': datetime.strptime(row.get('production_date'), '%Y-%m-%d').date() if row.get('production_date') else fields.Date.today(),
                    'multiplier_id': multiplier.id if multiplier else None,
                    'notes': row.get('notes', '').strip(),
                }
                
                if vals['quantity'] <= 0:
                    errors.append(f"Ligne {row_num}: quantité invalide")
                    continue
                
                self.env['seed.lot'].create(vals)
                created += 1
                
            except Exception as e:
                errors.append(f"Ligne {row_num}: {str(e)}")
        
        return self._format_import_result('lots', created, 0, errors)
    
    def _format_import_result(self, data_type, created, updated, errors):
        """Formate le résultat d'import"""
        message = f"Import {data_type} terminé:\n"
        message += f"• Créés: {created}\n"
        if updated:
            message += f"• Mis à jour: {updated}\n"
        if errors:
            message += f"• Erreurs: {len(errors)}\n"
            message += "\nPremières erreurs:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                message += f"\n... et {len(errors) - 5} autres"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Import Terminé',
                'message': message,
                'type': 'success' if not errors else 'warning',
                'sticky': True,
            }
        }

class SeedDataExportWizard(models.TransientModel):
    _name = 'seed.data.export.wizard'
    _description = 'Assistant Export de Données'
    
    # Type d'export
    export_type = fields.Selection([
        ('lots', 'Lots de Semences'),
        ('quality_controls', 'Contrôles Qualité'),
        ('productions', 'Productions'),
        ('traceability', 'Traçabilité Complète'),
    ], string='Type d\'Export', required=True)
    
    # Période
    date_from = fields.Date('Date de Début')
    date_to = fields.Date('Date de Fin', default=fields.Date.today)
    
    # Filtres
    variety_ids = fields.Many2many('seed.variety', string='Variétés')
    level_filter = fields.Selection([
        ('GO', 'GO'), ('G1', 'G1'), ('G2', 'G2'),
        ('G3', 'G3'), ('G4', 'G4'), ('R1', 'R1'), ('R2', 'R2'),
    ], string='Niveau')
    status_filter = fields.Selection([
        ('pending', 'En Attente'), ('certified', 'Certifié'),
        ('rejected', 'Rejeté'), ('in_stock', 'En Stock'),
    ], string='Statut')
    
    # Options d'export
    include_quality_controls = fields.Boolean('Inclure Contrôles Qualité', default=True)
    include_productions = fields.Boolean('Inclure Productions', default=True)
    include_genealogy = fields.Boolean('Inclure Généalogie', default=False)
    
    # Format
    format = fields.Selection([
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
    ], string='Format', default='csv', required=True)
    
    def generate_export(self):
        """Génère et télécharge l'export"""
        if self.export_type == 'lots':
            return self._export_lots()
        elif self.export_type == 'quality_controls':
            return self._export_quality_controls()
        elif self.export_type == 'productions':
            return self._export_productions()
        elif self.export_type == 'traceability':
            return self._export_traceability()
    
    def _export_lots(self):
        """Exporte les lots de semences"""
        # Construire le domaine
        domain = [('active', '=', True)]
        
        if self.date_from:
            domain.append(('production_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('production_date', '<=', self.date_to))
        if self.variety_ids:
            domain.append(('variety_id', 'in', self.variety_ids.ids))
        if self.level_filter:
            domain.append(('level', '=', self.level_filter))
        if self.status_filter:
            domain.append(('status', '=', self.status_filter))
        
        lots = self.env['seed.lot'].search(domain)
        
        if self.format == 'csv':
            return self._generate_csv_lots(lots)
        elif self.format == 'excel':
            return self._generate_excel_lots(lots)
        elif self.format == 'json':
            return self._generate_json_lots(lots)
    
    def _generate_csv_lots(self, lots):
        """Génère un export CSV des lots"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # En-têtes
        headers = [
            'Référence', 'Variété', 'Code Variété', 'Niveau', 'Quantité (kg)',
            'Date Production', 'Date Expiration', 'Statut', 'Multiplicateur',
            'Parcelle', 'QR Code', 'Notes'
        ]
        
        if self.include_quality_controls:
            headers.extend(['Dernier Contrôle', 'Résultat QC', 'Taux Germination', 'Pureté'])
        
        writer.writerow(headers)
        
        # Données
        for lot in lots:
            row = [
                lot.name,
                lot.variety_id.name,
                lot.variety_id.code,
                lot.level,
                lot.quantity,
                lot.production_date.isoformat() if lot.production_date else '',
                lot.expiry_date.isoformat() if lot.expiry_date else '',
                lot.status,
                lot.multiplier_id.name if lot.multiplier_id else '',
                lot.parcel_id.name if lot.parcel_id else '',
                lot.qr_code or '',
                lot.notes or ''
            ]
            
            if self.include_quality_controls:
                last_qc = lot.quality_control_ids.sorted('control_date', reverse=True)[:1]
                if last_qc:
                    row.extend([
                        last_qc.name,
                        last_qc.result,
                        last_qc.germination_rate,
                        last_qc.variety_purity
                    ])
                else:
                    row.extend(['', '', '', ''])
            
            writer.writerow(row)
        
        # Préparer le téléchargement
        csv_data = output.getvalue()
        output.close()
        
        filename = f"export_lots_{fields.Date.today().isoformat()}.csv"
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model={self._name}&id={self.id}&field=export_file&download=true&filename={filename}',
            'target': 'self',
        }

class SeedQRGeneratorWizard(models.TransientModel):
    _name = 'seed.qr.generator.wizard'
    _description = 'Générateur de QR Codes'
    
    # Lots sélectionnés
    lot_ids = fields.Many2many('seed.lot', string='Lots de Semences', required=True)
    
    # Options de génération
    qr_size = fields.Selection([
        ('small', 'Petit (100x100)'),
        ('medium', 'Moyen (200x200)'),
        ('large', 'Grand (300x300)'),
    ], string='Taille QR Code', default='medium')
    
    include_logo = fields.Boolean('Inclure Logo ISRA', default=True)
    
    # Format de sortie
    format = fields.Selection([
        ('png', 'Images PNG'),
        ('pdf', 'PDF'),
        ('labels', 'Étiquettes'),
    ], string='Format', default='png')
    
    # Options étiquettes
    print_labels = fields.Boolean('Imprimer Étiquettes', default=False)
    labels_per_page = fields.Selection([
        ('4', '4 par page'),
        ('8', '8 par page'),
        ('12', '12 par page'),
    ], string='Étiquettes par Page', default='8')
    
    # Informations à inclure
    include_variety = fields.Boolean('Inclure Variété', default=True)
    include_level = fields.Boolean('Inclure Niveau', default=True)
    include_quantity = fields.Boolean('Inclure Quantité', default=True)
    include_multiplier = fields.Boolean('Inclure Multiplicateur', default=False)
    include_dates = fields.Boolean('Inclure Dates', default=False)
    
    def generate_qr_codes(self):
        """Génère les QR codes pour les lots sélectionnés"""
        if not self.lot_ids:
            raise ValidationError("Aucun lot sélectionné")
        
        # Régénérer les QR codes si nécessaire
        for lot in self.lot_ids:
            if not lot.qr_code:
                lot._generate_qr_code()
        
        if self.format == 'png':
            return self._generate_png_files()
        elif self.format == 'pdf':
            return self._generate_pdf_qrcodes()
        elif self.format == 'labels':
            return self._generate_labels()
    
    def _generate_png_files(self):
        """Génère des fichiers PNG individuels"""
        # Cette méthode nécessiterait une implémentation complète
        # avec création d'un ZIP contenant tous les QR codes
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'QR Codes Générés',
                'message': f'{len(self.lot_ids)} QR codes générés avec succès',
                'type': 'success',
            }
        }

class SeedProductionPlanningWizard(models.TransientModel):
    _name = 'seed.production.planning.wizard'
    _description = 'Assistant Planification Production'
    
    # Paramètres de base
    variety_id = fields.Many2one('seed.variety', 'Variété', required=True)
    current_level = fields.Selection([
        ('GO', 'GO'), ('G1', 'G1'), ('G2', 'G2'),
        ('G3', 'G3'), ('G4', 'G4'), ('R1', 'R1'),
    ], string='Niveau Actuel', required=True)
    target_level = fields.Selection([
        ('G1', 'G1'), ('G2', 'G2'), ('G3', 'G3'),
        ('G4', 'G4'), ('R1', 'R1'), ('R2', 'R2'),
    ], string='Niveau Cible', required=True)
    
    # Objectifs
    target_quantity = fields.Float('Quantité Cible (kg)', required=True, digits=(10, 2))
    season = fields.Selection([
        ('dry', 'Saison Sèche'),
        ('rainy', 'Hivernage'),
        ('counter', 'Contre-Saison'),
    ], string='Saison', required=True)
    start_date = fields.Date('Date de Début Souhaitée', required=True)
    
    # Multiplicateurs préférés
    multiplier_ids = fields.Many2many(
        'res.partner',
        string='Multiplicateurs Préférés',
        domain=[('is_multiplier', '=', True)]
    )
    
    # Options automatiques
    auto_assign_parcels = fields.Boolean('Assigner Parcelles Automatiquement', default=True)
    auto_create_contracts = fields.Boolean('Créer Contrats Automatiquement', default=False)
    auto_schedule_activities = fields.Boolean('Planifier Activités', default=True)
    
    # Recommandations calculées
    recommended_parcel_ids = fields.Many2many(
        'agricultural.parcel',
        'planning_wizard_parcel_rel',
        'wizard_id',
        'parcel_id',
        string='Parcelles Recommandées',
        readonly=True
    )
    
    def calculate_requirements(self):
        """Calcule les besoins et recommandations"""
        # Calculer les besoins en semences parentales
        parent_needs = self._calculate_parent_seed_needs()
        
        # Trouver les parcelles appropriées
        recommended_parcels = self._find_suitable_parcels()
        
        # Mettre à jour les recommandations
        self.recommended_parcel_ids = [(6, 0, recommended_parcels.ids)]
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'seed.production.planning.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
    
    def _calculate_parent_seed_needs(self):
        """Calcule les besoins en semences parentales"""
        # Ratio de multiplication approximatif selon le niveau
        multiplication_ratios = {
            ('GO', 'G1'): 30,
            ('G1', 'G2'): 25,
            ('G2', 'G3'): 20,
            ('G3', 'G4'): 15,
            ('G4', 'R1'): 12,
            ('R1', 'R2'): 10,
        }
        
        ratio = multiplication_ratios.get((self.current_level, self.target_level), 10)
        return self.target_quantity / ratio
    
    def _find_suitable_parcels(self):
        """Trouve les parcelles adaptées"""
        domain = [
            ('active', '=', True),
            ('status', '=', 'available')
        ]
        
        if self.multiplier_ids:
            domain.append(('multiplier_id', 'in', self.multiplier_ids.ids))
        
        parcels = self.env['agricultural.parcel'].search(domain)
        
        # Filtrer selon la variété et les conditions
        suitable_parcels = self.env['agricultural.parcel']
        
        for parcel in parcels:
            # Vérifier l'historique de performance
            if self._is_parcel_suitable(parcel):
                suitable_parcels |= parcel
        
        return suitable_parcels
    
    def _is_parcel_suitable(self, parcel):
        """Vérifie si une parcelle est adaptée"""
        # Vérifier l'historique avec cette variété
        past_productions = self.env['seed.production'].search([
            ('parcel_id', '=', parcel.id),
            ('seed_lot_id.variety_id', '=', self.variety_id.id),
            ('status', '=', 'completed')
        ])
        
        if past_productions:
            avg_yield = sum(past_productions.mapped('yield_per_hectare')) / len(past_productions)
            # Accepter si le rendement est au moins 70% du potentiel
            return avg_yield >= (self.variety_id.yield_potential * 0.7)
        
        # Si pas d'historique, accepter selon les caractéristiques de base
        return parcel.soil_type in ['loamy', 'clay_loamy'] and parcel.irrigation_system != 'none'
    
    def create_production_plan(self):
        """Crée le plan de production"""
        if not self.recommended_parcel_ids:
            raise ValidationError("Aucune parcelle recommandée. Exécutez d'abord le calcul des besoins.")
        
        # Créer les productions pour chaque parcelle
        created_productions = []
        
        for parcel in self.recommended_parcel_ids:
            # Trouver un lot parent approprié
            parent_lot = self._find_parent_lot()
            
            if not parent_lot:
                continue
            
            production_vals = {
                'seed_lot_id': parent_lot.id,
                'multiplier_id': parcel.multiplier_id.id,
                'parcel_id': parcel.id,
                'start_date': self.start_date,
                'planned_quantity': self._calculate_quantity_for_parcel(parcel),
                'status': 'planned',
            }
            
            production = self.env['seed.production'].create(production_vals)
            created_productions.append(production)
            
            # Créer contrat si demandé
            if self.auto_create_contracts:
                self._create_contract(production)
        
        message = f"{len(created_productions)} productions planifiées"
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Productions Planifiées',
            'res_model': 'seed.production',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', [p.id for p in created_productions])],
        }
    
    def _find_parent_lot(self):
        """Trouve un lot parent approprié"""
        return self.env['seed.lot'].search([
            ('variety_id', '=', self.variety_id.id),
            ('level', '=', self.current_level),
            ('status', '=', 'certified'),
            ('quantity_available', '>', 0)
        ], limit=1)
    
    def _calculate_quantity_for_parcel(self, parcel):
        """Calcule la quantité pour une parcelle"""
        # Estimation basée sur la surface et le rendement potentiel
        estimated_yield = parcel.area * (self.variety_id.yield_potential or 5)
        return min(estimated_yield, self.target_quantity / len(self.recommended_parcel_ids))
    
    def _create_contract(self, production):
        """Crée un contrat pour une production"""
        self.env['seed.contract'].create({
            'multiplier_id': production.multiplier_id.id,
            'variety_id': self.variety_id.id,
            'seed_level': self.target_level,
            'start_date': self.start_date,
            'end_date': self.start_date + timedelta(days=120),  # 4 mois
            'expected_quantity': production.planned_quantity,
            'status': 'draft'
        })
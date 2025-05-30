#isra_seeds/models/parcel.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class AgriculturalParcel(models.Model):
    _name = 'agricultural.parcel'
    _description = 'Parcelle Agricole'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Identification
    name = fields.Char(
        'Nom de la Parcelle',
        required=True,
        tracking=True
    )
    code = fields.Char(
        'Code',
        help="Code unique de la parcelle"
    )
    
    # Propriétaire/Gérant
    multiplier_id = fields.Many2one(
        'res.partner',
        'Multiplicateur',
        domain=[('is_multiplier', '=', True)],
        required=True,
        tracking=True
    )
    
    # Caractéristiques physiques
    area = fields.Float(
        'Surface (ha)',
        required=True,
        digits=(8, 2),
        tracking=True,
        help="Surface en hectares"
    )
    
    # Géolocalisation
    latitude = fields.Float(
        'Latitude',
        digits=(10, 6),
        help="Coordonnée GPS - Latitude"
    )
    longitude = fields.Float(
        'Longitude',
        digits=(10, 6),
        help="Coordonnée GPS - Longitude"
    )
    
    # Adresse et localisation
    address = fields.Text(
        'Adresse',
        help="Adresse complète de la parcelle"
    )
    region = fields.Char('Région')
    department = fields.Char('Département')
    commune = fields.Char('Commune')
    village = fields.Char('Village')
    
    # Caractéristiques du sol
    soil_type = fields.Selection([
        ('clay', 'Argileux'),
        ('sandy', 'Sableux'),
        ('loamy', 'Limoneux'),
        ('clay_loamy', 'Argilo-limoneux'),
        ('sandy_loamy', 'Sablo-limoneux'),
        ('peaty', 'Tourbeux'),
    ], string='Type de Sol')
    
    soil_ph = fields.Float(
        'pH du Sol',
        digits=(3, 1),
        help="pH du sol (0-14)"
    )
    
    # Irrigation
    irrigation_system = fields.Selection([
        ('none', 'Aucun'),
        ('manual', 'Manuel'),
        ('sprinkler', 'Aspersion'),
        ('drip', 'Goutte-à-goutte'),
        ('flood', 'Inondation contrôlée'),
        ('furrow', 'Sillons'),
    ], string='Système d\'Irrigation')
    
    water_source = fields.Selection([
        ('river', 'Rivière'),
        ('well', 'Puits'),
        ('borehole', 'Forage'),
        ('dam', 'Barrage'),
        ('canal', 'Canal'),
        ('rain', 'Pluvial uniquement'),
    ], string='Source d\'Eau')
    
    # Statut et état
    status = fields.Selection([
        ('available', 'Disponible'),
        ('in_use', 'En Cours d\'Utilisation'),
        ('resting', 'En Repos'),
        ('maintenance', 'En Maintenance'),
    ], string='Statut', default='available', tracking=True)
    
    active = fields.Boolean('Actif', default=True)
    
    # Relations
    seed_lot_ids = fields.One2many(
        'seed.lot',
        'parcel_id',
        string='Lots de Semences'
    )
    production_ids = fields.One2many(
        'seed.production',
        'parcel_id',
        string='Productions'
    )
    soil_analysis_ids = fields.One2many(
        'agricultural.soil.analysis',
        'parcel_id',
        string='Analyses de Sol'
    )
    previous_crop_ids = fields.One2many(
        'agricultural.previous.crop',
        'parcel_id',
        string='Cultures Précédentes'
    )
    
    # Champs calculés
    seed_lot_count = fields.Integer(
        'Nombre de Lots',
        compute='_compute_seed_lot_count'
    )
    production_count = fields.Integer(
        'Nombre de Productions',
        compute='_compute_production_count'
    )
    last_soil_analysis = fields.Many2one(
        'agricultural.soil.analysis',
        'Dernière Analyse de Sol',
        compute='_compute_last_soil_analysis'
    )
    
    @api.depends('seed_lot_ids')
    def _compute_seed_lot_count(self):
        for record in self:
            record.seed_lot_count = len(record.seed_lot_ids)
    
    @api.depends('production_ids')
    def _compute_production_count(self):
        for record in self:
            record.production_count = len(record.production_ids)
    
    @api.depends('soil_analysis_ids.analysis_date')
    def _compute_last_soil_analysis(self):
        for record in self:
            if record.soil_analysis_ids:
                record.last_soil_analysis = record.soil_analysis_ids.sorted('analysis_date', reverse=True)[0]
            else:
                record.last_soil_analysis = False
    
    # Contraintes
    _sql_constraints = [
        ('area_positive', 'CHECK(area > 0)', 'La surface doit être positive !'),
        ('latitude_range', 'CHECK(latitude >= -90 AND latitude <= 90)', 'Latitude invalide !'),
        ('longitude_range', 'CHECK(longitude >= -180 AND longitude <= 180)', 'Longitude invalide !'),
        ('ph_range', 'CHECK(soil_ph >= 0 AND soil_ph <= 14)', 'pH du sol invalide !'),
    ]
    
    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        for record in self:
            if record.latitude and record.longitude:
                # Vérification spécifique pour le Sénégal
                if not (12.0 <= record.latitude <= 16.7 and -17.6 <= record.longitude <= -11.3):
                    # Warning mais pas d'erreur pour les coordonnées hors Sénégal
                    record.message_post(
                        body="⚠ Attention: Les coordonnées semblent être en dehors du Sénégal"
                    )

class SoilAnalysis(models.Model):
    _name = 'agricultural.soil.analysis'
    _description = 'Analyse de Sol'
    _order = 'analysis_date desc'
    
    parcel_id = fields.Many2one(
        'agricultural.parcel',
        'Parcelle',
        required=True,
        ondelete='cascade'
    )
    analysis_date = fields.Date(
        'Date d\'Analyse',
        required=True,
        default=fields.Date.today
    )
    
    # Paramètres chimiques
    ph = fields.Float('pH', digits=(3, 1))
    organic_matter = fields.Float('Matière Organique (%)', digits=(5, 2))
    nitrogen = fields.Float('Azote (N) (%)', digits=(5, 3))
    phosphorus = fields.Float('Phosphore (P) (ppm)', digits=(7, 1))
    potassium = fields.Float('Potassium (K) (ppm)', digits=(7, 1))
    
    # Paramètres physiques
    sand_content = fields.Float('Teneur en Sable (%)', digits=(5, 2))
    clay_content = fields.Float('Teneur en Argile (%)', digits=(5, 2))
    silt_content = fields.Float('Teneur en Limon (%)', digits=(5, 2))
    
    # Autres éléments
    calcium = fields.Float('Calcium (Ca) (ppm)', digits=(7, 1))
    magnesium = fields.Float('Magnésium (Mg) (ppm)', digits=(7, 1))
    sulfur = fields.Float('Soufre (S) (ppm)', digits=(7, 1))
    
    # Métadonnées
    laboratory = fields.Char('Laboratoire')
    analyst = fields.Char('Analyste')
    notes = fields.Text('Notes et Observations')
    
    # Recommandations
    recommendations = fields.Text('Recommandations')
    
    @api.constrains('sand_content', 'clay_content', 'silt_content')
    def _check_texture_total(self):
        for record in self:
            if record.sand_content and record.clay_content and record.silt_content:
                total = record.sand_content + record.clay_content + record.silt_content
                if abs(total - 100.0) > 1.0:  # Tolérance de 1%
                    raise ValidationError("La somme sable + argile + limon doit égaler 100% !")

class PreviousCrop(models.Model):
    _name = 'agricultural.previous.crop'
    _description = 'Culture Précédente'
    _order = 'year desc, season'
    
    parcel_id = fields.Many2one(
        'agricultural.parcel',
        'Parcelle',
        required=True,
        ondelete='cascade'
    )
    crop = fields.Char('Culture', required=True)
    year = fields.Integer('Année', required=True)
    season = fields.Selection([
        ('dry', 'Saison Sèche'),
        ('rainy', 'Hivernage'),
        ('counter_season', 'Contre-Saison'),
    ], string='Saison', required=True)
    
    variety = fields.Char('Variété')
    yield_obtained = fields.Float('Rendement Obtenu (t/ha)', digits=(5, 2))
    
    # Pratiques culturales
    fertilizer_used = fields.Text('Engrais Utilisés')
    pesticide_used = fields.Text('Pesticides Utilisés')
    tillage_method = fields.Char('Méthode de Labour')
    
    notes = fields.Text('Notes')
    
    @api.constrains('year')
    def _check_year(self):
        current_year = fields.Date.today().year
        for record in self:
            if record.year > current_year:
                raise ValidationError("L'année ne peut pas être dans le futur !")
            if record.year < current_year - 10:
                raise ValidationError("L'année semble trop ancienne (> 10 ans) !")
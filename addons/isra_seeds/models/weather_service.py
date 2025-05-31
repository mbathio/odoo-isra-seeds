# isra_seeds/models/weather_data.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SeedWeatherData(models.Model):
    _name = 'seed.weather.data'
    _description = 'Données Météorologiques'
    _order = 'record_date desc'
    
    # Relations
    production_id = fields.Many2one(
        'seed.production',
        'Production',
        ondelete='cascade'
    )
    parcel_id = fields.Many2one(
        'agricultural.parcel',
        'Parcelle',
        required=True
    )
    
    # Date et source
    record_date = fields.Date(
        'Date d\'Enregistrement',
        required=True,
        default=fields.Date.today
    )
    data_source = fields.Selection([
        ('manual', 'Saisie Manuelle'),
        ('api', 'API Automatique'),
        ('station', 'Station Météo'),
    ], string='Source des Données', default='manual', required=True)
    
    # Températures
    temperature_min = fields.Float('Température Min (°C)')
    temperature_max = fields.Float('Température Max (°C)')
    temperature_avg = fields.Float(
        'Température Moyenne (°C)',
        compute='_compute_temperature_avg',
        store=True
    )
    
    # Conditions météorologiques
    humidity = fields.Float('Humidité (%)')
    pressure = fields.Float('Pression (hPa)')
    rainfall = fields.Float('Précipitations (mm)')
    
    # Vent
    wind_speed = fields.Float('Vitesse Vent (km/h)')
    wind_direction = fields.Selection([
        ('N', 'Nord'),
        ('NE', 'Nord-Est'),
        ('E', 'Est'),
        ('SE', 'Sud-Est'),
        ('S', 'Sud'),
        ('SW', 'Sud-Ouest'),
        ('W', 'Ouest'),
        ('NW', 'Nord-Ouest'),
    ], string='Direction Vent')
    
    # Conditions générales
    weather_condition = fields.Selection([
        ('sunny', 'Ensoleillé'),
        ('partly_cloudy', 'Partiellement Nuageux'),
        ('cloudy', 'Nuageux'),
        ('rainy', 'Pluvieux'),
        ('stormy', 'Orageux'),
        ('foggy', 'Brumeux'),
    ], string='Condition Météo')
    
    # Autres données
    visibility = fields.Float('Visibilité (km)')
    uv_index = fields.Float('Index UV')
    
    # Notes
    notes = fields.Text('Observations')
    
    @api.depends('temperature_min', 'temperature_max')
    def _compute_temperature_avg(self):
        for record in self:
            if record.temperature_min and record.temperature_max:
                record.temperature_avg = (record.temperature_min + record.temperature_max) / 2
            else:
                record.temperature_avg = 0
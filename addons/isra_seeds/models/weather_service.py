# isra_seeds/models/weather_service.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import requests
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class SeedWeatherService(models.AbstractModel):
    _name = 'seed.weather.service'
    _description = 'Service Météorologique'

    @api.model
    def fetch_weather_data(self, latitude, longitude, date=None):
        """Récupère les données météo depuis une API externe"""
        if not date:
            date = fields.Date.today()
        
        api_key = self.env['ir.config_parameter'].sudo().get_param('seed.weather_api_key')
        if not api_key:
            raise UserError("Clé API météo non configurée. Veuillez configurer la clé OpenWeatherMap.")
        
        try:
            # Utiliser OpenWeatherMap API
            if isinstance(date, str):
                date = datetime.strptime(date, '%Y-%m-%d').date()
            
            # Pour les données historiques (plus de 5 jours)
            if (fields.Date.today() - date).days > 5:
                return self._fetch_historical_weather(latitude, longitude, date, api_key)
            else:
                return self._fetch_current_weather(latitude, longitude, api_key)
                
        except Exception as e:
            _logger.error(f"Erreur lors de la récupération des données météo: {e}")
            return None
    
    def _fetch_current_weather(self, latitude, longitude, api_key):
        """Récupère les données météo actuelles"""
        url = f"https://api.openweathermap.org/data/2.5/weather"
        params = {
            'lat': latitude,
            'lon': longitude,
            'appid': api_key,
            'units': 'metric',
            'lang': 'fr'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        return {
            'temperature_min': data['main']['temp_min'],
            'temperature_max': data['main']['temp_max'],
            'humidity': data['main']['humidity'],
            'pressure': data['main'].get('pressure'),
            'wind_speed': data['wind'].get('speed', 0) * 3.6,  # Convertir m/s en km/h
            'wind_direction': self._convert_wind_direction(data['wind'].get('deg', 0)),
            'weather_condition': self._map_weather_condition(data['weather'][0]['main']),
            'description': data['weather'][0]['description'],
            'visibility': data.get('visibility', 0) / 1000,  # Convertir en km
            'rainfall': data.get('rain', {}).get('1h', 0),
            'data_source': 'openweathermap'
        }
    
    def _fetch_historical_weather(self, latitude, longitude, date, api_key):
        """Récupère les données météo historiques"""
        # OpenWeatherMap One Call API pour les données historiques
        timestamp = int(datetime.combine(date, datetime.min.time()).timestamp())
        
        url = f"https://api.openweathermap.org/data/3.0/onecall/timemachine"
        params = {
            'lat': latitude,
            'lon': longitude,
            'dt': timestamp,
            'appid': api_key,
            'units': 'metric'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        current = data['data'][0]
        
        return {
            'temperature_min': current['temp'],
            'temperature_max': current['temp'],
            'humidity': current['humidity'],
            'pressure': current.get('pressure'),
            'wind_speed': current['wind_speed'] * 3.6,
            'wind_direction': self._convert_wind_direction(current.get('wind_deg', 0)),
            'weather_condition': self._map_weather_condition(current['weather'][0]['main']),
            'description': current['weather'][0]['description'],
            'rainfall': current.get('rain', {}).get('1h', 0),
            'data_source': 'openweathermap_historical'
        }
    
    def _convert_wind_direction(self, degrees):
        """Convertit les degrés en direction cardinale"""
        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        index = round(degrees / 45) % 8
        return directions[index]
    
    def _map_weather_condition(self, condition):
        """Mappe les conditions météo OpenWeatherMap vers nos conditions"""
        mapping = {
            'Clear': 'sunny',
            'Clouds': 'cloudy',
            'Rain': 'rainy',
            'Drizzle': 'rainy',
            'Thunderstorm': 'stormy',
            'Snow': 'rainy',  # Rare au Sénégal
            'Mist': 'foggy',
            'Fog': 'foggy',
            'Haze': 'partly_cloudy'
        }
        return mapping.get(condition, 'sunny')
    
    @api.model
    def auto_fetch_weather_for_productions(self):
        """Récupère automatiquement les données météo pour les productions en cours"""
        active_productions = self.env['seed.production'].search([
            ('status', '=', 'in_progress'),
            ('parcel_id.latitude', '!=', False),
            ('parcel_id.longitude', '!=', False)
        ])
        
        for production in active_productions:
            try:
                # Vérifier si des données existent déjà pour aujourd'hui
                existing_data = self.env['seed.weather.data'].search([
                    ('production_id', '=', production.id),
                    ('record_date', '=', fields.Date.today())
                ])
                
                if not existing_data:
                    weather_data = self.fetch_weather_data(
                        production.parcel_id.latitude,
                        production.parcel_id.longitude
                    )
                    
                    if weather_data:
                        self.env['seed.weather.data'].create({
                            'production_id': production.id,
                            'parcel_id': production.parcel_id.id,
                            'record_date': fields.Date.today(),
                            'temperature_min': weather_data['temperature_min'],
                            'temperature_max': weather_data['temperature_max'],
                            'humidity': weather_data['humidity'],
                            'wind_speed': weather_data['wind_speed'],
                            'wind_direction': weather_data['wind_direction'],
                            'weather_condition': weather_data['weather_condition'],
                            'rainfall': weather_data['rainfall'],
                            'data_source': 'api'
                        })
                        
            except Exception as e:
                _logger.error(f"Erreur lors de la récupération météo pour {production.name}: {e}")
                continue
    
    @api.model
    def get_weather_forecast(self, latitude, longitude, days=5):
        """Récupère les prévisions météo"""
        api_key = self.env['ir.config_parameter'].sudo().get_param('seed.weather_api_key')
        if not api_key:
            return []
        
        try:
            url = f"https://api.openweathermap.org/data/2.5/forecast"
            params = {
                'lat': latitude,
                'lon': longitude,
                'appid': api_key,
                'units': 'metric',
                'lang': 'fr'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            forecast = []
            
            for item in data['list'][:days * 8]:  # 8 prévisions par jour (toutes les 3h)
                forecast.append({
                    'datetime': datetime.fromtimestamp(item['dt']),
                    'temperature': item['main']['temp'],
                    'humidity': item['main']['humidity'],
                    'weather_condition': self._map_weather_condition(item['weather'][0]['main']),
                    'description': item['weather'][0]['description'],
                    'rainfall': item.get('rain', {}).get('3h', 0),
                    'wind_speed': item['wind']['speed'] * 3.6
                })
            
            return forecast
            
        except Exception as e:
            _logger.error(f"Erreur lors de la récupération des prévisions: {e}")
            return []
    
    @api.model
    def analyze_weather_impact(self, production_id):
        """Analyse l'impact météorologique sur une production"""
        production = self.env['seed.production'].browse(production_id)
        if not production.exists():
            return {}
        
        weather_data = self.env['seed.weather.data'].search([
            ('production_id', '=', production_id),
            ('record_date', '>=', production.start_date),
            ('record_date', '<=', production.end_date or fields.Date.today())
        ])
        
        if not weather_data:
            return {'status': 'no_data'}
        
        # Calculs d'analyse
        total_rainfall = sum(weather_data.mapped('rainfall'))
        avg_temperature = sum(weather_data.mapped('temperature_avg')) / len(weather_data)
        avg_humidity = sum(weather_data.mapped('humidity')) / len(weather_data)
        
        # Jours de conditions défavorables
        rainy_days = len(weather_data.filtered(lambda w: w.rainfall > 5))
        hot_days = len(weather_data.filtered(lambda w: w.temperature_max > 35))
        cold_days = len(weather_data.filtered(lambda w: w.temperature_min < 15))
        
        # Analyse des risques
        risks = []
        if total_rainfall < 100:  # Moins de 100mm pendant la production
            risks.append('drought_risk')
        elif total_rainfall > 500:
            risks.append('flood_risk')
        
        if hot_days > len(weather_data) * 0.3:  # Plus de 30% de jours chauds
            risks.append('heat_stress')
        
        if cold_days > len(weather_data) * 0.2:  # Plus de 20% de jours froids
            risks.append('cold_stress')
        
        if avg_humidity > 80:
            risks.append('disease_risk')
        
        return {
            'status': 'analyzed',
            'total_rainfall': total_rainfall,
            'avg_temperature': avg_temperature,
            'avg_humidity': avg_humidity,
            'rainy_days': rainy_days,
            'hot_days': hot_days,
            'cold_days': cold_days,
            'risks': risks,
            'data_points': len(weather_data)
        }

class SeedWeatherAlert(models.Model):
    _name = 'seed.weather.alert'
    _description = 'Alerte Météorologique'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char('Référence', required=True, default='New')
    alert_type = fields.Selection([
        ('heavy_rain', 'Pluie Intense'),
        ('drought', 'Sécheresse'),
        ('high_temperature', 'Température Élevée'),
        ('strong_wind', 'Vent Fort'),
        ('storm', 'Orage'),
        ('frost', 'Gel'),
    ], string='Type d\'Alerte', required=True)
    
    severity = fields.Selection([
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé'),
        ('extreme', 'Extrême'),
    ], string='Gravité', required=True)
    
    # Zones affectées
    region_affected = fields.Char('Région Affectée')
    parcel_ids = fields.Many2many(
        'agricultural.parcel',
        'weather_alert_parcel_rel',
        'alert_id',
        'parcel_id',
        string='Parcelles Affectées'
    )
    production_ids = fields.Many2many(
        'seed.production',
        'weather_alert_production_rel',
        'alert_id',
        'production_id',
        string='Productions Affectées'
    )
    
    # Timing
    start_time = fields.Datetime('Début Prévu', required=True)
    end_time = fields.Datetime('Fin Prévue')
    issued_time = fields.Datetime('Émise le', default=fields.Datetime.now)
    
    # Contenu
    description = fields.Text('Description', required=True)
    recommendations = fields.Text('Recommandations')
    
    # Statut
    status = fields.Selection([
        ('active', 'Active'),
        ('expired', 'Expirée'),
        ('cancelled', 'Annulée'),
    ], string='Statut', default='active', tracking=True)
    
    # Source
    source = fields.Selection([
        ('api', 'API Météo'),
        ('manual', 'Saisie Manuelle'),
        ('government', 'Service Météorologique National'),
    ], string='Source', default='api')
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('seed.weather.alert') or 'New'
        
        alert = super().create(vals)
        alert._notify_affected_users()
        return alert
    
    def _notify_affected_users(self):
        """Notifie les utilisateurs affectés par l'alerte"""
        # Récupérer les multiplicateurs affectés
        multipliers = self.parcel_ids.mapped('multiplier_id')
        multipliers |= self.production_ids.mapped('multiplier_id')
        
        # Créer des activités pour chaque multiplicateur
        for multiplier in multipliers:
            # Trouver l'utilisateur correspondant (si existe)
            user = self.env['res.users'].search([
                ('partner_id', '=', multiplier.id)
            ], limit=1)
            
            if user:
                self.activity_schedule(
                    'mail.mail_activity_data_warning',
                    user_id=user.id,
                    summary=f"Alerte météo: {self.alert_type}",
                    note=f"{self.description}\n\nRecommandations: {self.recommendations or 'Aucune'}"
                )
        
        # Notifier aussi les managers
        managers = self.env.ref('isra_seeds.group_seed_manager').users
        for manager in managers:
            self.activity_schedule(
                'mail.mail_activity_data_warning',
                user_id=manager.id,
                summary=f"Alerte météo {self.severity}: {self.alert_type}",
                note=f"Zone: {self.region_affected}\n{self.description}"
            )
    
    @api.model
    def check_weather_alerts(self):
        """Vérifie et crée des alertes météo automatiques"""
        # Récupérer les parcelles avec coordonnées GPS
        parcels = self.env['agricultural.parcel'].search([
            ('latitude', '!=', False),
            ('longitude', '!=', False),
            ('active', '=', True)
        ])
        
        weather_service = self.env['seed.weather.service']
        
        for parcel in parcels:
            try:
                # Récupérer les prévisions
                forecast = weather_service.get_weather_forecast(
                    parcel.latitude,
                    parcel.longitude,
                    days=3
                )
                
                if forecast:
                    self._analyze_forecast_for_alerts(parcel, forecast)
                    
            except Exception as e:
                _logger.error(f"Erreur lors de la vérification des alertes pour {parcel.name}: {e}")
                continue
    
    def _analyze_forecast_for_alerts(self, parcel, forecast):
        """Analyse les prévisions pour détecter des conditions d'alerte"""
        for prediction in forecast:
            # Pluie intense (> 50mm en 3h)
            if prediction['rainfall'] > 50:
                self._create_alert_if_not_exists(
                    'heavy_rain',
                    'high',
                    f"Pluie intense prévue: {prediction['rainfall']}mm",
                    parcel,
                    prediction['datetime']
                )
            
            # Température élevée (> 40°C)
            elif prediction['temperature'] > 40:
                self._create_alert_if_not_exists(
                    'high_temperature',
                    'medium',
                    f"Température élevée prévue: {prediction['temperature']}°C",
                    parcel,
                    prediction['datetime']
                )
            
            # Vent fort (> 60 km/h)
            elif prediction['wind_speed'] > 60:
                self._create_alert_if_not_exists(
                    'strong_wind',
                    'medium',
                    f"Vent fort prévu: {prediction['wind_speed']} km/h",
                    parcel,
                    prediction['datetime']
                )
    
    def _create_alert_if_not_exists(self, alert_type, severity, description, parcel, start_time):
        """Crée une alerte si elle n'existe pas déjà"""
        existing_alert = self.search([
            ('alert_type', '=', alert_type),
            ('parcel_ids', 'in', [parcel.id]),
            ('start_time', '>=', fields.Datetime.now()),
            ('status', '=', 'active')
        ], limit=1)
        
        if not existing_alert:
            # Trouver les productions affectées
            affected_productions = self.env['seed.production'].search([
                ('parcel_id', '=', parcel.id),
                ('status', '=', 'in_progress')
            ])
            
            self.create({
                'alert_type': alert_type,
                'severity': severity,
                'description': description,
                'start_time': start_time,
                'region_affected': f"{parcel.commune}, {parcel.department}",
                'parcel_ids': [(6, 0, [parcel.id])],
                'production_ids': [(6, 0, affected_productions.ids)],
                'recommendations': self._get_recommendations(alert_type),
                'source': 'api'
            })
    
    def _get_recommendations(self, alert_type):
        """Retourne les recommandations selon le type d'alerte"""
        recommendations = {
            'heavy_rain': "Éviter les travaux de terrain. Vérifier le drainage des parcelles. Protéger les semences stockées.",
            'drought': "Augmenter la fréquence d'irrigation. Surveiller l'état hydrique des cultures. Appliquer du paillage.",
            'high_temperature': "Irriguer tôt le matin ou tard le soir. Ombrager les jeunes plants si possible. Surveiller les signes de stress thermique.",
            'strong_wind': "Sécuriser les structures. Reporter les épandages. Vérifier l'ancrage des tuteurs.",
            'storm': "Éviter toute activité en extérieur. Sécuriser le matériel. Vérifier l'état des cultures après passage.",
            'frost': "Couvrir les jeunes plants. Arroser légèrement avant l'aube. Surveiller les zones basses."
        }
        return recommendations.get(alert_type, "Suivre les consignes de sécurité habituelles.")
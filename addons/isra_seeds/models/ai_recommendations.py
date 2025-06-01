# isra_seeds/models/ai_recommendations.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import json
import statistics
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class SeedAI(models.Model):
    _name = 'seed.ai'
    _description = 'Intelligence Artificielle pour Recommandations'
    
    @api.model
    def predict_optimal_planting_dates(self, variety_id, parcel_id):
        """Prédit les meilleures dates de plantation"""
        variety = self.env['seed.variety'].browse(variety_id)
        parcel = self.env['agricultural.parcel'].browse(parcel_id)
        
        if not variety.exists() or not parcel.exists():
            return {'error': 'Variété ou parcelle invalide'}
        
        # Analyser les données historiques
        historical_data = self._get_historical_production_data(variety_id, parcel_id)
        weather_patterns = self._get_weather_patterns(parcel.latitude, parcel.longitude)
        
        # Calculs des recommandations
        recommendations = []
        
        # Saison sèche (Novembre - Mai)
        dry_season_score = self._calculate_planting_score(
            variety, parcel, 'dry_season', historical_data, weather_patterns
        )
        if dry_season_score > 0.6:
            recommendations.append({
                'period': 'dry_season',
                'optimal_dates': ['2024-11-15', '2024-12-15'],
                'score': dry_season_score,
                'reasons': ['Faible risque de maladies', 'Irrigation contrôlée possible', 'Bonne qualité des semences']
            })
        
        # Hivernage (Juin - Octobre)
        rainy_season_score = self._calculate_planting_score(
            variety, parcel, 'rainy_season', historical_data, weather_patterns
        )
        if rainy_season_score > 0.6:
            recommendations.append({
                'period': 'rainy_season',
                'optimal_dates': ['2024-06-15', '2024-07-15'],
                'score': rainy_season_score,
                'reasons': ['Eau naturelle abondante', 'Croissance rapide', 'Coûts d\'irrigation réduits']
            })
        
        # Contre-saison (Février - Mai)
        counter_season_score = self._calculate_planting_score(
            variety, parcel, 'counter_season', historical_data, weather_patterns
        )
        if counter_season_score > 0.5:
            recommendations.append({
                'period': 'counter_season',
                'optimal_dates': ['2024-02-15', '2024-03-15'],
                'score': counter_season_score,
                'reasons': ['Températures modérées', 'Moins de pression parasitaire']
            })
        
        # Trier par score
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        
        return {
            'variety': variety.name,
            'parcel': parcel.name,
            'recommendations': recommendations,
            'best_period': recommendations[0]['period'] if recommendations else None,
            'confidence_level': self._calculate_confidence_level(historical_data)
        }
    
    @api.model
    def recommend_varieties_for_parcel(self, parcel_id):
        """Recommande des variétés selon les caractéristiques du sol"""
        parcel = self.env['agricultural.parcel'].browse(parcel_id)
        if not parcel.exists():
            return {'error': 'Parcelle invalide'}
        
        # Récupérer les analyses de sol récentes
        soil_analysis = parcel.soil_analysis_ids.sorted('analysis_date', reverse=True)[:1]
        
        if not soil_analysis:
            return {'error': 'Aucune analyse de sol disponible'}
        
        # Récupérer toutes les variétés actives
        varieties = self.env['seed.variety'].search([('active', '=', True)])
        
        recommendations = []
        
        for variety in varieties:
            score = self._calculate_variety_suitability_score(variety, parcel, soil_analysis)
            
            if score > 0.5:  # Seuil de recommandation
                reasons = self._get_variety_suitability_reasons(variety, parcel, soil_analysis)
                
                recommendations.append({
                    'variety_id': variety.id,
                    'variety_name': variety.name,
                    'variety_code': variety.code,
                    'crop_type': variety.crop_type,
                    'suitability_score': score,
                    'reasons': reasons,
                    'expected_yield': self._predict_yield(variety, parcel),
                    'risk_level': self._assess_risk_level(variety, parcel)
                })
        
        # Trier par score de compatibilité
        recommendations.sort(key=lambda x: x['suitability_score'], reverse=True)
        
        return {
            'parcel': parcel.name,
            'soil_type': parcel.soil_type,
            'recommendations': recommendations[:10],  # Top 10
            'analysis_date': soil_analysis.analysis_date.isoformat() if soil_analysis else None
        }
    
    @api.model
    def optimize_irrigation_schedule(self, production_id):
        """Optimise le calendrier d'irrigation"""
        production = self.env['seed.production'].browse(production_id)
        if not production.exists():
            return {'error': 'Production invalide'}
        
        variety = production.seed_lot_id.variety_id
        parcel = production.parcel_id
        
        # Récupérer les données météo récentes et prévisions
        weather_data = self.env['seed.weather.data'].search([
            ('production_id', '=', production_id),
            ('record_date', '>=', fields.Date.today() - timedelta(days=7))
        ])
        
        # Calculer les besoins en eau selon le stade de croissance
        days_since_planting = (fields.Date.today() - production.sowing_date).days if production.sowing_date else 0
        growth_stage = self._determine_growth_stage(variety, days_since_planting)
        
        # Besoins en eau par stade (mm/jour)
        water_needs = {
            'germination': 3,
            'vegetative': 5,
            'flowering': 7,
            'grain_filling': 6,
            'maturity': 2
        }
        
        daily_need = water_needs.get(growth_stage, 4)
        
        # Analyser les précipitations récentes
        recent_rainfall = sum(weather_data.mapped('rainfall')) if weather_data else 0
        
        # Recommandations d'irrigation
        recommendations = []
        
        for i in range(7):  # Prochains 7 jours
            date = fields.Date.today() + timedelta(days=i)
            
            # Prédire les besoins pour ce jour
            predicted_rainfall = self._predict_rainfall(parcel, date)
            irrigation_needed = max(0, daily_need - predicted_rainfall)
            
            if irrigation_needed > 1:  # Seuil minimal
                recommendations.append({
                    'date': date.isoformat(),
                    'irrigation_amount': irrigation_needed,
                    'time_recommended': '06:00',  # Tôt le matin
                    'reason': f'Besoin: {daily_need}mm, Pluie prévue: {predicted_rainfall}mm',
                    'priority': 'high' if irrigation_needed > 5 else 'medium'
                })
        
        return {
            'production': production.name,
            'growth_stage': growth_stage,
            'daily_water_need': daily_need,
            'recent_rainfall': recent_rainfall,
            'irrigation_schedule': recommendations,
            'irrigation_system': parcel.irrigation_system
        }
    
    @api.model
    def predict_quality_outcomes(self, lot_id):
        """Prédit les résultats de contrôle qualité"""
        lot = self.env['seed.lot'].browse(lot_id)
        if not lot.exists():
            return {'error': 'Lot invalide'}
        
        # Analyser l'historique de la variété
        variety_history = self._get_variety_quality_history(lot.variety_id.id)
        
        # Analyser les conditions de production
        production_factors = self._analyze_production_factors(lot)
        
        # Calculs prédictifs
        predicted_germination = self._predict_germination_rate(variety_history, production_factors)
        predicted_purity = self._predict_purity_rate(variety_history, production_factors)
        
        # Facteurs de risque
        risk_factors = []
        if production_factors.get('weather_stress', 0) > 0.7:
            risk_factors.append('Stress météorologique élevé')
        if production_factors.get('disease_pressure', 0) > 0.6:
            risk_factors.append('Pression parasitaire')
        if lot.is_expired:
            risk_factors.append('Lot proche de l\'expiration')
        
        # Niveau de confiance
        confidence = self._calculate_prediction_confidence(variety_history, production_factors)
        
        return {
            'lot': lot.name,
            'variety': lot.variety_id.name,
            'predictions': {
                'germination_rate': predicted_germination,
                'variety_purity': predicted_purity,
                'overall_quality': 'pass' if predicted_germination > 80 and predicted_purity > 95 else 'risk'
            },
            'confidence_level': confidence,
            'risk_factors': risk_factors,
            'recommendations': self._get_quality_recommendations(predicted_germination, predicted_purity, risk_factors)
        }
    
    def _get_historical_production_data(self, variety_id, parcel_id):
        """Récupère les données historiques de production"""
        productions = self.env['seed.production'].search([
            ('seed_lot_id.variety_id', '=', variety_id),
            ('parcel_id', '=', parcel_id),
            ('status', '=', 'completed'),
            ('start_date', '>=', fields.Date.today() - timedelta(days=1095))  # 3 ans
        ])
        
        data = []
        for prod in productions:
            weather_summary = self._summarize_weather_for_production(prod)
            data.append({
                'yield': prod.actual_yield,
                'yield_per_ha': prod.yield_per_hectare,
                'start_date': prod.start_date,
                'duration': prod.duration_days,
                'weather_summary': weather_summary,
                'issues_count': prod.issue_count
            })
        
        return data
    
    def _get_weather_patterns(self, latitude, longitude):
        """Analyse les patterns météorologiques historiques"""
        # Ici, on pourrait intégrer des données météo historiques
        # Pour la démo, on retourne des patterns typiques du Sénégal
        return {
            'dry_season': {
                'rainfall': 10,  # mm/mois
                'temperature': 28,  # °C moyenne
                'humidity': 45  # %
            },
            'rainy_season': {
                'rainfall': 180,  # mm/mois
                'temperature': 32,
                'humidity': 75
            },
            'counter_season': {
                'rainfall': 25,
                'temperature': 25,
                'humidity': 55
            }
        }
    
    def _calculate_planting_score(self, variety, parcel, season, historical_data, weather_patterns):
        """Calcule un score de pertinence pour la plantation"""
        score = 0.5  # Score de base
        
        # Facteur variété
        if variety.crop_type == 'rice':
            if season == 'rainy_season':
                score += 0.3  # Le riz préfère la saison des pluies
            elif season == 'dry_season' and parcel.irrigation_system in ['drip', 'flood']:
                score += 0.2  # Irrigation disponible
        elif variety.crop_type == 'maize':
            if season in ['rainy_season', 'counter_season']:
                score += 0.2
        
        # Facteur sol
        if parcel.soil_type in ['clay_loamy', 'loamy']:
            score += 0.1  # Bon type de sol
        
        # Facteur historique
        if historical_data:
            avg_yield = statistics.mean([d['yield_per_ha'] for d in historical_data if d['yield_per_ha']])
            if avg_yield > variety.yield_potential * 0.8:  # 80% du potentiel
                score += 0.2
        
        return min(1.0, score)  # Limiter à 1.0
    
    def _calculate_confidence_level(self, historical_data):
        """Calcule le niveau de confiance des prédictions"""
        if len(historical_data) >= 5:
            return 'high'
        elif len(historical_data) >= 2:
            return 'medium'
        else:
            return 'low'
    
    def _calculate_variety_suitability_score(self, variety, parcel, soil_analysis):
        """Calcule la compatibilité variété-parcelle"""
        score = 0.5  # Score de base
        
        # Facteur type de sol
        soil_preferences = {
            'rice': ['clay', 'clay_loamy'],
            'maize': ['loamy', 'sandy_loamy'],
            'peanut': ['sandy', 'sandy_loamy'],
            'sorghum': ['sandy', 'loamy'],
        }
        
        if parcel.soil_type in soil_preferences.get(variety.crop_type, []):
            score += 0.2
        
        # Facteur pH du sol
        if soil_analysis:
            soil_ph = soil_analysis.ph
            optimal_ph = {
                'rice': (5.5, 7.0),
                'maize': (6.0, 7.5),
                'peanut': (6.0, 7.0),
                'sorghum': (6.0, 8.0),
            }
            
            ph_range = optimal_ph.get(variety.crop_type, (6.0, 7.0))
            if ph_range[0] <= soil_ph <= ph_range[1]:
                score += 0.2
            elif abs(soil_ph - (sum(ph_range) / 2)) < 1:
                score += 0.1
        
        # Facteur irrigation
        irrigation_needs = {
            'rice': ['flood', 'drip'],
            'maize': ['sprinkler', 'drip'],
            'peanut': ['drip', 'manual'],
            'sorghum': ['drip', 'manual'],
        }
        
        if parcel.irrigation_system in irrigation_needs.get(variety.crop_type, []):
            score += 0.15
        
        # Facteur performance historique
        historical_performance = self._get_variety_performance_on_parcel(variety.id, parcel.id)
        if historical_performance:
            if historical_performance > 0.8:  # Bon historique
                score += 0.15
            elif historical_performance < 0.5:  # Mauvais historique
                score -= 0.1
        
        return min(1.0, max(0.0, score))
    
    def _get_variety_suitability_reasons(self, variety, parcel, soil_analysis):
        """Génère les raisons de compatibilité"""
        reasons = []
        
        # Type de sol
        if parcel.soil_type in ['loamy', 'clay_loamy']:
            reasons.append(f"Sol {parcel.soil_type} adapté au {variety.crop_type}")
        
        # pH
        if soil_analysis and 6.0 <= soil_analysis.ph <= 7.5:
            reasons.append(f"pH optimal ({soil_analysis.ph})")
        
        # Irrigation
        if parcel.irrigation_system != 'none':
            reasons.append(f"Système d'irrigation {parcel.irrigation_system} disponible")
        
        # Potentiel de rendement
        if variety.yield_potential > 5:
            reasons.append(f"Bon potentiel de rendement ({variety.yield_potential} t/ha)")
        
        return reasons
    
    def _predict_yield(self, variety, parcel):
        """Prédit le rendement potentiel"""
        base_yield = variety.yield_potential
        
        # Ajustements selon les conditions
        multiplier = 1.0
        
        # Facteur sol
        if parcel.soil_type in ['loamy', 'clay_loamy']:
            multiplier *= 1.1
        elif parcel.soil_type in ['sandy']:
            multiplier *= 0.9
        
        # Facteur irrigation
        if parcel.irrigation_system in ['drip', 'sprinkler']:
            multiplier *= 1.05
        elif parcel.irrigation_system == 'none':
            multiplier *= 0.8
        
        return round(base_yield * multiplier, 1)
    
    def _assess_risk_level(self, variety, parcel):
        """Évalue le niveau de risque"""
        risk_score = 0
        
        # Risques liés au sol
        if parcel.soil_type == 'sandy' and variety.crop_type == 'rice':
            risk_score += 2
        
        # Risques liés à l'irrigation
        if parcel.irrigation_system == 'none' and variety.crop_type in ['rice', 'maize']:
            risk_score += 2
        
        # Risques climatiques (à développer)
        risk_score += 1  # Risque de base
        
        if risk_score <= 2:
            return 'low'
        elif risk_score <= 4:
            return 'medium'
        else:
            return 'high'
    
    def _determine_growth_stage(self, variety, days_since_planting):
        """Détermine le stade de croissance"""
        maturity_days = variety.maturity_days or 120
        
        if days_since_planting < 0:
            return 'planning'
        elif days_since_planting <= 14:
            return 'germination'
        elif days_since_planting <= maturity_days * 0.4:
            return 'vegetative'
        elif days_since_planting <= maturity_days * 0.7:
            return 'flowering'
        elif days_since_planting <= maturity_days * 0.9:
            return 'grain_filling'
        else:
            return 'maturity'
    
    def _predict_rainfall(self, parcel, date):
        """Prédit les précipitations (simulation simple)"""
        # Ici, on intégrerait une vraie API météo
        # Pour la démo, on simule selon la saison
        month = date.month
        
        if 6 <= month <= 9:  # Saison des pluies
            return 5  # mm moyen par jour
        elif month in [5, 10]:  # Transitions
            return 2
        else:  # Saison sèche
            return 0
    
    def _get_variety_quality_history(self, variety_id):
        """Récupère l'historique qualité d'une variété"""
        controls = self.env['seed.quality.control'].search([
            ('seed_lot_id.variety_id', '=', variety_id),
            ('status', '=', 'completed'),
            ('control_date', '>=', fields.Date.today() - timedelta(days=730))  # 2 ans
        ])
        
        if not controls:
            return {}
        
        return {
            'avg_germination': statistics.mean(controls.mapped('germination_rate')),
            'avg_purity': statistics.mean(controls.mapped('variety_purity')),
            'pass_rate': len(controls.filtered(lambda c: c.result == 'pass')) / len(controls),
            'sample_size': len(controls)
        }
    
    def _analyze_production_factors(self, lot):
        """Analyse les facteurs de production affectant la qualité"""
        factors = {}
        
        # Analyser les productions liées
        productions = lot.production_ids
       # ...existing code...
        if productions:
            # Stress météorologique
            weather_issues = sum(
                sum(prod.issue_ids.filtered(lambda i: i.issue_type == 'weather').mapped('yield_impact'))
                for prod in productions
            ) / 100

            factors['weather_stress'] = min(1.0, weather_issues)

            # Pression parasitaire
            disease_issues = sum(
                sum(prod.issue_ids.filtered(lambda i: i.issue_type in ['disease', 'pest']).mapped('yield_impact'))
                for prod in productions
            ) / 100

            factors['disease_pressure'] = min(1.0, disease_issues)

            # Qualité de gestion
            management_score = 1.0 - (len(productions.mapped('issue_ids')) / max(1, len(productions)) * 0.1)
            factors['management_quality'] = max(0.0, management_score)
# ...existing code...
        
        # Âge du lot
        if lot.production_date:
            age_days = (fields.Date.today() - lot.production_date).days
            age_factor = max(0.0, 1.0 - (age_days / 365) * 0.1)  # Dégradation de 10% par an
            factors['storage_quality'] = age_factor
        
        return factors
    
    def _predict_germination_rate(self, variety_history, production_factors):
        """Prédit le taux de germination"""
        base_rate = variety_history.get('avg_germination', 85)  # Défaut 85%
        
        # Ajustements selon les facteurs
        adjustments = 0
        
        if 'weather_stress' in production_factors:
            adjustments -= production_factors['weather_stress'] * 10
        
        if 'storage_quality' in production_factors:
            adjustments += (production_factors['storage_quality'] - 0.8) * 15
        
        if 'management_quality' in production_factors:
            adjustments += (production_factors['management_quality'] - 0.8) * 10
        
        predicted_rate = base_rate + adjustments
        return max(0, min(100, predicted_rate))
    
    def _predict_purity_rate(self, variety_history, production_factors):
        """Prédit le taux de pureté"""
        base_rate = variety_history.get('avg_purity', 97)  # Défaut 97%
        
        # La pureté est moins affectée par les conditions, mais peut être impactée par la gestion
        adjustments = 0
        
        if 'management_quality' in production_factors:
            adjustments += (production_factors['management_quality'] - 0.8) * 5
        
        predicted_rate = base_rate + adjustments
        return max(0, min(100, predicted_rate))
    
    def _calculate_prediction_confidence(self, variety_history, production_factors):
        """Calcule le niveau de confiance des prédictions"""
        confidence_score = 0.5  # Base
        
        # Plus d'historique = plus de confiance
        if variety_history.get('sample_size', 0) > 10:
            confidence_score += 0.3
        elif variety_history.get('sample_size', 0) > 5:
            confidence_score += 0.2
        
        # Données de production disponibles
        if len(production_factors) > 2:
            confidence_score += 0.2
        
        if confidence_score > 0.8:
            return 'high'
        elif confidence_score > 0.6:
            return 'medium'
        else:
            return 'low'
    
    def _get_quality_recommendations(self, predicted_germination, predicted_purity, risk_factors):
        """Génère des recommandations qualité"""
        recommendations = []
        
        if predicted_germination < 80:
            recommendations.append("Effectuer un test de germination préliminaire")
            recommendations.append("Vérifier les conditions de stockage")
        
        if predicted_purity < 95:
            recommendations.append("Contrôler rigoureusement la pureté variétale")
            recommendations.append("Vérifier l'isolation des parcelles")
        
        if 'Stress météorologique élevé' in risk_factors:
            recommendations.append("Surveiller particulièrement la qualité sanitaire")
        
        if 'Lot proche de l\'expiration' in risk_factors:
            recommendations.append("Programmer un contrôle qualité en urgence")
            recommendations.append("Envisager un traitement de conservation si nécessaire")
        
        if not recommendations:
            recommendations.append("Conditions favorables - Contrôle qualité standard recommandé")
        
        return recommendations
    
    def _get_variety_performance_on_parcel(self, variety_id, parcel_id):
        """Récupère la performance historique d'une variété sur une parcelle"""
        productions = self.env['seed.production'].search([
            ('seed_lot_id.variety_id', '=', variety_id),
            ('parcel_id', '=', parcel_id),
            ('status', '=', 'completed')
        ])
        
        if not productions:
            return None
        
        # Calculer le ratio rendement réel / rendement potentiel
        variety = self.env['seed.variety'].browse(variety_id)
        if variety.yield_potential:
            avg_efficiency = statistics.mean([
                p.yield_per_hectare / variety.yield_potential 
                for p in productions 
                if p.yield_per_hectare and variety.yield_potential
            ])
            return avg_efficiency
        
        return None
    
    def _summarize_weather_for_production(self, production):
        """Résume les conditions météo d'une production"""
        weather_data = self.env['seed.weather.data'].search([
            ('production_id', '=', production.id)
        ])
        
        if not weather_data:
            return {}
        
        return {
            'avg_temperature': statistics.mean(weather_data.mapped('temperature_avg')),
            'total_rainfall': sum(weather_data.mapped('rainfall')),
            'avg_humidity': statistics.mean(weather_data.mapped('humidity')),
            'stress_days': len(weather_data.filtered(lambda w: w.temperature_max > 35 or w.rainfall > 50))
        }
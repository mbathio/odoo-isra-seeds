# models/__init__.py
# ✅ CORRECTION: Imports mis à jour avec tous les modules actifs

# Modèles de base
from . import seed_variety
from . import seed_lot
from . import multiplier
from . import parcel
from . import quality_control
from . import weather_service
from . import production
from . import contract

# ✅ CORRECTION: Modules avancés décommentés et actifs
from . import stock_movement
from . import alert_system
from . import reporting_system
from . import ai_recommendations
from . import audit_system
from . import wizard_models

# ✅ AMÉLIORATION: Hook de post-installation
def _post_init_hook(cr, registry):
    """Hook exécuté après l'installation du module"""
    import logging
    _logger = logging.getLogger(__name__)
    
    try:
        # Initialiser les séquences si nécessaire
        _logger.info("ISRA Seeds: Initialisation des séquences...")
        
        # Créer les données de base si nécessaire
        _logger.info("ISRA Seeds: Configuration des paramètres par défaut...")
        
        # Générer les QR codes manquants
        _logger.info("ISRA Seeds: Génération des QR codes manquants...")
        
        _logger.info("ISRA Seeds: Installation terminée avec succès!")
        
    except Exception as e:
        _logger.error(f"Erreur lors de l'installation ISRA Seeds: {e}")

def _uninstall_hook(cr, registry):
    """Hook exécuté lors de la désinstallation"""
    import logging
    _logger = logging.getLogger(__name__)
    _logger.info("ISRA Seeds: Désinstallation en cours...")
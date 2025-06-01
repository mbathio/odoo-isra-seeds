# __manifest__.py - C'est comme package.json pour Node.js
{
    'name': 'ISRA - Traçabilité des Semences',
    'version': '17.0.1.0.0',
    'category': 'Agriculture',
    'summary': 'Système de traçabilité des semences pour ISRA Saint-Louis',
    'description': """
        Système complet de gestion et traçabilité des semences :
        - Gestion des variétés de semences
        - Suivi des lots de semences (GO, G1, G2, R1, R2)
        - Gestion des multiplicateurs
        - Contrôles qualité
        - Génération de QR codes
        - Rapports de production
    """,
    'author': 'ISRA Saint-Louis',
    'website': 'https://www.isra.sn',
    'license': 'LGPL-3',
    'depends': [
        'base',          # Module de base Odoo
        'mail',          # Pour les notifications
        'web',           # Interface web
        'portal',        # Pour l'accès externe
    ],
    'data': [
        # Sécurité (IMPORTANT: toujours en premier)
        'security/security.xml',
        'security/ir.model.access.csv',
        
        # Données de base
        'data/variety_data.xml',
        
        # Vues (interface utilisateur)
        'views/variety_views.xml',
        'views/seed_lot_views.xml',
        'views/multiplier_views.xml',
        'views/quality_control_views.xml',
        'views/menu_views.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',  # ← Ajouter cette ligne
        'data/variety_data.xml',
    ],
    'demo': [
        # Données de démonstration (optionnel)
        'data/demo_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,  # Module principal (apparaît dans le menu Apps)
}
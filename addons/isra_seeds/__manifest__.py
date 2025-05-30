# -*- coding: utf-8 -*-
{
    'name': 'ISRA - Traçabilité des Semences',
    'version': '16.0.2.0.0',
    'summary': 'Système de traçabilité des semences pour l\'ISRA Saint-Louis',
    'description': """
        Système complet de traçabilité des semences permettant de gérer :
        * Les variétés de semences
        * Les lots de semences avec généalogie
        * Les multiplicateurs et parcelles
        * Les contrôles qualité
        * Les productions et activités
        * La génération de QR codes
        * Les rapports de traçabilité
        * Système d'alertes intelligent
        * Intégration météorologique
        * Intelligence artificielle pour recommandations
        * Audit trail complet
        * API mobile et web
    """,
    'category': 'Agriculture',
    'author': 'ISRA Saint-Louis',
    'website': 'https://www.isra.sn',
    'depends': [
        'base',
        'mail',
        'web',
        'contacts',
        # Modules commentés pour éviter les dépendances manquantes
        # 'stock',
        # 'quality_control',
        # 'report_xlsx',
        # 'web_notify',  # <-- Cette ligne était problématique
    ],
    'data': [
        # Sécurité - doit être en premier
        'security/groups.xml',
        'security/ir.model.access.csv',
        
        # Données de base
        'data/sequences.xml',
        
        # Vues principales - dans l'ordre de dépendance
        'views/seed_variety_views.xml',
        'views/seed_lot_views.xml',
        'views/multiplier_views.xml',
        'views/parcel_views.xml',
        'views/quality_control_views.xml',
        'views/production_views.xml',
        
        # Vues avancées (seront ajoutées progressivement)
        # 'views/stock_views.xml',
        # 'views/alert_views.xml',
        # 'views/weather_views.xml',
        # 'views/audit_views.xml',
        # 'views/wizard_views.xml',
        # 'views/mobile_views.xml',
        # 'views/settings_views.xml',
        
        # Vues système
        'views/dashboard_views.xml',
        'views/report_views.xml',
        'views/menus.xml',
        
        # Données de démo et emails (à la fin)
        # 'data/cron_jobs.xml',
        # 'data/email_templates.xml',
        'data/demo_data.xml',
    ],
    'demo': [
        'data/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'isra_seeds/static/src/css/isra_seeds.css',
            'isra_seeds/static/src/js/qr_code_widget.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'images': ['static/description/icon.png'],
}
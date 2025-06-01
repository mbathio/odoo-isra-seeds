
{
        'name': 'ISRA - Traçabilité des Semences',
    'version': '16.0.1.0.0',
    'summary': 'Système de traçabilité des semences pour l\'ISRA Saint-Louis',
    'description': """
        Système de traçabilité des semences permettant de gérer :
        * Les variétés de semences
        * Les lots de semences avec généalogie
        * Les multiplicateurs et parcelles
        * Les contrôles qualité
        * Les productions et activités
    """,
    'category': 'Agriculture',
    'author': 'ISRA Saint-Louis',
    'website': 'https://www.isra.sn',
    'depends': [
        'base',
        'mail',
        'web',
        'contacts',
    ],
    'external_dependencies': {
        'python': ['qrcode', 'dateutil', 'PIL'],
    },
    'data': [
        # Sécurité - doit être en premier
        'security/groups.xml',
        'security/ir.model.access.csv',
        
        # Données de base
        'data/sequences.xml',
        'data/email_templates.xml',
        'data/cron_jobs.xml',
        # Vues principales - simplifiées
        'views/seed_variety_views.xml',
        'views/seed_lot_views.xml',
        'views/multiplier_views.xml',
        'views/parcel_views.xml',
        'views/quality_control_views.xml',
        'views/production_views.xml',
        
         # Vues avancées
        'views/dashboard_views.xml',
        'views/mobile_views.xml',
        'views/report_views.xml',
        'views/settings_views.xml',
        'views/wizard_views.xml',

        # Menu
        'views/menus.xml',
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

    'init_xml': [],
    'update_xml': [], 
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3'
}
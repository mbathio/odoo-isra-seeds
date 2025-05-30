# -*- coding: utf-8 -*-
{
    'name': 'ISRA - Traçabilité des Semences',
    'version': '16.0.1.0.0',
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
    """,
    'category': 'Agriculture',
    'author': 'ISRA Saint-Louis',
    'website': 'https://www.isra.sn',
    'depends': [
        'base',
        'stock',
        'quality_control',
        'contacts',
        'mail',
        'web',
    ],
    'data': [
        # Sécurité
        'security/groups.xml',
        'security/ir.model.access.csv',
        
        # Données de base
        'data/sequences.xml',
        'data/demo_data.xml',
        
        # Vues
        'views/seed_variety_views.xml',
        'views/seed_lot_views.xml',
        'views/multiplier_views.xml',
        'views/parcel_views.xml',
        'views/quality_control_views.xml',
        'views/production_views.xml',
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
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'images': ['static/description/icon.png'],
}
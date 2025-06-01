# addons/isra_qr_integration/__manifest__.py
{
    'name': 'ISRA - Intégration QR Code',
    'version': '17.0.1.0.0',
    'category': 'Agriculture',
    'summary': 'Scanner QR Code et vérification des lots de semences',
    'description': """
        Module d'intégration QR Code pour ISRA:
        
        ✅ Scanner QR Code mobile et desktop
        ✅ Vérification en temps réel des lots
        ✅ Interface publique de vérification
        ✅ Upload d'images pour scan
        ✅ Support caméra avant/arrière
        ✅ Validation d'authenticité
        
        Compatible avec tous les navigateurs modernes.
    """,
    'author': 'ISRA Saint-Louis',
    'website': 'https://www.isra.sn',
    'license': 'LGPL-3',
    'depends': [
        'isra_seed_traceability',
        'web',
        'website',
        'portal',
    ],
    'external_dependencies': {
        'python': ['qrcode', 'pillow'],
    },
    'data': [
        # Templates et vues
        'views/qr_scanner_templates.xml',
        'views/qr_scanner_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # JavaScript pour le backend Odoo
            'isra_qr_integration/static/src/js/qr_scanner.js',
            'isra_qr_integration/static/src/css/qr_scanner.css',
        ],
        'web.assets_frontend': [
            # JavaScript pour le site public
            'isra_qr_integration/static/src/js/qr_scanner.js',
            'isra_qr_integration/static/src/css/qr_scanner.css',
            # Librairie jsQR depuis CDN
            'https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js',
        ],
        'website.assets_frontend': [
            # Styles spécifiques au site web
            'isra_qr_integration/static/src/css/qr_scanner.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
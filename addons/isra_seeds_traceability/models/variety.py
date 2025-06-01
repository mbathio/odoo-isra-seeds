# models/variety.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SeedVariety(models.Model):
    # _name = nom de la table dans PostgreSQL
    _name = 'isra.seed.variety'
    
    # _description = description pour l'interface
    _description = 'Variété de Semences'
    
    # _order = tri par défaut
    _order = 'name'
    
    # _inherit = hériter d'autres modèles (optionnel)
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # === CHAMPS DE BASE ===
    
    # Char = texte court (VARCHAR en SQL)
    name = fields.Char(
        string='Nom de la Variété',  # Label affiché
        required=True,               # Obligatoire (NOT NULL)
        tracking=True,               # Historique des modifications
        help='Nom complet de la variété (ex: Sahel 108)'
    )
    
    code = fields.Char(
        string='Code',
        required=True,
        size=10,                     # Limite de caractères
        copy=False,                  # Pas copié lors de duplication
        help='Code unique de la variété (ex: SAHEL108)'
    )
    
    # Selection = liste déroulante (ENUM en SQL)
    crop_type = fields.Selection([
        ('rice', 'Riz'),
        ('maize', 'Maïs'),
        ('peanut', 'Arachide'),
        ('sorghum', 'Sorgho'),
        ('cowpea', 'Niébé'),
        ('millet', 'Mil')
    ], string='Type de Culture', required=True)
    
    # Text = texte long (TEXT en SQL)
    description = fields.Text(
        string='Description',
        help='Description détaillée de la variété'
    )
    
    # Integer = nombre entier
    maturity_days = fields.Integer(
        string='Jours de Maturité',
        required=True,
        help='Nombre de jours de la plantation à la récolte'
    )
    
    # Float = nombre décimal
    yield_potential = fields.Float(
        string='Potentiel de Rendement (t/ha)',
        digits=(8, 2),  # 8 chiffres au total, 2 après la virgule
        help='Rendement potentiel en tonnes par hectare'
    )
    
    # Text pour stocker liste (comme JSON)
    resistances = fields.Text(
        string='Résistances',
        help='Résistances aux maladies et ravageurs'
    )
    
    origin = fields.Char(string='Origine')
    release_year = fields.Integer(string='Année de Sortie')
    
    # Boolean = case à cocher
    is_active = fields.Boolean(
        string='Actif',
        default=True,
        help='Décocher pour désactiver cette variété'
    )
    
    # === CHAMPS CALCULÉS ===
    
    # Computed = calculé automatiquement
    seed_lot_count = fields.Integer(
        string='Nombre de Lots',
        compute='_compute_seed_lot_count',
        help='Nombre total de lots de cette variété'
    )
    
    # === RELATIONS ===
    
    # One2many = relation 1 vers plusieurs (comme seedLots dans Prisma)
    seed_lot_ids = fields.One2many(
        comodel_name='isra.seed.lot',    # Modèle cible
        inverse_name='variety_id',       # Champ dans le modèle cible
        string='Lots de Semences'
    )
    
    # === CONTRAINTES ===
    
    _sql_constraints = [
        ('unique_code', 'UNIQUE(code)', 'Le code de la variété doit être unique'),
        ('positive_maturity', 'CHECK(maturity_days > 0)', 'Les jours de maturité doivent être positifs'),
    ]
    
    # === MÉTHODES ===
    
    @api.depends('seed_lot_ids')
    def _compute_seed_lot_count(self):
        """Calcule le nombre de lots pour chaque variété"""
        for variety in self:
            variety.seed_lot_count = len(variety.seed_lot_ids)
    
    @api.model
    def create(self, vals):
        """Méthode appelée à la création d'un enregistrement"""
        # Convertir le code en majuscules
        if 'code' in vals:
            vals['code'] = vals['code'].upper()
        return super().create(vals)
    
    def write(self, vals):
        """Méthode appelée lors de la modification"""
        if 'code' in vals:
            vals['code'] = vals['code'].upper()
        return super().write(vals)
    
    @api.constrains('maturity_days')
    def _check_maturity_days(self):
        """Validation personnalisée"""
        for variety in self:
            if variety.maturity_days < 30 or variety.maturity_days > 365:
                raise ValidationError("La maturité doit être entre 30 et 365 jours")
    
    def name_get(self):
        """Définit comment l'enregistrement s'affiche dans les listes"""
        result = []
        for variety in self:
            name = f"[{variety.code}] {variety.name}"
            result.append((variety.id, name))
        return result
    
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Permet de chercher par code ou nom"""
        args = args or []
        if name:
            args = ['|', ('code', operator, name), ('name', operator, name)] + args
        return super().name_search(name='', args=args, operator=operator, limit=limit)
# data/migration_script.py
"""
Script pour migrer les données de votre base PostgreSQL existante vers Odoo
À exécuter depuis le shell Odoo : odoo-bin shell -d isra_db
"""

import psycopg2
import json
from odoo import api, SUPERUSER_ID

def migrate_from_existing_database(env):
    """Migration complète depuis l'ancienne base de données"""
    
    print("🚀 Début de la migration des données...")
    
    # Connexion à l'ancienne base
    old_conn = psycopg2.connect(
        host="localhost",
        database="isra_seeds",  # Votre ancienne base
        user="user1",
        password="user1"
    )
    cursor = old_conn.cursor()
    
    # Mappings pour convertir les IDs
    variety_mapping = {}
    multiplier_mapping = {}
    parcel_mapping = {}
    user_mapping = {}
    
    try:
        # 1. Migration des utilisateurs
        print("👥 Migration des utilisateurs...")
        cursor.execute("""
            SELECT id, name, email, role, is_active, created_at
            FROM users 
            WHERE is_active = true
        """)
        users = cursor.fetchall()
        
        for user_data in users:
            # Convertir le rôle vers les énumérations Odoo
            role_mapping = {
                'ADMIN': 'ADMIN',
                'MANAGER': 'MANAGER', 
                'RESEARCHER': 'RESEARCHER',
                'TECHNICIAN': 'TECHNICIAN',
                'INSPECTOR': 'INSPECTOR',
                'MULTIPLIER': 'MULTIPLIER'
            }
            
            odoo_user = env['res.users'].create({
                'name': user_data[1],
                'login': user_data[2],
                'email': user_data[2],
                'is_active': user_data[4],
                'groups_id': [(4, env.ref(f'isra_seed_traceability.group_isra_{role_mapping[user_data[3]].lower()}').id)]
            })
            user_mapping[user_data[0]] = odoo_user.id
            print(f"   ✓ Utilisateur {user_data[1]} migré")
        
        # 2. Migration des variétés
        print("🌱 Migration des variétés...")
        cursor.execute("""
            SELECT id, code, name, crop_type, description, maturity_days, 
                   yield_potential, resistances, origin, release_year, is_active
            FROM varieties 
            WHERE is_active = true
        """)
        varieties = cursor.fetchall()
        
        for variety_data in varieties:
            # Convertir le type de culture
            crop_type_mapping = {
                'RICE': 'rice',
                'MAIZE': 'maize', 
                'PEANUT': 'peanut',
                'SORGHUM': 'sorghum',
                'COWPEA': 'cowpea',
                'MILLET': 'millet'
            }
            
            variety = env['isra.seed.variety'].create({
                'code': variety_data[1],
                'name': variety_data[2],
                'crop_type': crop_type_mapping.get(variety_data[3], 'rice'),
                'description': variety_data[4],
                'maturity_days': variety_data[5],
                'yield_potential': variety_data[6],
                'resistances': variety_data[7] or '',
                'origin': variety_data[8],
                'release_year': variety_data[9],
                'is_active': variety_data[10]
            })
            variety_mapping[variety_data[0]] = variety.id
            print(f"   ✓ Variété {variety_data[2]} migrée")
        
        # 3. Migration des multiplicateurs
        print("👨‍🌾 Migration des multiplicateurs...")
        cursor.execute("""
            SELECT id, name, status, address, latitude, longitude, 
                   years_experience, certification_level, specialization, 
                   phone, email, is_active
            FROM multipliers 
            WHERE is_active = true
        """)
        multipliers = cursor.fetchall()
        
        for mult_data in multipliers:
            # Convertir le statut et niveau de certification
            status_mapping = {'ACTIVE': 'active', 'INACTIVE': 'inactive'}
            cert_mapping = {
                'BEGINNER': 'beginner',
                'INTERMEDIATE': 'intermediate', 
                'EXPERT': 'expert'
            }
            
            multiplier = env['isra.multiplier'].create({
                'name': mult_data[1],
                'status': status_mapping.get(mult_data[2], 'active'),
                'address': mult_data[3],
                'latitude': mult_data[4],
                'longitude': mult_data[5],
                'years_experience': mult_data[6],
                'certification_level': cert_mapping.get(mult_data[7], 'beginner'),
                'phone': mult_data[9],
                'email': mult_data[10],
                'is_active': mult_data[11]
            })
            multiplier_mapping[mult_data[0]] = multiplier.id
            print(f"   ✓ Multiplicateur {mult_data[1]} migré")
        
        # 4. Migration des parcelles
        print("🏞️ Migration des parcelles...")
        cursor.execute("""
            SELECT id, name, area, latitude, longitude, status, 
                   soil_type, irrigation_system, address, multiplier_id, is_active
            FROM parcels 
            WHERE is_active = true
        """)
        parcels = cursor.fetchall()
        
        for parcel_data in parcels:
            status_mapping = {
                'AVAILABLE': 'available',
                'IN_USE': 'in_use', 
                'RESTING': 'resting'
            }
            
            parcel = env['isra.parcel'].create({
                'name': parcel_data[1],
                'area': parcel_data[2],
                'latitude': parcel_data[3],
                'longitude': parcel_data[4],
                'status': status_mapping.get(parcel_data[5], 'available'),
                'soil_type': parcel_data[6],
                'irrigation_system': parcel_data[7],
                'address': parcel_data[8],
                'multiplier_id': multiplier_mapping.get(parcel_data[9]),
                'is_active': parcel_data[10]
            })
            parcel_mapping[parcel_data[0]] = parcel.id
            print(f"   ✓ Parcelle {parcel_data[1]} migrée")
        
        # 5. Migration des lots de semences
        print("📦 Migration des lots de semences...")
        cursor.execute("""
            SELECT id, variety_id, level, quantity, production_date, 
                   expiry_date, multiplier_id, parcel_id, status, 
                   batch_number, parent_lot_id, notes, qr_code, is_active
            FROM seed_lots 
            WHERE is_active = true
            ORDER BY production_date
        """)
        seed_lots = cursor.fetchall()
        
        lot_mapping = {}
        for lot_data in seed_lots:
            # Convertir le statut et niveau
            status_mapping = {
                'PENDING': 'pending',
                'CERTIFIED': 'certified',
                'REJECTED': 'rejected',
                'IN_STOCK': 'in_stock',
                'SOLD': 'distributed',
                'ACTIVE': 'certified',
                'DISTRIBUTED': 'distributed'
            }
            
            # Créer le lot
            lot = env['isra.seed.lot'].create({
                'name': lot_data[0],  # Garder l'ID original comme nom
                'variety_id': variety_mapping.get(lot_data[1]),
                'level': lot_data[2],
                'quantity': lot_data[3],
                'production_date': lot_data[4],
                'expiry_date': lot_data[5],
                'multiplier_id': multiplier_mapping.get(lot_data[6]),
                'parcel_id': parcel_mapping.get(lot_data[7]),
                'status': status_mapping.get(lot_data[8], 'pending'),
                'batch_number': lot_data[9],
                'parent_lot_id': lot_mapping.get(lot_data[10]),  # Sera mis à jour plus tard
                'notes': lot_data[11],
                'is_active': lot_data[13]
            })
            lot_mapping[lot_data[0]] = lot.id
            print(f"   ✓ Lot {lot_data[0]} migré")
        
        # Mettre à jour les relations parent/enfant
        print("🔗 Mise à jour des relations parent/enfant...")
        cursor.execute("""
            SELECT id, parent_lot_id 
            FROM seed_lots 
            WHERE parent_lot_id IS NOT NULL AND is_active = true
        """)
        parent_relations = cursor.fetchall()
        
        for rel in parent_relations:
            child_lot = env['isra.seed.lot'].browse(lot_mapping.get(rel[0]))
            parent_lot_id = lot_mapping.get(rel[1])
            if child_lot and parent_lot_id:
                child_lot.parent_lot_id = parent_lot_id
        
        # 6. Migration des contrôles qualité
        print("🔬 Migration des contrôles qualité...")
        cursor.execute("""
            SELECT id, lot_id, control_date, germination_rate, variety_purity,
                   moisture_content, seed_health, result, observations, 
                   inspector_id, test_method, laboratory_ref
            FROM quality_controls
        """)
        quality_controls = cursor.fetchall()
        
        for qc_data in quality_controls:
            result_mapping = {'PASS': 'pass', 'FAIL': 'fail'}
            
            env['isra.quality.control'].create({
                'lot_id': lot_mapping.get(qc_data[1]),
                'control_date': qc_data[2],
                'germination_rate': qc_data[3],
                'variety_purity': qc_data[4],
                'moisture_content': qc_data[5],
                'seed_health': qc_data[6],
                'result': result_mapping.get(qc_data[7], 'fail'),
                'observations': qc_data[8],
                'inspector_id': user_mapping.get(qc_data[9]),
                'test_method': qc_data[10],
                'laboratory_ref': qc_data[11]
            })
            print(f"   ✓ Contrôle qualité du {qc_data[2]} migré")
        
        # 7. Migration des productions
        print("🚜 Migration des productions...")
        cursor.execute("""
            SELECT id, lot_id, start_date, end_date, sowing_date, harvest_date,
                   yield, conditions, multiplier_id, parcel_id, status,
                   planned_quantity, actual_yield, notes, weather_conditions
            FROM productions
        """)
        productions = cursor.fetchall()
        
        for prod_data in productions:
            status_mapping = {
                'PLANNED': 'planned',
                'IN_PROGRESS': 'in_progress',
                'COMPLETED': 'completed',
                'CANCELLED': 'cancelled'
            }
            
            production = env['isra.production'].create({
                'lot_id': lot_mapping.get(prod_data[1]),
                'start_date': prod_data[2],
                'end_date': prod_data[3],
                'sowing_date': prod_data[4],
                'harvest_date': prod_data[5],
                'multiplier_id': multiplier_mapping.get(prod_data[8]),
                'parcel_id': parcel_mapping.get(prod_data[9]),
                'status': status_mapping.get(prod_data[10], 'planned'),
                'planned_quantity': prod_data[11],
                'actual_yield': prod_data[12],
                'notes': prod_data[13],
                'weather_conditions': prod_data[14]
            })
            print(f"   ✓ Production {prod_data[0]} migrée")
        
        print("✅ Migration terminée avec succès!")
        print(f"   👥 {len(users)} utilisateurs")
        print(f"   🌱 {len(varieties)} variétés") 
        print(f"   👨‍🌾 {len(multipliers)} multiplicateurs")
        print(f"   🏞️ {len(parcels)} parcelles")
        print(f"   📦 {len(seed_lots)} lots de semences")
        print(f"   🔬 {len(quality_controls)} contrôles qualité")
        print(f"   🚜 {len(productions)} productions")
        
    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        raise
    finally:
        cursor.close()
        old_conn.close()

# Pour exécuter la migration :
# Dans le shell Odoo: migrate_from_existing_database(env)
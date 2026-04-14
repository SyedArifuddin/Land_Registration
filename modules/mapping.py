from psycopg2.extras import RealDictCursor
from flask import Blueprint, render_template, session, redirect, url_for
from auth import db_config, connect_db
from blockchain_config import land_chain

mapping_bp = Blueprint('mapping', __name__)

def sync_vault_to_blockchain():
    """Syncs deeds from DB to Blockchain so the GIS feed has live data."""
    try:
        conn = connect_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        # Fetch all records to populate the map
        cursor.execute("SELECT * FROM land_records")
        all_deeds = cursor.fetchall()
        conn.close()

        for deed in all_deeds:
            # Avoid duplicates in the blockchain memory
            exists = any(str(block.get('data', {}).get('land_id')) == str(deed['survey_no']) 
                        for block in land_chain.chain)
            
            if not exists:
                blockchain_payload = {
                    'land_id': str(deed['survey_no']),
                    'owner': deed.get('pattadar') or deed.get('owner_name', 'N/A'),
                    'area': deed.get('extent') or deed.get('area_sqft', '0'),
                    'officer': deed.get('officer') or deed.get('pattadar'),
                    'district': deed.get('location') or deed.get('district', 'N/A'),
                    'coordinates': deed.get('coordinates', '')
                }
                land_chain.add_block(blockchain_payload)
    except Exception as e:
        print(f"GIS Sync Error: {e}")

@mapping_bp.route('/features/mapping')
def index():
    if 'user' not in session: 
        return redirect(url_for('login_gate'))
    
    # Force a sync so the 'Live' feed isn't empty
    sync_vault_to_blockchain()
    
    current_user = session.get('user')
    return render_template('features/mapping.html', 
                           chain=land_chain.chain, 
                           user=current_user)
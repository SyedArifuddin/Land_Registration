from flask import Blueprint, render_template, session, redirect, url_for
import mysql.connector
from auth import db_config
from blockchain_config import land_chain

mapping_bp = Blueprint('mapping', __name__)

def sync_vault_to_blockchain():
    """Syncs deeds from DB to Blockchain so the GIS feed has live data."""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
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
                    'owner': deed['pattadar'],
                    'area': deed['extent'],
                    'officer': deed['officer'],
                    'district': deed['district'],
                    'coordinates': deed.get('coordinates') # Format: "17.38, 78.48"
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
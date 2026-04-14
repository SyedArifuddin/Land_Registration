from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import mysql.connector
import hashlib
import json
from auth import db_config
from blockchain_config import land_chain

inscription_bp = Blueprint('inscription', __name__)

@inscription_bp.route('/', methods=['GET', 'POST'])
def index():
    if 'user' not in session:
        return redirect(url_for('login_gate'))

    if request.method == 'POST':
        pattadar  = request.form.get('pattadar', '').strip()
        survey_no = request.form.get('survey_no', '').strip()
        extent    = request.form.get('extent', '').strip()
        district  = request.form.get('district', '').strip()
        coords    = request.form.get('coords', '').strip()
        officer   = session.get('user')

        if not pattadar or not survey_no or not coords:
            flash("CRITICAL: Pattadar name, survey number and coordinates are mandatory.")
            return redirect(url_for('inscription.index'))

        # Generate block hash
        prop_hash = hashlib.sha256(
            json.dumps({
                'owner':    pattadar,
                'survey':   survey_no,
                'district': district
            }, sort_keys=True).encode()
        ).hexdigest()

        # 1. Add to Blockchain
        land_chain.add_block({
            'owner':       pattadar,
            'land_id':     survey_no,
            'area':        extent,
            'district':    district,
            'coordinates': coords,
            'officer':     officer,
            'entry_type':  'INSCRIPTION'
        })

        # 2. Save to MySQL using actual land_records column names
        try:
            conn   = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO land_records
                    (pattadar, survey_no, extent, location, land_category, block_hash)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                pattadar,
                survey_no,
                extent or 0,
                district,
                'General',
                prop_hash
            ))
            conn.commit()
            conn.close()
            flash(f"SUCCESS: Survey {survey_no} inscribed on the Sovereign Ledger.")
        except Exception as e:
            flash(f"DB Error: {str(e)}")
            return redirect(url_for('inscription.index'))

        return redirect(url_for('inscription.index'))

    return render_template('features/inscription.html', user=session.get('user'))
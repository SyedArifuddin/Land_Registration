from flask import Blueprint, render_template, session, redirect, url_for, flash, make_response, request
import mysql.connector
from auth import db_config
from blockchain_config import land_chain
from fpdf import FPDF

vault_bp = Blueprint('vault', __name__)

@vault_bp.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login_gate'))

    current_user = session.get('user')
    search_query = request.args.get('search', '').strip()
    final_deeds  = []

    try:
        conn   = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Query using ACTUAL column names — no officer filter since column doesn't exist
        if search_query:
            cursor.execute("""
                SELECT * FROM land_records
                WHERE survey_no LIKE %s OR owner_name LIKE %s
                ORDER BY id DESC
            """, (f"%{search_query}%", f"%{search_query}%"))
        else:
            cursor.execute("SELECT * FROM land_records ORDER BY id DESC")

        db_records = cursor.fetchall()
        conn.close()

        for rec in db_records:
            # Find matching blockchain block for this record
            block_hash = rec.get('property_hash', 'DB_STORED')
            for block in land_chain.chain:
                data = block.get('data', {})
                if (str(data.get('land_id', '')) == str(rec.get('survey_no', '')) or
                    str(data.get('survey',  '')) == str(rec.get('survey_no', ''))):
                    block_hash = block.get('hash', block_hash)
                    break

            final_deeds.append({
                'survey_id':  rec.get('survey_no',    'N/A'),
                'owner':      rec.get('owner_name',   'N/A'),
                'district':   rec.get('location_name','N/A'),
                'area':       rec.get('area_sqft',    '0'),
                'category':   rec.get('land_category','General'),
                'status':     'VERIFIED',
                'block_hash': block_hash or 'PENDING',
                'cert_type':  'PATTADAR PASSBOOK',
                'db_id':      rec.get('id', '')
            })

    except Exception as e:
        flash(f"Vault Error: {e}")
        print(f"Vault Error: {e}")

    return render_template('features/vault.html', deeds=final_deeds, user=current_user)


@vault_bp.route('/view/<survey_id>')
def view_deed(survey_id):
    if 'user' not in session:
        return redirect(url_for('login_gate'))

    deed  = None
    proof = None
    try:
        conn   = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM land_records WHERE survey_no=%s", (survey_id,))
        deed = cursor.fetchone()
        conn.close()
    except Exception as e:
        flash(f"DB Error: {e}")
        return redirect(url_for('vault.index'))

    # Find blockchain proof
    for block in land_chain.chain:
        data = block.get('data', {})
        if (str(data.get('land_id', '')) == str(survey_id) or
            str(data.get('survey',  '')) == str(survey_id)):
            proof = block
            break

    return render_template('features/view_deed.html', deed=deed, proof=proof, user=session.get('user'))


@vault_bp.route('/export/<survey_id>')
def generate_pdf(survey_id):
    if 'user' not in session:
        return redirect(url_for('login_gate'))

    deed = None
    try:
        conn   = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM land_records WHERE survey_no=%s", (survey_id,))
        deed = cursor.fetchone()
        conn.close()
    except Exception as e:
        return f"Database Error: {e}"

    if not deed:
        return "Record not found", 404

    # Find block hash
    block_hash = deed.get('property_hash', 'N/A')
    for block in land_chain.chain:
        data = block.get('data', {})
        if str(data.get('land_id', '')) == str(survey_id):
            block_hash = block.get('hash', block_hash)
            break

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "SOVEREIGN LEDGER - LAND REGISTRY CERTIFICATE", ln=True, align='C')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Government of Telangana", ln=True, align='C')
    pdf.ln(8)
    pdf.set_draw_color(184, 134, 11)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(8)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 8, f"Survey No.     : {deed.get('survey_no',    'N/A')}", ln=True)
    pdf.cell(0, 8, f"Pattadar Name  : {deed.get('owner_name',   'N/A')}", ln=True)
    pdf.cell(0, 8, f"District       : {deed.get('location_name','N/A')}", ln=True)
    pdf.cell(0, 8, f"Area (sq.ft)   : {deed.get('area_sqft',    '0')}", ln=True)
    pdf.cell(0, 8, f"Land Category  : {deed.get('land_category','General')}", ln=True)
    pdf.ln(6)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, "Blockchain Proof Hash:", ln=True)
    pdf.set_font("Arial", '', 9)
    pdf.multi_cell(0, 6, str(block_hash))
    pdf.ln(6)
    pdf.set_font("Arial", 'I', 9)
    pdf.cell(0, 8, "This certificate is cryptographically secured on the Sovereign Ledger blockchain.", ln=True)

    response = make_response(pdf.output(dest='S').encode('latin-1'))
    response.headers.set('Content-Disposition', 'attachment', filename=f'Deed_{survey_id}.pdf')
    response.headers.set('Content-Type', 'application/pdf')
    return response


@vault_bp.route('/export-all')
def export_full_registry():
    if 'user' not in session:
        return redirect(url_for('login_gate'))

    search_query = request.args.get('search', '').strip()
    records = []
    try:
        conn   = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        if search_query:
            cursor.execute("""
                SELECT * FROM land_records
                WHERE survey_no LIKE %s OR owner_name LIKE %s
                ORDER BY id ASC
            """, (f"%{search_query}%", f"%{search_query}%"))
        else:
            cursor.execute("SELECT * FROM land_records ORDER BY id ASC")
        records = cursor.fetchall()
        conn.close()
    except Exception as e:
        return f"Export Error: {e}"

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "SOVEREIGN LEDGER - OFFICIAL LAND REGISTRY", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 8, "Government of Telangana - All Registered Parcels", ln=True, align='C')
    pdf.ln(6)

    # Header row
    pdf.set_fill_color(26, 35, 50)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(20, 8, "Sr.", border=1, fill=True)
    pdf.cell(35, 8, "Survey No.", border=1, fill=True)
    pdf.cell(55, 8, "Owner Name", border=1, fill=True)
    pdf.cell(45, 8, "District", border=1, fill=True)
    pdf.cell(35, 8, "Area (sq.ft)", border=1, ln=True, fill=True)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 9)
    for i, row in enumerate(records, 1):
        fill = i % 2 == 0
        pdf.set_fill_color(245, 245, 245)
        pdf.cell(20, 7, str(i),                              border=1, fill=fill)
        pdf.cell(35, 7, str(row.get('survey_no',    '')),   border=1, fill=fill)
        pdf.cell(55, 7, str(row.get('owner_name',   ''))[:25], border=1, fill=fill)
        pdf.cell(45, 7, str(row.get('location_name',''))[:20], border=1, fill=fill)
        pdf.cell(35, 7, str(row.get('area_sqft',    '')),   border=1, ln=True, fill=fill)

    response = make_response(pdf.output(dest='S').encode('latin-1'))
    response.headers.set('Content-Disposition', 'attachment', filename='Full_Registry.pdf')
    response.headers.set('Content-Type', 'application/pdf')
    return response
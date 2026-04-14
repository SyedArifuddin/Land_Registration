from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
import mysql.connector
from auth import db_config
from blockchain_config import land_chain
import datetime
import hashlib
import json

citizen_bp = Blueprint('citizen', __name__, url_prefix='/citizen')

def log_telemetry(event, detail):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO network_telemetry (event_type, data_value) VALUES (%s,%s)", (event, detail))
        conn.commit(); conn.close()
    except: pass

def notify(recipient, role, message):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO notifications (recipient,role,message) VALUES (%s,%s,%s)", (recipient,role,message))
        conn.commit(); conn.close()
    except: pass

def ensure_tables():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY, recipient VARCHAR(255),
            role VARCHAR(50), message TEXT, is_read TINYINT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS admin_messages (
            id INT AUTO_INCREMENT PRIMARY KEY, request_id INT,
            from_admin VARCHAR(255), to_citizen VARCHAR(255),
            message TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit(); conn.close()
    except Exception as e:
        print(f"Table Error: {e}")

ensure_tables()

# ─── AUTH ──────────────────────────────────────────────────────

@citizen_bp.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s AND role='citizen'", (username,password))
        user = cursor.fetchone(); conn.close()
        if user:
            session['user'] = user['username']
            session['role'] = 'citizen'
            log_telemetry("CITIZEN_LOGIN", f"{username} authenticated.")
            return redirect(url_for('citizen.dashboard'))
        flash("Invalid credentials.")
    return render_template('citizen_login.html')

@citizen_bp.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username,password,role) VALUES (%s,%s,'citizen')", (username,password))
            conn.commit(); conn.close()
            flash("Account created! Please Sign In.")
            return redirect(url_for('citizen.login'))
        except: flash("Username already exists.")
    return render_template('citizen_signup.html')

# ─── DASHBOARD ─────────────────────────────────────────────────

@citizen_bp.route('/dashboard')
def dashboard():
    if 'user' not in session or session.get('role') != 'citizen':
        return redirect(url_for('citizen.login'))
    username = session.get('user')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as cnt FROM notifications WHERE recipient=%s AND is_read=0", (username,))
    notif_count = cursor.fetchone()['cnt']
    cursor.execute("SELECT COUNT(*) as cnt FROM land_records WHERE pattadar=%s", (username,))
    my_property_count = cursor.fetchone()['cnt']
    conn.close()
    stats = {
        'height': len(land_chain.chain),
        'status': "VERIFIED",
        'hash':   land_chain.chain[-1]['hash'][:24] if land_chain.chain else "SYNCING",
        'shards': 3
    }
    return render_template('citizen_overview.html',
        user=username, stats=stats,
        notif_count=notif_count,
        my_property_count=my_property_count,
        global_activity=land_chain.chain[::-1])

# ─── MY PROPERTIES ─────────────────────────────────────────────

@citizen_bp.route('/my_properties')
def my_properties():
    if 'user' not in session or session.get('role') != 'citizen':
        return redirect(url_for('citizen.login'))
    assets = []
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM land_records WHERE pattadar=%s", (session.get('user'),))
        assets = cursor.fetchall(); conn.close()
    except Exception as e: print(f"Error: {e}")
    return render_template('citizen_properties.html', user=session.get('user'), assets=assets)

# ─── AUDIT / TRANSFER REQUESTS ─────────────────────────────────

@citizen_bp.route('/audit_trail')
def audit_trail():
    if 'user' not in session or session.get('role') != 'citizen':
        return redirect(url_for('citizen.login'))
    username = session.get('user')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username FROM users WHERE role='admin'")
    admins = cursor.fetchall()
    cursor.execute("SELECT * FROM land_records WHERE pattadar=%s", (username,))
    history = cursor.fetchall()
    cursor.execute('''SELECT tr.*, u.username as admin_name
        FROM transfer_requests tr
        LEFT JOIN users u ON tr.assigned_admin_id=u.id
        WHERE tr.sender=%s ORDER BY tr.id DESC''', (username,))
    my_requests = cursor.fetchall()
    for req in my_requests:
        cursor.execute("SELECT * FROM admin_messages WHERE request_id=%s ORDER BY created_at ASC", (req['id'],))
        req['messages'] = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) as cnt FROM notifications WHERE recipient=%s AND is_read=0", (username,))
    notif_count = cursor.fetchone()['cnt']
    conn.close()
    return render_template('citizen_audit.html',
        user=username, administrators=admins,
        history=history, my_requests=my_requests,
        notif_count=notif_count)

# ─── FORENSIC VERIFY ───────────────────────────────────────────

@citizen_bp.route('/forensic_verify')
def forensic_verify():
    if 'user' not in session or session.get('role') != 'citizen':
        return redirect(url_for('citizen.login'))
    query = request.args.get('query','').strip()
    result = None
    status = "AWAITING_INPUT"
    if query:
        for block in land_chain.chain:
            txs = block.get('transactions', [])
            tx  = txs[0] if txs else {}
            if str(tx.get('land_id','')) == query or str(tx.get('survey','')) == query or block.get('hash','') == query:
                result = block; status = "VALIDATED"; break
        if not result: status = "NOT_FOUND"
    total_acres = sum(float(b.get('transactions',[{}])[0].get('extent',0) or 0) for b in land_chain.chain if b.get('transactions'))
    telemetry = {'verified_acres': f"{total_acres:.2f}", 'active_shards': len(land_chain.chain)}
    return render_template('citizen_forensic.html',
        user=session.get('user'), query=query,
        result=result, status=status,
        telemetry=telemetry, chain=land_chain.chain)

# ─── DISPUTE FILING ────────────────────────────────────────────

@citizen_bp.route('/dispute_filing')
def dispute_filing():
    if 'user' not in session or session.get('role') != 'citizen':
        return redirect(url_for('citizen.login'))
    username = session.get('user')
    disputes = []
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM disputes WHERE claimant_a=%s ORDER BY id DESC", (username,))
        disputes = cursor.fetchall(); conn.close()
    except Exception as e: print(f"Error: {e}")
    return render_template('citizen_dispute.html', user=username, disputes=disputes)

@citizen_bp.route('/file_dispute', methods=['POST'])
def file_dispute():
    if 'user' not in session or session.get('role') != 'citizen':
        return jsonify({'status':'error','message':'Unauthorized'}), 401
    survey  = request.form.get('survey_no','').strip()
    party_b = request.form.get('party_b','').strip()
    reason  = request.form.get('reason','').strip()
    claimant_a = session.get('user')
    if not survey or not party_b or not reason:
        return jsonify({'status':'error','message':'All fields required.'}), 400
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO disputes (survey_no, claimant_a, claimant_b, reason, status) VALUES (%s,%s,%s,%s,'HEARING')",
                       (survey, claimant_a, party_b, reason))
        conn.commit(); conn.close()
        return jsonify({'status':'success','message':'Dispute filed successfully. Admin will review shortly.'})
    except Exception as e:
        return jsonify({'status':'error','message':str(e)}), 500

# ─── MARKET LISTINGS ───────────────────────────────────────────

@citizen_bp.route('/market_listings')
def market_listings():
    if 'user' not in session or session.get('role') != 'citizen':
        return redirect(url_for('citizen.login'))
    all_properties = []
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM land_records ORDER BY id DESC")
        all_properties = cursor.fetchall(); conn.close()
    except Exception as e: print(f"Error: {e}")
    return render_template('citizen_market.html', user=session.get('user'), all_properties=all_properties)

# ─── TAXATION ──────────────────────────────────────────────────

@citizen_bp.route('/taxation')
def taxation():
    if 'user' not in session or session.get('role') != 'citizen':
        return redirect(url_for('citizen.login'))
    assets = []
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM land_records WHERE pattadar=%s", (session.get('user'),))
        assets = cursor.fetchall(); conn.close()
    except Exception as e: print(f"Error: {e}")
    return render_template('citizen_taxation.html', user=session.get('user'), assets=assets)

# ─── REQUEST TRANSFER ──────────────────────────────────────────

@citizen_bp.route('/request_transfer', methods=['POST'])
def request_transfer():
    if 'user' not in session or session.get('role') != 'citizen':
        return jsonify({'status':'error','message':'Unauthorized'}), 401
    prop_input = request.form.get('property_id','').strip()
    receiver   = request.form.get('receiver_name','').strip()
    admin_id   = request.form.get('admin_id','').strip()
    sender     = session.get('user')
    if not prop_input or not receiver or not admin_id:
        return jsonify({'status':'error','message':'All fields required.'}), 400
    try:
        conn   = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Accept either DB id or survey_no
        cursor.execute(
            "SELECT id, survey_no FROM land_records WHERE id=%s OR survey_no=%s",
            (prop_input, prop_input)
        )
        land_rec = cursor.fetchone()
        if not land_rec:
            conn.close()
            return jsonify({'status':'error','message':f'Property "{prop_input}" not found. Enter the Property ID or Survey Number.'}), 404

        actual_id = land_rec['id']
        survey_no = land_rec['survey_no']

        # Get admin name
        cursor.execute("SELECT username FROM users WHERE id=%s", (admin_id,))
        row        = cursor.fetchone()
        admin_name = row['username'] if row else f"Admin #{admin_id}"

        # Check duplicate pending
        cursor.execute(
            "SELECT id FROM transfer_requests WHERE property_id=%s AND sender=%s AND status='Pending'",
            (actual_id, sender)
        )
        if cursor.fetchone():
            conn.close()
            return jsonify({'status':'error','message':'A pending request already exists for this property.'}), 400

        cursor.execute(
            "INSERT INTO transfer_requests (property_id,sender,receiver,assigned_admin_id,status) VALUES (%s,%s,%s,%s,'Pending')",
            (actual_id, sender, receiver, admin_id)
        )
        conn.commit()
        conn.close()
        notify(admin_name,'admin',
               f"New transfer request from <strong>{sender}</strong> "
               f"for Survey No. <strong>{survey_no}</strong> to <strong>{receiver}</strong>.")
        log_telemetry("HANDSHAKE", f"{sender}->Survey {survey_no}->{receiver} via {admin_name}")
        return jsonify({'status':'success',
                        'message':f'Request sent to {admin_name}. Track status in Transfer Requests.'})
    except Exception as e:
        return jsonify({'status':'error','message':str(e)}), 500

# ─── NOTIFICATIONS ─────────────────────────────────────────────

@citizen_bp.route('/notifications')
def notifications():
    if 'user' not in session or session.get('role') != 'citizen':
        return jsonify({'status':'error'}), 401
    username = session.get('user')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM notifications WHERE recipient=%s ORDER BY created_at DESC LIMIT 20", (username,))
    notifs = cursor.fetchall()
    cursor.execute("UPDATE notifications SET is_read=1 WHERE recipient=%s", (username,))
    conn.commit(); conn.close()
    for n in notifs: n['created_at'] = str(n['created_at'])
    return jsonify({'status':'ok','notifications':notifs})

# ─── REGISTER PROPERTY ─────────────────────────────────────────

@citizen_bp.route('/register_property', methods=['POST'])
def register_property():
    if 'user' not in session or session.get('role') != 'citizen':
        return jsonify({'status':'error','message':'Unauthorized'}), 401
    location = request.form.get('location')
    survey   = request.form.get('survey_no')
    area     = request.form.get('area')
    category = request.form.get('category')
    zoning   = request.form.get('zoning')
    owner    = session.get('user')
    if not location or not survey or not area:
        return jsonify({'status':'error','message':'Missing required fields.'}), 400
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        prop_hash = hashlib.sha256(json.dumps({'owner':owner,'survey':survey,'location':location}).encode()).hexdigest()
        cursor.execute("INSERT INTO land_records (pattadar, location, survey_no, extent, land_category) VALUES (%s,%s,%s,%s,%s)",
                       (owner, location, survey, area, category))
        conn.commit(); conn.close()
        land_chain.add_block({'type':'INSCRIPTION','owner':owner,'survey':survey,'location':location})
        return jsonify({'status':'success','message':'Property registered successfully.'})
    except Exception as e:
        return jsonify({'status':'error','message':str(e)}), 500

# ─── TRANSFER HISTORY ──────────────────────────────────────────

@citizen_bp.route('/transfer_history')
def transfer_history():
    if 'user' not in session or session.get('role') != 'citizen':
        return redirect(url_for('citizen.login'))
    username = session.get('user')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    # All transfers where citizen is sender OR receiver
    cursor.execute('''
        SELECT tr.*, u.username as admin_name
        FROM transfer_requests tr
        LEFT JOIN users u ON tr.assigned_admin_id = u.id
        WHERE tr.sender = %s OR tr.receiver = %s
        ORDER BY tr.id DESC
    ''', (username, username))
    all_transfers = cursor.fetchall()

    approved_count = sum(1 for t in all_transfers if t['status'] == 'Approved')
    rejected_count = sum(1 for t in all_transfers if t['status'] == 'Rejected')
    pending_count  = sum(1 for t in all_transfers if t['status'] == 'Pending')

    conn.close()
    return render_template('citizen_transfer_history.html',
        user=username,
        all_transfers=all_transfers,
        approved_count=approved_count,
        rejected_count=rejected_count,
        pending_count=pending_count)
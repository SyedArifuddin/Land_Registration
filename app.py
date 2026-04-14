from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from auth import init_db, db_config, is_device_registered, connect_db
from blockchain_config import land_chain
import socket
import datetime
import random
from psycopg2.extras import RealDictCursor

# --- IMPORT BLUEPRINTS ---
from modules.inscription import inscription_bp
from modules.mapping import mapping_bp
from modules.tribunal import tribunal_bp
from modules.vault import vault_bp
from modules.verifier import verifier_bp
from modules.citizen_auth import citizen_bp

app = Flask(__name__)
app.secret_key = 'sovereign_secret'
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Initialize Database
init_db()

# --- 1. REGISTER BLUEPRINTS ---
app.register_blueprint(inscription_bp, url_prefix='/inscription')
app.register_blueprint(mapping_bp, url_prefix='/mapping')
app.register_blueprint(tribunal_bp, url_prefix='/tribunal')
app.register_blueprint(vault_bp, url_prefix='/vault')
app.register_blueprint(verifier_bp, url_prefix='/verifier')
app.register_blueprint(citizen_bp)

# --- 2. HELPERS ---
def get_system_context():
    node_count = 3
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM network_nodes")
        res = cursor.fetchone()
        if res:
            node_count = res[0]
        conn.close()
    except:
        pass
    return {
        'telemetry': {
            'uptime': '99.99%',
            'load': f"{10 + (len(land_chain.chain) % 15)}%",
            'nodes': node_count,
            'node_status': 'Operational'
        },
        'stats': {
            'sync': 'Synchronized',
            'blocks': len(land_chain.chain),
            'total_nodes': node_count
        }
    }

def get_my_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# --- 3. LANDING & AUTH ---

@app.route('/')
def landing():
    if 'user' in session:
        if session.get('role') == 'citizen':
            return redirect(url_for('citizen.dashboard'))
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = request.form.get('username')
        pw   = request.form.get('password')
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, password, role) VALUES (%s, %s, %s)',
                (user, pw, 'admin')
            )
            conn.commit()
            conn.close()
            flash("Account created! Please Sign In.")
            return redirect(url_for('login_gate', role='admin'))
        except Exception:
            flash("Error: Username already exists.")
    return render_template('login.html', mode='signup')

@app.route('/login', methods=['GET', 'POST'])
def login_gate():
    role = request.args.get('role', 'user')
    if request.method == 'GET':
        session.clear()
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE qr_sync SET status='waiting', authenticated_user=NULL WHERE id=1"
            )
            conn.commit()
            conn.close()
        except:
            pass

    if request.method == 'POST':
        user = request.form.get('username')
        pw   = request.form.get('password')
        conn = connect_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            'SELECT * FROM users WHERE username=%s AND password=%s AND role=%s',
            (user, pw, 'admin')
        )
        account = cursor.fetchone()
        conn.close()
        if account:
            session['user'] = account['username']
            session['role'] = 'admin'
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid Admin Credentials.")

    if role == 'admin':
        scan_url = url_for('scan_endpoint', device_id='DEV-HYD-99', _external=True)
        return render_template('qr_scan.html', scan_url=scan_url, server_host=request.host)
    return render_template('login.html', mode='login')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('login_gate', role='admin'))
    ctx = get_system_context()
    return render_template(
        'main_dashboard.html',
        user=session['user'],
        chain=land_chain.chain,
        **ctx
    )

# --- 4. REGISTERED CITIZENS ---

@app.route('/registered_citizens')
def registered_citizens():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('login_gate', role='admin'))

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # All citizens
    cursor.execute("SELECT id, username FROM users WHERE role='citizen' ORDER BY id DESC")
    citizens = cursor.fetchall()

    # Property count per citizen
    for c in citizens:
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM land_records WHERE pattadar=%s",
            (c['username'],)
        )
        c['property_count'] = cursor.fetchone()['cnt']

        # Transfer request count
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM transfer_requests WHERE sender=%s",
            (c['username'],)
        )
        c['transfer_count'] = cursor.fetchone()['cnt']

    total_citizens = len(citizens)
    conn.close()

    ctx = get_system_context()
    return render_template(
        'registered_citizens.html',
        citizens=citizens,
        total_citizens=total_citizens,
        user=session['user'],
        **ctx
    )

# --- 5. REPORTS & STATISTICS ---

@app.route('/reports')
def reports():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('login_gate', role='admin'))

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Total citizens
    cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE role='citizen'")
    total_citizens = cursor.fetchone()['cnt']

    # Total land records
    cursor.execute("SELECT COUNT(*) as cnt FROM land_records")
    total_land = cursor.fetchone()['cnt']

    # Total area registered
    cursor.execute("SELECT SUM(extent) as total FROM land_records")
    total_area = cursor.fetchone()['total'] or 0

    # Transfer stats
    cursor.execute("SELECT COUNT(*) as cnt FROM transfer_requests")
    total_transfers = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM transfer_requests WHERE status='Approved'")
    approved_transfers = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM transfer_requests WHERE status='Rejected'")
    rejected_transfers = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM transfer_requests WHERE status='Pending'")
    pending_transfers = cursor.fetchone()['cnt']

    # Dispute stats
    cursor.execute("SELECT COUNT(*) as cnt FROM disputes")
    total_disputes = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM disputes WHERE LOWER(status) IN ('resolved', 'approved')")
    resolved_disputes = cursor.fetchone()['cnt']

    # Land by category
    cursor.execute("""
        SELECT land_category, COUNT(*) as cnt, SUM(extent) as area
        FROM land_records
        GROUP BY land_category
    """)
    land_by_category = cursor.fetchall()

    # Top 5 citizens by property count
    cursor.execute("""
        SELECT pattadar as owner_name, COUNT(*) as cnt, SUM(extent) as total_area
        FROM land_records
        GROUP BY pattadar
        ORDER BY cnt DESC LIMIT 5
    """)
    top_citizens = cursor.fetchall()

    # Recent 10 transfers — safe fallback if assigned_admin_id column does not exist
    try:
        cursor.execute("""
            SELECT tr.*, u.username as admin_name
            FROM transfer_requests tr
            LEFT JOIN users u ON tr.assigned_admin_id = u.id
            ORDER BY tr.id DESC LIMIT 10
        """)
    except Exception:
        # Column assigned_admin_id missing — fetch without the join
        cursor.execute("SELECT * FROM transfer_requests ORDER BY id DESC LIMIT 10")
    recent_transfers = cursor.fetchall()

    # Blockchain blocks
    total_blocks = len(land_chain.chain)

    conn.close()
    ctx = get_system_context()

    return render_template(
        'reports.html',
        total_citizens=total_citizens,
        total_land=total_land,
        total_area=round(float(total_area), 2),
        total_transfers=total_transfers,
        approved_transfers=approved_transfers,
        rejected_transfers=rejected_transfers,
        pending_transfers=pending_transfers,
        total_disputes=total_disputes,
        resolved_disputes=resolved_disputes,
        land_by_category=land_by_category,
        top_citizens=top_citizens,
        recent_transfers=recent_transfers,
        total_blocks=total_blocks,
        user=session['user'],
        **ctx
    )

# --- 6. ADMIN REQUEST MANAGEMENT ---

@app.route('/admin/manage_requests')
def manage_requests():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('login_gate', role='admin'))

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT id FROM users WHERE username=%s", (session.get('user'),))
    admin_data = cursor.fetchone()
    admin_id   = admin_data['id'] if admin_data else 0

    cursor.execute("SELECT * FROM disputes WHERE status='Under Review'")
    disputes = cursor.fetchall()

    cursor.execute("""
        SELECT tr.*, lr.location, lr.survey_no
        FROM transfer_requests tr
        LEFT JOIN land_records lr ON tr.property_id = lr.id
        WHERE tr.assigned_admin_id=%s AND tr.status='Pending'
    """, (admin_id,))
    transfers = cursor.fetchall()

    conn.close()
    return render_template('admin_requests.html', disputes=disputes, transfers=transfers)

# --- 7. APPROVE HANDSHAKE ---

@app.route('/admin/approve_handshake', methods=['POST'])
def approve_handshake():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    request_id = request.form.get('request_id')
    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM transfer_requests WHERE id=%s", (request_id,))
    req = cursor.fetchone()

    if req:
        new_block = land_chain.add_block(data={
            'type':        'OFFICIAL_TRANSFER',
            'property_id':  req['property_id'],
            'from':         req['sender'],
            'to':           req['receiver'],
            'signed_by':    session.get('user'),
            'timestamp':    str(datetime.datetime.now())
        })
        cursor.execute("""
            UPDATE transfer_requests
            SET status='Approved'
            WHERE id=%s
        """, (request_id,))
        cursor.execute(
            "UPDATE land_records SET pattadar=%s WHERE id=%s",
            (req['receiver'], req['property_id'])
        )
        # Notify citizen
        cursor.execute("""
            INSERT INTO notifications (recipient, role, message)
            VALUES (%s, 'citizen', %s)
        """, (req['sender'],
              f"Your transfer request for Property #{req['property_id']} has been "
              f"<strong>Approved</strong> by Admin <strong>{session.get('user')}</strong>. "
              f"Hash: {new_block['hash'][:20]}..."))
        conn.commit()
        conn.close()
        return jsonify({
            'status': 'success',
            'message': f"Transfer approved! Property {req['property_id']} transferred to {req['receiver']}."
        })

    conn.close()
    return jsonify({'status': 'error', 'message': 'Request not found.'})

# --- 8. REJECT HANDSHAKE ---

@app.route('/admin/reject_handshake', methods=['POST'])
def reject_handshake():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    request_id = request.form.get('request_id')
    reason     = request.form.get('reason', 'No reason provided.')

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM transfer_requests WHERE id=%s", (request_id,))
    req = cursor.fetchone()

    if req:
        cursor.execute(
            "UPDATE transfer_requests SET status='Rejected' WHERE id=%s",
            (request_id,)
        )
        cursor.execute("""
            INSERT INTO notifications (recipient, role, message)
            VALUES (%s, 'citizen', %s)
        """, (req['sender'],
              f"Your transfer request for Property #{req['property_id']} has been "
              f"<strong>Rejected</strong> by Admin <strong>{session.get('user')}</strong>. "
              f"Reason: {reason}"))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Request rejected and citizen notified.'})

    conn.close()
    return jsonify({'status': 'error', 'message': 'Request not found.'})

# --- 9. ADMIN SEND MESSAGE ---

@app.route('/admin/send_message', methods=['POST'])
def admin_send_message():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    request_id = request.form.get('request_id')
    message    = request.form.get('message', '').strip()
    admin_name = session.get('user')

    if not request_id or not message:
        return jsonify({'status': 'error', 'message': 'Missing fields.'}), 400

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT sender FROM transfer_requests WHERE id=%s", (request_id,))
    req = cursor.fetchone()

    if not req:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Request not found.'}), 404

    citizen = req['sender']
    cursor.execute("""
        INSERT INTO admin_messages (request_id, from_admin, to_citizen, message)
        VALUES (%s, %s, %s, %s)
    """, (request_id, admin_name, citizen, message))
    cursor.execute("""
        INSERT INTO notifications (recipient, role, message)
        VALUES (%s, 'citizen', %s)
    """, (citizen,
          f"Message from Admin <strong>{admin_name}</strong> regarding "
          f"Transfer Request #{request_id}: \"{message}\""))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Message sent to citizen.'})

# --- 10. ADMIN NOTIFICATIONS ---

@app.route('/admin/notifications')
def admin_notifications():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({'status': 'error'}), 401

    username = session.get('user')
    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT * FROM notifications
        WHERE recipient=%s AND role='admin'
        ORDER BY created_at DESC LIMIT 20
    """, (username,))
    notifs = cursor.fetchall()
    cursor.execute(
        "UPDATE notifications SET is_read=1 WHERE recipient=%s AND role='admin'",
        (username,)
    )
    conn.commit()
    conn.close()
    for n in notifs:
        n['created_at'] = str(n['created_at'])
    return jsonify({'status': 'ok', 'notifications': notifs})

@app.route('/admin/unread_count')
def admin_unread_count():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({'count': 0})
    username = session.get('user')
    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT COUNT(*) as cnt FROM notifications
        WHERE recipient=%s AND role='admin' AND is_read=0
    """, (username,))
    count = cursor.fetchone()['cnt']
    conn.close()
    return jsonify({'count': count})

# --- 11. STANDARD APPROVAL (backward compat) ---

@app.route('/admin/approve_transfer/<int:request_id>', methods=['POST'])
def approve_transfer(request_id):
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({'status': 'unauthorized'}), 403

    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM transfer_requests WHERE id=%s", (request_id,))
    req = cursor.fetchone()
    if req:
        land_chain.add_block(data={
            'type':        'TRANSFER',
            'property_id':  req['property_id'],
            'from':         req['sender'],
            'to':           req['receiver'],
            'timestamp':    str(datetime.datetime.now())
        })
        cursor.execute(
            "UPDATE transfer_requests SET status='Approved' WHERE id=%s",
            (request_id,)
        )
        conn.commit()
        flash("Transfer Approved.")
    conn.close()
    return redirect(url_for('manage_requests'))

@app.route('/admin/resolve_dispute/<int:dispute_id>', methods=['POST'])
def resolve_dispute(dispute_id):
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({'status': 'unauthorized'}), 403

    action = request.form.get('action')
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE disputes SET status=%s WHERE id=%s",
        (action, dispute_id)
    )
    conn.commit()
    conn.close()
    flash(f"Dispute {dispute_id} has been {action}.")
    return redirect(url_for('manage_requests'))

# --- 12. QR / MOBILE SYNC ---

@app.route('/check_auth')
def check_auth():
    conn = connect_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT status, authenticated_user FROM qr_sync WHERE id=1")
    row = cursor.fetchone()
    conn.close()
    if row and row['status'] == 'verified':
        session['user'] = row['authenticated_user']
        session['role'] = 'admin'
        return jsonify({'status': 'success'})
    return jsonify({'status': 'waiting'})

@app.route('/scan/<device_id>', methods=['GET', 'POST'])
def scan_endpoint(device_id):
    if request.method == 'POST':
        user = request.form.get('username')
        pw   = request.form.get('password')
        conn = connect_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            'SELECT * FROM users WHERE username=%s AND password=%s AND role=%s',
            (user, pw, 'admin')
        )
        account = cursor.fetchone()
        if account:
            cursor.execute(
                "UPDATE qr_sync SET status='verified', authenticated_user=%s WHERE id=1",
                (user,)
            )
            conn.commit()
            conn.close()
            return "<h1>✅ VERIFIED</h1>"
        conn.close()
        return "<h1>❌ MISMATCH</h1>"
    return render_template('access.html', device_id=device_id)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
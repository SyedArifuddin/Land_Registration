from psycopg2.extras import RealDictCursor
from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from auth import db_config, connect_db

tribunal_bp = Blueprint('tribunal', __name__)

@tribunal_bp.route('/', methods=['GET', 'POST'])
def index():
    if 'user' not in session:
        return redirect(url_for('login_gate'))

    current_user = session.get('user')

    if request.method == 'POST' and 'create_case' in request.form:
        survey_no = request.form.get('survey_no')
        party_a   = request.form.get('party_a')
        party_b   = request.form.get('party_b')
        reason    = request.form.get('reason', '')
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO disputes (survey_no, claimant_a, claimant_b, reason, status) VALUES (%s,%s,%s,%s,'HEARING')",
                (survey_no, party_a, party_b, reason)
            )
            conn.commit()
            conn.close()
            flash(f"Case opened: {party_a} vs {party_b}")
        except Exception as e:
            flash(f"Database Error: {e}")

    disputes = []
    try:
        conn = connect_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM disputes ORDER BY id DESC")
        disputes = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"Load Error: {e}")

    return render_template('features/tribunal.html', disputes=disputes, user=current_user)

@tribunal_bp.route('/update/<int:case_id>', methods=['POST'])
def update_status(case_id):
    new_status = request.form.get('status')
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE disputes SET status=%s WHERE id=%s", (new_status, case_id))
        conn.commit()
        conn.close()
        flash(f"Case #TRB-{case_id} updated to {new_status}")
    except Exception as e:
        flash(f"Update failed: {e}")
    return redirect(url_for('tribunal.index'))
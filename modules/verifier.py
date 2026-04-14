from psycopg2.extras import RealDictCursor
from flask import Blueprint, render_template, request, session, redirect, url_for
from auth import db_config, connect_db
from blockchain_config import land_chain

verifier_bp = Blueprint('verifier', __name__)

def sync_vault_to_blockchain():
    """Sync all land_records from the DB into the blockchain if not already present."""
    try:
        conn   = connect_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM land_records")
        all_records = cursor.fetchall()
        conn.close()

        for rec in all_records:
            survey = str(rec.get('survey_no', ''))
            already = any(
                str(block.get('data', {}).get('land_id', '')) == survey or
                str(block.get('data', {}).get('survey',  '')) == survey
                for block in land_chain.chain
            )
            if not already:
                land_chain.add_block({
                    'land_id':    survey,
                    'owner':      rec.get('pattadar',    'N/A'),
                    'extent':     str(rec.get('extent', '0')),
                    'district':   rec.get('location', 'N/A'),
                    'category':   rec.get('land_category', 'N/A'),
                    'hash_proof': rec.get('block_hash', '') or rec.get('property_hash', ''),
                    'entry_type': 'INSCRIPTION'
                })
    except Exception as e:
        print(f"Sync Error: {e}")


@verifier_bp.route('/', methods=['GET', 'POST'])
def index():
    if 'user' not in session:
        return redirect(url_for('login_gate'))

    # Always sync first so chain has latest records
    sync_vault_to_blockchain()

    current_user  = session.get('user')
    query         = request.args.get('query', '').strip()
    search_result = None
    status_code   = "AWAITING_INPUT"

    if query:
        # Search blockchain chain
        for block in land_chain.chain:
            data = block.get('data', {})
            if (str(data.get('land_id',  '')) == query or
                str(data.get('survey',   '')) == query or
                str(data.get('owner',    '')) == query or
                str(block.get('hash',    '')) == query):
                search_result = block
                status_code   = "VALIDATED"
                break

        # If not found on chain, try the database directly as fallback
        if not search_result:
            try:
                conn   = connect_db()
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(
                    "SELECT * FROM land_records WHERE survey_no=%s OR pattadar=%s",
                    (query, query)
                )
                rec = cursor.fetchone()
                conn.close()
                if rec:
                    search_result = {
                        'index': 'DB',
                        'hash':  rec.get('block_hash', '') or rec.get('property_hash', 'N/A'),
                        'data': {
                            'land_id':  rec.get('survey_no',    'N/A'),
                            'owner':    rec.get('pattadar',      'N/A'),
                            'extent':   str(rec.get('extent',     '0')),
                            'district': rec.get('location',      'N/A'),
                            'category': rec.get('land_category', 'N/A'),
                        }
                    }
                    status_code = "VALIDATED"
            except Exception as e:
                print(f"DB Fallback Error: {e}")

        if not search_result:
            status_code = "NOT_FOUND"

    # Stats
    total_acres = sum(
        float(b.get('data', {}).get('extent') or
              b.get('data', {}).get('area', 0) or 0)
        for b in land_chain.chain
        if isinstance(b.get('data'), dict)
    )

    telemetry = {
        "verified_acres": f"{total_acres:.2f}",
        "active_shards":  len(land_chain.chain)
    }

    return render_template(
        'features/verifier.html',
        result=search_result,
        query=query,
        status=status_code,
        telemetry=telemetry,
        chain=land_chain.chain,
        user=current_user
    )
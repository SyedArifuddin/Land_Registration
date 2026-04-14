from psycopg2.extras import RealDictCursor
# Updated to import from the correct filename 'blockchain'
from blockchain import Blockchain 
from auth import db_config, connect_db

land_chain = Blockchain()

# IMPORTANT: This helper ensures the 'chain' is not empty on startup
def sync_chain_from_db():
    try:
        conn = connect_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        # Fetch your stored records (inscriptions, etc.)
        cursor.execute("SELECT * FROM land_records") 
        records = cursor.fetchall()
        
        # If no records exist, create the Genesis Block
        if not records and len(land_chain.chain) == 0:
            land_chain.create_block(proof=100, previous_hash='0')
        
        # Logic to append existing records to land_chain.chain goes here...
        
        conn.close()
    except:
        # Fallback: Always ensure at least a Genesis block exists
        if len(land_chain.chain) == 0:
            land_chain.create_block(proof=100, previous_hash='0')

sync_chain_from_db()
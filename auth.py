import os
from urllib.parse import urlparse
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get('DATABASE_URL')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_NAME = os.environ.get('DB_NAME', 'postgres')
DB_PORT = int(os.environ.get('DB_PORT', 5432))
DB_SSLMODE = os.environ.get('DB_SSLMODE')

if DATABASE_URL:
    db_config = {
        'dsn': DATABASE_URL
    }
else:
    db_config = {
        'host': DB_HOST,
        'user': DB_USER,
        'password': DB_PASSWORD,
        'dbname': DB_NAME,
        'port': DB_PORT,
    }

if DB_SSLMODE:
    db_config['sslmode'] = DB_SSLMODE
elif DATABASE_URL:
    db_config['sslmode'] = 'require'


def connect_db():
    if 'dsn' in db_config:
        return psycopg2.connect(db_config['dsn'], sslmode=db_config.get('sslmode'))
    return psycopg2.connect(**db_config)


def init_db():
    conn = None
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE,
            password VARCHAR(255),
            role VARCHAR(50)
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS recognized_devices (
            id SERIAL PRIMARY KEY,
            device_signature VARCHAR(255) UNIQUE,
            username VARCHAR(255)
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS qr_sync (
            id INT PRIMARY KEY,
            status VARCHAR(50),
            authenticated_user VARCHAR(255)
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS network_nodes (
            id SERIAL PRIMARY KEY,
            node_name VARCHAR(255),
            status VARCHAR(100),
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS land_records (
            id SERIAL PRIMARY KEY,
            pattadar VARCHAR(255),
            location VARCHAR(255),
            survey_no VARCHAR(255) UNIQUE,
            extent VARCHAR(255),
            land_category VARCHAR(255),
            block_hash VARCHAR(255),
            property_hash VARCHAR(255),
            officer VARCHAR(255),
            district VARCHAR(255),
            coordinates TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS transfer_requests (
            id SERIAL PRIMARY KEY,
            property_id INTEGER REFERENCES land_records(id) ON DELETE SET NULL,
            sender VARCHAR(255),
            receiver VARCHAR(255),
            assigned_admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            status VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS disputes (
            id SERIAL PRIMARY KEY,
            survey_no VARCHAR(255),
            claimant_a VARCHAR(255),
            claimant_b VARCHAR(255),
            reason TEXT,
            status VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            recipient VARCHAR(255),
            role VARCHAR(50),
            message TEXT,
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS admin_messages (
            id SERIAL PRIMARY KEY,
            request_id INTEGER REFERENCES transfer_requests(id) ON DELETE CASCADE,
            from_admin VARCHAR(255),
            to_citizen VARCHAR(255),
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS network_telemetry (
            id SERIAL PRIMARY KEY,
            event_type VARCHAR(100),
            data_value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute("INSERT INTO qr_sync (id, status) VALUES (1, 'waiting') ON CONFLICT (id) DO NOTHING")
        conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        if conn:
            conn.close()


def is_device_registered(sig):
    conn = None
    try:
        conn = connect_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM recognized_devices WHERE device_signature = %s', (sig,))
        return cursor.fetchone()
    except Exception:
        return None
    finally:
        if conn:
            conn.close()
import os
from urllib.parse import unquote, urlparse
import mysql.connector
from mysql.connector import Error

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    parsed = urlparse(DATABASE_URL)
    db_config = {
        'host': parsed.hostname or 'localhost',
        'user': unquote(parsed.username or 'root'),
        'password': unquote(parsed.password or ''),
        'database': parsed.path.lstrip('/') or 'land_registry_db',
        'port': parsed.port or 3306,
    }
else:
    db_config = {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'user': os.environ.get('DB_USER', 'root'),
        'password': os.environ.get('DB_PASSWORD', 'Root@123'),
        'database': os.environ.get('DB_NAME', 'land_registry_db'),
        'port': int(os.environ.get('DB_PORT', 3306)),
    }


def init_db():
    try:
        conn = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password']
        )
        cursor = conn.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS land_registry_db")
        cursor.execute("USE land_registry_db")
        
        # Table for Users
        cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                          (id INT AUTO_INCREMENT PRIMARY KEY, 
                           username VARCHAR(255) UNIQUE, 
                           password VARCHAR(255), 
                           role VARCHAR(50))''')
        
        # Table for Device Mapping
        cursor.execute('''CREATE TABLE IF NOT EXISTS recognized_devices 
                          (id INT AUTO_INCREMENT PRIMARY KEY, 
                           device_signature VARCHAR(255) UNIQUE, 
                           username VARCHAR(255))''')

        # NEW: Table to synchronize Laptop and Phone status
        cursor.execute('''CREATE TABLE IF NOT EXISTS qr_sync 
                          (id INT PRIMARY KEY, 
                           status VARCHAR(50), 
                           authenticated_user VARCHAR(255))''')
        
        # Initialize the sync row
        cursor.execute("INSERT IGNORE INTO qr_sync (id, status) VALUES (1, 'waiting')")
        
        conn.commit()
    except Error as e:
        print(f"DB Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def is_device_registered(sig):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM recognized_devices WHERE device_signature = %s', (sig,))
        return cursor.fetchone()
    except: return None
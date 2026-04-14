import mysql.connector
from mysql.connector import Error

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Root@123',
    'database': 'land_registry_db'
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
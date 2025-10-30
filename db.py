import os
import pymysql

config = {
    'host': os.environ.get('DB_HOST'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASSWORD'),
    'database': os.environ.get('DB_NAME'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'cursorclass': pymysql.cursors.DictCursor
}

def get_connection():
    return pymysql.connect(**config)

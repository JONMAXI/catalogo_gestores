import pymysql

config = {
    'host': '34.9.147.5',
    'user': 'jonathan',
    'password': ')1>SbilQ,$VKr=hO',
    'database': 'estado_cuenta',
    'port': 3306,
    'cursorclass': pymysql.cursors.DictCursor
}

def get_connection():
    return pymysql.connect(**config)

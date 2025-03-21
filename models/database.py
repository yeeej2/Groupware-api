import pymysql

def get_db_connection():
    return pymysql.connect(
        host="172.16.21.200",  # 또는 실제 DB 서버 IP
        user="itsin",
        password="1234",
        database="groupware",
        cursorclass=pymysql.cursors.DictCursor
    )

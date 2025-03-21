from models.database import get_db_connection
from flask import Blueprint, request, jsonify

# 📌 Blueprint 생성
timeline_bp = Blueprint('timeline', __name__)

# 📌 특정 고객의 타임라인 조회 API (GET)
@timeline_bp.route('/timeline/<int:customer_id>', methods=['GET'])
def get_timeline(customer_id):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = """
        SELECT 
            t.timeline_id, 
            t.category, 
            t.event_date AS date, 
            t.description, 
            t.person, 
            t.amount, 
            c.cust_name AS company
        FROM timeline t
        JOIN customer c ON t.cust_id = c.cust_id
        WHERE t.cust_id = %s
        ORDER BY t.event_date DESC
        """
        cursor.execute(sql, (customer_id,))
        timeline_data = cursor.fetchall()
    
    connection.close()
    return jsonify(timeline_data), 200

# 📌 새로운 타임라인 데이터 추가 API (POST)
@timeline_bp.route('/timeline', methods=['POST'])
def add_timeline_entry():
    data = request.json
    required_fields = ['customer_id', 'category', 'event_date', 'description']

    # 필수 입력 값 확인
    if not all(field in data for field in required_fields):
        return jsonify({'error': '필수 입력 값이 누락되었습니다!'}), 400

    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = """
        INSERT INTO timeline (cust_id, category, event_date, description, person, amount)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (
            data['customer_id'],
            data['category'],
            data['event_date'],
            data['description'],
            data.get('person'),  # NULL 허용
            data.get('amount')  # NULL 허용
        ))
        connection.commit()

        # 새로 추가된 데이터 가져오기
        cursor.execute("SELECT LAST_INSERT_ID() AS last_id")
        last_id = cursor.fetchone()["last_id"]

        cursor.execute("""
            SELECT t.timeline_id, t.category, t.event_date, t.description, t.person, t.amount, c.cust_name AS company
            FROM timeline t
            JOIN customer c ON t.cust_id = c.cust_id
            WHERE t.timeline_id = %s
        """, (last_id,))
        new_entry = cursor.fetchone()
    
    connection.close()
    return jsonify(new_entry), 201


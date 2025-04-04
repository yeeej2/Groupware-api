from models.database import get_db_connection
from flask import Blueprint, request, jsonify
import logging

# 📌 Blueprint 생성
users_bp = Blueprint('users', __name__)

# 🔹 snake_case → camelCase 변환 함수
def snake_to_camel(snake_str):
    parts = snake_str.split('_')
    return parts[0] + ''.join(word.capitalize() for word in parts[1:])

# 🔹 모든 키를 camelCase로 변환하는 함수
def convert_keys_to_camel_case(data):
    if isinstance(data, list):  # 리스트 처리
        return [convert_keys_to_camel_case(item) for item in data]
    elif isinstance(data, dict):  # 딕셔너리 처리
        return {snake_to_camel(k): v for k, v in data.items()}
    return data

# 📌 Create a new user
@users_bp.route('/users', methods=['POST'])
def create_user():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
    INSERT INTO user (login_id, name, pw, pw_salt_val, last_con_ip, phone, email, reg_id, role_cd, depart_cd)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    values = (
        data['login_id'], data['name'], data['pw'], data['pw_salt_val'],
        data.get('last_con_ip'), data.get('phone'), data.get('email'),
        data.get('reg_id'), data.get('role_cd'), data.get('depart_cd')
    )
    cursor.execute(sql, values)
    conn.commit()
    user_id = cursor.lastrowid
    cursor.close()
    conn.close()

    return jsonify({'message': 'User created successfully', 'user_id': user_id}), 201

# 📌 사용자 검색 API
@users_bp.route('/users/search', methods=['POST'])
def search_users():
    """
    사용자 목록 검색 API
    - 요청 JSON 예시:
      {
        "type": "sales",  # 사용자 유형 ('sales' 또는 'engineer')
        "keyword": "홍길동"  # 검색 키워드 (이름 또는 이메일)
      }
    """
    data = request.json
    usr_type = data.get('type')  # 'sales' 또는 'engineer'
    keyword = data.get('keyword', '')  # 검색 키워드 (없으면 빈 문자열)

    conn = get_db_connection()
    cursor = conn.cursor()

    # 기본 쿼리
    query = "SELECT usr_id AS id, name, email, phone FROM user WHERE 1=1"
    params = []

    # 사용자 유형 필터 추가
    if usr_type == 'sales':
        query += " AND role_cd = 'SALES'"
    elif usr_type == 'engineer':
        query += " AND role_cd = 'ENGINEER'"

    # 검색 키워드 필터 추가
    if keyword:
        query += " AND (name LIKE %s OR email LIKE %s)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    try:
        # 쿼리 실행
        cursor.execute(query, params)
        users = cursor.fetchall()

        # camelCase로 변환
        users = convert_keys_to_camel_case(users)

        return jsonify({'result': 'success', 'data': users}), 200

    except Exception as e:
        logging.error(f"📌 사용자 목록 조회 중 오류 발생: {e}")
        return jsonify({'result': 'error', 'message': '사용자 목록 조회 실패'}), 500

    finally:
        cursor.close()
        conn.close()

@users_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM user WHERE usr_id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        return jsonify(user), 200
    else:
        return jsonify({'message': 'User not found'}), 404

# 📌 Update a user
@users_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
    UPDATE user
    SET login_id = %s, name = %s, pw = %s, pw_salt_val = %s, last_con_ip = %s,
        phone = %s, email = %s, role_cd = %s, depart_cd = %s, upd_id = %s
    WHERE usr_id = %s
    """
    values = (
        data['login_id'], data['name'], data['pw'], data['pw_salt_val'],
        data.get('last_con_ip'), data.get('phone'), data.get('email'),
        data.get('role_cd'), data.get('depart_cd'), data.get('upd_id'), user_id
    )
    cursor.execute(sql, values)
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'message': 'User updated successfully'}), 200

# 📌 Delete a user
@users_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM user WHERE usr_id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'message': 'User deleted successfully'}), 200
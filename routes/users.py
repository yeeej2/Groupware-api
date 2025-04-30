from models.database import get_db_connection
from flask import Blueprint, request, jsonify
import logging
import bcrypt

# 📌 Blueprint 생성
users_bp = Blueprint('users', __name__)

from auth.decorators import require_token
@users_bp.before_request
@require_token
def require_token_for_user_bp():
    pass

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
@users_bp.route('/usersss', methods=['POST'])
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
    query = "SELECT usr_id AS id, name, email, phone, position FROM user WHERE 1=1"
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


@users_bp.route('/users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM user;", ())
    user = cursor.fetchall()
    cursor.close()
    conn.close()

    if user:
        return jsonify({'result': 'success', "data" : user}), 200
    else:
        return jsonify({'message': 'User not found'}), 404
    


@users_bp.route('/roles', methods=['GET'])
def get_roles():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM roles;", ())
    roles = cursor.fetchall()
    cursor.close()
    conn.close()

    if roles:
        return jsonify({'result': 'success', "data" : roles}), 200
    else:
        return jsonify({'message': 'User not found'}), 404
    

@users_bp.route('/screens', methods=['GET'])
def get_screens():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM screens;", ())
    screens = cursor.fetchall()
    cursor.close()
    conn.close()

    if screens:
        return jsonify({'result': 'success', "data" : screens}), 200
    else:
        return jsonify({'message': 'User not found'}), 404
    







@users_bp.route('/users/me', methods=['GET'])
def get_my_info():
    usr_id = request.user["usr_id"]

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT usr_id, login_id, name, role_cd, depart_cd, email, phone, position  FROM user WHERE usr_id = %s", (usr_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "사용자를 찾을 수 없습니다."}), 404

        return jsonify({"user": user}), 200
    finally:
        cursor.close()
        conn.close()









@users_bp.route('/users/me', methods=['PUT'])
def update_my_info():
    usr_id = request.user["usr_id"]  # ✅ 로그인 유저 ID
    data = request.get_json()

    # 수정 가능한 필드만 따로 정의
    editable_fields = ["name", "phone", "depart_cd", "position"]

    # 필드가 하나라도 없을 수 있으니까 None이면 기존 값 유지되도록 SQL 작성
    set_clause = []
    values = []

    for field in editable_fields:
        if field in data:
            set_clause.append(f"{field} = %s")
            values.append(data[field])

    if not set_clause:
        return jsonify({"error": "수정할 항목이 없습니다."}), 400

    values.append(usr_id)  # WHERE 조건용

    query = f"""
        UPDATE user
        SET {', '.join(set_clause)}
        WHERE usr_id = %s
    """

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, tuple(values))
        conn.commit()

        # 수정된 결과 다시 조회해서 반환
        cursor.execute("SELECT usr_id, login_id, name, role_cd, depart_cd, email, phone, position FROM user WHERE usr_id = %s", (usr_id,))
        user = cursor.fetchone()
        return jsonify(user), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": "업데이트 실패", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()









@users_bp.route('/users/password', methods=['PUT'])
def change_password():
    usr_id = request.user["usr_id"]
    data = request.get_json()

    current_pw = data.get("current_password")
    new_pw = data.get("new_password")

    if not current_pw or not new_pw:
        return jsonify({"error": "현재 비밀번호와 새 비밀번호는 필수입니다."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 1. 현재 비밀번호 확인을 위한 DB 조회
        cursor.execute("SELECT pw, pw_salt_val FROM user WHERE usr_id = %s", (usr_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "사용자를 찾을 수 없습니다."}), 404

        stored_hash = user["pw"]
        stored_salt = user["pw_salt_val"]

        # 2. 기존 비밀번호 검증
        if not bcrypt.checkpw(current_pw.encode(), stored_hash.encode()):
            return jsonify({"error": "현재 비밀번호가 일치하지 않습니다."}), 401

        # 3. 새 비밀번호 해싱 및 salt 생성
        new_salt = bcrypt.gensalt()
        new_hashed_pw = bcrypt.hashpw(new_pw.encode(), new_salt).decode()

        # 4. DB 업데이트
        cursor.execute(
            "UPDATE user SET pw = %s, pw_salt_val = %s WHERE usr_id = %s",
            (new_hashed_pw, new_salt.decode(), usr_id)
        )
        conn.commit()

        return jsonify({"message": "비밀번호가 변경되었습니다."}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": "비밀번호 변경 실패", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()






@users_bp.route('/users/updateRole', methods=['POST'])
def update_user_role():
    data = request.get_json()
    logging.info("ssssssssssssss")
    logging.info(data)
    user_id = data.get("user_id")
    role_id = data.get("role_id")

    if not user_id or not role_id:
        return jsonify({"error": "user_id와 role_id는 필수입니다."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 유저가 있는지 확인
        cursor.execute("SELECT * FROM user WHERE usr_id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "존재하지 않는 사용자입니다."}), 404

        # 역할 업데이트
        cursor.execute("""
            UPDATE user
            SET role_cd = %s
            WHERE usr_id = %s
        """, (role_id, user_id))

        conn.commit()
        return jsonify({"result": "success"}), 200

    except Exception as e:
        print("DB 오류:", e)
        return jsonify({"error": "역할 업데이트 중 오류 발생"}), 500
    finally:
        cursor.close()
        conn.close()

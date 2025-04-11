from flask import Blueprint, request, jsonify, session
from models.database import get_db_connection
import bcrypt, logging

login_bp = Blueprint('login', __name__)

@login_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    login_id = data.get('username')
    password = data.get('password')
    logging.debug(f"Login attempt with ID: {login_id}")
    logging.debug(f"Login attempt with Password: {password}")

    if not login_id or not password:
        return jsonify({"error": "아이디와 비밀번호를 모두 입력해주세요."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. login_id로 사용자 조회
        query = "SELECT * FROM user WHERE login_id = %s"
        cursor.execute(query, (login_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "존재하지 않는 사용자입니다."}), 401

        # 2. bcrypt로 비밀번호 비교
        stored_hash = user['pw'].encode('utf-8')

        print(f"입력 비번: {password}")
        print(f"DB 비번 해시: {user['pw']}")
        print(f"DB 비번 길이: {len(user['pw'])}")
        print(f"checkpw 결과: {bcrypt.checkpw(password.encode(), user['pw'].encode())}")
        print(type(user['pw']))  # <class 'str'> 여야 함
        print(type(stored_hash))  # <class 'bytes'> 여야 함
        print(bcrypt.hashpw("1234".encode(), bcrypt.gensalt()).decode())

        if not bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            return jsonify({"error": "비밀번호가 틀렸습니다."}), 401

        # 3. 세션에 로그인 정보 저장
        session['user'] = {
            "usr_id": user['usr_id'],
            "login_id": user['login_id'],
            "name": user['name'],
            "role_cd": user['role_cd']
        }

        return jsonify({"message": "로그인 성공!", "user": session['user']}), 200

    except Exception as e:
        return jsonify({"error": f"서버 오류: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()





@login_bp.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({"message": "로그아웃 완료!"}), 200

@login_bp.route('/session', methods=['GET'])
def get_session():
    logging.info(f"Session data: {session}")
    user = session.get('user')
    if user:
        return jsonify({"user": user}), 200
    else:
        return jsonify({"error": "로그인되어 있지 않습니다."}), 401

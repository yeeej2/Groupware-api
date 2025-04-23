from flask import Blueprint, request, jsonify, current_app
from models.database import get_db_connection
import bcrypt, jwt, datetime
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+

from flask import Flask, request, jsonify
from flask_mail import Mail, Message
import random
import string
from extensions import mail  # ✅ 이렇게!
# Flask에서 Redis 연결
import redis

login_bp = Blueprint('login', __name__)

@login_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    login_id = data.get('username')
    password = data.get('password')

    if not login_id or not password:
        return jsonify({"error": "아이디와 비밀번호를 모두 입력해주세요."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM user WHERE login_id = %s", (login_id,))
        user = cursor.fetchone() 
        if not user:
            return jsonify({"error": "존재하지 않는 사용자입니다."}), 401

        if not bcrypt.checkpw(password.encode(), user['pw'].encode()):
            return jsonify({"error": "비밀번호가 틀렸습니다."}), 401

        # ✅ JWT 토큰 생성
        payload = {
            "usr_id": user['usr_id'],
            "login_id": user['login_id'],
            "role_cd": user['role_cd'],
            "email": user['email'],
            "name": user['name'],
            "phone": user['phone'],
            "depart_cd": user['depart_cd'],
            "position": user['position'],
            "exp": datetime.now(ZoneInfo("Asia/Seoul")) + timedelta(hours=2)       # 한국 시간 기준 +2시간
        }
        token = jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")

        return jsonify({"message": "로그인 성공!", "token": token, "user" : payload}), 200

    except Exception as e:
        return jsonify({"error": f"서버 오류: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()








@login_bp.route("/users", methods=["POST"])
def create_user():
    data = request.get_json()

    name = data.get("name")
    email = data.get("email")
    password = data.get("pw")  # 실제 비번
    role_cd = data.get("role_cd", "USER")  # 기본값 USER
    reg_id = data.get("reg_id", "system")

    # 전화 번호 추가
    phone = data.get("phone", None)

    # 부서 코드 추가
    depart_cd = data.get("depart_cd", None)

    # 직책 추가
    position = data.get("position", None)

    if not email or not password or not name:
        return jsonify({"error": "아이디, 이름, 비밀번호는 필수입니다."}), 400

    # 1. 비밀번호 해싱
    salt = bcrypt.gensalt()
    hashed_pw = bcrypt.hashpw(password.encode(), salt).decode()

    # 2. DB에 저장
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO user (login_id, name, email, phone, pw, pw_salt_val, role_cd, depart_cd, position, reg_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (email, name, email, phone, hashed_pw, salt.decode(), role_cd, depart_cd, position, reg_id),
        )
        conn.commit()
        return jsonify({"message": "회원가입 성공!"}), 201
    except Exception as e:
        logging.error(f"회원가입 오류: {e}")
        return jsonify({"error": "회원가입 중 오류 발생"}), 500
    finally:
        cursor.close()
        conn.close()



# 이메일 인증 코드 전송 API(중복 이메일 확인 및 인증 코드 전송)
@login_bp.route('/send_verification', methods=['POST'])
def send_verification():
    email = request.json.get('email')

    if not email:
        return jsonify({"error": "이메일을 입력해주세요."}), 400

    # ✅ 중복 이메일 확인
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM user WHERE login_id = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            return jsonify({"error": "이미 가입된 이메일입니다."}), 400

    except Exception as e:
        return jsonify({"error": f"DB 조회 중 오류: {str(e)}"}), 500
    finally:
        cursor.close()
        conn.close()

    


    # ✅ 인증 코드 생성 및 Redis 저장
    # 인증 코드 생성은 항상 새로
    code = ''.join(random.choices(string.digits, k=6))
    try:
        r = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

        # 기존 인증 코드가 존재하면 재전송 막기
        # if r.exists(f"verify:{email}"):
        #     # 기존 코드 재사용해서 재전송만 함
        #     return jsonify({"error": "이미 인증 메일이 발송되었습니다. 이메일을 확인해주세요."}), 400
        
        r.setex(f"verify:{email}", 300, code)  # 5분 동안 유지
    except Exception as e:
        return jsonify({"error": f"Redis 저장 실패: {str(e)}"}), 500

    # ✅ 이메일 전송
    try:
        msg = Message("회원가입 인증 코드", sender=current_app.config['MAIL_DEFAULT_SENDER'], recipients=[email])
        msg.body = f"[ITSIN] 인증 코드는 {code} 입니다. 5분 내 입력해주세요."
        mail.send(msg)
    except Exception as e:
        return jsonify({"error": f"이메일 전송 실패: {str(e)}"}), 500

    return jsonify({"message": "이메일 전송 완료!"}), 200

# 인증 코드 확인 API
@login_bp.route('/verify_code', methods=['POST'])
def verify_code():
    data = request.get_json()
    email = data.get("email")
    code = data.get("code")

    if not email or not code:
        return jsonify({"error": "이메일과 인증 코드를 모두 입력해주세요."}), 400

    r = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)
    real_code = r.get(f"verify:{email}")

    if not real_code:
        return jsonify({"error": "인증 코드가 만료되었거나 존재하지 않습니다."}), 400

    if code != real_code:
        return jsonify({"error": "인증 코드가 올바르지 않습니다."}), 400

    # 인증 성공
    r.delete(f"verify:{email}")  # 인증 성공 시 제거 (선택)
    return jsonify({"message": "이메일 인증 완료!"}), 200



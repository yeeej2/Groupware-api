from flask import Blueprint, request, jsonify
from models.database import get_db_connection
import logging

permissions_bp = Blueprint('permissions', __name__)

# ✅ 화면 권한 조회 API
@permissions_bp.route('/permissions/screens', methods=['GET'])
def get_screen_permissions():
    logging.info(request)
    role = request.args.get('role')  # ✅ role로 받기!

    if not role:
        return jsonify({"error": "역할(role) 파라미터가 필요합니다."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # role로 화면 권한 조회
        cursor.execute("""
            SELECT DISTINCT s.path
            FROM screen_permissions sp
            JOIN screens s ON sp.screen_id = s.id
            JOIN roles r ON sp.role_id = r.id
            WHERE r.name = %s
        """, (role,))
        screens = cursor.fetchall()

        logging.info("wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww")
        logging.info(f"role: {role}, screens: {screens}")
        screen_paths = [screen['path'] for screen in screens]
        return jsonify({"allowedScreens": screen_paths})

    except Exception as e:
        return jsonify({"error": f"DB 조회 중 오류: {str(e)}"}), 500
    finally:
        cursor.close()
        conn.close()


        






# 📁 auth/decorators.py

from functools import wraps
from flask import request, jsonify, current_app
import jwt

def require_token(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 🔥 OPTIONS 요청은 통과시켜야 CORS preflight 성공
        if request.method == "OPTIONS":
            return '', 200
        
        auth_header = request.headers.get("Authorization", None)

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"message": "인증 토큰이 필요합니다."}), 401

        token = auth_header.split(" ")[1]

        try:
            payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            request.user = payload  # 🔥 사용자 정보 저장
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "토큰이 만료되었습니다."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "유효하지 않은 토큰입니다."}), 401

        return func(*args, **kwargs)
    return wrapper





def require_role(*allowed_roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = getattr(request, 'user', None)
            if not user:
                return jsonify({"message": "인증되지 않은 요청입니다."}), 401

            if user["role_cd"] not in allowed_roles:
                return jsonify({"message": "접근 권한이 없습니다."}), 403

            return func(*args, **kwargs)
        return wrapper
    return decorator


# app.py
from flask import Flask
from flask_cors import CORS
from extensions import mail
from routes import register_blueprints  # ✅ mail이 분리됐으니 이건 ok

app = Flask(__name__)

# 📬 메일 서버 설정
app.config['MAIL_SERVER'] = 'outbound.daouoffice.com'  # 사내 SMTP 서버
app.config['MAIL_PORT'] = 25                            # 포트 번호
app.config['MAIL_USERNAME'] = ''         # 보내는 사람 메일 주소
app.config['MAIL_PASSWORD'] = ''             # 해당 계정의 비밀번호
app.config['MAIL_USE_TLS'] = False                      # TLS 안 씀 (25번 포트는 STARTTLS일 수도 있지만 여기선 False)
app.config['MAIL_USE_SSL'] = False                      # SSL도 안 씀
app.config['MAIL_DEFAULT_SENDER'] = ''   # 기본 보내는 사람 주소

# 초기화
mail.init_app(app)

# CORS
CORS(app, expose_headers=["Content-Disposition"])

# ✅ Blueprint 등록
register_blueprints(app)

@app.route('/')
def home():
    return "Hello, Flask API!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

from flask import Flask
from flask_cors import CORS
from routes import register_blueprints  # 📌 Blueprint 등록 함수 가져오기

app = Flask(__name__)
CORS(app)  # CORS 설정 (React에서 API 호출 가능)

# 📌 모든 Blueprint 한 번에 등록
register_blueprints(app)

@app.route('/')
def home():
    return "Hello, Flask API!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

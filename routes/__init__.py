from flask import Blueprint

# 📌 Blueprint 모듈 가져오기
from .files import files_bp
from .customers import customers_bp
from .timeline import timeline_bp
from .contract import contract_bp

# 📌 Blueprint 등록
def register_blueprints(app):
    app.register_blueprint(files_bp)      # 파일 관련 API 등록
    app.register_blueprint(customers_bp)  # 고객 관련 API 등록
    app.register_blueprint(timeline_bp)  # 타임라인 관련 API 등록
    app.register_blueprint(contract_bp)  # 계약 관련 API 등록

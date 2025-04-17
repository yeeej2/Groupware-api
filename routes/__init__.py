from flask import Blueprint

# 📌 Blueprint 모듈 가져오기
from .files import files_bp
from .customers import customers_bp
from .timeline import timeline_bp
from .contract import contract_bp
from .htmlToPdf import htmlToPdf_bp
from .email import email_bp
from .approval import approval_bp
from .users import users_bp
from .estimate import estimate_bp
from .products import products_bp
from .login import login_bp
from .excel import excel_bp
from .contractReivew import contractReivew_bp

# 📌 Blueprint 등록
def register_blueprints(app):
    app.register_blueprint(files_bp)      # 파일 관련 API 등록
    app.register_blueprint(customers_bp)  # 고객 관련 API 등록
    app.register_blueprint(timeline_bp)  # 타임라인 관련 API 등록
    app.register_blueprint(contract_bp)  # 계약 관련 API 등록
    app.register_blueprint(htmlToPdf_bp)  # 문서 관련 API 등록
    app.register_blueprint(email_bp)  # 이메일 관련 API 등록
    app.register_blueprint(approval_bp)  # 결재요청 관련 API 등록
    app.register_blueprint(users_bp)  # 사용자 관련 API 등록
    app.register_blueprint(estimate_bp)  # 견적 관련 API 등록
    app.register_blueprint(products_bp)  # 제품 관련 API 등록
    app.register_blueprint(login_bp)  # 로그인 관련 API 등록
    app.register_blueprint(excel_bp)  # 엑셀 관련 API 등록
    app.register_blueprint(contractReivew_bp)  # 계약검토서 관련 API 등록

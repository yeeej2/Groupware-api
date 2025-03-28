import os
import logging
from flask import Blueprint, request, jsonify, send_file
from jinja2 import Environment, FileSystemLoader
import pdfkit
from models.database import get_db_connection

from flask import render_template

import os

config = pdfkit.configuration(wkhtmltopdf='/usr/local/bin/wkhtmltopdf')  # 실제 경로 확인 필요

htmlToPdf_bp = Blueprint('htmlToPdf', __name__)

TEMPLATE_PATH = os.path.join(os.getcwd(), 'templates')  # 템플릿 폴더
PDF_OUTPUT_PATH = os.path.join(os.getcwd(), 'temp')
os.makedirs(PDF_OUTPUT_PATH, exist_ok=True)


@htmlToPdf_bp.route('/generate_pdf/<doc_type>/<int:doc_id>', methods=['GET'])
def generate_pdf(doc_type, doc_id):
    logging.info("미리보기 들어옴~~~~~~~~~~~~~~~~~~")

    include_logo = request.args.get('includeLogo', 'true') == 'true'
    include_signature  = request.args.get('includeSignature', 'true') == 'true'

    try:
        # 1. DB 연결 + 견적서 데이터 조회
        conn = get_db_connection()
        cursor = conn.cursor()

        if doc_type == 'estimate':
            cursor.execute("SELECT * FROM t_estimate WHERE id = %s", (doc_id,))
            template_name = 'estimate_template.html'
            pdf_filename = f'estimate_{doc_id}.pdf'
        elif doc_type == 'contract':
            cursor.execute("SELECT * FROM contract WHERE contract_id = %s", (doc_id,))
            template_name = 'contract_template.html'
            pdf_filename = f'contract_{doc_id}.pdf'
        else:
            return jsonify({'error': '지원되지 않는 문서 유형입니다.'}), 400
        

        data  = cursor.fetchone()
        cursor.close()
        conn.close()

        if not data :
            return jsonify({'error': '문서를 찾을 수 없습니다.'}), 404

        # 2. Jinja2 HTML 템플릿 렌더링
        env = Environment(loader=FileSystemLoader(TEMPLATE_PATH))
        #template = env.get_template(template_name)
        logo_path = "file:///usr/local/flask/yeji/groupware-api/static/logo.png"
        sign_path = "file:///usr/local/flask/yeji/groupware-api/static/sign.png"
        rendered = render_template(template_name, **data, include_logo=include_logo, include_signature=include_signature, logo_path=logo_path, sign_path=sign_path)

        # 3. PDF 생성
        output_path = os.path.join(PDF_OUTPUT_PATH, pdf_filename)
        #####pdfkit.from_string(rendered, '/tmp/output.pdf', configuration=config)
        #####pdfkit.from_string(rendered, output_path)
        pdfkit.from_string(
                rendered,
                output_path,
                configuration=config,
                options={
                    'enable-local-file-access': None,  # 로컬 파일 접근 허용 (이미지 경로용)
                    'encoding': 'UTF-8'                 # 한글 깨짐 방지
                }
            )
        
        logging.info("출력 시작")
        print(rendered)  # 또는 logging.info(rendered)
        logging.info("출력 끝")


        logging.info("data 시작")
        print(data)
        logging.info("data 끝")

        return jsonify({'status': 'success'})

    except Exception as e:
        logging.exception("PDF 생성 실패")
        return jsonify({'error': str(e)}), 500
    








@htmlToPdf_bp.route('/preview_pdf/<doc_type>/<int:doc_id>', methods=['GET'])
def preview_pdf(doc_type, doc_id):
    logging.info("emfdjdha???????????????????????");
    filename = f"{doc_type}_{doc_id}.pdf"
    filepath = os.path.join(PDF_OUTPUT_PATH, filename)

    if os.path.exists(filepath):
        return send_file(filepath, mimetype='application/pdf')
    else:
        return jsonify({'error': 'PDF 파일이 존재하지 않습니다.'}), 404
    





@htmlToPdf_bp.route('/download_pdf', methods=['GET'])
def download_pdf():
    logging.info("들어왔니!!!!! 다운로드~~~~")
    doc_type = request.args.get('doc_type')
    doc_id = request.args.get('doc_id')
    if not doc_type or not doc_id:
        return 'Missing parameters', 400

    # 파일 이름 구성 (generate_pdf랑 동일하게!)
    pdf_filename = f'{doc_type}_{doc_id}.pdf'
    pdf_path = os.path.join(PDF_OUTPUT_PATH, pdf_filename)

    if not os.path.exists(pdf_path):
        return '파일을 찾을 수 없습니다.', 404

    return send_file(pdf_path, as_attachment=True)



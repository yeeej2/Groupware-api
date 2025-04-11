import os
import logging
from flask import Blueprint, request, jsonify, send_file
from jinja2 import Environment, FileSystemLoader
import pdfkit
from models.database import get_db_connection
from datetime import datetime

from flask import render_template

import os

config = pdfkit.configuration(wkhtmltopdf='/usr/local/bin/wkhtmltopdf')  # 실제 경로 확인 필요

htmlToPdf_bp = Blueprint('htmlToPdf', __name__)

TEMPLATE_PATH = os.path.join(os.getcwd(), 'templates')  # 템플릿 폴더
PDF_OUTPUT_PATH = os.path.join(os.getcwd(), 'temp')
os.makedirs(PDF_OUTPUT_PATH, exist_ok=True)


@htmlToPdf_bp.route('/generate_pdf/<doc_type>/<int:doc_id>', methods=['GET'])
def generate_pdf(doc_type, doc_id):
    logging.info("PDF 생성 요청 수신")

    include_logo = request.args.get('includeLogo', 'true') == 'true'
    include_signature = request.args.get('includeSignature', 'true') == 'true'

    try:
        # 1. DB 연결 + 데이터 조회
        conn = get_db_connection()
        cursor = conn.cursor()

        if doc_type == 'estimate':
            # 견적서 기본 정보 및 고객/영업 정보 조회
            sql_estimate = """
            SELECT 
                e.id AS estimate_id,
                e.quote_id,
                e.quote_title,
                e.customer_id,
                c.customer_nm,
                c.tel_no AS customer_tel,
                c.address1 AS customer_address1,
                c.address2 AS customer_address2,
                c.address3 AS customer_address3,
                e.sales_id,
                u.name ,
                u.email ,
                u.phone ,
                u.position , 
                e.total_price_before_vat,
                e.vat,
                e.total_price_with_vat,
                DATE_FORMAT(e.valid_until, '%%Y년 %%m월 %%d일') AS valid_until,
                e.delivery_condition,
                e.payment_condition,
                e.warranty_period,
                e.remarks,
                e.opinion,
                e.memo,
                e.unty_file_no,
                e.quote_amount
            FROM estimate e
            LEFT JOIN customer c ON e.customer_id = c.customer_id
            LEFT JOIN user u ON e.sales_id = u.usr_id
            WHERE e.id = %s
            """
            cursor.execute(sql_estimate, (doc_id,))
            estimate = cursor.fetchone()

            if not estimate:
                return jsonify({'error': '견적서를 찾을 수 없습니다.'}), 404

            # 제품 목록 조회
            sql_products = """
            SELECT 
                p.id,
                p.p_name,
                p.p_description,
                p.p_price,
                ep.quantity,
                ep.unit_price,
                ep.total_price,
                ep.final_price 
            FROM t_estimate_product ep
            JOIN t_product_add p ON ep.product_id = p.id
            WHERE ep.estimate_id = %s
            """
            cursor.execute(sql_products, (doc_id,))
            products = cursor.fetchall()

            # 참조자 정보 조회
            sql_references = """
            SELECT 
                er.manager_id,
                er.manager_name,
                er.manager_email,
                er.tel_no,
                er.position
            FROM estimate_reference er
            WHERE er.estimate_id = %s
            """
            cursor.execute(sql_references, (doc_id,))
            references = cursor.fetchall()

            # `quote_amount`를 한글로 변환
            def convert_to_korean_currency(amount):
                if not amount or amount <= 0:
                    return "영원"
                
                units = ["", "십", "백", "천"]
                large_units = ["", "만", "억", "조"]
                nums = ["영", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]

                result = []
                num_str = str(int(amount))
                length = len(num_str)

                for i, digit in enumerate(num_str):
                    if digit != "0":
                        unit_idx = (length - i - 1) % 4  # 천, 백, 십, 일 단위
                        large_unit_idx = (length - i - 1) // 4  # 만, 억, 조 단위
                        result.append(nums[int(digit)] + units[unit_idx])
                        if unit_idx == 0:  # 일의 자리에서 큰 단위 추가
                            result.append(large_units[large_unit_idx])

                return "".join(result) + "원"

            total_price_korean = convert_to_korean_currency(estimate["total_price_with_vat"])

            today = datetime.today()
            formatted = today.strftime("%Y년 %m월 %d일")

            # 템플릿에 전달할 데이터 구성
            data = {
                "estimate": estimate,
                "items": products,
                "total_price_korean": total_price_korean,
                "date" : formatted,
                "references": references,
            }

            template_name = 'estimate_template.html'
            pdf_filename = f'estimate_{doc_id}.pdf'

        elif doc_type == 'contract':
            cursor.execute("SELECT * FROM contract WHERE contract_id = %s", (doc_id,))
            data = cursor.fetchone()
            if not data:
                return jsonify({'error': '계약서를 찾을 수 없습니다.'}), 404

            template_name = 'contract_template.html'
            pdf_filename = f'contract_{doc_id}.pdf'

        else:
            return jsonify({'error': '지원되지 않는 문서 유형입니다.'}), 400

        cursor.close()
        conn.close()

        # 2. Jinja2 HTML 템플릿 렌더링
        env = Environment(loader=FileSystemLoader(TEMPLATE_PATH))
        logo_path = "file:///usr/local/flask/yeji/groupware-api/static/logo.png"
        sign_path = "file:///usr/local/flask/yeji/groupware-api/static/sign.png"
        rendered = render_template(
            template_name,
            **data,
            include_logo=include_logo,
            include_signature=include_signature,
            logo_path=logo_path,
            sign_path=sign_path
        )

        # 3. PDF 생성
        output_path = os.path.join(PDF_OUTPUT_PATH, pdf_filename)
        pdfkit.from_string(
            rendered,
            output_path,
            configuration=config,
            options={
                'enable-local-file-access': None,  # 로컬 파일 접근 허용 (이미지 경로용)
                'encoding': 'UTF-8'  # 한글 깨짐 방지
            }
        )

        logging.info("PDF 생성 완료")
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



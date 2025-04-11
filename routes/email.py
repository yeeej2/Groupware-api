from flask import Blueprint, request, jsonify, current_app
from flask_mail import Message
import logging #로그 남기기
from extensions import mail  # ✅ 이렇게!

import os


# 📌 Blueprint 생성
email_bp = Blueprint('email', __name__)


PDF_OUTPUT_PATH = '/usr/local/flask/yeji/groupware-api/temp'

@email_bp.route('/send_email', methods=['POST'])
def send_email():
    data = request.get_json()
    to = data.get('to')
    cc = data.get('cc')
    subject = data.get('subject')
    body = data.get('body')
    logging.info(data)

    doc_type = data.get('documentType')
    doc_id = data.get('documentId')

    # PDF 파일 경로 구성
    pdf_filename = f"{doc_type}_{doc_id}.pdf"
    pdf_path = os.path.join(PDF_OUTPUT_PATH, pdf_filename)

    logging.info(pdf_filename)
    logging.info(pdf_path)

    if not os.path.exists(pdf_path):
        return jsonify({'error': 'PDF 파일이 존재하지 않습니다.'}), 404

    try:
        msg = Message(subject=subject, sender='yeji0045@itsin.co.kr', recipients=[to])
        if cc:
            msg.cc = [cc]
        msg.body = body or ""

        with open(pdf_path, 'rb') as f:
            msg.attach(pdf_filename, 'application/pdf', f.read())
        logging.info("send 완전 직전")
        aaa = mail.send(msg)
        logging.info("send 완료")
        logging.info(aaa)


        logging.info("끝?????")
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

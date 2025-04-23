from flask import Blueprint, request, jsonify, current_app
from flask_mail import Message
import logging #로그 남기기
from extensions import mail  # ✅ 이렇게!
import pdb
from datetime import datetime

import os


# 📌 Blueprint 생성
email_bp = Blueprint('email', __name__)

from auth.decorators import require_token
@email_bp.before_request
@require_token
def require_token_for_user_bp():
    pass




PDF_OUTPUT_PATH = '/usr/local/flask/yeji/groupware-api/temp'

@email_bp.route('/send_email', methods=['POST'])
def send_email():
    try:
        # 📌 요청 데이터
        to = request.form.get('to')
        cc = request.form.get('cc')
        subject = request.form.get('subject')
        body = request.form.get('body')
        doc_type = request.form.get('documentType')  # estimate, contract 등
        doc_id = request.form.get('documentId')

        logging.info(f"이메일 발송 요청 - to: {to}, subject: {subject}, doc_type: {doc_type}, doc_id: {doc_id}")

        # ✅ 수신자 이메일 검증
        if not to:
            return jsonify({'error': '수신자 이메일(to)은 최소 1개 이상이어야 합니다.'}), 400

        # 쉼표로 구분된 이메일 문자열을 리스트로 변환
        to_list = [email.strip() for email in to.split(',') if email.strip()]
        cc_list = [email.strip() for email in cc.split(',') if email.strip()] if cc else []

        # 📩 이메일 메시지 생성
        msg = Message(subject=subject, sender='admin@itsin.co.kr', recipients=to_list)
        if cc_list:
            msg.cc = cc_list
        msg.body = body or ""

        # ✅ 첨부된 파일 이름 미리 수집
        uploaded_filenames = [
            file.filename for file in request.files.getlist('attachments')
        ] if 'attachments' in request.files else []

        # 📎 1. 프론트에서 직접 업로드한 첨부파일 추가
        if 'attachments' in request.files:
            for file in request.files.getlist('attachments'):
                file_content = file.read()
                content_type = file.content_type or "application/octet-stream"
                msg.attach(file.filename, content_type, file_content)
                logging.info(f"사용자 업로드 첨부파일: {file.filename}")

        # # 📎 2. 서버에서 PDF 자동 첨부 (중복되지 않은 경우만)
        # if doc_type and doc_id:
        #     pdf_filename = f"{doc_type}_{doc_id}.pdf"
        #     pdf_path = os.path.join(PDF_OUTPUT_PATH, pdf_filename)

        #     if pdf_filename not in uploaded_filenames and os.path.exists(pdf_path):
        #         with open(pdf_path, "rb") as f:
        #             msg.attach(pdf_filename, "application/pdf", f.read())
        #             logging.info(f"자동 첨부된 PDF: {pdf_filename}")
        #     else:
        #         logging.info(f"PDF 중복 방지 또는 파일 없음: {pdf_filename}")

        # # 📎 3. 서버에서 Excel 자동 첨부 (중복되지 않은 경우만)
        # if doc_type == "estimate":
        #     pattern_prefix = f"estimate_{doc_id}_"
        #     matching_files = [
        #         f for f in os.listdir(PDF_OUTPUT_PATH)
        #         if f.startswith(pattern_prefix) and f.endswith(".xlsx")
        #     ]

        #     if matching_files:
        #         matching_files.sort(reverse=True)  # 최신 파일 우선
        #         excel_path = os.path.join(PDF_OUTPUT_PATH, matching_files[0])
        #         excel_filename = os.path.basename(excel_path)

        #         if excel_filename not in uploaded_filenames:
        #             with open(excel_path, "rb") as f:
        #                 msg.attach(
        #                     filename=excel_filename,
        #                     content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        #                     data=f.read()
        #                 )
        #                 logging.info(f"자동 첨부된 Excel: {excel_filename}")
        #         else:
        #             logging.info(f"Excel 중복 방지됨: {excel_filename}")
        #     else:
        #         logging.warning(f"Excel 파일 없음: {pattern_prefix}*.xlsx")

        # ✅ 이메일 전송
        logging.info("이메일 전송 중...")
        mail.send(msg)
        logging.info("이메일 전송 완료!")

        return jsonify({'status': 'ok'}), 200

    except Exception as e:
        logging.exception("이메일 전송 실패")
        return jsonify({'error': str(e)}), 500
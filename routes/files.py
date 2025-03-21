import os
import logging
import re  # 🔥 정규 표현식 모듈 추가
from flask import Blueprint, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from models.database import get_db_connection
import pdb  # Python Debugger
import uuid

# 📌 Blueprint 생성
files_bp = Blueprint('files', __name__)

# 파일 저장 폴더 설정
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

# 업로드 폴더가 없으면 생성
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 📌 한글 파일명을 유지하는 secure_filename 함수
def custom_secure_filename(filename):
    filename = filename.strip().replace(" ", "_")  # 공백을 _로 변환
    filename = re.sub(r"[^가-힣a-zA-Z0-9_.-]", "", filename)  # 한글, 영문, 숫자, `_`, `.`만 허용
    return filename







# 파일 업로드
@files_bp.route('/upload', methods=['POST'])
def upload_file():
    logging.info("🔥 파일 업로드 요청 도착!")

    files = request.files.getlist('file')
    untyFileNo = request.form.get("untyFileNo")  # FormData에서 가져오기

    logging.info("받아온 통합첨부파일==" + untyFileNo);
    max_file_seq = 1
    isNew = False  #완저 새로운 파일인지 체크
    unty_file_no = None


    # 📌 백엔드에서 UUID 생성
    if not untyFileNo: # untyFileNo 있음
        logging.info("untyFileNo 있음");
        unty_file_no = untyFileNo
        isNew = False
    else: # untyFileNo 없음
        logging.info("untyFileNo 없음");
        unty_file_no = str(uuid.uuid4())
        isNew = True

    if not files or len(files) == 0:
        logging.error("🚨 업로드된 파일이 없습니다.")
        return jsonify({"error": "No files uploaded"}), 400

    for file in files:
        if file.filename == '':
            logging.error("🚨 선택된 파일의 이름이 없습니다.")
            return jsonify({"error": "Invalid file name"}), 400

        # 📌 한글 파일명을 유지하면서 보안 처리
        filename = custom_secure_filename(file.filename)

        # 🔥 파일명이 비어 있지 않은지 확인
        if not filename:
            logging.error("🚨 파일명이 유효하지 않습니다.")
            return jsonify({"error": "Invalid file name"}), 400

        # 📌 파일 저장 경로 (디렉토리 + 파일명 포함!)
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        # 🔍 디버깅용 로그 (파일 저장 경로 확인)
        logging.info(f"📁 저장할 파일 경로: {file_path}")

        # 📌 디렉토리가 없으면 자동 생성
        if not os.path.exists(UPLOAD_FOLDER):
            logging.info(f"📂 업로드 폴더 생성: {UPLOAD_FOLDER}")
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # 📌 파일 저장 (파일명이 포함된 경로여야 함)
        try:
            file.save(file_path)
        except Exception as e:
            logging.error(f"🚨 파일 저장 중 오류 발생: {e}")
            return jsonify({"error": "File save failed", "details": str(e)}), 500

        # 📌 DB에 파일 정보 저장
        conn = get_db_connection()
        cursor = conn.cursor()
        if isNew: # 완전 새로운 파일
            cursor.execute("INSERT INTO files (file_name, file_path, unty_file_no, file_seq) VALUES (%s, %s, %s, %s)", (filename, file_path, unty_file_no, max_file_seq))
        else: # untyFileNo 없음
            # 📌 같은 `unty_file_no` 그룹에서 가장 큰 `file_seq` 찾기
            cursor.execute("SELECT COALESCE(MAX(file_seq), 1) FROM files WHERE unty_file_no = %s", (unty_file_no,))
            max_file_seq = cursor.fetchone()["COALESCE(MAX(file_seq), 1)"]
            cursor.execute("INSERT INTO files (file_name, file_path, unty_file_no, file_seq) VALUES (%s, %s, %s, %s)", (filename, file_path, unty_file_no, max_file_seq))
            
        conn.commit()
        conn.close()
        max_file_seq = max_file_seq + 1
        

    return jsonify({"message": "Files uploaded successfully", "untyFileNo": unty_file_no})










# 저장된 파일 리스트 조회 API
@files_bp.route('/files/<untyfileno>', methods=['GET'])
def get_files(untyfileno):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files WHERE unty_file_no = %s", (untyfileno,))
    files = cursor.fetchall()
    conn.close()
    file_list = [{"id": row["file_id"], "file_name": row["file_name"], "file_path": row["file_path"]} for row in files]
    return jsonify(file_list)






# 📌 특정 통합첨부파일번호(`untyFileNo`)에 속한 모든 파일 다운로드 API
@files_bp.route('/download/<untyFileNo>', methods=['GET'])
def download_files(untyFileNo):
    logging.info(f"📥 파일 다운로드 요청 - 통합첨부파일번호: {untyFileNo}")

    # 📌 DB에서 해당 `untyFileNo`에 해당하는 파일 목록 조회
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_name FROM files WHERE unty_file_no = %s", (untyFileNo,))
    files = cursor.fetchall()
    conn.close()

    if not files:
        logging.warning(f"⚠️ 해당 통합첨부파일번호({untyFileNo})에 대한 파일이 없습니다.")
        return jsonify({"error": "No files found for this untyFileNo" , "files": []}), 404

    # 📌 파일 목록을 JSON 응답으로 반환 (프론트엔드에서 개별 다운로드)
    file_list = [file["file_name"] for file in files]
    return jsonify({"files": file_list})

# 📌 개별 파일 다운로드 API
@files_bp.route('/download/file/<filename>', methods=['GET'])
def download_file(filename):
    logging.info(f"📥 개별 파일 다운로드 요청: {filename}")

    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        logging.error(f"🚨 파일이 존재하지 않음: {filename}")
        return jsonify({"error": "File not found"}), 404  # ✅ JSON 응답 반환

    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)





# 📌 특정 파일 삭제 API
@files_bp.route('/delete/<fileId>', methods=['DELETE'])
def delete_file(fileId):
    logging.info("fileId 해당 파일 삭제" + fileId)

    # 파일 정보 조회
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files WHERE file_id = %s", (fileId,))
    files = cursor.fetchall()
    conn.close()

    # 파일 정보 db에서 삭제
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM files WHERE file_Id = %s", (fileId,))
    conn.commit()
    conn.close()
    return jsonify({"message": f"{fileId} deleted successfully!"})
    


# TODO: 파일 id 로 처리
# TODO: 파일 바로 다운로드 말고 불러와서 프론트에서 다운로드
# TODO: 순서 재처리, 각 uuid 에 따라 순서 증가

    


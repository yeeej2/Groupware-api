import os
import logging
import re  # 🔥 정규 표현식 모듈 추가
from flask import Blueprint, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from models.database import get_db_connection
import pdb  # Python Debugger
import uuid
from urllib.parse import quote

# 📌 Blueprint 생성
files_bp = Blueprint('files', __name__)

from auth.decorators import require_token
@files_bp.before_request
@require_token
def require_token_for_user_bp():
    pass

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

    logging.info("받아온 통합첨부파일 == " + str(untyFileNo))
    max_file_seq = 1
    isNew = False
    unty_file_no = None

    if not untyFileNo or untyFileNo == "null":
        logging.info("📌 새로운 untyFileNo 생성")
        unty_file_no = str(uuid.uuid4())
        isNew = True
    else:
        unty_file_no = untyFileNo
        isNew = False

    if not files or len(files) == 0:
        logging.error("🚨 업로드된 파일이 없습니다.")
        return jsonify({"error": "No files uploaded"}), 400

    for file in files:
        if file.filename == '':
            logging.error("🚨 선택된 파일의 이름이 없습니다.")
            return jsonify({"error": "Invalid file name"}), 400

        # 🔥 원본 파일명 저장용 (한글 포함됨)
        original_name = file.filename

        # 🔧 확장자 추출
        _, ext = os.path.splitext(original_name)
        if not ext:
            logging.warning("❗ 확장자 없는 파일")
            ext = ""  # 확장자 없는 파일도 허용

        # ✅ 안전한 UUID 기반 파일명 생성 (확장자 유지)
        unique_filename = f"{str(uuid.uuid4())}{ext}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

        # 업로드 폴더 없으면 생성
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # 실제 파일 저장
        try:
            file.save(file_path)
            logging.info(f"📁 저장 완료: {file_path}")
        except Exception as e:
            logging.error(f"🚨 파일 저장 중 오류 발생: {e}")
            return jsonify({"error": "File save failed", "details": str(e)}), 500

        # DB에 파일 정보 저장
        conn = get_db_connection()
        cursor = conn.cursor()
        if isNew:
            cursor.execute("""
                INSERT INTO files (file_name, unique_file_name, file_path, unty_file_no, file_seq)
                VALUES (%s, %s, %s, %s, %s)
            """, (original_name, unique_filename, file_path, unty_file_no, max_file_seq))
        else:
            cursor.execute("SELECT COALESCE(MAX(file_seq), 1) FROM files WHERE unty_file_no = %s", (unty_file_no,))
            max_file_seq = cursor.fetchone()["COALESCE(MAX(file_seq), 1)"]
            cursor.execute("""
                INSERT INTO files (file_name, unique_file_name, file_path, unty_file_no, file_seq)
                VALUES (%s, %s, %s, %s, %s)
            """, (original_name, unique_filename, file_path, unty_file_no, max_file_seq))

        conn.commit()
        conn.close()
        max_file_seq += 1

    return jsonify({"message": "Files uploaded successfully", "untyFileNo": unty_file_no})










@files_bp.route('/files/<untyfileno>', methods=['GET'])
def get_files(untyfileno):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT file_id, file_name, unique_file_name FROM files WHERE unty_file_no = %s
    """, (untyfileno,))
    files = cursor.fetchall()
    conn.close()

    file_list = [
        {
            "id": row["file_id"],
            "file_name": row["file_name"],
            "unique_file_name": row["unique_file_name"]
        } for row in files
    ]
    return jsonify(file_list)







# 📌 특정 통합첨부파일번호(`untyFileNo`)에 속한 모든 파일 다운로드 API
@files_bp.route('/download/<untyFileNo>', methods=['GET'])
def download_files(untyFileNo):
    logging.info(f"📥 파일 다운로드 요청 - 통합첨부파일번호: {untyFileNo}")

    # 📌 DB에서 해당 `untyFileNo`에 해당하는 파일 목록 조회
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_id FROM files WHERE unty_file_no = %s", (untyFileNo,))
    files = cursor.fetchall()
    conn.close()

    if not files:
        logging.warning(f"⚠️ 해당 통합첨부파일번호({untyFileNo})에 대한 파일이 없습니다.")
        return jsonify({"error": "No files found for this untyFileNo" , "files": []}), 404

    # 📌 파일 목록을 JSON 응답으로 반환 (프론트엔드에서 개별 다운로드)
    file_list = [file["file_id"] for file in files]
    return jsonify({"files": file_list})



@files_bp.route('/download/file/<int:fileId>', methods=['GET'])
def download_file(fileId):
    logging.info(f"📥 개별 파일 다운로드 요청: {fileId}")

    # DB 조회
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT file_name, unique_file_name FROM files WHERE file_id = %s
    """, (fileId,))
    file = cursor.fetchone()
    conn.close()

    logging.info(f"📥 DB 조회 결과: {file}")

    if not file:
        logging.error(f"🚨 파일이 존재하지 않음: {fileId}")
        return jsonify({"error": "File not found"}), 404

    try:
        # 파일이 실제 존재하는지 확인
        file_path = os.path.join(UPLOAD_FOLDER, file["unique_file_name"])
        if not os.path.exists(file_path):
            logging.error("🚨 실제 파일이 서버에 존재하지 않음!")
            return jsonify({"error": "Physical file not found"}), 404

        original_name = file["file_name"] or "downloaded_file.xls"
        response = send_from_directory(
            UPLOAD_FOLDER,
            file["unique_file_name"],
            as_attachment=True,
            mimetype="application/octet-stream"
        )

        # ❌ filename="..." 생략하고
        # ✅ filename*=UTF-8''만 사용
        cd_value = f"attachment; filename*=UTF-8''{quote(original_name)}"
        response.headers["Content-Disposition"] = cd_value
        return response

    except Exception as e:
        logging.exception("❌ 파일 다운로드 처리 중 예외 발생")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500









@files_bp.route('/delete/<int:fileId>', methods=['DELETE'])
def delete_file(fileId):
    logging.info(f"파일 삭제 요청: {fileId}")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT unique_file_name FROM files WHERE file_id = %s", (fileId,))
    file = cursor.fetchone()

    if not file:
        conn.close()
        return jsonify({"error": "File not found"}), 404

    unique_file_name = file["unique_file_name"]
    file_path = os.path.join(UPLOAD_FOLDER, unique_file_name)

    # 실제 파일 삭제
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            logging.error(f"🚨 파일 삭제 중 오류 발생: {e}")
            return jsonify({"error": "File deletion failed", "details": str(e)}), 500

    # DB에서 삭제
    cursor.execute("DELETE FROM files WHERE file_id = %s", (fileId,))
    conn.commit()
    conn.close()

    return jsonify({"message": f"{fileId} deleted successfully!"})

    


# TODO: 파일 id 로 처리
# TODO: 파일 바로 다운로드 말고 불러와서 프론트에서 다운로드
# TODO: 순서 재처리, 각 uuid 에 따라 순서 증가

    
















@files_bp.route('/files/copy/<untyFileNo>', methods=['POST'])
def copy_files(untyFileNo):
    """
    통합 첨부 파일 번호(untyFileNo)에 해당하는 파일들을 복사하고,
    새로운 통합 첨부 파일 번호를 생성하여 반환하는 API
    """
    logging.info(f"📋 파일 복사 요청 - 통합첨부파일번호: {untyFileNo}")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1) 기존 untyFileNo에 해당하는 파일 목록 조회
        cursor.execute("""
            SELECT file_name, unique_file_name, file_path
            FROM files
            WHERE unty_file_no = %s
        """, (untyFileNo,))
        files = cursor.fetchall()

        if not files:
            logging.warning(f"⚠️ 해당 통합첨부파일번호({untyFileNo})에 대한 파일이 없습니다.")
            return jsonify({"error": "No files found for this untyFileNo"}), 404

        # 2) 새로운 통합 첨부 파일 번호 생성
        new_unty_file_no = str(uuid.uuid4())
        logging.info(f"📌 새로운 통합첨부파일번호 생성: {new_unty_file_no}")

        # 3) 파일 복사 및 DB에 새로운 파일 정보 저장
        for file in files:
            original_name = file["file_name"]
            unique_file_name = file["unique_file_name"]
            original_file_path = file["file_path"]

            # 새로운 파일명 생성
            _, ext = os.path.splitext(unique_file_name)
            new_unique_file_name = f"{str(uuid.uuid4())}{ext}"
            new_file_path = os.path.join(UPLOAD_FOLDER, new_unique_file_name)

            # 파일 복사
            try:
                with open(original_file_path, 'rb') as src_file:
                    with open(new_file_path, 'wb') as dest_file:
                        dest_file.write(src_file.read())
                logging.info(f"📁 파일 복사 완료: {original_file_path} -> {new_file_path}")
            except Exception as e:
                logging.error(f"🚨 파일 복사 중 오류 발생: {e}")
                return jsonify({"error": "File copy failed", "details": str(e)}), 500

            # DB에 새로운 파일 정보 저장
            cursor.execute("""
                INSERT INTO files (file_name, unique_file_name, file_path, unty_file_no, file_seq)
                VALUES (%s, %s, %s, %s, %s)
            """, (original_name, new_unique_file_name, new_file_path, new_unty_file_no, 1))  # file_seq는 1로 초기화

        # DB 커밋
        conn.commit()

        # 4) 새로운 통합 첨부 파일 번호 반환
        return jsonify({"message": "Files copied successfully", "new_untyFileNo": new_unty_file_no}), 200

    except Exception as e:
        conn.rollback()
        logging.error(f"🚨 파일 복사 처리 중 오류 발생: {e}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

    finally:
        conn.close()

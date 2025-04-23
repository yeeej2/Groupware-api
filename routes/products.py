from models.database import get_db_connection
from flask import Blueprint, request, jsonify
import os
import logging
from werkzeug.utils import secure_filename
from flask import send_from_directory


# 📌 Blueprint 생성
products_bp = Blueprint('products', __name__)

from auth.decorators import require_token
@products_bp.before_request
@require_token
def require_token_for_user_bp():
    pass

# 이미지 업로드 경로
UPLOAD_FOLDER = '/var/www/html/ERD/image'  # 실제 업로드 경로
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# 업로드 폴더 생성
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 📌 제품 등록 API
@products_bp.route('/api/products', methods=['POST'])
def create_product():
    """
    제품 등록 API
    """
    logging.info("=== [POST] /api/products 요청 수신 ===")
    logging.debug(f"Headers: {dict(request.headers)}")
    logging.debug(f"Form Data: {request.form.to_dict()}")
    logging.debug(f"Files: {request.files.to_dict()}")

    # 1) 폼 데이터 추출
    vendor = request.form.get('p_vendor')
    product_name = request.form.get('p_name')
    price = request.form.get('p_price')
    fw_throughput = request.form.get('fwThroughput')
    ips_throughput = request.form.get('ipsThroughput')

    # 2) 이미지 파일 처리
    image = request.files.get('image')
    if not image or not image.filename:
        logging.error("이미지 파일이 포함되지 않거나 파일명이 없음")
        return jsonify({"success": False, "error": "No image file or filename"}), 400

    _, ext = os.path.splitext(image.filename)  # 확장자 추출(.png, .jpg 등)
    if not ext:  # 확장자가 없는 경우 처리
        logging.error("이미지 파일에 확장자가 없음")
        return jsonify({"success": False, "error": "Invalid image file extension"}), 400

    safe_product_name = secure_filename(product_name or "default_product")  # 기본값 설정
    filename = safe_product_name + ext
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    web_path = f"/image/{filename}"

    # 3) 이미지 저장
    try:
        image.save(save_path)
        logging.info(f"이미지 저장 완료: {save_path}")
    except Exception as e:
        logging.error(f"이미지 저장 실패: {e}")
        return jsonify({"success": False, "error": "Failed to save image"}), 500

    # 4) 데이터베이스 삽입
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = """
        INSERT INTO t_product_add (
            p_name, p_vendor, p_imgpath, p_price, p_FWThrouput, p_IPSThrouput
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (product_name, vendor, web_path, price, fw_throughput, ips_throughput))
        conn.commit()
        logging.info("DB INSERT 성공")
    except Exception as e:
        logging.error(f"DB Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

    logging.info("=== [POST] /api/products 처리 완료 ===")
    return jsonify({"success": True, "message": "제품이 성공적으로 등록되었습니다."}), 201


# 📌 제품 수정 API
@products_bp.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """
    제품 수정 API
    """
    logging.info(f"=== [PUT] /api/products/{product_id} 요청 수신 ===")
    logging.debug(f"Headers: {dict(request.headers)}")
    logging.debug(f"Form Data: {request.form.to_dict()}")
    logging.debug(f"Files: {request.files.to_dict()}")

    try:
        # 요청 데이터 처리
        vendor = request.form.get('p_vendor')
        product_name = request.form.get('p_name')
        price = request.form.get('p_price')
        fw_throughput = request.form.get('fwThroughput')
        ips_throughput = request.form.get('ipsThroughput')
        description = request.form.get('p_description')

        # 1) 이미지 파일 처리
        image = request.files.get('image')
        file_path = None

        if image and image.filename:
            _, ext = os.path.splitext(image.filename)  # 확장자 추출(.png, .jpg 등)
            if not ext:  # 확장자가 없는 경우 처리
                logging.error("이미지 파일에 확장자가 없음")
                return jsonify({"success": False, "error": "Invalid image file extension"}), 400

            safe_product_name = secure_filename(product_name or "default_product")  # 기본값 설정
            filename = safe_product_name + ext
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            web_path = f"/image/{filename}"

            # 이미지 저장
            try:
                image.save(file_path)
                logging.info(f"이미지 저장 완료: {file_path}")
            except Exception as e:
                logging.error(f"이미지 저장 실패: {e}")
                return jsonify({"success": False, "error": "Failed to save image"}), 500
        else:
            # 이미지가 업로드되지 않은 경우 기존 경로 유지
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT p_imgpath FROM t_product_add WHERE id = %s", (product_id,))
            existing_image = cursor.fetchone()
            if existing_image:
                web_path = existing_image[0]
            else:
                logging.warning("기존 이미지를 찾을 수 없음")
                web_path = None

        # 2) 데이터베이스 업데이트
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = """
        UPDATE t_product_add
        SET 
            p_name = %s,
            p_vendor = %s,
            p_imgpath = %s,
            p_price = %s,
            p_FWThrouput = %s,
            p_IPSThrouput = %s,
            p_description = %s
        WHERE id = %s
        """
        cursor.execute(sql, (
            product_name,
            vendor,
            web_path,
            price,
            fw_throughput,
            ips_throughput,
            description,
            product_id
        ))
        conn.commit()
        logging.info("DB UPDATE 성공")
        return jsonify({"success": True, "message": "제품이 성공적으로 수정되었습니다."}), 200

    except Exception as e:
        logging.error(f"Error updating product: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        conn.close()


@products_bp.route('/api/products', methods=['GET'])
def get_products():
    """
    제품 목록 조회 API
    """
    try:
        # 검색 조건 처리
        search_query = request.args.get('searchQuery', '')
        vendor = request.args.get('vendor', None)
        page = request.args.get('page', 1, type=int)
        limit = 12
        offset = (page - 1) * limit

        # 기본 쿼리
        sql = """
        SELECT 
            id, p_name, p_vendor, p_imgpath, p_price, p_FWThrouput, p_IPSThrouput, p_description
        FROM t_product_add
        WHERE 1=1
        """
        params = []

        # 검색 조건 추가
        if search_query:
            sql += " AND p_name LIKE %s"
            params.append(f"%{search_query}%")
        if vendor:
            sql += " AND p_vendor = %s"
            params.append(vendor)

        # 정렬 및 페이징
        sql += " ORDER BY id DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        logging.info(f"Executing SQL: {sql} with params: {params}")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        products = cursor.fetchall()
        logging.info(f"여기 넘어감?????")

        if not products:
            logging.warning("No products found for the given query.")
            products = []

        # 총 개수 조회
        count_sql = "SELECT COUNT(*) FROM t_product_add WHERE 1=1"
        count_params = []

        if search_query:
            count_sql += " AND p_name LIKE %s"
            count_params.append(f"%{search_query}%")
        if vendor:
            count_sql += " AND p_vendor = %s"
            count_params.append(vendor)

        logging.info(f"Executing Count SQL: {count_sql} with params: {count_params}")
        cursor.execute(count_sql, count_params)
        total_count = cursor.fetchone()
        logging.info(f"total_count{total_count}")

        if total_count is None:
            logging.warning("Total count query returned None. Setting total_count to 0.")
            total_count = 0
        else:
            logging.info(f"설마여기????")
            total_count = total_count['COUNT(*)']  # 딕셔너리 키를 사용해 접근
            logging.info(f"ㄴㄴㄴ????")

        return jsonify({"success": True, "products": products, "totalCount": total_count}), 200

    except Exception as e:
        logging.error(f"Error fetching products: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        conn.close()


@products_bp.route('/api/products/<int:product_id>', methods=['GET'])
def get_product_detail(product_id):
    logging.info("들어오김함??")
    """
    제품 상세 조회 API
    """
    try:
        # 데이터 조회
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = """
        SELECT 
            id, p_name, p_vendor, p_imgpath AS imagePath, p_price, p_FWThrouput, p_IPSThrouput, p_description
        FROM t_product_add
        WHERE id = %s
        """

        logging.info("dkdjdjdjkdsdkjdkjsdjklsdfjkldjklsfdjklsdfjkl")
        logging.info(sql)
        cursor.execute(sql, (product_id,))
        product = cursor.fetchone()

        if not product:
            return jsonify({"success": False, "error": "제품을 찾을 수 없습니다."}), 404

        return jsonify({"success": True, "data": product}), 200

    except Exception as e:
        logging.error(f"Error fetching product detail: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        conn.close()







# @products_bp.route('/image/<path:filename>') --> htmlToPdf.py 로 옮김!!! 2025.04.23 토큰 인증 때문에...


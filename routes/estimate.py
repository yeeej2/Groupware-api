from flask import Blueprint, request, jsonify
import pymysql
from models.database import get_db_connection
import logging
import json
from decimal import Decimal
from datetime import datetime

# 🔥 로깅 설정
logging.basicConfig(level=logging.DEBUG)

# 🔹 Blueprint 생성
estimate_bp = Blueprint('estimate', __name__)

# 🔹 snake_case → camelCase 변환 함수
def snake_to_camel(snake_str):
    parts = snake_str.split('_')
    return parts[0] + ''.join(word.capitalize() for word in parts[1:])

# 🔹 모든 키를 camelCase로 변환하는 함수
def convert_keys_to_camel_case(data):
    if isinstance(data, list):  # 리스트 처리
        return [convert_keys_to_camel_case(item) for item in data]
    elif isinstance(data, dict):  # 딕셔너리 처리
        return {snake_to_camel(k): v for k, v in data.items()}
    return data

# 🔹 JSON 변환 함수 (Decimal, datetime 변환)
def custom_json_converter(obj):
    if isinstance(obj, Decimal):  # Decimal → float 변환
        return float(obj)
    if isinstance(obj, datetime):  # datetime → 문자열 변환
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    return str(obj)






















@estimate_bp.route('/api/estimates/add', methods=['POST'])
def add_estimate():
    """
    새로운 견적 추가 API
    """
    data = request.json

    # 견적 정보
    quote_id = data.get('quote_id')
    quote_title = data.get('quote_title')
    customer_id = data.get('customer_id')
    sales_id = data.get('sales_id')
    valid_until = data.get('valid_until')
    delivery_condition = data.get('delivery_condition')
    payment_condition = data.get('payment_condition')
    warranty_period = data.get('warranty_period')
    remarks = data.get('remarks')
    opinion = data.get('opinion')
    memo = data.get('memo')
    quote_amount = data.get('quote_amount')
    unty_file_no = data.get('unty_file_no')  # 추가된 파일 번호

    total_price_before_vat = data.get('total_price_before_vat')
    vat = data.get('vat')
    total_price_with_vat = data.get('total_price_with_vat')

    # 제품 목록
    products = data.get('products', [])

    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            # 0) `quote_id` 자동 생성
            today = datetime.now().strftime('%Y%m%d')  # 현재 날짜 (YYYYMMDD)
            cursor.execute("SELECT COUNT(*) AS cnt FROM estimate WHERE quote_id LIKE %s", (f"ITS-{today}-%",))
            count = cursor.fetchone()["cnt"] + 1  # 오늘 날짜 기준으로 생성된 견적서 수 + 1
            quote_id = f"ITS-{today}-{count:03d}"  # ITS-YYYYMMDD-XXX 형식

            # 1) `estimate` 테이블에 데이터 삽입
            sql_estimate = """
            INSERT INTO estimate (
                quote_id, quote_title, customer_id, sales_id, valid_until,
                delivery_condition, payment_condition, warranty_period, remarks,
                opinion, memo, total_price_before_vat, vat, total_price_with_vat, quote_amount, unty_file_no
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql_estimate, (
                quote_id, quote_title, customer_id, sales_id, valid_until,
                delivery_condition, payment_condition, warranty_period, remarks,
                opinion, memo, total_price_before_vat, vat, total_price_with_vat, quote_amount, unty_file_no
            ))
            estimate_id = cursor.lastrowid

            # 2) `t_estimate_product` 테이블에 제품 데이터 삽입
            sql_product = """
            INSERT INTO t_estimate_product (
                estimate_id, product_id, quantity, unit_price, discount_rate,
                total_price, final_price
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            for product in products:
                product_id = product.get('product_id')
                quantity = product.get('quantity', 1)
                unit_price = product.get('unit_price', 0)
                discount_rate = product.get('discount_rate', 0)
                total_price = product.get('total_price', 0)
                final_price = product.get('final_price', 0)

                cursor.execute(sql_product, (
                    estimate_id, product_id, quantity, unit_price, discount_rate,
                    total_price, final_price
                ))

        conn.commit()
        return jsonify({"success": True, "estimate_id": estimate_id}), 201

    except Exception as e:
        conn.rollback()
        logging.error(f"Error adding estimate: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        conn.close()






























@estimate_bp.route('/api/estimates', methods=['GET'])
def get_estimates():
    """
    견적서 목록 조회 함수
    - estimate 테이블에서 모든 견적서를 조회
    """
    customer_nm = request.args.get('customerNmQuery', '')
    quote_title = request.args.get('quoteTitleQuery', '')
    quote_id = request.args.get('quoteIdQuery', '')
    sales_nm = request.args.get('salesNmQuery', '')
    status = request.args.get('statusQuery', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    logging.info("=== [GET] /api/estimates 요청 수신 ===")
    try:
        # 견적서 목록 조회 쿼리
        sql = """
        SELECT 
            DATE_FORMAT(e.valid_until, '%Y-%m-%d') AS valid_until,
            e.*,
            c.customer_nm,
            u.name AS sales_nm
        FROM estimate e
        LEFT JOIN customer c ON e.customer_id = c.customer_id
        LEFT JOIN user u ON e.sales_id = u.usr_id
        WHERE 1=1
        """
        if customer_nm:
            sql += f" AND c.customer_nm LIKE '%{customer_nm}%'"
        if quote_title:
            sql += f" AND e.quote_title LIKE '%{quote_title}%'"
        if quote_id:
            sql += f" AND e.quote_id LIKE '%{quote_id}%'"
        if sales_nm:
            sql += f" AND u.name LIKE '%{sales_nm}%'"
        if status:
            sql += f" AND e.remarks LIKE '%{status}%'"

        sql += f" ORDER BY e.id DESC"

        logging.info(sql);
        cursor.execute(sql)
        estimates = cursor.fetchall()

        return jsonify({"estimates": estimates})
    except Exception as e:
        logging.error(f"DB Error (견적 조회): {e}")
        return jsonify({"success": False, "error": str(e)}), 500





@estimate_bp.route('/api/estimates/<int:estimate_id>', methods=['GET'])
def get_estimate_detail(estimate_id):
    """
    특정 견적서 상세 조회 API
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1) `estimate` 테이블에서 견적서 기본 정보 조회
        sql_estimate = """
        SELECT 
            e.id AS estimate_id,
            e.quote_id,
            e.quote_title,
            e.customer_id,
            e.sales_id,
            DATE_FORMAT(e.valid_until, '%%Y-%%m-%%d') AS valid_until,
            e.delivery_condition,
            e.payment_condition,
            e.warranty_period,
            e.remarks,
            e.opinion,
            e.memo,
            e.total_price_before_vat,
            e.vat,
            e.total_price_with_vat,
            e.unty_file_no,  -- 추가된 파일 번호
            c.customer_nm,
            u.name AS sales_nm,
            e.quote_amount
        FROM estimate e
        LEFT JOIN customer c ON e.customer_id = c.customer_id
        LEFT JOIN user u ON e.sales_id = u.usr_id
        WHERE e.id = %s
        """
        cursor.execute(sql_estimate, (estimate_id,))
        estimate = cursor.fetchone()

        if not estimate:
            return jsonify({"success": False, "error": "견적서를 찾을 수 없습니다."}), 404

        # 2) `t_estimate_product` 테이블에서 제품 목록 조회
        sql_products = """
        SELECT 
            p.id,
            p.p_price,
            p.p_name,
            p.p_description,
            p.p_vendor AS vendor,
            ep.quantity,
            ep.unit_price,
            ep.discount_rate as discountRate,
            ep.total_price,
            ep.final_price
        FROM t_estimate_product ep
        JOIN t_product_add p ON ep.product_id = p.id
        WHERE ep.estimate_id = %s
        """
        cursor.execute(sql_products, (estimate_id,))
        products = cursor.fetchall()

        # 3) `quote_amount`를 한글로 변환
        def convert_to_korean_currency(amount):
            units = ["", "만", "억", "조"]
            nums = ["영", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]
            result = []
            num_str = str(int(amount))
            length = len(num_str)

            for i, digit in enumerate(num_str):
                if digit != "0":
                    unit_idx = (length - i - 1) // 4
                    result.append(nums[int(digit)] + (units[unit_idx] if (length - i - 1) % 4 == 0 else ""))
            return "".join(result) + "원"

        total_price_korean = convert_to_korean_currency(estimate["quote_amount"])

        # 4) 응답 데이터 구성
        response = {
            "success": True,
            "data": {
                "estimate": estimate,
                "products": products,
                "total_price_korean": total_price_korean
            }
        }

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Error fetching estimate detail: {e}")
        return jsonify({"success": False, "error": "데이터 조회 중 오류 발생"}), 500

    finally:
        cursor.close()
        conn.close()






@estimate_bp.route('/api/estimates/<int:estimate_id>', methods=['PUT'])
def update_estimate(estimate_id):
    data = request.json

    # 견적 정보
    quote_id = data.get('quote_id')
    quote_title = data.get('quote_title')
    customer_id = data.get('customer_id')
    sales_id = data.get('sales_id')
    quote_amount = data.get('quote_amount')
    valid_until = data.get('valid_until')
    delivery_condition = data.get('delivery_condition')
    payment_condition = data.get('payment_condition')
    warranty_period = data.get('warranty_period')
    remarks = data.get('remarks')
    opinion = data.get('opinion')
    memo = data.get('memo')
    total_price_before_vat = data.get('total_price_before_vat')
    vat = data.get('vat')
    total_price_with_vat = data.get('total_price_with_vat')
    unty_file_no = data.get('unty_file_no')  # 추가된 파일 번호

    # 새로 넘어온 제품 목록
    products = data.get('products', [])

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1) estimate 갱신
            sql_est = """
            UPDATE estimate
            SET
                quote_id = %s,
                quote_title = %s,
                customer_id = %s,
                sales_id = %s,
                quote_amount = %s,
                valid_until = %s,
                delivery_condition = %s,
                payment_condition = %s,
                warranty_period = %s,
                remarks = %s,
                opinion = %s,
                memo = %s,
                total_price_before_vat = %s,
                vat = %s,
                total_price_with_vat = %s,
                unty_file_no = %s
            WHERE id = %s;
            """
            cursor.execute(sql_est, (
                quote_id, quote_title, customer_id, sales_id, quote_amount,
                valid_until, delivery_condition, payment_condition, warranty_period,
                remarks, opinion, memo, total_price_before_vat, vat, total_price_with_vat,
                unty_file_no, estimate_id
            ))

            # 2) t_estimate_product 전체 삭제 → 재삽입
            del_sql = "DELETE FROM t_estimate_product WHERE estimate_id = %s"
            cursor.execute(del_sql, (estimate_id,))

            # 3) 새 products 배열을 순회하여 INSERT
            ins_sql = """
            INSERT INTO t_estimate_product
              (estimate_id, product_id, quantity, unit_price, total_price, discount_rate, final_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            for item in products:
                product_id = item.get("product_id")
                quantity = item.get("quantity", 1)
                unit_price = item.get('unit_price')
                total_price = item.get('total_price')
                discount_rate = item.get('discount_rate')
                final_price = item.get('final_price')

                cursor.execute(ins_sql, (
                    estimate_id, product_id, quantity, unit_price, total_price, discount_rate, final_price
                ))

        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()







@estimate_bp.route('/api/estimates/<int:estimate_id>', methods=['DELETE'])
def delete_estimate(estimate_id):
    """
    특정 견적서 삭제 API
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1) `t_estimate_product` 테이블에서 관련 제품 데이터 삭제
            sql_delete_products = "DELETE FROM t_estimate_product WHERE estimate_id = %s"
            cursor.execute(sql_delete_products, (estimate_id,))

            # 2) `estimate` 테이블에서 견적서 삭제
            sql_delete_estimate = "DELETE FROM estimate WHERE id = %s"
            cursor.execute(sql_delete_estimate, (estimate_id,))

        conn.commit()
        return jsonify({"success": True, "message": "견적서가 성공적으로 삭제되었습니다."}), 200

    except Exception as e:
        conn.rollback()
        logging.error(f"Error deleting estimate: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        conn.close()





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
customers_bp = Blueprint('customers', __name__)

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

# 🔥 고객 정보 조회 API
@customers_bp.route('/customers/<int:customerId>', methods=['GET'])
def get_customer(customerId):
    """
    특정 고객 정보를 조회하는 API
    - URL: /customers/<customerId>
    """
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT * FROM customer WHERE customer_id = %s", (customerId,))
    customer = cursor.fetchone()

    cursor.close()
    conn.close()

    if not customer:
        return jsonify({"error": "고객 정보를 찾을 수 없습니다."}), 404  # 고객이 없을 경우 404 반환

    logging.info(f"조회된 고객 데이터: {customer}")  # 로그 출력
    return jsonify(convert_keys_to_camel_case(customer))  # camelCase로 변환 후 반환


# 🔥 고객 리스트 조회 API
@customers_bp.route('/customers', methods=['GET'])
def get_customers():
    """
    고객 리스트를 조회하는 API (검색 기능 포함)
    - URL: /customers
    """
    search_query = request.args.get("search", "").strip()  # 검색어 가져오기
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        if search_query:
            sql_query = "SELECT * FROM customer WHERE customer_nm LIKE %s"
            cursor.execute(sql_query, (f"%{search_query}%",))
        else:
            sql_query = "SELECT * FROM customer"
            cursor.execute(sql_query)

        customers = cursor.fetchall()
        customers = convert_keys_to_camel_case(customers)  # camelCase로 변환
        return jsonify(customers)  # 검색 결과 반환

    except Exception as e:
        logging.error(f"Error fetching customers: {str(e)}")
        return jsonify({"error": "데이터 조회 중 오류 발생"}), 500

    finally:
        cursor.close()
        conn.close()


# 🔥 고객 정보 추가 API
@customers_bp.route('/customers', methods=['POST'])
def add_customer():
    """
    새로운 고객 정보를 추가하는 API
    - URL: /customers
    """
    logging.info("새 고객 추가 요청 도착")  # 로그 출력
    data = request.json
    logging.info(f"받은 데이터: {data}")  # 로그 출력

    conn = get_db_connection()
    cursor = conn.cursor()

    insert_query = """
    INSERT INTO customer (
        customer_nm, customer_type, biz_num, mng_nm, tel_no, address1, address2, address3, 
        comment, engineer_id, sales_id, unty_file_no, reg_id, reg_dt, upd_id, upd_dt
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
    """

    try:
        cursor.execute(insert_query, (
            data.get("customerNm"), data.get("customerType"), data.get("bizNum"), data.get("mngNm"),
            data.get("telNo"), data.get("address1"), data.get("address2"), data.get("address3"),
            data.get("comment"), data.get("engineerId"), data.get("salesId"), data.get("untyFileNo"),
            data.get("regId"), data.get("updId")
        ))

        conn.commit()
        newCustomerId = cursor.lastrowid  # 방금 삽입한 고객의 ID 가져오기
        return jsonify({"message": "고객 정보 저장 성공", "newCustomerId": newCustomerId}), 201

    except pymysql.MySQLError as e:
        conn.rollback()
        logging.error(f"DB 오류 발생: {str(e)}")  # 오류 로그 기록
        return jsonify({"error": f"DB 오류 발생: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()


# 🔥 고객 정보 삭제 API
@customers_bp.route('/customers/<int:customerId>', methods=['DELETE'])
def delete_customer(customerId):
    """
    특정 고객 정보를 삭제하는 API
    - URL: /customers/<customerId>
    """
    logging.info(f"고객 삭제 요청 - ID: {customerId}")  # 로그 출력

    conn = get_db_connection()
    cursor = conn.cursor()

    delete_query = "DELETE FROM customer WHERE customer_id = %s"

    try:
        cursor.execute(delete_query, (customerId,))

        if cursor.rowcount == 0:
            return jsonify({"error": "해당 ID의 고객이 없습니다."}), 404  # 고객이 없을 경우 404 반환

        conn.commit()
        return jsonify({"message": "고객 정보가 삭제되었습니다.", "customerId": customerId}), 200  # 삭제 성공

    except pymysql.MySQLError as e:
        conn.rollback()
        logging.error(f"DB 오류 발생: {str(e)}")  # 오류 로그 기록
        return jsonify({"error": f"DB 오류 발생: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()
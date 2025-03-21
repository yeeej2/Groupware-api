from flask import Blueprint, request, jsonify
import pymysql
from models.database import get_db_connection
import logging #로그 남기기

import json
from decimal import Decimal
from datetime import datetime



logging.basicConfig(level=logging.DEBUG)

customers_bp = Blueprint('customers', __name__)  # 블루프린트 생성

# 🔹 snake_case → camelCase 변환 함수 (자동 변환)
def snake_to_camel(snake_str):
    parts = snake_str.split('_')
    return parts[0] + ''.join(word.capitalize() for word in parts[1:])

# 🔹 모든 키를 자동 변환하는 함수
def convert_keys_to_camel_case(data):
    if isinstance(data, list):  # ✅ 리스트 처리 (여러 개의 데이터)
        return [convert_keys_to_camel_case(item) for item in data]
    elif isinstance(data, dict):  # ✅ 딕셔너리 처리 (단일 데이터)
        return {snake_to_camel(k): v for k, v in data.items()}
    return data

# 🔹 JSON 변환 함수 (Decimal, datetime 변환)
def custom_json_converter(obj):
    if isinstance(obj, Decimal):  # 🔥 Decimal → float 변환
        return float(obj)
    if isinstance(obj, datetime):  # 🔥 datetime → 문자열 변환
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    return str(obj)

# 🔥 고객 정보 조회 API (GET /customers/<id>)
@customers_bp.route('/customers/<int:id>', methods=['GET'])
def get_customer(id):
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT * FROM customer WHERE cust_id = %s", (id,))

    customer = cursor.fetchone()

    cursor.close()
    conn.close()

    if not customer:
        return jsonify({"error": "고객 정보를 찾을 수 없습니다."}), 404  # ❌ 고객이 없을 경우 404 반환
    
    print("조회된 데이터:", customer)  # 🔥 콘솔에서 데이터 확인
    logging.info(f"조회된 고객 데이터: {customer}")  # 🔥 로그 출력

    return jsonify(convert_keys_to_camel_case(customer))  # ✅ 고객 데이터 JSON으로 반환


# 🔥 고객 정보 수정 API (PUT /customers/<id>)
@customers_bp.route('/customers/<int:id>', methods=['PUT'])
def update_customer(id):
    logging.info(f"고객id : {id}")  # 🔥 로그 출력
    data = request.json
    logging.info(f"고객정보 수정 데이터: {data}")  # 🔥 로그 출력
    conn = get_db_connection()
    cursor = conn.cursor()

    update_query = """
    UPDATE customer SET
        cust_name = %s, cust_biz_no = %s, cust_grade = %s, 
        phone = %s, fax = %s, addr = %s, addr_dtl = %s, 
        cust_sales_amt = %s, updated_at = CURRENT_TIMESTAMP
    WHERE cust_id = %s
    """
    
    try:
        cursor.execute(update_query, (
            data.get('custName'), data.get('custBizNo'), data.get('custGrade'), 
            data.get('phone'), data.get('fax'), data.get('addr'), data.get('addrDtl'), 
            data.get('custSalesAmt'), id
        ))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "해당 ID의 고객이 없습니다."}), 404  # ❌ 존재하지 않는 고객 ID

        conn.commit()
        return jsonify({"message": "고객 정보가 수정되었습니다."}), 200  # ✅ 업데이트 성공
    
    except pymysql.MySQLError as e:
        return jsonify({"error": f"DB 오류 발생: {str(e)}"}), 500  # ❌ DB 에러 처리
    
    finally:
        cursor.close()
        conn.close()


# 🔥 고객 리스트 조회 API (검색 추가)
@customers_bp.route('/customers', methods=['GET'])
def get_customers():
    search_query = request.args.get("search", "").strip()  # 🔹 검색어 가져오기
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        if search_query:
            sql_query = "SELECT * FROM customer WHERE cust_name LIKE %s"
            cursor.execute(sql_query, (f"%{search_query}%",))
        else:
            sql_query = "SELECT * FROM customer"
            cursor.execute(sql_query)

        customers = cursor.fetchall()
        response_data = json.loads(json.dumps(customers, default=custom_json_converter))

        return jsonify(response_data)  # ✅ 검색 결과 반환

    except Exception as e:
        logging.error(f"Error fetching customers: {str(e)}")
        return jsonify({"error": "데이터 조회 중 오류 발생"}), 500
    
    finally:
        cursor.close()
        conn.close()



# 🔥 고객 정보 추가 API (POST /customers)
@customers_bp.route('/customers', methods=['POST'])
def add_customer():
    logging.info("새 고객 추가 요청 도착")  # 🔥 로그 출력
    data = request.json  # React에서 보낸 JSON 데이터 받기
    logging.info(f"받은 데이터: {data}")  # 🔥 로그 출력

    conn = get_db_connection()
    cursor = conn.cursor()

    insert_query = """
    INSERT INTO customer (
        cust_name, rep_name, cust_biz_no, cust_grade, phone, fax, addr, addr_dtl, cust_status, 
        cust_sales_amt, sales_id, memo, created_at, updated_at
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '1', %s, NOW(), NOW())
    """

    try:
        cursor.execute(insert_query, (
            data.get("customer"), data.get("manager"), data.get("bizNumber"), data.get("level"),
            data.get("phone"), data.get("fax"), data.get("address"), data.get("addressDetail"), data.get("status"),
            data.get("salesAmt"),  data.get("memo")  # ✅ 'memo' 대신 'note' 사용 (백엔드 응답 확인 필요)
        ))

        conn.commit()
        new_customer_id = cursor.lastrowid  # 방금 삽입한 고객의 ID 가져오기
        return jsonify({"message": "고객 정보 저장 성공", "id": new_customer_id}), 201

    except pymysql.MySQLError as e:
        conn.rollback()
        logging.error(f"DB 오류 발생: {str(e)}")  # 🔥 오류 로그 기록
        return jsonify({"error": f"DB 오류 발생: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()




# 🔥 고객 정보 삭제 API (DELETE /customers/<id>)
@customers_bp.route('/customers/<int:id>', methods=['DELETE'])
def delete_customer(id):
    logging.info(f"고객 삭제 요청 - ID: {id}")  # 🔥 로그 출력

    conn = get_db_connection()
    cursor = conn.cursor()

    delete_query = "DELETE FROM customer WHERE cust_id = %s"

    try:
        cursor.execute(delete_query, (id,))

        if cursor.rowcount == 0:
            return jsonify({"error": "해당 ID의 고객이 없습니다."}), 404  # ❌ 고객이 없을 경우 404 반환

        conn.commit()
        return jsonify({"message": "고객 정보가 삭제되었습니다.", "id": id}), 200  # ✅ 삭제 성공
    
    except pymysql.MySQLError as e:
        conn.rollback()
        logging.error(f"DB 오류 발생: {str(e)}")  # 🔥 오류 로그 기록
        return jsonify({"error": f"DB 오류 발생: {str(e)}"}), 500  # ❌ DB 오류 발생 시 처리
    
    finally:
        cursor.close()
        conn.close()


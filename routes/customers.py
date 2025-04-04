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















# 🔥 고객 정보 및 담당자 리스트 조회 API
@customers_bp.route('/customers/<int:customerId>', methods=['GET'])
def get_customer(customerId):
    """
    특정 고객 정보와 담당자 리스트를 조회하는 API
    - URL: /customers/<customerId>
    - 응답 JSON 예시:
      {
        "customer": { ... },
        "managers": [ ... ]
      }
    """
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        # 1) 고객 정보 조회
        query = """
        SELECT 
            c.*, 
            d.email AS sales_email,
            e.email AS engineer_email
        FROM customer c
        LEFT JOIN user d ON c.sales_id = d.usr_id
        LEFT JOIN user e ON c.engineer_id = e.usr_id
        WHERE c.customer_id = %s
        """
        cursor.execute(query, (customerId,))

        customer = cursor.fetchone()

        if not customer:
            return jsonify({"error": "고객 정보를 찾을 수 없습니다."}), 404  # 고객이 없을 경우 404 반환

        # 2) 담당자 리스트 조회
        cursor.execute("SELECT * FROM customer_manager WHERE customer_id = %s", (customerId,))
        managers = cursor.fetchall()

        # 3) camelCase로 변환
        customer = convert_keys_to_camel_case(customer)
        managers = convert_keys_to_camel_case(managers)

        # 4) 응답 데이터 구성
        response = {
            "customer": customer,
            "managers": managers
        }

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Error fetching customer data: {str(e)}")
        return jsonify({"error": "데이터 조회 중 오류 발생"}), 500

    finally:
        cursor.close()
        conn.close()


# 🔥 고객 리스트 조회 API
@customers_bp.route('/customers', methods=['GET'])
def get_customers():
    """
    고객 리스트를 조회하는 API (검색 기능 포함)
    - URL: /customers
    """
    logging.info(request)
    search_query = request.args.get('searchQuery', '')
    biz_num_query = request.args.get('bizNumQuery', '')
    mng_nm_query = request.args.get('mngNmQuery', '')
    customer_type_query = request.args.get('customerTypeQuery', '')

    query = """
        SELECT 
        c.*, 
        COUNT(cm.manager_id) AS manager_count
        FROM customer c
        LEFT JOIN customer_manager cm ON c.customer_id = cm.customer_id
        WHERE 1=1
    """

    # 고객명 검색
    if search_query:
        query += f" AND customer_nm LIKE '%{search_query}%'"

    # 사업자등록번호 검색
    if biz_num_query:
        query += f" AND biz_num LIKE '%{biz_num_query}%'"

    # 대표자명 검색
    if mng_nm_query:
        query += f" AND mng_nm LIKE '%{mng_nm_query}%'"

    # 고객 유형 검색
    if customer_type_query:
        query += f" AND customer_type = '{customer_type_query}'"

    query += " GROUP BY c.customer_id"

    # 데이터 조회
    try:
        logging.info(query);
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        customers = cursor.fetchall()
        return jsonify(convert_keys_to_camel_case(customers))

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
    - 요청 JSON 예시:
      { -> before
        "customer": { ... },
        "managers": [ ... ]
      }

      { -> after
        "customer": {...},
        "managers": [...],
        "device": {...},            ← ✅ 장비 정보
        "sub_devices": [...]        ← ✅ 서브 장비 리스트
    }
    """
    logging.info("새 고객 추가 요청 도착")
    data = request.json
    customer_data = data.get("customer")
    managers_data = data.get("managers", [])

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1) 고객 정보 저장
        insert_customer_query = """
        INSERT INTO customer (
            customer_nm, customer_type, biz_num, mng_nm, tel_no, address1, address2, address3, 
            comment, engineer_id, sales_id, unty_file_no, reg_id, reg_dt, upd_id, upd_dt
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
        """
        cursor.execute(insert_customer_query, (
            customer_data.get("customerNm"), customer_data.get("customerType"), customer_data.get("bizNum"),
            customer_data.get("mngNm"), customer_data.get("telNo"), customer_data.get("address1"),
            customer_data.get("address2"), customer_data.get("address3"), customer_data.get("comment"),
            customer_data.get("engineerId"), customer_data.get("salesId"), customer_data.get("untyFileNo"),
            customer_data.get("regId"), customer_data.get("updId")
        ))
        new_customer_id = cursor.lastrowid

        # 2) 담당자 리스트 저장
        insert_manager_query = """
        INSERT INTO customer_manager (
            customer_id, manager_id, manager_nm, tel_no, email, position, mng_yn, reg_id, reg_dt, upd_id, upd_dt
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
        """
        for idx, manager in enumerate(managers_data, start=1):  # manager_id는 1부터 시작
            cursor.execute(insert_manager_query, (
                new_customer_id, idx, manager.get("managerNm"), manager.get("telNo"),
                manager.get("email"), manager.get("position"), manager.get("mngYn"),
                customer_data.get("regId"), customer_data.get("updId")
            ))

        # 3) 장비 정보 저장
        device_data = data.get("device")
        insert_device_query = """
        INSERT INTO device (
            customer_id, model_name, serial_no, firmware_version, hostname, device_ip,
            device_id, device_pw, is_redundant, termination_date, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        cursor.execute(insert_device_query, (
            new_customer_id,
            device_data.get("model_name"), device_data.get("serial_no"), device_data.get("firmware_version"),
            device_data.get("hostname"), device_data.get("device_ip"), device_data.get("device_id"),
            device_data.get("device_pw"), device_data.get("is_redundant"), device_data.get("termination_date")
        ))
        new_device_id = cursor.lastrowid


        # 4) 서브 장비 리스트 저장 (backup/기타 통합)
        sub_devices = data.get("sub_devices", [])

        insert_sub_device_query = """
        INSERT INTO sub_device (
            device_id,
            device_type,
            model_name,
            hostname,
            device_ip,
            login_id,
            login_pw,
            serial_no,
            access_port,
            access_host,
            service_type,
            created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """

        for item in sub_devices:
            cursor.execute(insert_sub_device_query, (
                new_device_id,                      # 상위 device 테이블의 ID
                item.get("device_type"),            # backup / etc
                item.get("model_name"),
                item.get("hostname"),
                item.get("device_ip"),              # etcDeviceList만 사용
                item.get("login_id"),
                item.get("login_pw"),
                item.get("serial_no"),
                item.get("access_port"),            # backup 장비일 경우 사용
                item.get("access_host"),            # backup 장비일 경우 사용
                item.get("service_type"),           # backup 장비일 경우 사용
            ))




        conn.commit()
        return jsonify({"message": "고객 정보 저장 성공", "newCustomerId": new_customer_id}), 201

    except pymysql.MySQLError as e:
        conn.rollback()
        logging.error(f"DB 오류 발생: {str(e)}")
        return jsonify({"error": f"DB 오류 발생: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()


# 🔥 고객 정보 수정 API
@customers_bp.route('/customers/<int:id>', methods=['PUT'])
def update_customer(id):
    """
    고객 정보를 수정하는 API
    - URL: /customers/<id>
    - 요청 JSON 예시:
      {
        "customer": { ... },
        "managers": [ ... ]
      }
    """
    logging.info(f"고객 수정 요청 - ID: {id}")
    data = request.json
    customer_data = data.get("customer")
    managers_data = data.get("managers", [])

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1) 고객 정보 수정
        update_customer_query = """
        UPDATE customer SET
            customer_nm = %s, customer_type = %s, biz_num = %s, mng_nm = %s, tel_no = %s,
            address1 = %s, address2 = %s, address3 = %s, comment = %s, engineer_id = %s,
            sales_id = %s, unty_file_no = %s, upd_id = %s, upd_dt = NOW()
        WHERE customer_id = %s
        """
        cursor.execute(update_customer_query, (
            customer_data.get("customerNm"), customer_data.get("customerType"), customer_data.get("bizNum"),
            customer_data.get("mngNm"), customer_data.get("telNo"), customer_data.get("address1"),
            customer_data.get("address2"), customer_data.get("address3"), customer_data.get("comment"),
            customer_data.get("engineerId"), customer_data.get("salesId"), customer_data.get("untyFileNo"),
            customer_data.get("updId"), id
        ))

        # 2) 기존 담당자 삭제
        delete_manager_query = "DELETE FROM customer_manager WHERE customer_id = %s"
        cursor.execute(delete_manager_query, (id,))

        # 3) 새로운 담당자 리스트 저장
        insert_manager_query = """
        INSERT INTO customer_manager (
            customer_id, manager_id, manager_nm, tel_no, email, position, mng_yn, reg_id, reg_dt, upd_id, upd_dt
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
        """
        for idx, manager in enumerate(managers_data, start=1):  # manager_id는 1부터 시작
            cursor.execute(insert_manager_query, (
                id, idx, manager.get("managerNm"), manager.get("telNo"),
                manager.get("email"), manager.get("position"), manager.get("mngYn"),
                customer_data.get("regId"), customer_data.get("updId")
            ))

        conn.commit()
        return jsonify({"message": "고객 정보 수정 성공"}), 200

    except pymysql.MySQLError as e:
        conn.rollback()
        logging.error(f"DB 오류 발생: {str(e)}")
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
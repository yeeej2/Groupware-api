from flask import Blueprint, request, jsonify
import pymysql
from models.database import get_db_connection
import logging
import json
from decimal import Decimal
from datetime import datetime
from auth.decorators import require_token

# 🔥 로깅 설정
logging.basicConfig(level=logging.DEBUG)

# 🔹 Blueprint 생성
customers_bp = Blueprint('customers', __name__)

@customers_bp.before_request
@require_token
def require_token_for_user_bp():
    pass

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
    특정 고객 정보와 관련 데이터를 조회하는 API
    - URL: /customers/<customerId>
    - 응답 JSON 예시:
      {
        "customer": { ... },
        "managers": [ ... ],
        "device": { ... },
        "sub_devices": [ ... ],
        "backupList": [ ... ],
        "etcDeviceList": [ ... ],
        "service": { ... },
        "issues": [ ... ]
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

        # 3) 장비 정보 조회
        cursor.execute("SELECT DATE_FORMAT(t.termination_date, '%%Y-%%m-%%d') AS termination_date, t.* FROM device t WHERE t.customer_id = %s", (customerId,))
        device = cursor.fetchone()

        backupList = []
        etcDeviceList = []
        if device:
            # 서브 장비 리스트 조회
            cursor.execute("SELECT * FROM sub_device WHERE device_type = 'backup' AND device_id = %s", (device['id'],))
            backupList = cursor.fetchall()

            cursor.execute("SELECT * FROM sub_device WHERE device_type = 'etc' AND device_id = %s", (device['id'],))
            etcDeviceList = cursor.fetchall()

        # 4) 서비스 정보 조회
        sql = """
        SELECT
            DATE_FORMAT(t.installation_date, '%%Y-%%m-%%d') AS installation_date,
            t.service_type,
            t.report_yn,
            t.asset_info,
            t.service_scope,
            t.license_type,
            t.maintenance_level,
            t.monitoring_level,
            t.security_policy,
            t.monitoring_registration,
            t.special_note,
            t.engineer_id,
            t.installation_date,
            e.email AS service_engineer_email,
            e.usr_id AS service_engineer_id
        FROM customer_service t
        LEFT JOIN user e ON t.engineer_id = e.usr_id
        WHERE t.customer_id = %s
        """ 
        cursor.execute(sql, (customerId,))
        service = cursor.fetchone()

        # 5) 이슈 정보 조회
        sql = """
        SELECT DATE_FORMAT(t.issue_date, '%%Y-%%m-%%dT%%H:%%i') AS issue_date
             , t.id
             , t.detail
             , e.usr_id AS operator_id
             , e.name AS operator
          FROM customer_issue t
            LEFT JOIN user e ON t.operator = e.usr_id
         WHERE t.customer_id = %s ORDER BY t.issue_date DESC
        """ 
        cursor.execute(sql , (customerId,))
        issueList = cursor.fetchall()

        # 6) camelCase로 변환
        if service:
            for key in ['service_scope', 'license_type', 'security_policy', 'monitoring_registration']:
                if service.get(key):
                    try:
                        service[key] = json.loads(service[key])
                    except json.JSONDecodeError:
                        service[key] = []  # 파싱 실패 시 빈 배열로 대체

        customer = convert_keys_to_camel_case(customer)
        managers = convert_keys_to_camel_case(managers)
        device = device
        backupList = backupList
        etcDeviceList = etcDeviceList
        service = service
        issueList = issueList


        # 7) 응답 데이터 구성
        response = {
            "customer": customer,
            "managers": managers,
            "device": device,
            "backupList": backupList,
            "etcDeviceList": etcDeviceList,
            "service": service,
            "issueList": issueList
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
    logging.info("고객 리스트 조회 요청 도착")
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

    query += " GROUP BY c.customer_id desc"

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
      {
        "customer": { ... },
        "managers": [ ... ],
        "device": { ... },
        "sub_devices": [ ... ],
        "service": { ... }
      }
    """
    logging.info("새 고객 추가 요청 도착")
    data = request.json
    logging.info("요청 데이터")
    logging.info(data)
    customer_data = data.get("customer")
    managers_data = data.get("managers", [])
    device_data = data.get("device")
    sub_devices = data.get("sub_devices", [])
    service_data = data.get("service")
    issue_list = data.get("issueList", [])
    

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

        # 4) 서브 장비 리스트 저장
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

        # 5) 서비스 정보 저장
        if service_data:
            insert_service_query = """
            INSERT INTO customer_service (
                customer_id, service_type, report_yn, asset_info, service_scope, license_type,
                maintenance_level, monitoring_level, security_policy, monitoring_registration,
                special_note, engineer_id, installation_date, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            cursor.execute(insert_service_query, (
                new_customer_id,
                service_data.get("service_type"), service_data.get("report_yn"), service_data.get("asset_info"),
                json.dumps(service_data.get("service_scope"), ensure_ascii=False), json.dumps(service_data.get("license_type"), ensure_ascii=False),
                service_data.get("maintenance_level"), service_data.get("monitoring_level"),
                json.dumps(service_data.get("security_policy"), ensure_ascii=False), json.dumps(service_data.get("monitoring_registration"), ensure_ascii=False),
                service_data.get("special_note"), service_data.get("service_engineer_id"),
                service_data.get("installation_date")
            ))


        # 6) 이슈 정보 저장
        if issue_list:
            insert_issue_query = """
            INSERT INTO customer_issue (
                customer_id, issue_date, operator, detail, created_at
            ) VALUES (%s, %s, %s, %s, NOW())
            """
            for issue in issue_list:
                cursor.execute(insert_issue_query, (
                    new_customer_id,
                    issue.get("issue_date"),
                    issue.get("operator_id"),
                    issue.get("detail")
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
        "managers": [ ... ],
        "device": { ... },
        "sub_devices": [ ... ]
      }
    """
    logging.info(f"고객 수정 요청 - ID: {id}")
    customer_id = id
    data = request.json
    customer_data = data.get("customer")
    managers_data = data.get("managers", [])
    device_data = data.get("device")
    sub_devices = data.get("sub_devices", [])
    service_data = data.get("service")
    issue_list = data.get("issueList", [])

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
            customer_data.get("updId"), customer_id
        ))

        # 2) 기존 담당자 삭제
        delete_manager_query = "DELETE FROM customer_manager WHERE customer_id = %s"
        cursor.execute(delete_manager_query, (customer_id,))

        # 3) 새로운 담당자 리스트 저장
        insert_manager_query = """
        INSERT INTO customer_manager (
            customer_id, manager_id, manager_nm, tel_no, email, position, mng_yn, reg_id, reg_dt, upd_id, upd_dt
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
        """
        for idx, manager in enumerate(managers_data, start=1):  # manager_id는 1부터 시작
            cursor.execute(insert_manager_query, (
                customer_id, idx, manager.get("managerNm"), manager.get("telNo"),
                manager.get("email"), manager.get("position"), manager.get("mngYn"),
                customer_data.get("regId"), customer_data.get("updId")
            ))

        # 4) 장비 정보 수정 또는 추가
        if device_data:
            # 장비가 이미 존재하는지 확인
            cursor.execute("SELECT id FROM device WHERE customer_id = %s", (customer_id,))
            existing_device = cursor.fetchone()

            if existing_device:
                # 기존 장비 수정
                update_device_query = """
                UPDATE device SET
                    model_name = %s, serial_no = %s, firmware_version = %s, hostname = %s, device_ip = %s,
                    device_id = %s, device_pw = %s, is_redundant = %s, termination_date = %s, updated_at = NOW()
                WHERE customer_id = %s
                """
                cursor.execute(update_device_query, (
                    device_data.get("model_name"), device_data.get("serial_no"), device_data.get("firmware_version"),
                    device_data.get("hostname"), device_data.get("device_ip"), device_data.get("device_id"),
                    device_data.get("device_pw"), device_data.get("is_redundant"), device_data.get("termination_date"),
                    customer_id
                ))
                device_id = existing_device["id"]
            else:
                # 새로운 장비 추가
                insert_device_query = """
                INSERT INTO device (
                    customer_id, model_name, serial_no, firmware_version, hostname, device_ip,
                    device_id, device_pw, is_redundant, termination_date, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """
                cursor.execute(insert_device_query, (
                    id,
                    device_data.get("model_name"), device_data.get("serial_no"), device_data.get("firmware_version"),
                    device_data.get("hostname"), device_data.get("device_ip"), device_data.get("device_id"),
                    device_data.get("device_pw"), device_data.get("is_redundant"), device_data.get("termination_date")
                ))
                device_id = cursor.lastrowid
        else:
            device_id = None

        # 5) 기존 서브 장비 삭제
        delete_sub_device_query = "DELETE FROM sub_device WHERE device_id = %s"
        if id:
            cursor.execute(delete_sub_device_query, (device_id,))

        # 6) 새로운 서브 장비 리스트 저장
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
                device_id,                      # 상위 device 테이블의 ID
                item.get("device_type"),        # backup / etc
                item.get("model_name"),
                item.get("hostname"),
                item.get("device_ip"),          # etcDeviceList만 사용
                item.get("login_id"),
                item.get("login_pw"),
                item.get("serial_no"),
                item.get("access_port"),        # backup 장비일 경우 사용
                item.get("access_host"),        # backup 장비일 경우 사용
                item.get("service_type"),       # backup 장비일 경우 사용
            ))


        # 7) 서비스 정보 수정
        if service_data:
            update_service_query = """
            UPDATE customer_service SET
                service_type = %s, 
                report_yn = %s, 
                asset_info = %s, 
                service_scope = %s, 
                license_type = %s,
                maintenance_level = %s, 
                monitoring_level = %s, 
                security_policy = %s, 
                monitoring_registration = %s,
                special_note = %s, 
                engineer_id = %s, 
                installation_date = %s
            WHERE customer_id = %s
            """
            logging.info("서비스 수정사항")
            logging.info(service_data)
            logging.info("service_type")
            logging.info(service_data.get("license_type"))
            
            cursor.execute(update_service_query, (
                service_data.get("service_type"), 
                service_data.get("report_yn"), 
                service_data.get("asset_info"),
                json.dumps(service_data.get("service_scope"), ensure_ascii=False),  # UTF-8로 저장
                json.dumps(service_data.get("license_type"), ensure_ascii=False),  # UTF-8로 저장
                service_data.get("maintenance_level"), 
                service_data.get("monitoring_level"),
                json.dumps(service_data.get("security_policy"), ensure_ascii=False),  # UTF-8로 저장
                json.dumps(service_data.get("monitoring_registration"), ensure_ascii=False),  # UTF-8로 저장
                service_data.get("special_note"), 
                service_data.get("service_engineer_id"),
                service_data.get("installation_date"),
                customer_id
            ))


        # 8) 기존 이슈 정보 삭제 및 새로 추가
        delete_issue_query = "DELETE FROM customer_issue WHERE customer_id = %s"
        cursor.execute(delete_issue_query, (customer_id,))

        if issue_list:
            insert_issue_query = """
            INSERT INTO customer_issue (
                customer_id, issue_date, operator, detail, created_at
            ) VALUES (%s, %s, %s, %s, NOW())
            """
            for issue in issue_list:
                cursor.execute(insert_issue_query, (
                    customer_id,
                    issue.get("issue_date"),
                    issue.get("operator_id"),
                    issue.get("detail")
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
    고객과 관련된 모든 데이터를 삭제하는 API
    """
    logging.info(f"고객 삭제 요청 - ID: {customerId}")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1) 관련 데이터 삭제
        delete_issue_query = "DELETE FROM customer_issue WHERE customer_id = %s"
        cursor.execute(delete_issue_query, (customerId,))

        delete_service_query = "DELETE FROM customer_service WHERE customer_id = %s"
        cursor.execute(delete_service_query, (customerId,))

        delete_sub_device_query = """
        DELETE sd FROM sub_device sd
        JOIN device d ON sd.device_id = d.id
        WHERE d.customer_id = %s
        """
        cursor.execute(delete_sub_device_query, (customerId,))

        delete_device_query = "DELETE FROM device WHERE customer_id = %s"
        cursor.execute(delete_device_query, (customerId,))

        delete_manager_query = "DELETE FROM customer_manager WHERE customer_id = %s"
        cursor.execute(delete_manager_query, (customerId,))

        # 2) 고객 삭제
        delete_customer_query = "DELETE FROM customer WHERE customer_id = %s"
        cursor.execute(delete_customer_query, (customerId,))

        if cursor.rowcount == 0:
            return jsonify({"error": "해당 ID의 고객이 없습니다."}), 404

        conn.commit()
        return jsonify({"message": "고객 및 관련 데이터가 삭제되었습니다.", "customerId": customerId}), 200

    except pymysql.MySQLError as e:
        conn.rollback()
        logging.error(f"DB 오류 발생: {str(e)}")
        return jsonify({"error": f"DB 오류 발생: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()




@customers_bp.route('/customers/<int:customer_id>/managers', methods=['GET'])
def get_customer_managers(customer_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    customer_id,
                    manager_id,
                    manager_nm,
                    tel_no,
                    email,
                    position,
                    mng_yn
                FROM customer_manager
                WHERE customer_id = %s
                ORDER BY manager_id
            """
            cursor.execute(sql, (customer_id,))
            managers = cursor.fetchall()
        return jsonify({"success": True, "data": managers})
    except Exception as e:
        logging.error(f"담당자 목록 조회 중 오류 발생: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

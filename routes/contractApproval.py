from flask import Blueprint, request, jsonify
from models.database import get_db_connection
from auth.decorators import require_token
from datetime import datetime
import logging

contractApproval_bp = Blueprint('contractApproval', __name__)
logging.basicConfig(level=logging.DEBUG)

@contractApproval_bp.before_request
@require_token
def require_token_for_user_bp():
    pass

# 🔹 snake_case → camelCase 변환 함수
def snake_to_camel(snake_str):
    parts = snake_str.split('_')
    return parts[0] + ''.join(word.capitalize() for word in parts[1:])

# 🔹 모든 키를 camelCase로 변환하는 함수
def convert_keys_to_camel_case(data):
    if isinstance(data, list):
        return [convert_keys_to_camel_case(item) for item in data]
    elif isinstance(data, dict):
        return {snake_to_camel(k): v for k, v in data.items()}
    return data

def null_if_empty(value):
    return None if value == '' else value

# 🔥 수주품의서 등록 (POST)
@contractApproval_bp.route('/contractApproval', methods=['POST'])
def create_contract_approval():
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        service_items = data.pop('serviceItems', [])

        # Validate estimate_id and contract_id
        estimate_id = data.get('estimateId')
        contract_id = data.get('contractId')

        if estimate_id and contract_id:
            return jsonify({'status': 'fail', 'message': 'Only one of estimateId or contractId should be provided.'}), 400

        if not estimate_id and not contract_id:
            return jsonify({'status': 'fail', 'message': 'Either estimateId or contractId must be provided.'}), 400

        # Handle 'Other' cases for paymentType and vendorPaymentType
        if data.get('paymentType') == '기타':
            data['paymentType'] = data.get('paymentTypeOther')
        if data.get('vendorPaymentType') == '기타':
            data['vendorPaymentType'] = data.get('vendorPaymentTypeOther')

        # 1. 채번 생성
        today = datetime.today().strftime('%Y%m%d')
        cursor.execute("""
            SELECT COUNT(*) + 1 AS next_seq
            FROM contract_approval
            WHERE DATE(created_at) = CURDATE()
        """)
        next_seq = cursor.fetchone()['next_seq']
        contract_approval_no = f"ORD-{today}-{next_seq:03d}"

        # 2. 채번 저장
        data['contractApprovalNo'] = contract_approval_no

        # 3. Insert 쿼리
        sql = """
        INSERT INTO contract_approval (
            contract_approval_no, estimate_id, contract_id, version, project_name,
            customer_company_id, end_customer_id, sales_id, tax_invoice_manager_id, tax_invoice_request_date,
            contract_start_date, contract_end_date, payment_type, payment_condition, submit_documents,
            sales_amount, purchase_amount, profit, vendor_manager_name, vendor_manager_position,
            vendor_company_name, vendor_manager_email, vendor_manager_phone, vendor_order_request_date,
            vendor_delivery_address, vendor_payment_type, vendor_payment_condition, unty_file_no, special_notes
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            data.get('contractApprovalNo'),
            null_if_empty(data.get('estimateId')),
            null_if_empty(data.get('contractId')),
            data.get('version'),
            data.get('projectName'),
            null_if_empty(data.get('customerCompanyId')),
            null_if_empty(data.get('endCustomerId')),
            null_if_empty(data.get('salesId')),
            null_if_empty(data.get('taxInvoiceManagerId')),
            data.get('taxInvoiceRequestDate'),
            data.get('contractStartDate'),
            data.get('contractEndDate'),
            data.get('paymentType'),
            data.get('paymentCondition'),
            data.get('submitDocuments'),
            data.get('salesAmount'),
            data.get('purchaseAmount'),
            data.get('profit'),
            data.get('vendorManagerName'),
            data.get('vendorManagerPosition'),
            data.get('vendorCompanyName'),
            data.get('vendorManagerEmail'),
            data.get('vendorManagerPhone'),
            data.get('vendorOrderRequestDate'),
            data.get('vendorDeliveryAddress'),
            data.get('vendorPaymentType'),
            data.get('vendorPaymentCondition'),
            data.get('untyFileNo'),
            data.get('specialNotes')
        )


        cursor.execute(sql, values)
        contract_approval_id = cursor.lastrowid


        logging.info("DSDSDSDSDSㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇㅇ")
        logging.info(service_items)
        # 4. 서비스 항목 삽입
        if service_items:
            for item in service_items:
                cursor.execute('''
                    INSERT INTO contract_approval_service (
                        contract_approval_id, service_type, contract_type, service_category,
                        item_name, description, unit, quantity, unit_price, amount
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    contract_approval_id,
                    item.get('serviceType'),
                    item.get('contractType'),
                    item.get('serviceCategory'),
                    item.get('itemName'),
                    item.get('description'),
                    item.get('unit'),
                    item.get('quantity', 0),
                    item.get('unitPrice', 0),
                    item.get('amount', 0)
                ))

        conn.commit()
        return jsonify({'status': 'success', 'newId': contract_approval_id})
    except Exception as e:
        conn.rollback()
        logging.exception("Create contract approval failed")
        return jsonify({'status': 'fail', 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# 🔥 수주품의서 단건 조회 (GET)
@contractApproval_bp.route('/contractApproval/<int:contract_approval_id>', methods=['GET'])
def get_contract_approval(contract_approval_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Fetch contract approval details
        cursor.execute('''
            SELECT  DATE_FORMAT(ca.contract_start_date, '%%Y-%%m-%%d') AS contract_start_date,
                    DATE_FORMAT(ca.contract_end_date, '%%Y-%%m-%%d') AS contract_end_date,
                    DATE_FORMAT(ca.vendor_order_request_date, '%%Y-%%m-%%d') AS vendor_order_request_date,
                    DATE_FORMAT(ca.tax_invoice_request_date, '%%Y-%%m-%%d') AS tax_invoice_request_date,
                   c.customer_nm AS customer_company, 
                   ec.customer_nm AS end_customer, 
                   u.name AS sales_manager_name, 
                   u.email AS sales_manager_email, 
                   u.phone AS sales_manager_phone,
                   tu.name AS tax_invoice_manager_name, 
                   tu.email AS tax_invoice_manager_email, 
                   tu.phone AS tax_invoice_manager_phone,
                    CASE 
                        WHEN ca.payment_type != '일시납' AND ca.payment_type != '월납' THEN '기타'
                        ELSE ca.payment_type
                    END AS payment_type,
                    CASE 
                        WHEN ca.vendor_payment_type != '일시납' AND ca.vendor_payment_type != '월납' THEN '기타'
                        ELSE ca.vendor_payment_type
                    END AS vendor_payment_type,
                    ca.payment_type AS payment_type_other,
                    ca.vendor_payment_type AS vendor_payment_type_other, 
                    IF(ca.contract_id IS NOT NULL, 'contract', 'estimate') AS no_type,   
                    ca.*,
                    COALESCE(cc.contract_no, e.quote_id) AS no
            FROM contract_approval ca
            LEFT JOIN customer c ON ca.customer_company_id = c.customer_id
            LEFT JOIN customer ec ON ca.end_customer_id = ec.customer_id
            LEFT JOIN user u ON ca.sales_id = u.usr_id
            LEFT JOIN user tu ON ca.tax_invoice_manager_id = tu.usr_id
            LEFT JOIN estimate e ON ca.estimate_id = e.id
            LEFT JOIN contract cc ON ca.contract_id = cc.contract_id
            WHERE ca.contract_approval_id = %s
        ''', (contract_approval_id,))
        contract = cursor.fetchone()

        if not contract:
            return jsonify({'status': 'fail', 'message': 'Not Found'}), 404

        # Fetch associated service items
        cursor.execute('SELECT * FROM contract_approval_service WHERE contract_approval_id = %s', (contract_approval_id,))
        services = cursor.fetchall()
        services = convert_keys_to_camel_case(services)


        # Convert keys to camelCase
        result = convert_keys_to_camel_case({
            **contract,
            'serviceItems': services
        })

        return jsonify({'status': 'success', 'data': result})
    except Exception as e:
        logging.exception("Get contract approval failed")
        return jsonify({'status': 'fail', 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 🔥 수주품의서 수정 (PUT)
@contractApproval_bp.route('/contractApproval/<int:contract_approval_id>', methods=['PUT'])
def update_contract_approval(contract_approval_id):
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        service_items = data.pop('serviceItems', [])

        # Update 'Other' cases for paymentType and vendorPaymentType in update_contract_approval
        if data.get('paymentType') == '기타':
            data['paymentType'] = data.get('paymentTypeOther')
        if data.get('vendorPaymentType') == '기타':
            data['vendorPaymentType'] = data.get('vendorPaymentTypeOther')

        sql = """
        UPDATE contract_approval SET 
        contract_approval_no = %s, estimate_id = %s, contract_id = %s, version = %s, project_name = %s, 
        customer_company_id = %s, end_customer_id = %s, sales_id = %s, tax_invoice_manager_id = %s, tax_invoice_request_date = %s, 
        contract_start_date = %s, contract_end_date = %s, payment_type = %s, payment_condition = %s, submit_documents = %s, 
        sales_amount = %s, purchase_amount = %s, profit = %s, vendor_manager_name = %s, vendor_manager_position = %s, 
        vendor_company_name = %s, vendor_manager_email = %s, vendor_manager_phone = %s, vendor_order_request_date = %s, 
        vendor_delivery_address = %s, vendor_payment_type = %s, vendor_payment_condition = %s, unty_file_no = %s, special_notes = %s
        WHERE contract_approval_id = %s
        """

        values = (
            data['contractApprovalNo'], data['estimateId'], data['contractId'], data['version'], data['projectName'],
            data['customerCompanyId'], data['endCustomerId'], data['salesId'], data['taxInvoiceManagerId'], data['taxInvoiceRequestDate'],
            data['contractStartDate'], data['contractEndDate'], data['paymentType'], data['paymentCondition'], data['submitDocuments'],
            data['salesAmount'], data['purchaseAmount'], data['profit'], data['vendorManagerName'], data['vendorManagerPosition'],
            data['vendorCompanyName'], data['vendorManagerEmail'], data['vendorManagerPhone'], data['vendorOrderRequestDate'],
            data['vendorDeliveryAddress'], data['vendorPaymentType'], data['vendorPaymentCondition'], data['untyFileNo'], data['specialNotes'],
            contract_approval_id
        )

        cursor.execute(sql, values)

        cursor.execute('DELETE FROM contract_approval_service WHERE contract_approval_id = %s', (contract_approval_id,))
        if service_items:
            for item in service_items:
                cursor.execute('''
                    INSERT INTO contract_approval_service
                    (contract_approval_id, service_type, contract_type, service_category, item_name, description, unit, quantity, unit_price, amount)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    contract_approval_id,
                    item.get('serviceType'),
                    item.get('contractType'),
                    item.get('serviceCategory'),
                    item.get('itemName'),
                    item.get('description'),
                    item.get('unit'),
                    item.get('quantity', 0),
                    item.get('unitPrice', 0),
                    item.get('amount', 0)
                ))

        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        logging.exception("Update contract approval failed")
        return jsonify({'status': 'fail', 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 🔥 수주품의서 삭제 (DELETE)
@contractApproval_bp.route('/contractApproval/<int:contract_approval_id>', methods=['DELETE'])
def delete_contract_approval(contract_approval_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM contract_approval WHERE contract_approval_id = %s', (contract_approval_id,))
        cursor.execute('DELETE FROM contract_approval_service WHERE contract_approval_id = %s', (contract_approval_id,))
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        logging.exception("Delete contract approval failed")
        return jsonify({'status': 'fail', 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 🔥 수주품의서 목록 조회 (GET)
@contractApproval_bp.route('/contractApproval', methods=['GET'])
def list_contract_approvals():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 쿼리 파라미터 가져오기
        contract_approval_no = request.args.get('contractApprovalNo')
        created_at = request.args.get('createdAt')
        customer_company = request.args.get('customerCompany')
        end_customer = request.args.get('endCustomer')

        # 기본 SQL 쿼리
        query = """
            SELECT
                ca.contract_approval_id,
                ca.contract_approval_no,
                ca.project_name,
                ca.contract_start_date,
                ca.contract_end_date,
                ca.sales_amount,
                DATE_FORMAT(ca.created_at, '%%Y/%%m/%%d') AS created_at,
                c.customer_nm AS customer_company_name,
                ec.customer_nm AS end_customer_name
            FROM contract_approval ca
            LEFT JOIN customer c ON ca.customer_company_id = c.customer_id
            LEFT JOIN customer ec ON ca.end_customer_id = ec.customer_id
            WHERE 1=1
        """

        # 조건 추가
        params = []
        if contract_approval_no:
            query += " AND ca.contract_approval_no LIKE %s"
            params.append(f"%{contract_approval_no}%")
        if created_at:
            query += " AND DATE(ca.created_at) = %s"
            params.append(created_at)
        if customer_company:
            query += " AND c.customer_nm LIKE %s"
            params.append(f"%{customer_company}%")
        if end_customer:
            query += " AND ec.customer_nm LIKE %s"
            params.append(f"%{end_customer}%")

        # 정렬 추가
        query += " ORDER BY ca.created_at DESC"

        # 쿼리 실행
        cursor.execute(query, params)
        results = cursor.fetchall()

        # camelCase 변환
        results = convert_keys_to_camel_case(results)

        return jsonify({'status': 'success', 'data': results})
    except Exception as e:
        logging.error(f"[수주품의서 목록 조회 오류] {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()
from flask import Blueprint, request, jsonify
from models.database import get_db_connection
import logging #로그 남기기
from datetime import datetime

logging.basicConfig(level=logging.DEBUG)

contractApproval_bp = Blueprint('contractApproval', __name__)  # 블루프린트 생성

from auth.decorators import require_token
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
    if isinstance(data, list):  # 리스트 처리
        return [convert_keys_to_camel_case(item) for item in data]
    elif isinstance(data, dict):  # 딕셔너리 처리
        return {snake_to_camel(k): v for k, v in data.items()}
    return data





@contractApproval_bp.route('/contractApprovals', methods=['GET'])
def list_contract_reviews():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 쿼리 파라미터 가져오기
        estimate_no = request.args.get('estimateNo', '').strip()
        estimate_version = request.args.get('estimateVersion', '').strip()
        contract_review_no = request.args.get('contractReviewNo', '').strip()
        created_at = request.args.get('createdAt', '').strip()
        execute_date = request.args.get('executeDate', '').strip()
        customer_company = request.args.get('customerCompany', '').strip()
        end_customer = request.args.get('endCustomer', '').strip()

        # 기본 SQL 쿼리
        query = """
            SELECT
                cr.id AS contract_review_id,
                cr.contract_review_no,
                cr.project_name,
                cr.estimate_id,
                DATE_FORMAT(cr.execute_date, '%%Y/%%m/%%d') AS execute_date,
                cr.contract_amount,
                DATE_FORMAT(cr.created_at, '%%Y/%%m/%%d') AS created_at,
                cr.updated_at,
                cr.customer_company_id,
                cr.end_customer_id,
                cr.opinion,
                e.quote_id,
                c.customer_nm AS customer_company_name,
                c2.customer_nm AS end_customer_name
            FROM contract_review cr
            LEFT JOIN estimate e ON cr.estimate_id = e.id  
            LEFT JOIN customer c ON cr.customer_company_id = c.customer_id
            LEFT JOIN customer c2 ON cr.end_customer_id = c2.customer_id
            WHERE 1=1
        """

        # 조건 추가
        params = []
        if estimate_no:
            query += " AND e.quote_id LIKE %s"
            params.append(f"%{estimate_no}%")
        if estimate_version:
            query += " AND e.version = %s"
            params.append(estimate_version)
        if contract_review_no:
            query += " AND cr.contract_review_no LIKE %s"
            params.append(f"%{contract_review_no}%")
        if created_at:
            query += " AND DATE(cr.created_at) = %s"
            params.append(created_at)
        if execute_date:
            query += " AND DATE(cr.execute_date) = %s"
            params.append(execute_date)
        if customer_company:
            query += " AND c.customer_nm LIKE %s"
            params.append(f"%{customer_company}%")
        if end_customer:
            query += " AND c2.customer_nm LIKE %s"
            params.append(f"%{end_customer}%")

        # 정렬 추가
        query += " ORDER BY cr.created_at DESC"


        logging.info(f"[최종 쿼리] {query}")
        logging.info(f"[파라미터] {params}")


        # 쿼리 실행
        cursor.execute(query, params)
        results = cursor.fetchall()

        return jsonify({'status': 'success', 'data': results})
    except Exception as e:
        logging.error(f"[계약 검토서 목록 조회 오류] {e}")
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()





@contractApproval_bp.route('/contractApprovals/<int:id>', methods=['GET'])
def get_contract_review(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 마스터 정보
        sql = """
            SELECT
                cr.id AS contract_review_id,
                cr.contract_review_no,
                cr.project_name,
                cr.estimate_id,
                DATE_FORMAT(cr.execute_date, '%%Y-%%m-%%d') AS execute_date,
                cr.contract_amount,
                cr.created_at,
                cr.updated_at,
                cr.customer_company_id,
                cr.end_customer_id,
                cr.opinion,
                e.quote_id as estimate_no,
                e.version,
                cr.unty_file_no,
                c.customer_nm AS customer_company,
                c2.customer_nm AS end_customer
            FROM contract_review cr
            LEFT JOIN estimate e ON cr.estimate_id = e.id
            LEFT JOIN customer c ON cr.customer_company_id = c.customer_id
            LEFT JOIN customer c2 ON cr.end_customer_id = c2.customer_id
            WHERE cr.id = %s
        """
        cursor.execute(sql, (id,))
        review = cursor.fetchone()
        review = convert_keys_to_camel_case(review)

        if not review:
            return jsonify({'status': 'error', 'message': '존재하지 않는 검토서입니다.'}), 404

        # 매출 흐름도
        cursor.execute("SELECT route_text FROM contract_sales_route WHERE contract_review_id = %s", (id,))
        sales_routes = [row['route_text'] for row in cursor.fetchall()]
        sales_routes = convert_keys_to_camel_case(sales_routes)
        review['salesRoute'] = sales_routes

        # 계약 상세 정보
        cursor.execute("SELECT * FROM contract_detail WHERE contract_review_id = %s", (id,))
        contract_detail = cursor.fetchall()
        contract_detail = convert_keys_to_camel_case(contract_detail)
        review['contractDetails'] = contract_detail

        return jsonify({'status': 'success', 'data': review})
    except Exception as e:
        logging.error(e)
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()





@contractApproval_bp.route('/contractApprovals', methods=['POST'])
def create_contract_review():
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 0. 오늘 날짜 기반으로 채번 번호 생성
        today = datetime.today().strftime('%Y%m%d')  # YYYYMMDD 형식
        cursor.execute("""
            SELECT COUNT(*) + 1 AS next_seq
            FROM contract_review
            WHERE DATE(created_at) = CURDATE()
        """)
        next_seq = cursor.fetchone()['next_seq']
        contract_review_no = f"REV-{today}-{next_seq:03d}"  # REV-YYYYMMDD-XXX 형식


        # 1. 마스터 저장
        insert_review_sql = """
            INSERT INTO contract_review (
                contract_review_no, project_name, estimate_id, execute_date,
                customer_company_id, end_customer_id, opinion,
                contract_amount, unty_file_no
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        review_values = (
            contract_review_no, data['projectName'], data.get('estimateId'), data.get('executeDate'),
            data.get('customerCompanyId'), data.get('endCustomerId'), data.get('opinion'),
            data.get('contractAmount'), data.get('untyFileNo')
        )
        cursor.execute(insert_review_sql, review_values)
        review_id = cursor.lastrowid

        # 2. 매출 흐름 저장
        insert_route_sql = """
            INSERT INTO contract_sales_route (contract_review_id, route_text)
            VALUES (%s, %s)
        """
        for route in data.get('salesRoute', []):
            cursor.execute(insert_route_sql, (review_id, route))

        # 3. 계약 세부사항 저장
        insert_detail_sql = """
            INSERT INTO contract_detail (contract_review_id, category, standard, detail)
            VALUES (%s, %s, %s, %s)
        """
        for item in data.get('contractDetails', []):
            cursor.execute(insert_detail_sql, (
                review_id,
                item.get('category'),
                item.get('standard'),
                item.get('detail')
            ))

        conn.commit()
        return jsonify({'status': 'success', 'newId': review_id})
    except Exception as e:
        logging.error(e)
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()





@contractApproval_bp.route('/contractApprovals/<int:id>', methods=['PUT'])
def update_contract_review(id):
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. 마스터 수정
        update_sql = """
            UPDATE contract_review SET
                project_name = %s, estimate_id = %s, execute_date = %s,
                customer_company_id = %s, end_customer_id = %s, opinion = %s,
                contract_amount = %s, unty_file_no = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        cursor.execute(update_sql, (
            data['projectName'], data.get('estimateId'), data.get('executeDate'),
            data.get('customerCompanyId'), data.get('endCustomerId'), data.get('opinion'),
            data.get('contractAmount'), data.get('untyFileNo'), id
        ))

        # 2. 기존 매출 흐름 삭제 후 재삽입
        cursor.execute("DELETE FROM contract_sales_route WHERE contract_review_id = %s", (id,))
        insert_route_sql = "INSERT INTO contract_sales_route (contract_review_id, route_text) VALUES (%s, %s)"
        for route in data.get('salesRoute', []):
            cursor.execute(insert_route_sql, (id, route))

        # 3. 기존 계약 세부사항 삭제
        cursor.execute("DELETE FROM contract_detail WHERE contract_review_id = %s", (id,))

        # 4. 새로운 계약 세부사항 삽입
        insert_detail_sql = """
            INSERT INTO contract_detail (contract_review_id, category, standard, detail)
            VALUES (%s, %s, %s, %s)
        """
        for item in data.get('contractDetails', []):
            cursor.execute(insert_detail_sql, (
                id,
                item.get('category'),
                item.get('standard'),
                item.get('detail')
            ))

        conn.commit()
        return jsonify({'status': 'success', 'updatedId': id})
    except Exception as e:
        logging.error(e)
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()





@contractApproval_bp.route('/contractApprovals/<int:id>', methods=['DELETE'])
def delete_contract_review(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. 수주품의서 존재 여부 확인
        cursor.execute("SELECT id FROM contract_approval WHERE id = %s", (id,))
        review = cursor.fetchone()
        if not review:
            return jsonify({'status': 'error', 'message': '존재하지 않는 계약 검토서입니다.'}), 404

        # 2. 관련 데이터 삭제
        # cursor.execute("DELETE FROM contract_sales_route WHERE contract_review_id = %s", (id,))
        # cursor.execute("DELETE FROM contract_detail WHERE contract_review_id = %s", (id,))
        # cursor.execute("DELETE FROM contract_review WHERE id = %s", (id,))

        conn.commit()
        return jsonify({'status': 'success', 'deletedId': id})
    except Exception as e:
        logging.error(f"[계약 검토서 삭제 오류] {e}")
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

from flask import Blueprint, request, jsonify
from models.database import get_db_connection
import logging #로그 남기기



logging.basicConfig(level=logging.DEBUG)

contract_bp = Blueprint('contract', __name__)  # 블루프린트 생성









#리스트 조회
@contract_bp.route('/contracts', methods=['GET'])
def list_contracts():
    """
    쿼리 파라미터 예시:
    GET /contracts?search=클라우드&product=네트워크&manager=김철수&start_date=2025-01-01&end_date=2025-12-31&taskType=전체&sort=contract_date

    반환 예시:
    [
      {
        "contract_id": 1,
        "contract_no": "CT2300001",
        "contract_name": "맞춤형 클라우드 도입 계약",
        "customer_name": "핑거포스트",
        "contract_dt": "2023-01-01",
        "approver": "홍길동",
        "amount": 100000,
        "tax": 10000,
        "total_amount": 110000,
        ...
      },
      ...
    ]
    """
    conn = get_db_connection()
    try:
        # 1) 쿼리 파라미터 가져오기
        search = request.args.get('search', '').strip()
        product = request.args.get('product', '').strip()
        manager = request.args.get('manager', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        task_type = request.args.get('taskType', '전체').strip()
        sort = request.args.get('sort', 'contract_date').strip()

        # 2) 기본 SQL 생성 (JOIN으로 고객사 이름을 얻거나, 필요한 경우 상품 테이블도 JOIN)
        #    여기서는 customer 테이블만 LEFT JOIN 예시
        sql = """
        SELECT 
            c.contract_id,
            c.contract_no,
            c.contract_name,
            c.contract_dt AS contract_date,
            c.contract_start_dt,
            c.contract_end_dt,
            c.approver AS manager,
            c.amount,
            c.tax,
            c.total_amount,
            cust.customer_nm AS customer_name
        FROM contract c
        LEFT JOIN customer cust 
               ON c.customer_id = cust.customer_id
        """
        where_clauses = []
        params = []

        # 3) 검색조건(WHERE) 동적 구성
        if search:
            # 계약명이나 고객명에 search 단어가 포함되는지
            where_clauses.append("(c.contract_name LIKE %s OR cust.customer_nm LIKE %s)")
            params.append(f"%{search}%")
            params.append(f"%{search}%")
        
        if manager:
            # 담당자(approver) 검색
            where_clauses.append("c.approver LIKE %s")
            params.append(f"%{manager}%")

        # 예: 계약일 범위 조회
        if start_date and end_date:
            where_clauses.append("c.contract_dt BETWEEN %s AND %s")
            params.append(start_date)
            params.append(end_date)
        elif start_date:
            where_clauses.append("c.contract_dt >= %s")
            params.append(start_date)
        elif end_date:
            where_clauses.append("c.contract_dt <= %s")
            params.append(end_date)

        # product 조건이 있는 경우: contract_product / product 테이블 JOIN 필요
        # 간단히 contract_product 안에 product_id가 있다고 가정. product 이름 검색하려면 추가 JOIN 필요
        if product:
            sql += """
            LEFT JOIN contract_product cp 
                   ON c.contract_id = cp.contract_id
            LEFT JOIN product p 
                   ON cp.product_id = p.product_id
            """
            # productName으로 상품명 검색
            where_clauses.append("p.p_name LIKE %s")
            params.append(f"%{product}%")

        # taskType(계약구분) = c.contract_type 라고 가정
        if task_type and task_type != "전체":
            where_clauses.append("c.contract_type = %s")
            params.append(task_type)

        # 4) WHERE 절 동적 결합
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        # 5) 정렬(sort)
        #    기본값 contract_dt (DESC 정렬 예시) -- 필요에 맞게 ASC/DESC 조정
        #    만약 프런트에서 ASC/DESC를 같이 넘겨주려면 추가 파라미터 필요
        valid_sort_fields = ["contract_dt", "amount", "customer_name"]  # 허용할 정렬 컬럼
        if sort not in valid_sort_fields:
            sort = "contract_dt"
        sql += f" ORDER BY c.{sort} DESC"

        # 6) SQL 실행
        with conn.cursor() as cursor:
            logging.info("최종 SQL: %s", sql)
            logging.info("params: %s", params)
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        # 7) JSON 응답
        return jsonify(rows), 200
    
    except Exception as e:
        logging.exception("Error in list_contracts")
        return jsonify({"result": False, "error": str(e)}), 500
    finally:
        conn.close()




# 저장
@contract_bp.route('/contracts', methods=['POST'])
def create_contract():
    """
    Body 예시:
    {
      "contract_name": "테스트 계약",
      "customer_id": 123,
      "estimate_id": null,
      "contract_dt": "2023-01-01",
      "contract_start_dt": "2023-02-01",
      "contract_end_dt": "2023-12-31",
      "tax_type": "매출과세",
      "unit_price_type": "부가세 포함",
      "quantity": 10,
      "amount": 100000,
      "tax": 10000,
      "total_amount": 110000,
      "pay_terms": "30일",
      "warranty_period": "1년",
      "contract_type": "연간 계약",
      "delivery_dt": "2023-03-01",
      "approver": "홍길동",
      "memo": "비고",
      "products": [
        {
          "product_id": 1,
          "quantity": 2,
          "unit_price": 30000,
          "tax_rate": 10,
          "tax_amount": 3000,
          "total_price": 33000,
          "sales_dt": "2023-03-01",
          "sales_cycle": "monthly",
          "memo": "비고1"
        },
        {
          "product_id": 2,
          "quantity": 1,
          "unit_price": 70000,
          "tax_rate": 10,
          "tax_amount": 7000,
          "total_price": 77000,
          "sales_dt": "2023-03-05",
          "sales_cycle": "monthly",
          "memo": "비고2"
        }
      ]
    }
    """
    data = request.get_json()
    conn = get_db_connection()
    logging.info("함수 시작");
    try:
        with conn.cursor() as cursor:
            # ✅ 1) DB 함수로 계약번호 채번
            cursor.execute("SELECT FnGenerateContractNo() AS contract_no")
            contract_no = cursor.fetchone()["contract_no"]
            logging.info("채번 완료 == " + contract_no);

            # ✅ 2) 계약 테이블 insert
            sql_contract = """
                INSERT INTO contract(
                  contract_no, 
                  contract_name, customer_id, estimate_id, contract_dt,
                  contract_start_dt, contract_end_dt, tax_type, unit_price_type,
                  quantity, amount, tax, total_amount, pay_terms,
                  warranty_period, contract_type, delivery_dt, approver, memo , unty_file_no
                )
                VALUES (
                  %(contract_no)s,
                  %(contract_name)s, %(customer_id)s, %(estimate_id)s, %(contract_dt)s,
                  %(contract_start_dt)s, %(contract_end_dt)s, %(tax_type)s, %(unit_price_type)s,
                  %(quantity)s, %(amount)s, %(tax)s, %(total_amount)s, %(pay_terms)s,
                  %(warranty_period)s, %(contract_type)s, %(delivery_dt)s, %(approver)s, %(memo)s, %(untyFileNo)s
                )
            """
            contract_params = {
                'contract_no': contract_no,
                'contract_name': data.get('contract_name'),
                'customer_id': data.get('customer_id'),
                'estimate_id': data.get('estimate_id'),
                'contract_dt': data.get('contract_dt'),
                'contract_start_dt': data.get('contract_start_dt'),
                'contract_end_dt': data.get('contract_end_dt'),
                'tax_type': data.get('tax_type'),
                'unit_price_type': data.get('unit_price_type'),
                'quantity': data.get('quantity'),
                'amount': data.get('amount'),
                'tax': data.get('tax'),
                'total_amount': data.get('total_amount'),
                'pay_terms': data.get('pay_terms'),
                'warranty_period': data.get('warranty_period'),
                'contract_type': data.get('contract_type'),
                'delivery_dt': data.get('delivery_dt'),
                'approver': data.get('approver'),
                'memo': data.get('memo'),
                'untyFileNo': data.get('untyFileNo')
            }
            cursor.execute(sql_contract, contract_params)

            new_contract_id = cursor.lastrowid

            # ✅ 3) 계약 제품 insert
            products = data.get('products', [])
            sql_product = """
                INSERT INTO contract_product(
                  contract_id, product_id, quantity, unit_price, 
                  tax_rate, tax_amount, total_price, sales_dt, sales_cycle, memo
                )
                VALUES (
                  %(contract_id)s, %(product_id)s, %(quantity)s, %(unit_price)s,
                  %(tax_rate)s, %(tax_amount)s, %(total_price)s, %(sales_dt)s, %(sales_cycle)s, %(memo)s
                )
            """
            for p in products:
                product_params = {
                    'contract_id': new_contract_id,
                    'product_id': p.get('product_id'),
                    'quantity': p.get('quantity'),
                    'unit_price': p.get('unit_price'),
                    'tax_rate': p.get('tax_rate'),
                    'tax_amount': p.get('tax_amount'),
                    'total_price': p.get('total_price'),
                    'sales_dt': p.get('sales_dt'),
                    'sales_cycle': p.get('sales_cycle'),
                    'memo': p.get('memo'),
                }
                cursor.execute(sql_product, product_params)

            conn.commit()

        return jsonify({
            "result": True,
            "message": "Contract created successfully",
            "contract_id": new_contract_id,
            "contract_no": contract_no
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"result": False, "error": str(e)}), 500
    finally:
        conn.close()











# 2) 계약 상세조회 (수정화면 진입 시 데이터 조회)
@contract_bp.route('/contracts/<int:contract_id>', methods=['GET'])
def get_contract_detail(contract_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # (1) 계약 정보 + 고객사명 + 견적명 JOIN
            sql_contract = """
                SELECT
                    cust.customer_nm,
                    CONCAT(e.quote_id, '(', e.quote_details, ')') AS quote_name,
                    DATE_FORMAT(c.contract_dt, '%%Y-%%m-%%d') AS contract_dt,
                    DATE_FORMAT(c.contract_start_dt, '%%Y-%%m-%%d') AS contract_start_dt,
                    DATE_FORMAT(c.contract_end_dt, '%%Y-%%m-%%d') AS contract_end_dt,
                    DATE_FORMAT(c.delivery_dt, '%%Y-%%m-%%d') AS delivery_dt,
                    c.*
                FROM contract c
                LEFT JOIN customer cust ON c.customer_id = cust.customer_id
                LEFT JOIN t_estimate e ON c.estimate_id = e.id
                WHERE c.contract_id = %s
                """

            cursor.execute(sql_contract, (contract_id,))
            contract_data = cursor.fetchone()

            if not contract_data:
                return jsonify({"result": False, "message": "Not found"}), 404

            # (2) 계약 제품 정보 + 제품명 JOIN
            sql_products = """
            SELECT
                cp.*,
                p.p_name,
                p.p_price
            FROM contract_product cp
            LEFT JOIN t_product_add p
                   ON cp.product_id = p.id
            WHERE cp.contract_id = %s
            """
            cursor.execute(sql_products, (contract_id,))
            products = cursor.fetchall()

            # (3) products 배열을 contract_data에 추가
            contract_data["products"] = products

        return jsonify({"result": True, "data": contract_data}), 200
    except Exception as e:
        return jsonify({"result": False, "error": str(e)}), 500
    finally:
        conn.close()


# 3) 계약 수정(갱신)
@contract_bp.route('/contracts/<int:contract_id>', methods=['PUT'])
def update_contract(contract_id):
    data = request.get_json()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1) contract 테이블 업데이트
            sql_update_contract = """
                UPDATE contract
                SET
                  contract_name = %(contract_name)s,
                  customer_id = %(customer_id)s,
                  estimate_id = %(estimate_id)s,
                  contract_dt = %(contract_dt)s,
                  contract_start_dt = %(contract_start_dt)s,
                  contract_end_dt = %(contract_end_dt)s,
                  tax_type = %(tax_type)s,
                  unit_price_type = %(unit_price_type)s,
                  quantity = %(quantity)s,
                  amount = %(amount)s,
                  tax = %(tax)s,
                  total_amount = %(total_amount)s,
                  pay_terms = %(pay_terms)s,
                  warranty_period = %(warranty_period)s,
                  contract_type = %(contract_type)s,
                  delivery_dt = %(delivery_dt)s,
                  approver = %(approver)s,
                  memo = %(memo)s,
                  unty_file_no = %(unty_file_no)s
                WHERE contract_id = %(contract_id)s
            """
            contract_params = {
                'contract_id': contract_id,
                'contract_name': data.get('contract_name'),
                'customer_id': data.get('customer_id'),
                'estimate_id': data.get('estimate_id'),
                'contract_dt': data.get('contract_dt'),
                'contract_start_dt': data.get('contract_start_dt'),
                'contract_end_dt': data.get('contract_end_dt'),
                'tax_type': data.get('tax_type'),
                'unit_price_type': data.get('unit_price_type'),
                'quantity': data.get('quantity'),
                'amount': data.get('amount'),
                'tax': data.get('tax'),
                'total_amount': data.get('total_amount'),
                'pay_terms': data.get('pay_terms'),
                'warranty_period': data.get('warranty_period'),
                'contract_type': data.get('contract_type'),
                'delivery_dt': data.get('delivery_dt'),
                'approver': data.get('approver'),
                'memo': data.get('memo'),
                'unty_file_no': data.get('untyFileNo')
            }
            cursor.execute(sql_update_contract, contract_params)

            # 2) contract_product 삭제 후 재삽입(단순화 방법)
            #    - 혹은, product_id별로 개별 UPDATE/INSERT를 해줄 수도 있습니다.
            sql_delete_products = "DELETE FROM contract_product WHERE contract_id = %s"
            cursor.execute(sql_delete_products, (contract_id,))

            products = data.get('products', [])
            sql_insert_product = """
                INSERT INTO contract_product(
                  contract_id, product_id, quantity, unit_price, 
                  tax_rate, tax_amount, total_price, sales_dt, sales_cycle, memo
                )
                VALUES (
                  %(contract_id)s, %(product_id)s, %(quantity)s, %(unit_price)s,
                  %(tax_rate)s, %(tax_amount)s, %(total_price)s, %(sales_dt)s, %(sales_cycle)s, %(memo)s
                )
            """
            for p in products:
                product_params = {
                    'contract_id': contract_id,
                    'product_id': p.get('product_id'),
                    'quantity': p.get('quantity'),
                    'unit_price': p.get('unit_price'),
                    'tax_rate': p.get('tax_rate'),
                    'tax_amount': p.get('tax_amount'),
                    'total_price': p.get('total_price'),
                    'sales_dt': p.get('sales_dt'),
                    'sales_cycle': p.get('sales_cycle'),
                    'memo': p.get('memo'),
                }
                cursor.execute(sql_insert_product, product_params)

            conn.commit()

        return jsonify({"result": True, "message": "Contract updated successfully"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"result": False, "error": str(e)}), 500
    finally:
        conn.close()

# 4) 계약 삭제
@contract_bp.route('/contracts//<int:contract_id>', methods=['DELETE'])
def delete_contract(contract_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "DELETE FROM contract WHERE contract_id = %s"
            cursor.execute(sql, (contract_id,))
            # contract_product 는 ON DELETE CASCADE가 걸려있으므로 자동 삭제
            conn.commit()
        return jsonify({"result": True, "message": "Contract deleted successfully"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"result": False, "error": str(e)}), 500
    finally:
        conn.close()
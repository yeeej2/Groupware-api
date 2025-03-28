from flask import Blueprint, request, jsonify
from models.database import get_db_connection
import logging
from datetime import datetime
import pdb
import traceback


logging.basicConfig(level=logging.DEBUG)

approval_bp = Blueprint('approval', __name__)

def generate_approval_doc_number(conn):
    """
    고유 결재 문서 번호를 생성하는 예시 함수
    ex) APP-YYYYMMDD-0001
    """
    today_str = datetime.now().strftime('%Y%m%d')
    
    # 오늘 날짜 기준으로 approval에 몇 건이 들어갔는지 세기
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM approval
            WHERE DATE(request_date) = CURDATE()
        """)
        result = cursor.fetchone()   # 예: {'cnt': 5}

        # 딕셔너리 키 직접 접근
        count = result['cnt']
    
    # 시퀀스 번호(1부터 시작) 4자리 zero-padding
    seq = f"{count + 1:04d}"
    return f"APP-{today_str}-{seq}"

@approval_bp.route('/approval/request', methods=['POST'])
def create_approval_request():

    """
    결재 요청 등록 API
    - approval 테이블에 INSERT
    - approval_history 테이블에 'REQUEST' 액션 INSERT
    """

    logging.info("승인요청 시작!")
    try:
        # 1) 요청 파라미터 파싱
        data = request.get_json()
        logging.info("여기는 통과")

        doc_type = data.get('doc_type', 'ESTIMATE')                # 예: "ESTIMATE"
        doc_id = data.get('doc_id', 297)                             # 연결되는 문서 PK
        approval_task_name = data.get('approval_task_name', '견적서 승인 요청')
        title = data.get('title', '제목 없음')
        content = data.get('content', '본문 내용 입니다~~~')
        unty_file_no = data.get('unty_file_no', None)
        requester_id = data.get('requester_id', 1) # TODO : 요청자 id 나중에 세션으로 받아와야 할듯
        
        # 결재 이력을 남길 때 필요한 승인자(첫 결재자)
        approver_id = data.get('approver_id') or 1  # 실제론 여럿 일 수도 있음...... 현재는 자기자신으로......
        logging.info("sssddddddddd")
        logging.info(approver_id)


        logging.info("logging.info(unty_file_no")
        logging.info(unty_file_no)

        # 2) DB 커넥션 가져오기
        conn = get_db_connection()
        
        try:
            # 3) 문서번호 생성
            approval_doc_number = generate_approval_doc_number(conn)

            # 4) approval INSERT
            insert_approval_sql = """
                INSERT INTO approval (
                    doc_type, doc_id, 
                    approval_task_name, 
                    approval_doc_number, 
                    title, content, 
                    unty_file_no, status, 
                    requester_id, request_date
                )
                VALUES (
                    %s, %s, 
                    %s, 
                    %s, 
                    %s, %s, 
                    %s, '승인요청', 
                    %s, NOW()
                )
            """
            
            with conn.cursor() as cursor:
                cursor.execute(insert_approval_sql, (
                    doc_type, doc_id,
                    approval_task_name,
                    approval_doc_number,
                    title, content,
                    unty_file_no,
                    requester_id
                ))
                
                # 방금 INSERT된 PK (approval_id) 가져오기
                approval_id = cursor.lastrowid
                
                # 5) approval_history INSERT (REQUEST 액션)
                insert_history_sql = """
                    INSERT INTO approval_history (
                        approval_id, approver_id,
                        action, comment,
                        action_date, created_at
                    )
                    VALUES (
                        %s, %s,
                        'REQUEST', '',
                        NOW(), NOW()
                    )
                """
                cursor.execute(insert_history_sql, (
                    approval_id, approver_id
                ))

                # 5-1) contract 테이블에 approval_id 업데이트
                update_contract_sql = """
                    UPDATE contract
                    SET approval_id = %s
                    WHERE contract_id = %s
                """
                cursor.execute(update_contract_sql, (approval_id, "6")) ## 임시 테스트로 값 고정
                logging.info("rPdir djqepdlxmehla?????????????????????");

            # 모든 쿼리 정상 완료 시 commit
            conn.commit()

        except Exception as e:
            conn.rollback()
            traceback.print_exc()  # 🔥 콘솔에 전체 에러 경로 다 보여줌
            logging.error("Error while inserting approval/request: %s", str(e))
            return jsonify({
                'result': 'error',
                'message': str(e)
            }), 500

        finally:
            conn.close()

        # 성공 시 응답
        return jsonify({
            'result': 'success',
            'approval_id': approval_id,
            'approval_doc_number': approval_doc_number
        })

    except Exception as ex:
        logging.error("Unexpected error in create_approval_request: %s", str(ex))
        return jsonify({'result': 'error', 'message': str(ex)}), 500
    















@approval_bp.route('/approval/approve', methods=['POST'])
def approve_approval():
    """
    결재 승인 처리 API
    - 요청 JSON 예시:
      {
         "approval_id": 10,
         "approver_id": 2001,
         "comment": "승인합니다."
      }
    """
    try:
        data = request.get_json()
        approval_id = data['approval_id']
        approver_id = data['approver_id']
        comment = data.get('comment', '')

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 1) approval_history에 APPROVE 이력 삽입
                insert_sql = """
                    INSERT INTO approval_history (
                        approval_id, approver_id, action, comment,
                        action_date, created_at
                    )
                    VALUES (
                        %s, %s, '승인', %s, NOW(), NOW()
                    )
                """
                cursor.execute(insert_sql, (approval_id, approver_id, comment))

                # 2) approval 테이블의 status를 'APPROVED'로 업데이트
                #    final_approver_id, final_approval_date 도 갱신
                update_sql = """
                    UPDATE approval
                    SET status = '승인',
                        final_approver_id = %s,
                        final_approval_date = NOW()
                    WHERE approval_id = %s
                """
                cursor.execute(update_sql, (approver_id, approval_id))

            conn.commit()

        except Exception as e:
            conn.rollback()
            logging.error("Error in approve_approval: %s", str(e))
            return jsonify({'result': 'error', 'message': str(e)}), 500
        finally:
            conn.close()

        return jsonify({'result': 'success', 'approval_id': approval_id})

    except Exception as ex:
        logging.error("Unexpected error in approve_approval: %s", str(ex))
        return jsonify({'result': 'error', 'message': str(ex)}), 500












@approval_bp.route('/approval/reject', methods=['POST'])
def reject_approval():
    """
    결재 반려 처리 API
    - 요청 JSON 예시:
      {
         "approval_id": 10,
         "approver_id": 2001,
         "comment": "사유: 금액 오류로 반려합니다."
      }
    """
    try:
        data = request.get_json()
        approval_id = data['approval_id']
        approver_id = data['approver_id']
        comment = data.get('comment', '')

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 1) approval_history 테이블에 REJECT 이력
                insert_sql = """
                    INSERT INTO approval_history (
                        approval_id, approver_id, action, comment,
                        action_date, created_at
                    )
                    VALUES (
                        %s, %s, '반려', %s, NOW(), NOW()
                    )
                """
                cursor.execute(insert_sql, (approval_id, approver_id, comment))

                # 2) approval 테이블 상태를 'REJECTED'로 업데이트
                #    최종 승인자(여기서는 반려자), 반려 시각 저장
                update_sql = """
                    UPDATE approval
                    SET status = '반려',
                        final_approver_id = %s,
                        final_approval_date = NOW()
                    WHERE approval_id = %s
                """
                cursor.execute(update_sql, (approver_id, approval_id))

            conn.commit()

        except Exception as e:
            conn.rollback()
            logging.error("Error in reject_approval: %s", str(e))
            return jsonify({'result': 'error', 'message': str(e)}), 500
        finally:
            conn.close()

        return jsonify({'result': 'success', 'approval_id': approval_id})

    except Exception as ex:
        logging.error("Unexpected error in reject_approval: %s", str(ex))
        return jsonify({'result': 'error', 'message': str(ex)}), 500









@approval_bp.route('/approval/<int:approval_id>', methods=['GET'])
def get_approval_detail(approval_id):
    """
    결재 상세 조회 API
    - 결재 메인 정보 + 결재 이력 조회
    - 응답 JSON 예시:
      {
        "result": "success",
        "approval": {
           "approval_id": 10,
           "doc_type": "ESTIMATE",
           "doc_id": 101,
           "approval_task_name": "견적서 승인 요청",
           "approval_doc_number": "APP-20250327-0001",
           "title": "결재 제목",
           "content": "<p>본문</p>",
           "unty_file_no": 123,
           "status": "REQUESTING",
           "requester_id": 1001,
           "request_date": "2025-03-27 11:00:00",
           "final_approver_id": null,
           "final_approval_date": null
        },
        "history": [
           {
             "history_id": 1,
             "approval_id": 10,
             "approver_id": 2001,
             "action": "REQUEST",
             "comment": "",
             "action_date": "2025-03-27 11:00:01",
             "created_at": "2025-03-27 11:00:01"
           },
           ...
        ]
      }
    """
    logging.info("상세 조회!!!");
    conn = get_db_connection()
    try:
        # 1) approval 테이블 조회
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    a.approval_id,
                    a.doc_type,
                    a.doc_id,
                    a.approval_task_name,
                    a.approval_doc_number,
                    a.title,
                    a.content,
                    a.unty_file_no,
                    a.status,
                    a.requester_id,
                    DATE_FORMAT(a.request_date, '%%Y-%%m-%%d %%H:%%i:%%s') AS request_date,
                    a.final_approver_id,
                    DATE_FORMAT(a.final_approval_date, '%%Y-%%m-%%d %%H:%%i:%%s') AS final_approval_date,
                    h.comment AS latest_reject_comment
                FROM approval a
                LEFT JOIN (
                    SELECT ah1.approval_id, ah1.comment
                    FROM approval_history ah1
                    WHERE ah1.action = '반려'
                    AND ah1.history_id = (
                        SELECT MAX(ah2.history_id)
                        FROM approval_history ah2
                        WHERE ah2.approval_id = ah1.approval_id AND ah2.action = '반려'
                    )
                ) h ON a.approval_id = h.approval_id
                WHERE a.approval_id = %s
            """, (approval_id,))
            logging.info("whghlwwlwlwlwlwlwlwl");
            logging.info(cursor);
            approval_row = cursor.fetchone()
            if not approval_row:
                return jsonify({'result': 'error', 'message': 'Approval not found'}), 404

        # 2) approval_history 테이블 조회
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    history_id, approval_id, approver_id,
                    action, comment,
                    DATE_FORMAT(action_date, '%%Y-%%m-%%d %%H:%%i:%%s') AS action_date,
                    DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') AS created_at
                FROM approval_history
                WHERE approval_id = %s
                ORDER BY history_id ASC
            """, (approval_id,))

            history_rows = cursor.fetchall()
        
        logging.info("초치치ㅗㅚ종");
        logging.info(approval_row);
        logging.info(history_rows);

        return jsonify({
            'result': 'success',
            'approval': approval_row,
            'history': history_rows
        })

    except Exception as ex:
        logging.error("Error in get_approval_detail: %s", str(ex))
        return jsonify({'result': 'error', 'message': str(ex)}), 500
    finally:
        conn.close()

















@approval_bp.route('/approval/list', methods=['GET'])
def get_approval_list():
    """
    결재 리스트 조회 API
    - 요청 파라미터:
      - status: 결재 상태 필터 (예: '승인요청', '승인', '반려')
      - requester_id: 요청자 ID 필터
      - page: 페이지 번호 (기본값: 1)
      - per_page: 페이지당 항목 수 (기본값: 10)
    - 응답 JSON 예시:
      {
        "result": "success",
        "data": [
          {
            "approval_id": 1,
            "approval_doc_number": "APP-20250327-0001",
            "title": "결재 제목",
            "status": "승인요청",
            "request_date": "2025-03-27 11:00:00",
            "requester_id": 1001
          },
          ...
        ],
        "pagination": {
          "page": 1,
          "per_page": 10,
          "total": 25
        }
      }
    """
    try:
        # 요청 파라미터 가져오기
        status = request.args.get('status')  # 결재 상태 필터
        requester_id = request.args.get('requester_id')  # 요청자 ID 필터
        page = int(request.args.get('page', 1))  # 페이지 번호 (기본값: 1)
        per_page = int(request.args.get('per_page', 10))  # 페이지당 항목 수 (기본값: 10)

        offset = (page - 1) * per_page  # 페이징을 위한 offset 계산

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 기본 SQL 쿼리
                sql = """
                    SELECT
                        *
                    FROM approval
                    WHERE 1=1
                """
                params = []

                # 상태 필터 추가
                if status:
                    sql += " AND status = %s"
                    params.append(status)

                # 요청자 ID 필터 추가
                if requester_id:
                    sql += " AND requester_id = %s"
                    params.append(requester_id)

                # 정렬 및 페이징 추가
                sql += " ORDER BY request_date DESC LIMIT %s OFFSET %s"
                params.extend([per_page, offset])

                # 쿼리 실행
                cursor.execute(sql, params)
                approvals = cursor.fetchall()

                # 총 항목 수 계산
                cursor.execute("""
                    SELECT COUNT(*) AS total
                    FROM approval
                    WHERE 1=1
                """ + (" AND status = %s" if status else "") + (" AND requester_id = %s" if requester_id else ""),
                params[:-2] if params else [])
                total = cursor.fetchone()['total']

            # 응답 데이터 구성
            return jsonify({
                'result': 'success',
                'data': approvals,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total
                }
            }), 200

        except Exception as e:
            logging.error("Error in get_approval_list: %s", str(e))
            return jsonify({'result': 'error', 'message': str(e)}), 500

        finally:
            conn.close()

    except Exception as ex:
        logging.error("Unexpected error in get_approval_list: %s", str(ex))
        return jsonify({'result': 'error', 'message': str(ex)}), 500
    





@approval_bp.route('/approval/updateStatus/<int:approval_id>', methods=['POST'])
def update_approval_status(approval_id):
    """
    결재 상태 업데이트 API
    - 요청 JSON 예시:
      {
        "status": "승인대기",
        "comment": "상태 변경 사유"
      }
    """
    try:
        # 요청 데이터 파싱
        data = request.get_json()
        new_status = data.get('status')
        comment = data.get('comment', '').strip()
        approver_id = data.get('approver_id')

        if not new_status:
            return jsonify({'result': 'error', 'message': 'Status is required'}), 400

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 1) approval 테이블의 status 업데이트
                update_sql = """
                    UPDATE approval
                    SET status = %s
                    WHERE approval_id = %s
                """
                cursor.execute(update_sql, (new_status, approval_id))

                # 2) approval_history 테이블에 상태 변경 이력 추가
                insert_history_sql = """
                    INSERT INTO approval_history (
                        approval_id, approver_id, action, comment,
                        action_date, created_at
                    )
                    VALUES (
                        %s, %s, %s, %s, NOW(), NOW()
                    )
                """
                cursor.execute(insert_history_sql, (
                    approval_id, approver_id, new_status, comment
                ))

            conn.commit()

            return jsonify({'result': 'success', 'message': 'Status updated successfully'}), 200

        except Exception as e:
            conn.rollback()
            logging.error("Error in update_approval_status: %s", str(e))
            return jsonify({'result': 'error', 'message': str(e)}), 500

        finally:
            conn.close()

    except Exception as ex:
        logging.error("Unexpected error in update_approval_status: %s", str(ex))
        return jsonify({'result': 'error', 'message': str(ex)}), 500
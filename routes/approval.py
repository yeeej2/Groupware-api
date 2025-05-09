from flask import Blueprint, request, jsonify
from models.database import get_db_connection
import logging
from datetime import datetime
import traceback

logging.basicConfig(level=logging.DEBUG)
approval_bp = Blueprint('approval', __name__)

from auth.decorators import require_token
@approval_bp.before_request
@require_token
def require_token_for_user_bp():
    pass

# 결재 상태 상수
class ApprovalStatus:
    DRAFT = '작성중'
    REQUESTING = '승인요청'
    PENDING = '승인대기'
    APPROVED = '승인'
    REJECTED = '반려'
    CANCELLED = '취소'

class ApprovalAction:
    REQUEST = '승인요청'
    APPROVE = '승인'
    REJECT = '반려'
    CANCEL = '취소'

def generate_approval_doc_number(conn):
    """고유 결재 문서 번호 생성"""
    today_str = datetime.now().strftime('%Y%m%d')
    
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM approval
            WHERE DATE(created_at) = CURDATE()
        """)
        result = cursor.fetchone()
        count = result['cnt']
    
    seq = f"{count + 1:04d}"
    return f"APP-{today_str}-{seq}"

@approval_bp.route('/approval/request', methods=['POST'])
def create_approval_request():
    """결재 요청 등록 API"""
    try:
        data = request.get_json()
        approvers = data.get('approvers', [])  # 결재자 목록
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 1. 문서번호 생성
                approval_doc_number = generate_approval_doc_number(conn)

                # 2. approval 테이블에 기본 정보 저장
                insert_approval_sql = """
                    INSERT INTO approval (
                        doc_type, doc_id, 
                        approval_task_name, 
                        approval_doc_number, 
                        title, content, 
                        unty_file_no, status, 
                        requester_id, created_at
                    )
                    VALUES (
                        %s, %s, 
                        %s, 
                        %s, 
                        %s, %s, 
                        %s, %s, 
                        %s, NOW()
                    )
                """
                
                cursor.execute(insert_approval_sql, (
                    data.get('doc_type', 'ESTIMATE'),
                    data.get('doc_id'),
                    data.get('approval_task_name', '견적서 승인 요청'),
                    approval_doc_number,
                    data.get('title', '제목 없음'),
                    data.get('content', ''),
                    data.get('unty_file_no'),
                    ApprovalStatus.REQUESTING,
                    data.get('requester_id')
                ))
                
                approval_id = cursor.lastrowid

                # 3. approval_line 테이블에 결재자 정보 저장
                for order, approver in enumerate(approvers, 1):
                    insert_line_sql = """
                        INSERT INTO approval_line (
                            approval_id, approver_id,
                            `order`, status
                        )
                        VALUES (
                            %s, %s,
                            %s, %s
                        )
                    """
                    cursor.execute(insert_line_sql, (
                        approval_id,
                        approver['approver_id'],
                        order,
                        ApprovalStatus.PENDING
                    ))

                # 4. approval_history에 요청 이력 저장 (한 번만 기록)
                insert_history_sql = """
                    INSERT INTO approval_history (
                        approval_id, approver_id,
                        action, comment,
                        created_at
                    )
                    VALUES (
                        %s, %s,
                        %s, %s,
                        NOW()
                    )
                """
                cursor.execute(insert_history_sql, (
                    approval_id,
                    data.get('requester_id'),
                    ApprovalAction.REQUEST,
                    '결재 요청이 등록되었습니다.'
                ))

            conn.commit()
            return jsonify({
                'result': 'success',
                'approval_id': approval_id,
                'approval_doc_number': approval_doc_number
            })

        except Exception as e:
            conn.rollback()
            traceback.print_exc()
            logging.error("Error while inserting approval/request: %s", str(e))
            return jsonify({
                'result': 'error',
                'message': str(e)
            }), 500

        finally:
            conn.close()

    except Exception as ex:
        logging.error("Unexpected error in create_approval_request: %s", str(ex))
        return jsonify({'result': 'error', 'message': str(ex)}), 500

@approval_bp.route('/approval/process', methods=['POST'])
def process_approval():
    """결재 처리 API (승인/반려)"""
    try:
        data = request.get_json()
        approval_id = data['approval_id']
        approver_id = data['approver_id']
        action = data['action']  # '승인' or '반려'
        comment = data.get('comment', '')

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 1. 현재 결재자 확인
                cursor.execute("""
                    SELECT line_id, `order`
                    FROM approval_line
                    WHERE approval_id = %s
                    AND approver_id = %s
                    AND status = %s
                """, (approval_id, approver_id, ApprovalStatus.PENDING))
                current_line = cursor.fetchone()
                
                if not current_line:
                    raise Exception('현재 결재 순서가 아닙니다.')

                # 2. 결재 처리
                if action == ApprovalAction.APPROVE:
                    # 현재 결재자 승인 처리
                    cursor.execute("""
                        UPDATE approval_line
                        SET status = %s,
                            comment = %s,
                            approved_at = NOW()
                        WHERE line_id = %s
                    """, (ApprovalStatus.APPROVED, comment, current_line['line_id']))
                    
                    # 다음 결재자가 있는지 확인
                    cursor.execute("""
                        SELECT line_id
                        FROM approval_line
                        WHERE approval_id = %s
                        AND `order` > %s
                        AND status = %s
                        LIMIT 1
                    """, (approval_id, current_line['order'], ApprovalStatus.PENDING))
                    next_line = cursor.fetchone()

                    if next_line:
                        # 다음 결재자에게 넘김
                        cursor.execute("""
                            UPDATE approval
                            SET status = %s
                            WHERE approval_id = %s
                        """, (ApprovalStatus.PENDING, approval_id))
                    else:
                        # 최종 승인
                        cursor.execute("""
                            UPDATE approval
                            SET status = %s,
                                final_approver_id = %s,
                                final_approval_date = NOW()
                            WHERE approval_id = %s
                        """, (ApprovalStatus.APPROVED, approver_id, approval_id))
                else:
                    # 반려 처리
                    # 1. 현재 결재자 반려 처리
                    cursor.execute("""
                        UPDATE approval_line
                        SET status = %s,
                            comment = %s,
                            approved_at = NOW()
                        WHERE line_id = %s
                    """, (ApprovalStatus.REJECTED, comment, current_line['line_id']))

                    # 2. 남은 결재 라인 모두 반려 처리
                    cursor.execute("""
                        UPDATE approval_line
                        SET status = %s,
                            comment = '이전 결재자에 의해 반려됨'
                        WHERE approval_id = %s
                        AND `order` > %s
                        AND status = %s
                    """, (ApprovalStatus.REJECTED, approval_id, current_line['order'], ApprovalStatus.PENDING))

                    # 3. 결재 문서 상태 반려로 변경
                    cursor.execute("""
                        UPDATE approval
                        SET status = %s,
                            final_approver_id = %s,
                            final_approval_date = NOW()
                        WHERE approval_id = %s
                    """, (ApprovalStatus.REJECTED, approver_id, approval_id))

                # 3. 이력 저장 (항상 기록)
                cursor.execute("""
                    INSERT INTO approval_history (
                        approval_id, approver_id,
                        action, comment,
                        created_at
                    )
                    VALUES (
                        %s, %s,
                        %s, %s,
                        NOW()
                    )
                """, (approval_id, approver_id, action, comment))

            conn.commit()
            return jsonify({'result': 'success'})

        except Exception as e:
            conn.rollback()
            logging.error("Error in process_approval: %s", str(e))
            return jsonify({'result': 'error', 'message': str(e)}), 500
        finally:
            conn.close()

    except Exception as ex:
        logging.error("Unexpected error in process_approval: %s", str(ex))
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
                        created_at
                    )
                    VALUES (
                        %s, %s, %s, %s, NOW()
                    )
                """
                cursor.execute(insert_sql, (approval_id, approver_id, ApprovalAction.APPROVE, comment))

                # 2) approval 테이블의 status를 '승인'으로 업데이트
                #    final_approver_id, final_approval_date 도 갱신
                update_sql = """
                    UPDATE approval
                    SET status = %s,
                        final_approver_id = %s,
                        final_approval_date = NOW()
                    WHERE approval_id = %s
                """
                cursor.execute(update_sql, (ApprovalStatus.APPROVED, approver_id, approval_id))

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
                        created_at
                    )
                    VALUES (
                        %s, %s, %s, %s, NOW()
                    )
                """
                cursor.execute(insert_sql, (approval_id, approver_id, ApprovalAction.REJECT, comment))

                # 2) approval 테이블 상태를 '반려'로 업데이트
                #    최종 승인자(여기서는 반려자), 반려 시각 저장
                update_sql = """
                    UPDATE approval
                    SET status = %s,
                        final_approver_id = %s,
                        final_approval_date = NOW()
                    WHERE approval_id = %s
                """
                cursor.execute(update_sql, (ApprovalStatus.REJECTED, approver_id, approval_id))

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

@approval_bp.route('/approval/cancel/<int:approval_id>', methods=['POST'])
def cancel_approval(approval_id):
    """결재 취소 API"""
    try:
        data = request.get_json()
        requester_id = data.get('requester_id')
        comment = data.get('comment', '')

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 1. 결재 상태 확인
                cursor.execute("""
                    SELECT status, requester_id 
                    FROM approval 
                    WHERE approval_id = %s
                """, (approval_id,))
                approval = cursor.fetchone()
                
                if not approval:
                    raise Exception('결재를 찾을 수 없습니다.')
                
                if approval['status'] in [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED]:
                    raise Exception('이미 처리된 결재는 취소할 수 없습니다.')
                
                if approval['requester_id'] != requester_id:
                    raise Exception('결재 요청자만 취소할 수 있습니다.')

                # 2. 결재 상태 업데이트
                cursor.execute("""
                    UPDATE approval 
                    SET status = %s 
                    WHERE approval_id = %s
                """, (ApprovalStatus.CANCELLED, approval_id))

                # 3. 결재 라인 상태 업데이트
                cursor.execute("""
                    UPDATE approval_line 
                    SET status = %s 
                    WHERE approval_id = %s
                """, (ApprovalStatus.CANCELLED, approval_id))

                # 4. 취소 이력 추가
                cursor.execute("""
                    INSERT INTO approval_history (
                        approval_id, approver_id,
                        action, comment,
                        created_at
                    )
                    VALUES (
                        %s, %s,
                        %s, %s,
                        NOW()
                    )
                """, (approval_id, requester_id, ApprovalAction.CANCEL, comment))

            conn.commit()
            return jsonify({'result': 'success'})

        except Exception as e:
            conn.rollback()
            logging.error("Error in cancel_approval: %s", str(e))
            return jsonify({'result': 'error', 'message': str(e)}), 500
        finally:
            conn.close()

    except Exception as ex:
        logging.error("Unexpected error in cancel_approval: %s", str(ex))
        return jsonify({'result': 'error', 'message': str(ex)}), 500

@approval_bp.route('/approval/<int:approval_id>', methods=['GET'])
def get_approval_detail(approval_id):
    """결재 상세 조회 API"""
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 1. 결재 기본 정보 조회
                cursor.execute("""
                    SELECT 
                        a.*,
                        r.name as requester_name,
                        f.name as final_approver_name,
                        h.comment AS latest_reject_comment
                    FROM approval a
                    LEFT JOIN user r ON a.requester_id = r.usr_id
                    LEFT JOIN user f ON a.final_approver_id = f.usr_id
                    LEFT JOIN (
                        SELECT ah1.approval_id, ah1.comment
                        FROM approval_history ah1
                        WHERE ah1.action = 'REJECT'
                        AND ah1.history_id = (
                            SELECT MAX(ah2.history_id)
                            FROM approval_history ah2
                            WHERE ah2.approval_id = ah1.approval_id 
                            AND ah2.action = 'REJECT'
                        )
                    ) h ON a.approval_id = h.approval_id
                    WHERE a.approval_id = %s
                """, (approval_id,))
                approval = cursor.fetchone()

                if not approval:
                    return jsonify({'result': 'error', 'message': 'Approval not found'}), 404

                # 2. 결재 라인 조회
                cursor.execute("""
                    SELECT 
                        al.*,
                        u.name as approver_name,
                        u.depart_cd,
                        u.position
                    FROM approval_line al
                    LEFT JOIN user u ON al.approver_id = u.usr_id
                    WHERE al.approval_id = %s
                    ORDER BY al.order
                """, (approval_id,))
                approval_line = cursor.fetchall()

                # 3. 결재 이력 조회
                cursor.execute("""
                    SELECT 
                        ah.*,
                        u.name as approver_name,
                        u.depart_cd,
                        u.position
                    FROM approval_history ah
                    LEFT JOIN user u ON ah.approver_id = u.usr_id
                    WHERE ah.approval_id = %s
                    ORDER BY ah.history_id
                """, (approval_id,))
                history = cursor.fetchall()

                return jsonify({
                    'result': 'success',
                    'approval': approval,
                    'approvalLine': approval_line,
                    'history': history
                })

        except Exception as e:
            logging.error("Error in get_approval_detail: %s", str(e))
            return jsonify({'result': 'error', 'message': str(e)}), 500
        finally:
            conn.close()

    except Exception as ex:
        logging.error("Unexpected error in get_approval_detail: %s", str(ex))
        return jsonify({'result': 'error', 'message': str(ex)}), 500

@approval_bp.route('/approval/list', methods=['GET'])
def get_approval_list():
    """결재 리스트 조회 API"""
    try:
        # 요청 파라미터 가져오기
        status = request.args.get('status')
        requester_id = request.args.get('requester_id')
        approver_id = request.args.get('approver_id')  # 결재자 ID 추가
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))

        offset = (page - 1) * per_page

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 기본 SQL 쿼리
                sql = """
                    SELECT DISTINCT
                        a.*,
                        r.name as requester_name,
                        f.name as final_approver_name
                    FROM approval a
                    LEFT JOIN user r ON a.requester_id = r.usr_id
                    LEFT JOIN user f ON a.final_approver_id = f.usr_id
                    LEFT JOIN approval_line al ON a.approval_id = al.approval_id
                    WHERE 1=1
                """
                params = []

                # 상태 필터 추가
                if status:
                    sql += " AND a.status = %s"
                    params.append(status)

                # 요청자 ID 필터 추가
                if requester_id:
                    sql += " AND a.requester_id = %s"
                    params.append(requester_id)

                # 결재자 ID 필터 추가
                if approver_id:
                    sql += " AND al.approver_id = %s"
                    params.append(approver_id)

                # 정렬 및 페이징 추가
                sql += " ORDER BY a.created_at DESC LIMIT %s OFFSET %s"
                params.extend([per_page, offset])

                # 쿼리 실행
                cursor.execute(sql, params)
                approvals = cursor.fetchall()

                # 총 항목 수 계산
                count_sql = """
                    SELECT COUNT(DISTINCT a.approval_id) AS total
                    FROM approval a
                    LEFT JOIN approval_line al ON a.approval_id = al.approval_id
                    WHERE 1=1
                """
                count_params = []

                if status:
                    count_sql += " AND a.status = %s"
                    count_params.append(status)
                if requester_id:
                    count_sql += " AND a.requester_id = %s"
                    count_params.append(requester_id)
                if approver_id:
                    count_sql += " AND al.approver_id = %s"
                    count_params.append(approver_id)

                cursor.execute(count_sql, count_params)
                total = cursor.fetchone()['total']

            return jsonify({
                'result': 'success',
                'data': approvals,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total
                }
            })

        except Exception as e:
            logging.error("Error in get_approval_list: %s", str(e))
            return jsonify({'result': 'error', 'message': str(e)}), 500
        finally:
            conn.close()

    except Exception as ex:
        logging.error("Unexpected error in get_approval_list: %s", str(ex))
        return jsonify({'result': 'error', 'message': str(ex)}), 500

@approval_bp.route('/approval/line/update', methods=['POST'])
def update_approval_line():
    """결재 라인 상태 업데이트 API"""
    try:
        data = request.get_json()
        approval_id = data['approval_id']
        approver_id = data['approver_id']
        status = data['status']
        comment = data.get('comment', '')

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 1. 현재 결재 라인 확인
                cursor.execute("""
                    SELECT line_id, `order`
                    FROM approval_line
                    WHERE approval_id = %s
                    AND approver_id = %s
                """, (approval_id, approver_id))
                current_line = cursor.fetchone()
                
                if not current_line:
                    raise Exception('결재 라인을 찾을 수 없습니다.')

                # 2. 결재 라인 상태 업데이트
                cursor.execute("""
                    UPDATE approval_line
                    SET status = %s,
                        comment = %s,
                        created_at = NOW()
                    WHERE line_id = %s
                """, (status, comment, current_line['line_id']))

                # 3. 이력 저장 (한 번만 기록)
                if data.get('record_history', True):
                    cursor.execute("""
                        INSERT INTO approval_history (
                            approval_id, approver_id,
                            action, comment,
                            created_at
                        )
                        VALUES (
                            %s, %s,
                            %s, %s,
                            NOW()
                        )
                    """, (approval_id, approver_id, status, comment))

            conn.commit()
            return jsonify({'result': 'success'})

        except Exception as e:
            conn.rollback()
            logging.error("Error in update_approval_line: %s", str(e))
            return jsonify({'result': 'error', 'message': str(e)}), 500
        finally:
            conn.close()

    except Exception as ex:
        logging.error("Unexpected error in update_approval_line: %s", str(ex))
        return jsonify({'result': 'error', 'message': str(ex)}), 500

@approval_bp.route('/approval/updateStatus/<int:approval_id>', methods=['POST'])
def update_approval_status(approval_id):
    """결재 상태 업데이트 API"""
    try:
        data = request.get_json()
        new_status = data['status']
        comment = data.get('comment', '')
        approver_id = data.get('approver_id')
        record_history = data.get('record_history', True)

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 1. 결재 존재 여부 확인
                cursor.execute("""
                    SELECT status 
                    FROM approval 
                    WHERE approval_id = %s
                """, (approval_id,))
                approval = cursor.fetchone()
                
                if not approval:
                    raise Exception('결재를 찾을 수 없습니다.')

                # 2. 결재 상태 업데이트
                cursor.execute("""
                    UPDATE approval
                    SET status = %s,
                        updated_at = NOW()
                    WHERE approval_id = %s
                """, (new_status, approval_id))

                # 3. 이력 저장 (한 번만 기록)
                # 결재 요청 상태로 변경하는 경우에는 이력을 기록하지 않음
                if record_history and approver_id and new_status != ApprovalStatus.REQUESTING:
                    cursor.execute("""
                        INSERT INTO approval_history (
                            approval_id, approver_id,
                            action, comment,
                            created_at
                        )
                        VALUES (
                            %s, %s,
                            %s, %s,
                            NOW()
                        )
                    """, (approval_id, approver_id, new_status, comment))

            conn.commit()
            return jsonify({'result': 'success'})

        except Exception as e:
            conn.rollback()
            logging.error("Error in update_approval_status: %s", str(e))
            return jsonify({'result': 'error', 'message': str(e)}), 500
        finally:
            conn.close()

    except Exception as ex:
        logging.error("Unexpected error in update_approval_status: %s", str(ex))
        return jsonify({'result': 'error', 'message': str(ex)}), 500

@approval_bp.route('/approval/line/<int:approval_id>', methods=['GET'])
def get_approval_line(approval_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # 결재 라인 정보 조회
                cursor.execute("""
                    SELECT 
                        al.line_id,
                        al.approval_id,
                        al.approver_id,
                        al.order,
                        al.status,
                        al.comment,
                        al.approved_at,
                        al.created_at,
                        u.name as approver_name,
                        u.depart_cd,
                        u.position
                    FROM approval_line al
                    JOIN user u ON al.approver_id = u.usr_id
                    WHERE al.approval_id = %s
                    ORDER BY al.order
                """, (approval_id,))
                
                lines = cursor.fetchall()
                
                if not lines:
                    return jsonify({
                        'result': 'error',
                        'message': '결재 라인 정보가 없습니다.'
                    }), 404

                # 결과를 딕셔너리 리스트로 변환
                line_data = [{
                    'line_id': line['line_id'],
                    'approval_id': line['approval_id'],
                    'approver_id': line['approver_id'],
                    'order': line['order'],
                    'status': line['status'],
                    'comment': line['comment'],
                    'approved_at': line['approved_at'].strftime('%Y-%m-%d %H:%M:%S') if line['approved_at'] else None,
                    'created_at': line['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                    'approver_name': line['approver_name'],
                    'depart_cd': line['depart_cd'],
                    'position': line['position']
                } for line in lines]

                return jsonify({
                    'result': 'success',
                    'data': line_data
                })

    except Exception as e:
        print(f"Error in get_approval_line: {str(e)}")
        return jsonify({
            'result': 'error',
            'message': '결재 라인 조회 중 오류가 발생했습니다.'
        }), 500





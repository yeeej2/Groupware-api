from models.database import get_db_connection
from flask import Blueprint, request, jsonify
import logging

# 📌 Blueprint 생성
users_bp = Blueprint('users', __name__)

# 📌 Create a new user
@users_bp.route('/users', methods=['POST'])
def create_user():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
    INSERT INTO user (login_id, name, pw, pw_salt_val, last_con_ip, phone, email, reg_id, role_cd, depart_cd)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    values = (
        data['login_id'], data['name'], data['pw'], data['pw_salt_val'],
        data.get('last_con_ip'), data.get('phone'), data.get('email'),
        data.get('reg_id'), data.get('role_cd'), data.get('depart_cd')
    )
    cursor.execute(sql, values)
    conn.commit()
    user_id = cursor.lastrowid
    cursor.close()
    conn.close()

    return jsonify({'message': 'User created successfully', 'user_id': user_id}), 201

# 📌 Read user(s)
@users_bp.route('/users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM user")
    users = cursor.fetchall()
    cursor.close()
    conn.close()

    logging.info("📌 User list")
    logging.info(users) 

    return jsonify({'result': 'success', 'data': users}), 200

@users_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM user WHERE usr_id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        return jsonify(user), 200
    else:
        return jsonify({'message': 'User not found'}), 404

# 📌 Update a user
@users_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
    UPDATE user
    SET login_id = %s, name = %s, pw = %s, pw_salt_val = %s, last_con_ip = %s,
        phone = %s, email = %s, role_cd = %s, depart_cd = %s, upd_id = %s
    WHERE usr_id = %s
    """
    values = (
        data['login_id'], data['name'], data['pw'], data['pw_salt_val'],
        data.get('last_con_ip'), data.get('phone'), data.get('email'),
        data.get('role_cd'), data.get('depart_cd'), data.get('upd_id'), user_id
    )
    cursor.execute(sql, values)
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'message': 'User updated successfully'}), 200

# 📌 Delete a user
@users_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM user WHERE usr_id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'message': 'User deleted successfully'}), 200
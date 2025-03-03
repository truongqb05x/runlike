from flask import Flask, request, jsonify, abort
from mysql.connector import pooling
from datetime import datetime
from flask import Flask, send_from_directory

app = Flask(__name__, static_folder='templates')


# Tạo kết nối pool đến cơ sở dữ liệu theo cấu hình của bạn
pool = pooling.MySQLConnectionPool(
    # pool_name="mypool",  # Nếu cần đặt tên cho pool
    pool_size=7,  # Kích thước pool
    host='localhost',
    user='root',
    password='',
    database='test'
)

def get_db_connection():
    # Lấy kết nối từ pool
    return pool.get_connection()

# ============================
# ROUTES API
# ============================
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

# 1. Lấy danh sách bài viết (có thể lọc theo UID nếu truyền query parameter uid)
@app.route('/api/posts', methods=['GET'])
def get_posts():
    search_uid = request.args.get('uid')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    posts = []
    if search_uid:
        query = """
            SELECT DISTINCT p.id, p.external_post_id, p.created_at
            FROM posts p 
            JOIN post_uids pu ON p.id = pu.post_id
            WHERE pu.uid LIKE %s
        """
        cursor.execute(query, ('%' + search_uid + '%',))
    else:
        query = "SELECT id, external_post_id, created_at FROM posts"
        cursor.execute(query)
    posts = cursor.fetchall()

    # Lấy danh sách UID cho mỗi bài viết
    for post in posts:
        cursor.execute("SELECT uid FROM post_uids WHERE post_id = %s", (post['id'],))
        uids = cursor.fetchall()
        post['uids'] = [row['uid'] for row in uids]

    cursor.close()
    conn.close()
    return jsonify(posts)

# 2. Tạo bài viết mới kèm danh sách UID (dữ liệu gửi qua JSON)
@app.route('/api/posts', methods=['POST'])
def create_post():
    data = request.get_json()
    if not data or 'external_post_id' not in data:
        return jsonify({'error': 'Missing external_post_id'}), 400
    external_post_id = data['external_post_id']
    created_at = datetime.utcnow()  # Sử dụng thời gian hiện tại theo chuẩn UTC

    conn = get_db_connection()
    cursor = conn.cursor()
    # Chèn bài viết mới
    query = "INSERT INTO posts (external_post_id, created_at) VALUES (%s, %s)"
    cursor.execute(query, (external_post_id, created_at))
    conn.commit()
    post_id = cursor.lastrowid

    # Nếu có danh sách UID, thêm từng UID vào bảng post_uids
    if 'uids' in data and isinstance(data['uids'], list):
        for uid in data['uids']:
            cursor.execute("INSERT INTO post_uids (post_id, uid) VALUES (%s, %s)", (post_id, uid))
        conn.commit()

    cursor.close()
    conn.close()
    return jsonify({'message': 'Post created', 'post_id': post_id}), 201

# 3. Cập nhật danh sách UID của một bài viết (thay thế toàn bộ UID hiện có)
@app.route('/api/posts/<int:post_id>/uids', methods=['PUT'])
def update_post_uids(post_id):
    data = request.get_json()
    if not data or 'uids' not in data:
        return jsonify({'error': 'Missing uids field'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    # Xóa toàn bộ UID cũ của bài viết
    cursor.execute("DELETE FROM post_uids WHERE post_id = %s", (post_id,))
    # Chèn lại danh sách UID mới
    for uid in data['uids']:
        cursor.execute("INSERT INTO post_uids (post_id, uid) VALUES (%s, %s)", (post_id, uid))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Post uids updated'}), 200

# 4. Lấy danh sách global UID
@app.route('/api/global_uids', methods=['GET'])
def get_global_uids():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT uid FROM global_uids")
    rows = cursor.fetchall()
    # Mỗi dòng là tuple, lấy phần tử đầu tiên của tuple
    uids = [row[0] for row in rows]
    cursor.close()
    conn.close()
    return jsonify(uids)

# 5. Cập nhật toàn bộ danh sách global UID
@app.route('/api/global_uids', methods=['PUT'])
def update_global_uids():
    data = request.get_json()
    if not data or 'uids' not in data:
        return jsonify({'error': 'Missing uids field'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    # Xóa toàn bộ dữ liệu cũ trong bảng global_uids
    cursor.execute("DELETE FROM global_uids")
    for uid in data['uids']:
        cursor.execute("INSERT INTO global_uids (uid) VALUES (%s)", (uid,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Global uids updated'}), 200

# 6. Route thống kê: trả về số UID like của từng bài viết (dựa trên external_post_id)
@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT p.external_post_id, COUNT(pu.uid) AS uid_count 
        FROM posts p 
        LEFT JOIN post_uids pu ON p.id = pu.post_id 
        GROUP BY p.id
    """
    cursor.execute(query)
    stats = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(stats)

if __name__ == '__main__':
    app.run(debug=True)

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g, flash
import mysql.connector
from mysql.connector import Error
import os

# Configuration Settings
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'trip')
}

SECRET_KEY = os.getenv('SECRET_KEY', 'your_secret_key')

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['DB_CONFIG'] = DB_CONFIG

def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
    return g.db

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
        return conn
    except Error as e:
        print(f"Database connection error: {e}")
        return None
        
import pymysql

def execute_db(query, params):
    # Replace with your actual database connection and execution logic
    conn = pymysql.connect(user='root', password='', host='localhost', database='trip')
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user_type = session['user_type']
    
    if request.method == 'POST':
        data = request.form.to_dict()

        if user_type == 'teacher':
            query = 'UPDATE teacher SET  password = %s,phone = %s WHERE user_id = %s'
        else:
            query = 'UPDATE student SET  password = %s,phone = %s WHERE user_id = %s'

        execute_db(query, (data['password'],data['phone'],user_id))
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile'))

    else:
        if user_type == 'teacher':
            query = 'SELECT * FROM teacher WHERE user_id = %s'
        else:
            query = 'SELECT * FROM student WHERE user_id = %s'
        
        user = query_db(query, (user_id,), fetchone=True)
        if user:
            return render_template('edit_profile.html', user=user)
        else:
            flash('User not found', 'error')
            return redirect(url_for('profile'))

@app.teardown_appcontext
def teardown_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query_db(query, args=(), fetchone=False):
    conn = get_db_connection()
    if conn is None:
        return None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(query, args)
        if query.strip().upper().startswith('SELECT'):
            result = cursor.fetchall()
            return (result[0] if result else None) if fetchone else result
        else:
            conn.commit()
            return None
    except Error as e:
        print(f"Query error: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def execute_db(query, params):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        cursor.close()
        conn.close()
    except Error as e:
        print(f"Execution error: {e}")


@app.route('/')
def index():
    return render_template('index2.html')

@app.route('/submit_usn', methods=['POST'])
def submit_usn():
    usn = request.form.get('usn')
    if not usn:
        return jsonify({"success": False, "message": "USN is required"}), 400

    attendance_data = query_db('SELECT * FROM attendance1 WHERE student_id = %s', (usn,))
    if not attendance_data:
        return render_template('searching.html', attendance_data=None, message='Attendance data not yet uploaded for the given USN.')

    for row in attendance_data:
        total_classes_conducted = row['total_classes_conducted']
        total_classes_attended = row['total_classes_attended']
        row['attendance_percentage'] = (total_classes_attended / total_classes_conducted) * 100 if total_classes_conducted > 0 else 0

    return render_template('searching.html', attendance_data=attendance_data)

@app.route('/student_attendance')
def student_attendance():
    if 'user_id' not in session or session.get('user_type') != 'student':
        return redirect(url_for('index'))

    student_id = session['user_id']
    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT subject_id, total_classes_conducted, total_classes_attended 
    FROM attendance1 
    WHERE student_id = %s
    """
    cursor.execute(query, (student_id,))
    attendance_data = cursor.fetchall()
    
    for row in attendance_data:
        total_classes_conducted = row['total_classes_conducted']
        total_classes_attended = row['total_classes_attended']
        if total_classes_conducted > 0:
            row['attendance_percentage'] = (total_classes_attended / total_classes_conducted) * 100
        else:
            row['attendance_percentage'] = 0
    
    cursor.close()
    return render_template('student_getattend.html', attendance_data=attendance_data)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_type', None)
    return redirect(url_for('index'))

@app.route('/subjects', methods=['GET'])
def get_subjects():
    semester = request.args.get('semester')
    if not semester:
        return jsonify({"success": False, "message": "Semester is required"}), 400

    query = 'SELECT subject_name FROM subject WHERE sub_sem = %s'
    subjects = query_db(query, (semester,))
    
    if subjects:
        return jsonify({"success": True, "subjects": subjects})
    else:
        return jsonify({"success": False, "message": "No subjects found for the selected semester"}), 404
    
@app.route('/update_attendance', methods=['POST'])
def update_attendance():
    if 'user_id' not in session or session.get('user_type') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized access'})

    teacher_id = session['user_id']
    data = request.form.to_dict()
    student_id = request.form.get('student_id')
    
    if not student_id:
        return jsonify({'success': False, 'message': 'Student ID is required'})

    connection = get_db()
    cursor = connection.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM student WHERE user_id = %s", (student_id,))
        student_exists = cursor.fetchone()[0] > 0

        if not student_exists:
            return jsonify({'success': False, 'message': 'Student ID does not exist'})

        for key, value in data.items():
            if key.startswith('attended_'):
                subject_name = key.split('_')[1]  # Ensuring we get the subject_id
                attended_values = value.split(' ')
                cursor.execute("SELECT subject_id FROM subject WHERE subject_name = %s", (subject_name,))
                subject_id = cursor.fetchone()[0]
                conducted_key = f'conducted_{subject_name}'
                conducted_values = data.get(conducted_key, '').split(',')
                
                cursor.execute("SELECT COUNT(*) FROM teacher_subject WHERE teacher_id = %s AND subject_id = %s", (teacher_id, subject_id))
                authorized = cursor.fetchone()[0] > 0

                if  authorized:
                    return jsonify({'success': False, 'message': f'Unauthorized to update attendance for subject {subject_name}'})

                for attended, conducted in zip(attended_values, conducted_values):
                    attended = int(attended.strip())
                    conducted = int(conducted.strip())

                    cursor.execute("SELECT COUNT(*) FROM attendance1 WHERE student_id = %s AND subject_id = %s", (student_id, subject_id))
                    record_exists = cursor.fetchone()[0] > 0

                    if record_exists:
                        cursor.execute("""
                            UPDATE attendance1 
                            SET total_classes_attended = %s, total_classes_conducted = %s
                            WHERE student_id = %s AND subject_id = %s
                        """, (attended, conducted, student_id, subject_id))
                    else:
                        cursor.execute("""
                            INSERT INTO attendance1 (student_id, subject_id, total_classes_attended, total_classes_conducted)
                            VALUES (%s, %s, %s, %s)
                        """, (student_id, subject_id, attended, conducted))

        connection.commit()
        return jsonify({'success': True, 'message': 'Attendance updated successfully'})
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()



@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    user_type = request.form.get('user_type')

    if not email or not password or not user_type:
        return jsonify({"success": False, "message": "Email, password, and user type are required"}), 400

    user = None
    if user_type == 'teacher':
        user = query_db('SELECT * FROM teacher WHERE email = %s AND password = %s', (email, password), fetchone=True)
    elif user_type == 'student':
        user = query_db('SELECT * FROM student WHERE email = %s AND password = %s', (email, password), fetchone=True)
    else:
        return jsonify({"success": False, "message": "Invalid user type"}), 400

    if user:
        session['user_id'] = user['user_id']
        session['user_type'] = user_type
        if user_type == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        elif user_type == 'student':
            return redirect(url_for('student_dashboard'))
    else:
        error = 'Invalid username or password. Please try again.'
        return render_template('index2.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        user_id = request.form.get('id_number')
        email = request.form.get('email')
        password = request.form.get('password')
        gender = request.form.get('gender')
        branch = request.form.get('branch')
        dob = request.form.get('dob')
        phone = request.form.get('phone')
        user_type = request.form.get('user_type')

        if not email or not password or not user_type:
            flash("Email, password, and user type are required", "error")
            return redirect(url_for('register'))

        if user_type == 'teacher':
            existing_user = query_db('SELECT * FROM teacher WHERE email = %s', (email,), fetchone=True)
            if existing_user:
                flash("Email already registered for teacher", "error")
                return redirect(url_for('register'))
            query = '''
                INSERT INTO teacher (name, user_id, email, password, gender, branch, dob, phone) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            '''
        elif user_type == 'student':
            existing_user = query_db('SELECT * FROM student WHERE email = %s', (email,), fetchone=True)
            if existing_user:
                flash("Email already registered for student", "error")
                return redirect(url_for('register'))
            query = '''
                INSERT INTO student (name, user_id, email, password, gender, branch, dob, phone) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            '''
        else:
            flash("Invalid user type", "error")
            return redirect(url_for('register'))

        execute_db(query, (name, user_id, email, password, gender, branch, dob, phone))
        session['user_id'] = user_id
        session['user_type'] = user_type
        return redirect(url_for(f'{user_type}_dashboard'))

    return render_template('register.html')

@app.route('/profile')
def profile():
    if 'user_id' in session:
        user_id = session['user_id']
        user_type = session['user_type']

        query = 'SELECT * FROM teacher WHERE user_id = %s' if user_type == 'teacher' else 'SELECT * FROM student WHERE user_id = %s'
        user = query_db(query, (user_id,), fetchone=True)

        if user:
            template = 'profileTeach.html' if user_type == 'teacher' else 'profile.html'
            return render_template(template, user=user)
        else:
            return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))

@app.route('/search_page')
def search_page():
    return render_template('searching.html')

@app.route('/attend_page')
def attend_page():
    return render_template('try4.html')

@app.route('/about_page1')
def about_page1():
    return render_template('About1.html')

@app.route('/tatten_page')
def tatten_page():
    return render_template('tattendence.html')

@app.route('/student')
def student_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'student':
        return redirect(url_for('index'))
    return render_template('student.html')

@app.route('/teacher')
def teacher_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'teacher':
        return redirect(url_for('index'))
    return render_template('teacher.html')

if __name__ == '__main__':
    app.run(debug=True) 

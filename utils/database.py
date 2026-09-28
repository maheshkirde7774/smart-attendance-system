import sqlite3
import os
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database.db')

def get_db_connection():
    """Returns a database connection with dictionary-like row access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Initializes the database schema and default admin and seed data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'Admin',
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            roll_no TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            department TEXT NOT NULL,
            class_name TEXT NOT NULL,
            qr_code TEXT,
            face_registered INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Attendance table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT NOT NULL,
            method TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id) ON DELETE CASCADE
        )
    ''')

    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')

    # Insert default settings if not exists
    default_settings = {
        'late_threshold': '09:30:00',
        'academic_year': '2026-2027',
        'system_title': 'SMART ATTENDANCE',
        'tagline': 'Attend Today for a Better Tomorrow',
        'institution_name': 'Apex Institute of Technology & AI',
        'camera_index': '0',
        'face_confidence_threshold': '65'
    }
    for key, val in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

    # Insert default admin user if not exists
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        admin_pass = generate_password_hash('admin123')
        cursor.execute('''
            INSERT INTO users (username, password_hash, role, name, email)
            VALUES (?, ?, 'Admin', 'Chief Administrator', 'admin@smartattendance.edu')
        ''', ('admin', admin_pass))

    # Insert faculty user if not exists
    cursor.execute("SELECT id FROM users WHERE username = 'faculty'")
    if not cursor.fetchone():
        fac_pass = generate_password_hash('faculty123')
        cursor.execute('''
            INSERT INTO users (username, password_hash, role, name, email)
            VALUES (?, ?, 'Faculty', 'Dr. Elena Vance', 'elena.vance@smartattendance.edu')
        ''', ('faculty', fac_pass))

    # Seed initial students if table is empty
    cursor.execute("SELECT COUNT(*) as count FROM students")
    if cursor.fetchone()['count'] == 0:
        sample_students = [
            ("STU-2026-001", "CS101", "Alexander Drake", "alex.drake@smartattendance.edu", "Computer Science", "CS-Final"),
            ("STU-2026-002", "CS102", "Sophia Martinez", "sophia.m@smartattendance.edu", "Computer Science", "CS-Final"),
            ("STU-2026-003", "AI201", "Ethan Chen", "ethan.chen@smartattendance.edu", "AI & Data Science", "AI-3A"),
            ("STU-2026-004", "AI202", "Aria Sharma", "aria.sharma@smartattendance.edu", "AI & Data Science", "AI-3A"),
            ("STU-2026-005", "IT301", "Marcus Brody", "m.brody@smartattendance.edu", "Information Technology", "IT-2B"),
            ("STU-2026-006", "IT302", "Zoe Alverez", "zoe.a@smartattendance.edu", "Information Technology", "IT-2B"),
            ("STU-2026-007", "EC401", "Lucas Sterling", "lucas.s@smartattendance.edu", "Electronics", "EC-3A"),
            ("STU-2026-008", "ME501", "Maya Lin", "maya.lin@smartattendance.edu", "Mechanical", "ME-4A")
        ]

        for s_id, roll, name, email, dept, cls in sample_students:
            qr_file = f"qr_{s_id}.png"
            cursor.execute('''
                INSERT INTO students (student_id, roll_no, name, email, department, class_name, qr_code, face_registered)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            ''', (s_id, roll, name, email, dept, cls, qr_file))

        # Add some historical seed attendance for charts
        today = date.today()
        # Seed previous 5 days
        for i in range(1, 6):
            past_date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            cursor.execute("INSERT INTO attendance (student_id, date, time, status, method) VALUES (?, ?, '09:05:12', 'Present', 'Face Recognition')", ("STU-2026-001", past_date))
            cursor.execute("INSERT INTO attendance (student_id, date, time, status, method) VALUES (?, ?, '09:12:44', 'Present', 'QR Scan')", ("STU-2026-002", past_date))
            cursor.execute("INSERT INTO attendance (student_id, date, time, status, method) VALUES (?, ?, '09:42:10', 'Late', 'Face Recognition')", ("STU-2026-003", past_date))
            cursor.execute("INSERT INTO attendance (student_id, date, time, status, method) VALUES (?, ?, '09:18:22', 'Present', 'QR Scan')", ("STU-2026-004", past_date))
            cursor.execute("INSERT INTO attendance (student_id, date, time, status, method) VALUES (?, ?, '08:58:33', 'Present', 'Face Recognition')", ("STU-2026-005", past_date))

        # Today's seed attendance (3 present, 1 late)
        today_str = today.strftime('%Y-%m-%d')
        cursor.execute("INSERT INTO attendance (student_id, date, time, status, method) VALUES (?, ?, '09:08:14', 'Present', 'Face Recognition')", ("STU-2026-001", today_str))
        cursor.execute("INSERT INTO attendance (student_id, date, time, status, method) VALUES (?, ?, '09:15:30', 'Present', 'QR Scan')", ("STU-2026-002", today_str))
        cursor.execute("INSERT INTO attendance (student_id, date, time, status, method) VALUES (?, ?, '09:45:00', 'Late', 'Face Recognition')", ("STU-2026-003", today_str))
        cursor.execute("INSERT INTO attendance (student_id, date, time, status, method) VALUES (?, ?, '09:20:10', 'Present', 'QR Scan')", ("STU-2026-004", today_str))

    conn.commit()
    conn.close()

# --- USER MANAGEMENT ---
def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username)).fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def verify_user(username, password):
    user = get_user_by_username(username)
    if user and check_password_hash(user['password_hash'], password):
        return user
    return None

def update_user_profile(user_id, name, email, current_password=None, new_password=None):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return False, "User not found"
    
    if new_password:
        if not current_password or not check_password_hash(user['password_hash'], current_password):
            conn.close()
            return False, "Current password does not match"
        new_hash = generate_password_hash(new_password)
        conn.execute("UPDATE users SET name = ?, email = ?, password_hash = ? WHERE id = ?", (name, email, new_hash, user_id))
    else:
        conn.execute("UPDATE users SET name = ?, email = ? WHERE id = ?", (name, email, user_id))
    conn.commit()
    conn.close()
    return True, "Profile updated successfully"

# --- SETTINGS MANAGEMENT ---
def get_settings():
    conn = get_db_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {row['key']: row['value'] for row in rows}

def update_settings(settings_dict):
    conn = get_db_connection()
    for k, v in settings_dict.items():
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, str(v)))
    conn.commit()
    conn.close()
    return True

# --- STUDENT MANAGEMENT ---
def get_all_students(search=None, department=None, class_name=None):
    conn = get_db_connection()
    query = "SELECT * FROM students WHERE 1=1"
    params = []

    if search:
        query += " AND (name LIKE ? OR student_id LIKE ? OR roll_no LIKE ? OR email LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])
    if department:
        query += " AND department = ?"
        params.append(department)
    if class_name:
        query += " AND class_name = ?"
        params.append(class_name)

    query += " ORDER BY id DESC"
    students = conn.execute(query, params).fetchall()
    conn.close()
    return students

def get_student_by_id(id_val):
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (id_val,)).fetchone()
    conn.close()
    return student

def get_student_by_student_id(student_id):
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
    conn.close()
    return student

def add_student(student_id, roll_no, name, email, department, class_name):
    conn = get_db_connection()
    try:
        qr_file = f"qr_{student_id}.png"
        conn.execute('''
            INSERT INTO students (student_id, roll_no, name, email, department, class_name, qr_code, face_registered)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        ''', (student_id, roll_no, name, email, department, class_name, qr_file))
        conn.commit()
        conn.close()
        return True, "Student added successfully"
    except sqlite3.IntegrityError as e:
        conn.close()
        if "student_id" in str(e):
            return False, "Student ID already exists"
        elif "roll_no" in str(e):
            return False, "Roll number already exists"
        return False, f"Database error: {str(e)}"
    except Exception as e:
        conn.close()
        return False, str(e)

def update_student(id_val, roll_no, name, email, department, class_name):
    conn = get_db_connection()
    try:
        conn.execute('''
            UPDATE students
            SET roll_no = ?, name = ?, email = ?, department = ?, class_name = ?
            WHERE id = ?
        ''', (roll_no, name, email, department, class_name, id_val))
        conn.commit()
        conn.close()
        return True, "Student updated successfully"
    except Exception as e:
        conn.close()
        return False, str(e)

def delete_student(id_val):
    conn = get_db_connection()
    student = conn.execute("SELECT student_id FROM students WHERE id = ?", (id_val,)).fetchone()
    if student:
        conn.execute("DELETE FROM attendance WHERE student_id = ?", (student['student_id'],))
        conn.execute("DELETE FROM students WHERE id = ?", (id_val,))
        conn.commit()
    conn.close()
    return True

def set_face_registered(student_id, status=1):
    conn = get_db_connection()
    conn.execute("UPDATE students SET face_registered = ? WHERE student_id = ?", (status, student_id))
    conn.commit()
    conn.close()

# --- ATTENDANCE MANAGEMENT ---
def mark_attendance(student_id, method, custom_date=None, custom_time=None):
    """
    Marks attendance for a student:
    - Checks if student exists
    - Prevents duplicate attendance for the same day
    - Checks against configured late threshold (default 09:30:00)
    - Records date, time, status ('Present' or 'Late'), method
    """
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        return {"success": False, "message": f"Student ID '{student_id}' not found in system."}

    now = datetime.now()
    date_str = custom_date if custom_date else now.strftime('%Y-%m-%d')
    time_str = custom_time if custom_time else now.strftime('%H:%M:%S')

    # Check for existing attendance on this date
    existing = conn.execute(
        "SELECT * FROM attendance WHERE student_id = ? AND date = ?",
        (student_id, date_str)
    ).fetchone()

    if existing:
        conn.close()
        return {
            "success": False,
            "already_marked": True,
            "message": f"Attendance already recorded today for {student['name']} ({existing['status']} at {existing['time']}) via {existing['method']}.",
            "student": dict(student),
            "record": dict(existing)
        }

    # Fetch late threshold
    setting_row = conn.execute("SELECT value FROM settings WHERE key = 'late_threshold'").fetchone()
    late_threshold = setting_row['value'] if setting_row else "09:30:00"

    status = "Present"
    try:
        att_time_obj = datetime.strptime(time_str, '%H:%M:%S').time()
        thresh_time_obj = datetime.strptime(late_threshold, '%H:%M:%S').time()
        if att_time_obj > thresh_time_obj:
            status = "Late"
    except Exception:
        status = "Present"

    conn.execute('''
        INSERT INTO attendance (student_id, date, time, status, method)
        VALUES (?, ?, ?, ?, ?)
    ''', (student_id, date_str, time_str, status, method))
    conn.commit()

    record_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()['id']
    conn.close()

    return {
        "success": True,
        "already_marked": False,
        "message": f"Attendance marked as {status} for {student['name']}",
        "student": dict(student),
        "record": {
            "id": record_id,
            "student_id": student_id,
            "date": date_str,
            "time": time_str,
            "status": status,
            "method": method
        }
    }

def get_attendance_records(search=None, date_filter=None, department=None, student_id=None, status=None, limit=None):
    conn = get_db_connection()
    query = '''
        SELECT a.id, a.student_id, a.date, a.time, a.status, a.method, a.created_at,
               s.roll_no, s.name, s.department, s.class_name, s.email
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        WHERE 1=1
    '''
    params = []

    if search:
        query += " AND (s.name LIKE ? OR s.student_id LIKE ? OR s.roll_no LIKE ?)"
        t = f"%{search}%"
        params.extend([t, t, t])
    if date_filter:
        query += " AND a.date = ?"
        params.append(date_filter)
    if department:
        query += " AND s.department = ?"
        params.append(department)
    if student_id:
        query += " AND a.student_id = ?"
        params.append(student_id)
    if status:
        query += " AND a.status = ?"
        params.append(status)

    query += " ORDER BY a.date DESC, a.time DESC"

    if limit:
        query += f" LIMIT {int(limit)}"

    records = conn.execute(query, params).fetchall()
    conn.close()
    return records

def get_dashboard_stats():
    conn = get_db_connection()
    today_str = date.today().strftime('%Y-%m-%d')

    # Total students
    total_students_row = conn.execute("SELECT COUNT(*) as count FROM students").fetchone()
    total_students = total_students_row['count'] if total_students_row else 0

    # Today's attendance
    today_records = conn.execute('''
        SELECT a.*, s.name, s.roll_no, s.department, s.class_name
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        WHERE a.date = ?
        ORDER BY a.time DESC
    ''', (today_str,)).fetchall()

    present_today = sum(1 for r in today_records if r['status'] == 'Present')
    late_today = sum(1 for r in today_records if r['status'] == 'Late')
    total_attended = present_today + late_today
    absent_today = max(0, total_students - total_attended)

    percentage = round((total_attended / total_students * 100), 1) if total_students > 0 else 0

    # Recent 10 attendance records
    recent = conn.execute('''
        SELECT a.id, a.student_id, a.date, a.time, a.status, a.method,
               s.name, s.roll_no, s.department, s.class_name
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        ORDER BY a.date DESC, a.time DESC
        LIMIT 8
    ''').fetchall()

    # Weekly stats for chart (last 7 days)
    weekly_data = []
    for i in range(6, -1, -1):
        day_date = date.today() - timedelta(days=i)
        day_str = day_date.strftime('%Y-%m-%d')
        label = day_date.strftime('%a, %d %b')
        
        day_rows = conn.execute("SELECT status FROM attendance WHERE date = ?", (day_str,)).fetchall()
        p = sum(1 for r in day_rows if r['status'] == 'Present')
        l = sum(1 for r in day_rows if r['status'] == 'Late')
        a = max(0, total_students - (p + l))
        weekly_data.append({
            "date": day_str,
            "label": label,
            "present": p,
            "late": l,
            "absent": a,
            "total_students": total_students
        })

    conn.close()

    return {
        "total_students": total_students,
        "present_today": present_today,
        "late_today": late_today,
        "absent_today": absent_today,
        "total_attended_today": total_attended,
        "attendance_percentage": percentage,
        "today_records": [dict(r) for r in today_records],
        "recent_records": [dict(r) for r in recent],
        "weekly_data": weekly_data
    }

def get_analytics_data():
    conn = get_db_connection()
    today = date.today()
    total_students_row = conn.execute("SELECT COUNT(*) as count FROM students").fetchone()
    total_students = total_students_row['count'] if total_students_row else 1

    # Daily trend (past 14 days)
    daily_trends = []
    for i in range(13, -1, -1):
        cur_date = today - timedelta(days=i)
        d_str = cur_date.strftime('%Y-%m-%d')
        rows = conn.execute("SELECT status FROM attendance WHERE date = ?", (d_str,)).fetchall()
        pres = sum(1 for r in rows if r['status'] == 'Present')
        lt = sum(1 for r in rows if r['status'] == 'Late')
        pct = round(((pres + lt) / total_students * 100), 1) if total_students > 0 else 0
        daily_trends.append({
            "date": d_str,
            "label": cur_date.strftime('%d %b'),
            "present": pres,
            "late": lt,
            "absent": max(0, total_students - (pres + lt)),
            "percentage": pct
        })

    # Department-wise stats
    dept_rows = conn.execute("SELECT DISTINCT department FROM students").fetchall()
    dept_stats = []
    for d in dept_rows:
        dept = d['department']
        dept_total = conn.execute("SELECT COUNT(*) as count FROM students WHERE department = ?", (dept,)).fetchone()['count']
        dept_att = conn.execute('''
            SELECT COUNT(DISTINCT a.student_id) as count
            FROM attendance a
            JOIN students s ON a.student_id = s.student_id
            WHERE s.department = ? AND a.date >= ?
        ''', (dept, (today - timedelta(days=30)).strftime('%Y-%m-%d'))).fetchone()['count']
        
        dept_pct = round((dept_att / dept_total * 100), 1) if dept_total > 0 else 0
        dept_stats.append({
            "department": dept,
            "total_students": dept_total,
            "attended_count": dept_att,
            "percentage": dept_pct
        })

    # Student-wise attendance summary
    student_summary = conn.execute('''
        SELECT s.student_id, s.roll_no, s.name, s.department, s.class_name,
               COUNT(a.id) as total_days_attended,
               SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
               SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) as late_count
        FROM students s
        LEFT JOIN attendance a ON s.student_id = a.student_id
        GROUP BY s.student_id
        ORDER BY s.roll_no ASC
    ''').fetchall()

    student_stats = []
    # Assume 10 total active school days in current period
    active_days = max(len(set(r['date'] for r in conn.execute("SELECT DISTINCT date FROM attendance").fetchall())), 1)
    for s in student_summary:
        pres = s['present_count'] or 0
        lt = s['late_count'] or 0
        tot = pres + lt
        pct = round((tot / active_days * 100), 1) if active_days > 0 else 0
        student_stats.append({
            "student_id": s['student_id'],
            "roll_no": s['roll_no'],
            "name": s['name'],
            "department": s['department'],
            "class_name": s['class_name'],
            "present_count": pres,
            "late_count": lt,
            "total_attended": tot,
            "percentage": min(100.0, pct)
        })

    # Methods breakdown
    method_rows = conn.execute('''
        SELECT method, COUNT(*) as count
        FROM attendance
        GROUP BY method
    ''').fetchall()
    methods_data = {row['method']: row['count'] for row in method_rows}

    # Status breakdown
    status_rows = conn.execute('''
        SELECT status, COUNT(*) as count
        FROM attendance
        GROUP BY status
    ''').fetchall()
    status_data = {row['status']: row['count'] for row in status_rows}

    conn.close()

    return {
        "daily_trends": daily_trends,
        "dept_stats": dept_stats,
        "student_stats": student_stats,
        "methods_data": methods_data,
        "status_data": status_data,
        "active_days": active_days
    }

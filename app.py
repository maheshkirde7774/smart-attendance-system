import os
import io
import csv
from datetime import datetime, date
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, Response, send_file
)

from utils.database import (
    init_db, verify_user, get_user_by_id, update_user_profile,
    get_all_students, get_student_by_id, get_student_by_student_id,
    add_student, update_student, delete_student, set_face_registered,
    mark_attendance, get_attendance_records, get_dashboard_stats,
    get_analytics_data, get_settings, update_settings
)
from utils.qr_generator import generate_student_qr, verify_qr_data
from utils.face_recognition import (
    recognize_face, save_face_samples, train_model
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'smart-attendance-ultra-secret-key-2026')

# Initialize DB on import/startup
init_db()

# Generate initial QR codes for seeded students if missing
def ensure_seed_qr_codes():
    students = get_all_students()
    for s in students:
        qr_file = f"qr_{s['student_id']}.png"
        qr_path = os.path.join(app.root_path, 'static', 'qrcodes', qr_file)
        if not os.path.exists(qr_path):
            generate_student_qr(s['student_id'], s['name'], s['roll_no'])

ensure_seed_qr_codes()

# --- AUTH DECORATOR ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_global_data():
    settings = get_settings()
    current_user = None
    if 'user_id' in session:
        current_user = get_user_by_id(session['user_id'])
    return {
        'settings': settings,
        'current_user': current_user,
        'current_time': datetime.now().strftime('%H:%M:%S'),
        'current_date': date.today().strftime('%A, %d %B %Y')
    }

# --- ROUTES ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = verify_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['name'] = user['name']
            flash(f"Welcome back, {user['name']}!", 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    stats = get_dashboard_stats()
    return render_template('dashboard.html', stats=stats)

@app.route('/students')
@login_required
def students():
    search = request.args.get('search', '').strip()
    department = request.args.get('department', '').strip()
    class_name = request.args.get('class_name', '').strip()

    student_list = get_all_students(search=search, department=department, class_name=class_name)
    
    # Get distinct departments and classes for filters
    all_students_raw = get_all_students()
    departments = sorted(list(set(s['department'] for s in all_students_raw if s['department'])))
    classes = sorted(list(set(s['class_name'] for s in all_students_raw if s['class_name'])))

    return render_template('students.html',
                           students=student_list,
                           departments=departments,
                           classes=classes,
                           search=search,
                           selected_dept=department,
                           selected_class=class_name)

@app.route('/attendance')
@login_required
def attendance():
    stats = get_dashboard_stats()
    students_list = get_all_students()
    return render_template('attendance.html', stats=stats, students=students_list)

@app.route('/qr-scanner')
@login_required
def qr_scanner():
    stats = get_dashboard_stats()
    return render_template('qr-scanner.html', stats=stats)

@app.route('/face-recognition')
@login_required
def face_recognition_page():
    stats = get_dashboard_stats()
    return render_template('face-recognition.html', stats=stats)

@app.route('/records')
@login_required
def records():
    search = request.args.get('search', '').strip()
    date_filter = request.args.get('date', '').strip()
    department = request.args.get('department', '').strip()
    status_filter = request.args.get('status', '').strip()

    record_list = get_attendance_records(
        search=search,
        date_filter=date_filter,
        department=department,
        status=status_filter
    )

    all_students_raw = get_all_students()
    departments = sorted(list(set(s['department'] for s in all_students_raw if s['department'])))

    return render_template('attendance.html', # We also have records integrated or dedicated
                           is_records_view=True,
                           records=record_list,
                           departments=departments,
                           search=search,
                           selected_date=date_filter,
                           selected_dept=department,
                           selected_status=status_filter)

@app.route('/analytics')
@login_required
def analytics():
    analytics_data = get_analytics_data()
    stats = get_dashboard_stats()
    return render_template('analytics.html', analytics=analytics_data, stats=stats)

@app.route('/reports')
@login_required
def reports():
    date_filter = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    department = request.args.get('department', '')
    status_filter = request.args.get('status', '')

    record_list = get_attendance_records(
        date_filter=date_filter,
        department=department,
        status=status_filter
    )

    all_students_raw = get_all_students()
    departments = sorted(list(set(s['department'] for s in all_students_raw if s['department'])))
    
    total_students = len(all_students_raw)
    present_count = sum(1 for r in record_list if r['status'] == 'Present')
    late_count = sum(1 for r in record_list if r['status'] == 'Late')
    absent_count = max(0, total_students - (present_count + late_count))

    summary = {
        "total_records": len(record_list),
        "present_count": present_count,
        "late_count": late_count,
        "absent_count": absent_count,
        "percentage": round(((present_count + late_count) / total_students * 100), 1) if total_students > 0 else 0
    }

    return render_template('reports.html',
                           records=record_list,
                           departments=departments,
                           selected_date=date_filter,
                           selected_dept=department,
                           selected_status=status_filter,
                           summary=summary)

@app.route('/settings')
@login_required
def settings_page():
    current_settings = get_settings()
    return render_template('settings.html', settings=current_settings)

# --- API ENDPOINTS ---

@app.route('/api/stats')
@login_required
def api_stats():
    return jsonify(get_dashboard_stats())

@app.route('/api/recognize_face', methods=['POST'])
@login_required
def api_recognize_face():
    """
    Receives base64 camera frame from client,
    executes OpenCV face detection & recognition.
    If matching student found: marks attendance (preventing duplicates).
    If unknown person: rejects and returns match: false.
    """
    data = request.get_json() or {}
    image_data = data.get('image')

    if not image_data:
        return jsonify({"success": False, "match": False, "message": "No image frame received"}), 400

    rec_result = recognize_face(image_data)

    if not rec_result["match"]:
        return jsonify({
            "success": False,
            "match": False,
            "status": rec_result["status"],
            "box": rec_result.get("box"),
            "confidence": rec_result.get("confidence", 0),
            "message": rec_result.get("message", "Unknown or unverified face.")
        })

    # Recognized student ID
    student_id = rec_result["student_id"]
    confidence = rec_result["confidence"]

    # Mark attendance
    att_res = mark_attendance(student_id, method="Face Recognition")

    return jsonify({
        "success": True,
        "match": True,
        "confidence": confidence,
        "box": rec_result.get("box"),
        "student": att_res.get("student"),
        "already_marked": att_res.get("already_marked", False),
        "message": att_res.get("message"),
        "record": att_res.get("record")
    })

@app.route('/api/mark_attendance_qr', methods=['POST'])
@login_required
def api_mark_attendance_qr():
    """
    Receives decoded QR string (student_id),
    verifies student existence, and marks attendance.
    """
    data = request.get_json() or {}
    qr_data = data.get('qr_data')

    if not qr_data:
        return jsonify({"success": False, "message": "No QR code data provided"}), 400

    student_id = verify_qr_data(qr_data)
    student = get_student_by_student_id(student_id)

    if not student:
        return jsonify({
            "success": False,
            "message": f"Invalid QR Code: Student '{student_id}' does not exist in the system."
        }), 404

    att_res = mark_attendance(student_id, method="QR Scan")

    return jsonify({
        "success": att_res.get("success", False),
        "already_marked": att_res.get("already_marked", False),
        "student": att_res.get("student"),
        "message": att_res.get("message"),
        "record": att_res.get("record")
    })

@app.route('/api/mark_attendance_manual', methods=['POST'])
@login_required
def api_mark_attendance_manual():
    data = request.get_json() or {}
    student_id = data.get('student_id')
    status = data.get('status', 'Present')

    if not student_id:
        return jsonify({"success": False, "message": "Student ID is required"}), 400

    att_res = mark_attendance(student_id, method="Manual")
    return jsonify(att_res)

@app.route('/api/students/add', methods=['POST'])
@login_required
def api_add_student():
    data = request.form if request.form else (request.get_json() or {})
    student_id = data.get('student_id', '').strip()
    roll_no = data.get('roll_no', '').strip()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    department = data.get('department', '').strip()
    class_name = data.get('class_name', '').strip()

    if not all([student_id, roll_no, name, email, department, class_name]):
        return jsonify({"success": False, "message": "All fields are required"}), 400

    success, msg = add_student(student_id, roll_no, name, email, department, class_name)
    if success:
        # Generate QR
        generate_student_qr(student_id, name, roll_no)
        return jsonify({"success": True, "message": "Student added successfully", "student_id": student_id})
    return jsonify({"success": False, "message": msg}), 400

@app.route('/api/students/edit', methods=['POST'])
@login_required
def api_edit_student():
    data = request.form if request.form else (request.get_json() or {})
    id_val = data.get('id')
    roll_no = data.get('roll_no', '').strip()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    department = data.get('department', '').strip()
    class_name = data.get('class_name', '').strip()

    if not all([id_val, roll_no, name, email, department, class_name]):
        return jsonify({"success": False, "message": "All fields are required"}), 400

    success, msg = update_student(id_val, roll_no, name, email, department, class_name)
    if success:
        return jsonify({"success": True, "message": "Student updated successfully"})
    return jsonify({"success": False, "message": msg}), 400

@app.route('/api/students/delete', methods=['POST'])
@login_required
def api_delete_student():
    data = request.get_json() or request.form or {}
    id_val = data.get('id')
    if not id_val:
        return jsonify({"success": False, "message": "ID is required"}), 400

    delete_student(id_val)
    return jsonify({"success": True, "message": "Student and attendance records deleted"})

@app.route('/api/students/register_face', methods=['POST'])
@login_required
def api_register_face():
    """
    Receives student_id and an array of base64 face sample images.
    Extracts faces with Haar Cascade and updates the face recognition model.
    """
    data = request.get_json() or {}
    student_id = data.get('student_id')
    images = data.get('images', [])

    if not student_id or not images:
        return jsonify({"success": False, "message": "Student ID and image samples are required"}), 400

    success, msg = save_face_samples(student_id, images)
    if success:
        set_face_registered(student_id, 1)
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "message": msg}), 400

@app.route('/api/export_csv')
@login_required
def api_export_csv():
    """Exports attendance records to CSV."""
    date_filter = request.args.get('date', '').strip()
    department = request.args.get('department', '').strip()
    status_filter = request.args.get('status', '').strip()
    search = request.args.get('search', '').strip()

    records = get_attendance_records(
        search=search,
        date_filter=date_filter,
        department=department,
        status=status_filter
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Record ID", "Student ID", "Roll Number", "Student Name", "Department", "Class", "Date", "Time", "Status", "Method"])

    for r in records:
        writer.writerow([
            r['id'],
            r['student_id'],
            r['roll_no'],
            r['name'],
            r['department'],
            r['class_name'],
            r['date'],
            r['time'],
            r['status'],
            r['method']
        ])

    output.seek(0)
    filename = f"attendance_report_{date.today().strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@app.route('/api/settings/update', methods=['POST'])
@login_required
def api_update_settings():
    data = request.get_json() or request.form or {}
    updates = {}
    for key in ['late_threshold', 'academic_year', 'system_title', 'tagline', 'institution_name', 'face_confidence_threshold']:
        if key in data:
            updates[key] = data[key]

    if updates:
        update_settings(updates)
        return jsonify({"success": True, "message": "Settings updated successfully"})
    return jsonify({"success": False, "message": "No settings provided"}), 400

@app.route('/api/profile/update', methods=['POST'])
@login_required
def api_update_profile():
    data = request.get_json() or request.form or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    current_password = data.get('current_password', '').strip()
    new_password = data.get('new_password', '').strip()

    if not name or not email:
        return jsonify({"success": False, "message": "Name and email are required"}), 400

    user_id = session['user_id']
    success, msg = update_user_profile(user_id, name, email, current_password, new_password)

    if success:
        session['name'] = name
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "message": msg}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting SMART ATTENDANCE on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)

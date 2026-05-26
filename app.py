import os
import uuid
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database import get_db
from utils.certificate import generate_certificate

app = Flask(__name__)
app.secret_key = 'super_secret_lms_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['CERTIFICATES_FOLDER'] = 'certificates'

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CERTIFICATES_FOLDER'], exist_ok=True)

# Helper for login required
def login_required(role=None):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash('Unauthorized access!', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

def log_activity(user_id, action, details=""):
    conn = get_db()
    conn.execute("INSERT INTO activity_logs (user_id, action, details) VALUES (?, ?, ?)", (user_id, action, details))
    conn.commit()
    conn.close()

def ensure_certificate(student_id, course_id):
    """Ensures a certificate exists for a student and course if completed."""
    conn = get_db()
    # Check if certificate already exists
    existing = conn.execute("""
        SELECT id FROM certificates 
        WHERE student_id = ? AND course_id = ?
    """, (student_id, course_id)).fetchone()
    
    if not existing:
        student = conn.execute("SELECT name FROM users WHERE id = ?", (student_id,)).fetchone()
        course = conn.execute("SELECT title FROM courses WHERE id = ?", (course_id,)).fetchone()
        
        if not student or not course:
            conn.close()
            return None
            
        cert_id = "EDUTECH-" + str(uuid.uuid4())[:8].upper()
        student_name = student['name']
        course_title = course['title']
        
        filename = None
        try:
            filename = generate_certificate(student_name, course_title, cert_id)
        except Exception as e:
            print(f"PDF Generation failed: {e}")
            # We still proceed to insert the DB record as requested
            
        conn.execute("""
            INSERT INTO certificates (certificate_id, student_id, course_id, pdf_path)
            VALUES (?, ?, ?, ?)
        """, (cert_id, student_id, course_id, filename))
        
        # Ensure completion record in course_progress
        conn.execute("""
            INSERT INTO course_progress (student_id, course_id, is_completed, completed_at)
            SELECT ?, ?, 1, CURRENT_TIMESTAMP
            WHERE NOT EXISTS (SELECT 1 FROM course_progress WHERE student_id = ? AND course_id = ?)
        """, (student_id, course_id, student_id, course_id))
        
        conn.commit()
    conn.close()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password'].strip()
        
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['name'] = user['name']
            log_activity(user['id'], 'login', f'User logged in as {user["role"]}')
            
            # Role-based redirect directly from login
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'faculty':
                return redirect(url_for('faculty_dashboard'))
            elif user['role'] == 'student':
                return redirect(url_for('student_dashboard'))
            elif user['role'] == 'parent':
                return redirect(url_for('parent_dashboard'))
            
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_activity(session['user_id'], 'logout', 'User logged out')
        session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required()
def dashboard():
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'faculty':
        return redirect(url_for('faculty_dashboard'))
    elif role == 'student':
        return redirect(url_for('student_dashboard'))
    elif role == 'parent':
        return redirect(url_for('parent_dashboard'))
    return abort(403)

# ================= ADMIN ROUTES =================
@app.route('/admin')
@login_required(role='admin')
def admin_dashboard():
    conn = get_db()
    stats = {
        'students': conn.execute("SELECT COUNT(*) as count FROM users WHERE role='student'").fetchone()['count'],
        'faculty': conn.execute("SELECT COUNT(*) as count FROM users WHERE role='faculty'").fetchone()['count'],
        'courses': conn.execute("SELECT COUNT(*) as count FROM courses").fetchone()['count'],
        'revenue': conn.execute("SELECT SUM(amount) as total FROM payments WHERE status='success'").fetchone()['total'] or 0.0
    }
    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 5").fetchall()
    conn.close()
    return render_template('dashboard_admin.html', stats=stats, users=users)

@app.route('/admin/users', methods=['GET', 'POST'])
@login_required(role='admin')
def manage_users():
    conn = get_db()
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].strip().lower()
        password = generate_password_hash(request.form['password'].strip())
        role = request.form['role']
        try:
            conn.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)", (name, email, password, role))
            conn.commit()
            flash('User added successfully!', 'success')
        except Exception as e:
            flash('Error adding user. Email might exist.', 'danger')
    
    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template('admin_users.html', users=users)

@app.route('/admin/courses')
@login_required(role='admin')
def admin_courses():
    conn = get_db()
    courses = conn.execute("""
        SELECT c.*, u.name as faculty_name 
        FROM courses c 
        LEFT JOIN users u ON c.faculty_id = u.id
    """).fetchall()
    conn.close()
    return render_template('admin_courses.html', courses=courses)

@app.route('/admin/payments')
@login_required(role='admin')
def admin_payments():
    conn = get_db()
    payments = conn.execute("""
        SELECT p.*, u.name as student_name 
        FROM payments p 
        JOIN users u ON p.student_id = u.id 
        ORDER BY p.created_at DESC
    """).fetchall()
    conn.close()
    return render_template('admin_payments.html', payments=payments)

# ================= FACULTY ROUTES =================
@app.route('/faculty')
@login_required(role='faculty')
def faculty_dashboard():
    conn = get_db()
    faculty_id = session['user_id']
    courses = conn.execute("SELECT * FROM courses WHERE faculty_id = ?", (faculty_id,)).fetchall()
    conn.close()
    return render_template('dashboard_faculty.html', courses=courses)

@app.route('/faculty/courses/new', methods=['GET', 'POST'])
@login_required(role='faculty')
def create_course():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        price = request.form['price']
        
        conn = get_db()
        conn.execute("INSERT INTO courses (title, description, category, price, faculty_id) VALUES (?, ?, ?, ?, ?)",
                     (title, description, category, price, session['user_id']))
        conn.commit()
        conn.close()
        flash('Course created successfully', 'success')
        return redirect(url_for('faculty_dashboard'))
    return render_template('course_create.html')

@app.route('/faculty/course/<int:course_id>/modules', methods=['POST'])
@login_required(role='faculty')
def add_module(course_id):
    title = request.form['title']
    conn = get_db()
    conn.execute("INSERT INTO modules (course_id, title) VALUES (?, ?)", (course_id, title))
    conn.commit()
    conn.close()
    return redirect(url_for('faculty_course_detail', course_id=course_id))

@app.route('/faculty/course/<int:course_id>')
@login_required(role='faculty')
def faculty_course_detail(course_id):
    conn = get_db()
    course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    modules = conn.execute("SELECT * FROM modules WHERE course_id = ?", (course_id,)).fetchall()
    videos = conn.execute("SELECT v.* FROM videos v JOIN modules m ON v.module_id = m.id WHERE m.course_id = ?", (course_id,)).fetchall()
    conn.close()
    return render_template('faculty_course_detail.html', course=course, modules=modules, videos=videos)

@app.route('/faculty/assignments')
@login_required(role='faculty')
def faculty_assignments():
    conn = get_db()
    faculty_id = session['user_id']
    assignments = conn.execute("""
        SELECT a.*, c.title as course_title 
        FROM assignments a 
        JOIN courses c ON a.course_id = c.id 
        WHERE c.faculty_id = ?
    """, (faculty_id,)).fetchall()
    conn.close()
    return render_template('faculty_assignments.html', assignments=assignments)

@app.route('/faculty/live_classes')
@login_required(role='faculty')
def faculty_live_classes():
    conn = get_db()
    # Mock live classes for demo
    live_classes = conn.execute("SELECT * FROM live_classes").fetchall()
    conn.close()
    return render_template('faculty_live_classes.html', live_classes=live_classes)


@app.route('/faculty/module/<int:module_id>/videos', methods=['POST'])
@login_required(role='faculty')
def add_video(module_id):
    title = request.form['title']
    video_url = request.form['video_url']
    conn = get_db()
    module = conn.execute("SELECT course_id FROM modules WHERE id = ?", (module_id,)).fetchone()
    conn.execute("INSERT INTO videos (module_id, title, video_url) VALUES (?, ?, ?)", (module_id, title, video_url))
    conn.commit()
    conn.close()
    return redirect(url_for('faculty_course_detail', course_id=module['course_id']))

# ================= STUDENT ROUTES =================
@app.route('/student')
@login_required(role='student')
def student_dashboard():
    conn = get_db()
    student_id = session['user_id']
    
    enrollments = conn.execute("""
        SELECT e.*, c.title, c.description, c.thumbnail 
        FROM enrollments e 
        JOIN courses c ON e.course_id = c.id 
        WHERE e.student_id = ?
    """, (student_id,)).fetchall()
    
    # Advanced Stats
    total_enrollments = len(enrollments)
    completed_courses = conn.execute("SELECT COUNT(*) as count FROM enrollments WHERE student_id = ? AND progress >= 100", (student_id,)).fetchone()['count']
    videos_watched = conn.execute("SELECT COUNT(*) as count FROM video_watch_history WHERE student_id = ? AND is_completed = 1", (student_id,)).fetchone()['count']
    
    # Attendance %
    attendance_data = conn.execute("SELECT status FROM attendance WHERE student_id = ?", (student_id,)).fetchall()
    total_days = len(attendance_data)
    present_days = sum(1 for d in attendance_data if d['status'] == 'present')
    attendance_pct = (present_days / total_days * 100) if total_days > 0 else 0
    
    # Assignments & Assessments
    pending_assignments = conn.execute("""
        SELECT COUNT(*) as count FROM assignments a
        WHERE a.course_id IN (SELECT course_id FROM enrollments WHERE student_id = ?)
        AND a.id NOT IN (SELECT assignment_id FROM submissions WHERE student_id = ?)
    """, (student_id, student_id)).fetchone()['count']
    
    upcoming_assessments = conn.execute("""
        SELECT COUNT(*) as count FROM assessments a
        WHERE a.course_id IN (SELECT course_id FROM enrollments WHERE student_id = ?)
        AND a.id NOT IN (SELECT assessment_id FROM assessment_submissions WHERE student_id = ?)
    """, (student_id, student_id)).fetchone()['count']
    
    certificates_earned = conn.execute("SELECT COUNT(*) as count FROM certificates WHERE student_id = ?", (student_id,)).fetchone()['count']
    
    # Overall Progress
    avg_progress = conn.execute("SELECT AVG(progress) as avg FROM enrollments WHERE student_id = ?", (student_id,)).fetchone()['avg'] or 0
    
    stats = {
        'enrolled': total_enrollments,
        'completed': completed_courses,
        'videos_watched': videos_watched,
        'attendance_pct': round(attendance_pct, 1),
        'pending_assignments': pending_assignments,
        'upcoming_assessments': upcoming_assessments,
        'certificates_earned': certificates_earned,
        'overall_progress': round(avg_progress, 1)
    }
    
    conn.close()
    return render_template('dashboard_student.html', enrollments=enrollments, stats=stats)

@app.route('/student/my-courses')
@login_required(role='student')
def student_my_courses():
    conn = get_db()
    student_id = session['user_id']
    enrollments = conn.execute("""
        SELECT e.*, c.title, c.description, c.thumbnail, c.instructor_name 
        FROM enrollments e 
        JOIN courses c ON e.course_id = c.id 
        WHERE e.student_id = ?
    """, (student_id,)).fetchall()
    conn.close()
    return render_template('student_my_courses.html', enrollments=enrollments)

@app.route('/student/attendance')
@login_required(role='student')
def student_attendance():
    conn = get_db()
    student_id = session['user_id']
    attendance = conn.execute("SELECT * FROM attendance WHERE student_id = ? ORDER BY date DESC", (student_id,)).fetchall()
    
    present_days = sum(1 for d in attendance if d['status'] == 'present')
    total_days = len(attendance)
    attendance_pct = (present_days / total_days * 100) if total_days > 0 else 0
    
    conn.close()
    return render_template('student_attendance.html', attendance=attendance, pct=round(attendance_pct, 1))

@app.route('/student/assessments')
@login_required(role='student')
def student_assessments():
    conn = get_db()
    student_id = session['user_id']
    assessments = conn.execute("""
        SELECT a.*, c.title as course_title, s.obtained_marks, s.status as sub_status
        FROM assessments a
        JOIN courses c ON a.course_id = c.id
        JOIN enrollments e ON c.id = e.course_id
        LEFT JOIN assessment_submissions s ON a.id = s.assessment_id AND s.student_id = ?
        WHERE e.student_id = ?
    """, (student_id, student_id)).fetchall()
    conn.close()
    return render_template('student_assessments.html', assessments=assessments)

@app.route('/student/assignments')
@login_required(role='student')
def student_assignments():
    conn = get_db()
    student_id = session['user_id']
    assignments = conn.execute("""
        SELECT a.*, c.title as course_title, s.status as sub_status, s.marks
        FROM assignments a
        JOIN courses c ON a.course_id = c.id
        JOIN enrollments e ON c.id = e.course_id
        LEFT JOIN submissions s ON a.id = s.assignment_id AND s.student_id = ?
        WHERE e.student_id = ?
    """, (student_id, student_id)).fetchall()
    conn.close()
    return render_template('student_assignments.html', assignments=assignments)

@app.route('/student/certificates')
@login_required(role='student')
def student_certificates():
    conn = get_db()
    student_id = session['user_id']

    # Auto-generate for any course that reached 100% but has no cert yet
    completed_courses = conn.execute("""
        SELECT course_id FROM enrollments 
        WHERE student_id = ? AND progress >= 100
    """, (student_id,)).fetchall()
    
    for row in completed_courses:
        ensure_certificate(student_id, row['course_id'])

    certs = conn.execute("""
        SELECT ce.*, co.title as course_title
        FROM certificates ce
        LEFT JOIN courses co ON ce.course_id = co.id
        WHERE ce.student_id = ?
        ORDER BY ce.issued_at DESC
    """, (student_id,)).fetchall()

    conn.close()
    return render_template('student_certificates.html', certs=certs)

@app.route('/student/progress')
@login_required(role='student')
def student_progress():
    conn = get_db()
    student_id = session['user_id']
    enrollments = conn.execute("""
        SELECT e.*, c.title 
        FROM enrollments e 
        JOIN courses c ON e.course_id = c.id 
        WHERE e.student_id = ?
    """, (student_id,)).fetchall()
    conn.close()
    return render_template('student_progress.html', enrollments=enrollments)

@app.route('/student/video-learning')
@login_required(role='student')
def student_video_learning():
    conn = get_db()
    student_id = session['user_id']
    # Show videos from enrolled courses
    videos = conn.execute("""
        SELECT v.*, c.title as course_title, c.id as course_id, wh.is_completed
        FROM videos v
        JOIN modules m ON v.module_id = m.id
        JOIN courses c ON m.course_id = c.id
        JOIN enrollments e ON c.id = e.course_id
        LEFT JOIN video_watch_history wh ON v.id = wh.video_id AND wh.student_id = ?
        WHERE e.student_id = ?
    """, (student_id, student_id)).fetchall()
    
    # Also include seeded course single videos
    seeded_courses = conn.execute("""
        SELECT c.*, e.progress
        FROM courses c
        JOIN enrollments e ON c.id = e.course_id
        WHERE e.student_id = ? AND c.video_url IS NOT NULL
    """, (student_id,)).fetchall()
    
    conn.close()
    return render_template('student_video_learning.html', videos=videos, seeded_courses=seeded_courses)

@app.route('/student/notifications')
@login_required(role='student')
def student_notifications():
    conn = get_db()
    notifications = conn.execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC", (session['user_id'],)).fetchall()
    conn.close()
    return render_template('student_notifications.html', notifications=notifications)

@app.route('/student/profile', methods=['GET', 'POST'])
@login_required(role='student')
def student_profile():
    conn = get_db()
    student_id = session['user_id']
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        password = request.form['password']
        if password:
            hashed_pw = generate_password_hash(password)
            conn.execute("UPDATE users SET name = ?, phone = ?, password = ? WHERE id = ?", (name, phone, hashed_pw, student_id))
        else:
            conn.execute("UPDATE users SET name = ?, phone = ? WHERE id = ?", (name, phone, student_id))
        conn.commit()
        session['name'] = name
        flash('Profile updated successfully!', 'success')
        
    user = conn.execute("""
        SELECT u.*, s.batch_id, b.name as batch_name,
        (SELECT COUNT(*) FROM enrollments WHERE student_id = u.id) as course_count
        FROM users u
        LEFT JOIN students s ON u.id = s.user_id
        LEFT JOIN batches b ON s.batch_id = b.id
        WHERE u.id = ?
    """, (student_id,)).fetchone()
    conn.close()
    return render_template('student_profile.html', user=user)

@app.route('/courses')
@login_required(role='student')
def browse_courses():
    conn = get_db()
    courses = conn.execute("SELECT * FROM courses").fetchall()
    conn.close()
    return render_template('student_courses.html', courses=courses)

@app.route('/course/<int:course_id>/enroll', methods=['POST'])
@login_required(role='student')
def enroll_course(course_id):
    conn = get_db()
    student_id = session['user_id']
    # Check if already enrolled
    existing = conn.execute("SELECT id FROM enrollments WHERE student_id=? AND course_id=?", (student_id, course_id)).fetchone()
    if not existing:
        conn.execute("INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)", (student_id, course_id))
        conn.commit()
        log_activity(student_id, 'enroll_course', f'Enrolled in course {course_id}')
        flash('Successfully enrolled in course!', 'success')
    else:
        flash('Already enrolled.', 'info')
    conn.close()
    return redirect(url_for('student_dashboard'))

@app.route('/student/course/<int:course_id>')
@login_required(role='student')
def student_course_detail(course_id):
    conn = get_db()
    student_id = session['user_id']
    course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    modules = conn.execute("SELECT * FROM modules WHERE course_id = ? ORDER BY order_num", (course_id,)).fetchall()
    videos = conn.execute("SELECT v.* FROM videos v JOIN modules m ON v.module_id = m.id WHERE m.course_id = ?", (course_id,)).fetchall()
    
    enrollment = conn.execute("SELECT progress FROM enrollments WHERE student_id = ? AND course_id = ?", (student_id, course_id)).fetchone()
    
    conn.close()
    return render_template('student_course_detail.html', course=course, modules=modules, videos=videos, enrollment=enrollment)

@app.route('/course/<int:course_id>/mark_done', methods=['POST'])
@login_required(role='student')
def mark_course_done(course_id):
    student_id = session['user_id']
    
    # Update progress in enrollments to 100 first
    conn = get_db()
    conn.execute("UPDATE enrollments SET progress = 100 WHERE student_id = ? AND course_id = ?", (student_id, course_id))
    conn.commit()
    conn.close()
    
    # Trigger certificate generation
    ensure_certificate(student_id, course_id)

    flash('Course completed! Certificate generated.', 'success')
    return redirect(url_for('student_course_detail', course_id=course_id))

@app.route('/student/video/<int:video_id>')
@login_required(role='student')
def watch_video(video_id):
    conn = get_db()
    video = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    if not video:
        conn.close()
        return abort(404)
    module = conn.execute("SELECT * FROM modules WHERE id = ?", (video['module_id'],)).fetchone()
    course = conn.execute("SELECT * FROM courses WHERE id = ?", (module['course_id'],)).fetchone()
    conn.close()
    return render_template('video_player.html', video=video, course=course)

# ================= WEBHOOKS =================
@app.route('/webhook/video_progress', methods=['POST'])
@login_required(role='student')
def video_progress_webhook():
    data = request.json
    video_id = data.get('video_id')
    course_id = data.get('course_id')
    progress_percent = data.get('progress')
    
    student_id = session['user_id']
    conn = get_db()
    conn.execute("UPDATE enrollments SET progress = ? WHERE student_id = ? AND course_id = ?", (progress_percent, student_id, course_id))
    conn.commit()
    conn.close()
    
    # Auto trigger cert if progress hits 100
    if progress_percent >= 100:
        ensure_certificate(student_id, course_id)
        
    return jsonify({"status": "success", "message": "Progress tracked"})

@app.route('/webhook/generate_certificate', methods=['POST'])
@login_required(role='student')
def generate_cert_webhook():
    data = request.json
    course_id = data.get('course_id')
    student_id = session['user_id']
    
    ensure_certificate(student_id, course_id)
    
    conn = get_db()
    cert = conn.execute("SELECT certificate_id FROM certificates WHERE student_id = ? AND course_id = ?", (student_id, course_id)).fetchone()
    conn.close()
    
    if cert:
        return jsonify({"status": "success", "cert_id": cert['certificate_id'], "url": url_for('download_certificate', cert_id=cert['certificate_id'])})
    return jsonify({"status": "error", "message": "Failed to generate certificate"}), 500

@app.route('/certificates/<cert_id>')
def download_certificate(cert_id):
    conn = get_db()
    cert = conn.execute("SELECT pdf_path FROM certificates WHERE certificate_id = ?", (cert_id,)).fetchone()
    conn.close()
    if cert:
        return send_from_directory(app.config['CERTIFICATES_FOLDER'], cert['pdf_path'])
    return abort(404)

# ================= PAYMENT SIMULATION =================
@app.route('/payment', methods=['GET', 'POST'])
@login_required()
def payment():
    conn = get_db()
    student_id = session['user_id']
    if request.method == 'POST':
        amount = request.form['amount']
        purpose = request.form['purpose']
        txn_id = "TXN" + str(uuid.uuid4())[:8].upper()
        
        conn.execute("INSERT INTO payments (student_id, amount, purpose, status, transaction_id) VALUES (?, ?, ?, ?, ?)",
                     (student_id, amount, purpose, 'success', txn_id))
        conn.commit()
        
        flash(f'Payment of ${amount} successful! TXN ID: {txn_id}', 'success')
        return redirect(url_for('payment'))
        
    payments = conn.execute("SELECT * FROM payments WHERE student_id = ? ORDER BY created_at DESC", (student_id,)).fetchall()
    conn.close()
    return render_template('payment.html', payments=payments)

# ================= PARENT ROUTES =================
@app.route('/parent')
@login_required(role='parent')
def parent_dashboard():
    return render_template('dashboard_parent.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)

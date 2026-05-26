import sqlite3
import os
import uuid
from werkzeug.security import generate_password_hash

DB_NAME = "database.db"

def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Core User Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL, -- admin, student, faculty, parent
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    try: cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    except sqlite3.OperationalError: pass

    # Specific Profiles
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        parent_id INTEGER,
        batch_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (parent_id) REFERENCES users (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS faculty (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        department TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS parents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Courses & Learning
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        category TEXT,
        thumbnail TEXT,
        difficulty TEXT,
        duration TEXT,
        instructor_name TEXT,
        video_url TEXT,
        price REAL DEFAULT 0.0,
        status TEXT DEFAULT 'active', -- draft, active
        faculty_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (faculty_id) REFERENCES users (id)
    )
    ''')

    try: cursor.execute("ALTER TABLE courses ADD COLUMN thumbnail TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE courses ADD COLUMN difficulty TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE courses ADD COLUMN duration TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE courses ADD COLUMN instructor_name TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE courses ADD COLUMN video_url TEXT")
    except sqlite3.OperationalError: pass

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS course_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        is_completed BOOLEAN DEFAULT 0,
        completed_at TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES users (id),
        FOREIGN KEY (course_id) REFERENCES courses (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS video_watch_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        video_id INTEGER,
        course_id INTEGER,
        is_completed BOOLEAN DEFAULT 0,
        FOREIGN KEY (student_id) REFERENCES users (id),
        FOREIGN KEY (video_id) REFERENCES videos (id),
        FOREIGN KEY (course_id) REFERENCES courses (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        order_num INTEGER,
        FOREIGN KEY (course_id) REFERENCES courses (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        video_url TEXT,
        duration INTEGER, -- in seconds
        FOREIGN KEY (module_id) REFERENCES modules (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        progress REAL DEFAULT 0.0,
        enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES users (id),
        FOREIGN KEY (course_id) REFERENCES courses (id)
    )
    ''')

    # Assignments
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        due_date TIMESTAMP,
        file_url TEXT,
        instructor_name TEXT,
        FOREIGN KEY (course_id) REFERENCES courses (id)
    )
    ''')
    
    try: cursor.execute("ALTER TABLE assignments ADD COLUMN instructor_name TEXT")
    except sqlite3.OperationalError: pass

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        file_url TEXT,
        status TEXT DEFAULT 'submitted', -- submitted, graded
        marks REAL,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (assignment_id) REFERENCES assignments (id),
        FOREIGN KEY (student_id) REFERENCES users (id)
    )
    ''')

    # Attendance & Classes
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        faculty_id INTEGER,
        FOREIGN KEY (faculty_id) REFERENCES users (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        batch_id INTEGER NOT NULL,
        date DATE NOT NULL,
        status TEXT, -- present, absent, late
        FOREIGN KEY (student_id) REFERENCES users (id),
        FOREIGN KEY (batch_id) REFERENCES batches (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS live_classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        meeting_link TEXT,
        schedule TIMESTAMP,
        status TEXT DEFAULT 'scheduled', -- scheduled, ongoing, completed
        FOREIGN KEY (batch_id) REFERENCES batches (id)
    )
    ''')

    # Payments
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        purpose TEXT NOT NULL, -- fee, course_purchase
        status TEXT DEFAULT 'pending', -- pending, success, failed
        transaction_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES users (id)
    )
    ''')

    # Certificates
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS certificates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        certificate_id TEXT UNIQUE NOT NULL,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        pdf_path TEXT,
        issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES users (id),
        FOREIGN KEY (course_id) REFERENCES courses (id)
    )
    ''')

    # Communications & Tracking
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        sender_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (batch_id) REFERENCES batches (id),
        FOREIGN KEY (sender_id) REFERENCES users (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        is_read BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        total_marks INTEGER,
        due_date TIMESTAMP,
        FOREIGN KEY (course_id) REFERENCES courses (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS assessment_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        obtained_marks INTEGER,
        status TEXT DEFAULT 'completed',
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (assessment_id) REFERENCES assessments (id),
        FOREIGN KEY (student_id) REFERENCES users (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        file_url TEXT,
        material_type TEXT, -- pdf, video, link
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (course_id) REFERENCES courses (id)
    )
    ''')
    
    # Pre-populate admin user
    cursor.execute("SELECT id FROM users WHERE email='admin@edutech.com'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                       ('EduTech Admin', 'admin@edutech.com', generate_password_hash('admin123'), 'admin'))
    
    # Seed Courses
    courses_to_seed = [
        ("Python Programming Basics", "Master the fundamentals of Python programming from scratch.", "Programming", "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=400&h=250&fit=crop", "Beginner", "10 Hours", "John Smith", "https://www.youtube.com/embed/rfscVS0vtbw"),
        ("Advanced Python", "Deep dive into advanced Python concepts like decorators and generators.", "Programming", "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?w=400&h=250&fit=crop", "Advanced", "15 Hours", "Sarah Wilson", "https://www.youtube.com/embed/f79m180jlr8"),
        ("Web Development with Flask", "Build modern web applications using the Flask framework.", "Web Development", "https://images.unsplash.com/photo-1518770660439-4636190af475?w=400&h=250&fit=crop", "Intermediate", "12 Hours", "Mike Johnson", "https://www.youtube.com/embed/Z1RJmh_OqeA"),
        ("HTML & CSS Mastery", "Learn the building blocks of the web and design beautiful websites.", "Design", "https://images.unsplash.com/photo-1542831371-29b0f74f9713?w=400&h=250&fit=crop", "Beginner", "8 Hours", "Emily Davis", "https://www.youtube.com/embed/mU6anWqZJcc"),
        ("JavaScript Essentials", "Make your websites interactive with JavaScript.", "Programming", "https://images.unsplash.com/photo-1579468118864-1b9ea3c0db4a?w=400&h=250&fit=crop", "Beginner", "10 Hours", "Chris Anderson", "https://www.youtube.com/embed/W6NZ1OtI8AY"),
        ("SQLite Database Management", "Understand relational databases and SQL using SQLite.", "Database", "https://images.unsplash.com/photo-1544383835-bda2bc66a55d?w=400&h=250&fit=crop", "Intermediate", "6 Hours", "Patricia Lee", "https://www.youtube.com/embed/byHcYRpMgI4"),
        ("Data Structures in Python", "Optimize your code by learning essential data structures.", "Computer Science", "https://images.unsplash.com/photo-1516116216624-53e697fedbea?w=400&h=250&fit=crop", "Intermediate", "14 Hours", "David Miller", "https://www.youtube.com/embed/RBSGKlAvoiM"),
        ("Object Oriented Programming", "Learn the OOP paradigm in Python. Master classes and objects.", "Programming", "https://images.unsplash.com/photo-1498050108023-c5249f4df085?w=400&h=250&fit=crop", "Intermediate", "8 Hours", "Jennifer Garcia", "https://www.youtube.com/embed/Ej_02ICOIgs"),
        ("REST API Development with Flask", "Create robust RESTful APIs using Flask.", "Web Development", "https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=400&h=250&fit=crop", "Advanced", "10 Hours", "Robert Taylor", "https://www.youtube.com/embed/qbLc5a9jdXo"),
        ("Full Stack LMS Project", "Bring it all together by building a complete LMS.", "Web Development", "https://images.unsplash.com/photo-1501504905252-473c47e087f8?w=400&h=250&fit=crop", "Advanced", "20 Hours", "James White", "https://www.youtube.com/embed/v9qI6M-xIdM")
    ]

    cursor.execute("SELECT COUNT(*) FROM courses")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO courses (title, description, category, thumbnail, difficulty, duration, instructor_name, video_url, status, faculty_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', 1)
        """, courses_to_seed)

    # Seed Demo Faculty
    cursor.execute("SELECT id FROM users WHERE email='faculty@edutech.com'")
    demo_faculty = cursor.fetchone()
    if not demo_faculty:
        cursor.execute("INSERT INTO users (name, email, password, role, phone) VALUES (?, ?, ?, ?, ?)",
                       ('Prof. Sarah Faculty', 'faculty@edutech.com', generate_password_hash('faculty123'), 'faculty', '+1 987 654 3210'))
        faculty_user_id = cursor.lastrowid
        cursor.execute("INSERT INTO faculty (user_id, department) VALUES (?, ?)", (faculty_user_id, 'Computer Science'))
        # Update some courses to belong to this faculty
        cursor.execute("UPDATE courses SET faculty_id = ? WHERE id <= 10", (faculty_user_id,))
    else:
        faculty_user_id = demo_faculty['id']

    # Seed Demo Student
    cursor.execute("SELECT id FROM users WHERE email='student@edutech.com'")
    demo_student = cursor.fetchone()
    if not demo_student:
        cursor.execute("INSERT INTO users (name, email, password, role, phone) VALUES (?, ?, ?, ?, ?)",
                       ('John Student', 'student@edutech.com', generate_password_hash('student123'), 'student', '+1 234 567 8900'))
        student_user_id = cursor.lastrowid
        cursor.execute("INSERT INTO batches (name, faculty_id) VALUES (?, ?)", ("Alpha Batch 2026", faculty_user_id))
        batch_id = cursor.lastrowid
        cursor.execute("INSERT INTO students (user_id, batch_id) VALUES (?, ?)", (student_user_id, batch_id))
    else:
        student_user_id = demo_student['id']
        cursor.execute("SELECT batch_id FROM students WHERE user_id = ?", (student_user_id,))
        row = cursor.fetchone()
        if row and row['batch_id']:
            batch_id = row['batch_id']
        else:
            cursor.execute("INSERT INTO batches (name, faculty_id) VALUES (?, ?)", ("Alpha Batch 2026", faculty_user_id))
            batch_id = cursor.lastrowid
            cursor.execute("INSERT OR REPLACE INTO students (user_id, batch_id) VALUES (?, ?)", (student_user_id, batch_id))

    # Seed Demo Parent
    cursor.execute("SELECT id FROM users WHERE email='parent@edutech.com'")
    demo_parent = cursor.fetchone()
    if not demo_parent:
        cursor.execute("INSERT INTO users (name, email, password, role, phone) VALUES (?, ?, ?, ?, ?)",
                       ('Mr. Robert Parent', 'parent@edutech.com', generate_password_hash('parent123'), 'parent', '+1 555 123 4567'))
        parent_user_id = cursor.lastrowid
        cursor.execute("INSERT INTO parents (user_id) VALUES (?)", (parent_user_id,))
        # Link parent to student
        cursor.execute("UPDATE students SET parent_id = ? WHERE user_id = ?", (parent_user_id, student_user_id))
    else:
        parent_user_id = demo_parent['id']

    # Seed 10 Batches if empty
    cursor.execute("SELECT COUNT(*) FROM batches")
    if cursor.fetchone()[0] < 10:
        batches_to_seed = [(f"Batch {i+1} - 2026", faculty_user_id) for i in range(1, 10)]
        cursor.executemany("INSERT INTO batches (name, faculty_id) VALUES (?, ?)", batches_to_seed)

    # Seed 10 Enrollments
    cursor.execute("SELECT COUNT(*) FROM enrollments WHERE student_id = ?", (student_user_id,))
    if cursor.fetchone()[0] == 0:
        progress_values = [10.0, 25.0, 40.0, 55.0, 70.0, 80.0, 100.0, 15.0, 30.0, 45.0]
        enrollments = [(student_user_id, i+1, progress_values[i]) for i in range(10)]
        cursor.executemany("INSERT INTO enrollments (student_id, course_id, progress) VALUES (?, ?, ?)", enrollments)

    # Seed 10 Attendance records
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ?", (student_user_id,))
    if cursor.fetchone()[0] < 10:
        attendance_data = [(student_user_id, batch_id, f'2026-05-{i+11:02d}', 'present' if i%3!=0 else ('absent' if i%3==1 else 'late')) for i in range(10)]
        cursor.executemany("INSERT INTO attendance (student_id, batch_id, date, status) VALUES (?, ?, ?, ?)", attendance_data)

    # Seed 10 Assessments
    cursor.execute("SELECT COUNT(*) FROM assessments")
    if cursor.fetchone()[0] <= 10: # already had some
        assessments_to_add = [(i+1, f'Final Exam: {courses_to_seed[i-1][0]}', 100, f'2026-07-{i:02d}') for i in range(1, 11)]
        cursor.executemany("INSERT INTO assessments (course_id, title, total_marks, due_date) VALUES (?, ?, ?, ?)", assessments_to_add)

    # Seed 10 Assessment Submissions (Marks Entry)
    cursor.execute("SELECT COUNT(*) FROM assessment_submissions WHERE student_id = ?", (student_user_id,))
    if cursor.fetchone()[0] < 10:
        marks = [92, 88, 95, 84, 76, 89, 91, 78, 85, 93]
        submissions = [(i+1, student_user_id, marks[i], 'completed') for i in range(10)]
        cursor.executemany("INSERT INTO assessment_submissions (assessment_id, student_id, obtained_marks, status) VALUES (?, ?, ?, ?)", submissions)

    # Seed 10 Materials
    cursor.execute("SELECT COUNT(*) FROM materials")
    if cursor.fetchone()[0] == 0:
        materials = [(i%10 + 1, f"Lecture Notes - {courses_to_seed[i%10][0]}", "notes.pdf", "pdf") for i in range(10)]
        cursor.executemany("INSERT INTO materials (course_id, title, file_url, material_type) VALUES (?, ?, ?, ?)", materials)

    # Seed 10 Live Classes
    cursor.execute("SELECT COUNT(*) FROM live_classes")
    if cursor.fetchone()[0] == 0:
        live_classes = [(batch_id, f"Session {i+1}: Q&A", "https://zoom.us/demo", f"2026-06-{i+10:02d} 10:00:00", "scheduled") for i in range(10)]
        cursor.executemany("INSERT INTO live_classes (batch_id, title, meeting_link, schedule, status) VALUES (?, ?, ?, ?, ?)", live_classes)

    # Seed 10 Notifications
    cursor.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ?", (faculty_user_id,))
    if cursor.fetchone()[0] == 0:
        faculty_notifs = [(faculty_user_id, f"Faculty Alert {i+1}", f"Sample notification for faculty {i+1}") for i in range(10)]
        cursor.executemany("INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)", faculty_notifs)

    # Seed 10 Payments (Fees) for Parent view
    cursor.execute("SELECT COUNT(*) FROM payments WHERE student_id = ?", (student_user_id,))
    if cursor.fetchone()[0] < 10:
        p_data = [(student_user_id, 100.0 * (i+1), f"Semester Fee - Installment {i+1}", 'success' if i%4!=0 else 'pending', f'TXN-{uuid.uuid4().hex[:8].upper()}') for i in range(10)]
        cursor.executemany("INSERT INTO payments (student_id, amount, purpose, status, transaction_id) VALUES (?, ?, ?, ?, ?)", p_data)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("EduTech LMS Database fully initialized and seeded with Faculty/Parent demo data.")

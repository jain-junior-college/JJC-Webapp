import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from models import db, User, Student, Fee, Exam, Enquiry, Stream, AcademicClass, Subject, Teacher, Attendance, Resource, ClassStreamFee, ScheduledTest, TestMark, TimetableEntry
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
# Ensure upload folder exists
os.makedirs(os.path.join(app.root_path, 'static/uploads'), exist_ok=True)

# Cloudinary Configuration
cloudinary.config(
    cloud_name = "dcgwjfpr1",
    api_key = "221175245642669",
    api_secret = "g8x0B42ShixAAa-fgWiTJgEgQe4",
    secure = True
)

# Database Configuration
db_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Skip DB initialization during build phase on Render to prevent column mismatch crashes
IS_BUILD = os.environ.get('RENDER') and not os.environ.get('DATABASE_URL')

if not IS_BUILD:
    # ---------------------------------------------------------
    # DATABASE EMERGENCY MIGRATION (Runs before SQLAlchemy starts)
    # ---------------------------------------------------------
    import psycopg2
    def emergency_migration():
        db_url = os.environ.get('DATABASE_URL')
        if not db_url: return
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            # Add Columns if they are missing
            cur.execute("ALTER TABLE academic_class ADD COLUMN IF NOT EXISTS base_fees FLOAT DEFAULT 0.0;")
            cur.execute("ALTER TABLE student ADD COLUMN IF NOT EXISTS base_fees FLOAT DEFAULT 0.0;")
            cur.execute("ALTER TABLE student ADD COLUMN IF NOT EXISTS concession FLOAT DEFAULT 0.0;")
            cur.execute("ALTER TABLE student ADD COLUMN IF NOT EXISTS total_fees FLOAT DEFAULT 0.0;")
            
            # Create class_stream_fee table if missing
            cur.execute("""
                CREATE TABLE IF NOT EXISTS class_stream_fee (
                    id SERIAL PRIMARY KEY,
                    class_id INTEGER NOT NULL REFERENCES academic_class(id),
                    stream_id INTEGER NOT NULL REFERENCES stream(id),
                    base_fees FLOAT NOT NULL DEFAULT 0.0
                );
            """)
            
            # Create scheduled_test table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_test (
                    id SERIAL PRIMARY KEY,
                    class_id INTEGER NOT NULL REFERENCES academic_class(id),
                    stream_id INTEGER NOT NULL REFERENCES stream(id),
                    subject_id INTEGER NOT NULL REFERENCES subject(id),
                    exam_type VARCHAR(50) NOT NULL,
                    test_date DATE NOT NULL,
                    total_marks FLOAT DEFAULT 25.0,
                    passing_marks FLOAT DEFAULT 9.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # EMERGENCY PATCH: Add passing_marks to existing table if missing
            cur.execute("""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='scheduled_test' AND column_name='passing_marks') THEN
                        ALTER TABLE scheduled_test ADD COLUMN passing_marks FLOAT DEFAULT 9.0;
                    END IF;
                END $$;
            """)

            # Create test_mark table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS test_mark (
                    id SERIAL PRIMARY KEY,
                    test_id INTEGER NOT NULL REFERENCES scheduled_test(id) ON DELETE CASCADE,
                    student_id INTEGER NOT NULL REFERENCES student(id),
                    marks_obtained FLOAT NOT NULL
                );
            """)

            # Create timetable table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS timetable (
                    id SERIAL PRIMARY KEY,
                    class_id INTEGER NOT NULL REFERENCES academic_class(id),
                    stream_id INTEGER NOT NULL REFERENCES stream(id),
                    subject_id INTEGER NOT NULL REFERENCES subject(id),
                    teacher_id INTEGER NOT NULL REFERENCES teacher(id),
                    day VARCHAR(20) NOT NULL,
                    start_time VARCHAR(10) NOT NULL,
                    end_time VARCHAR(10) NOT NULL
                );
            """)
            
            conn.commit()
            cur.close()
            conn.close()
            print("Emergency Migration: Success")
        except Exception as e:
            print(f"Emergency Migration: Deferred or skipped ({e})")

    emergency_migration()
    # ---------------------------------------------------------
    db.init_app(app)
else:
    print("Build phase detected: Skipping DB initialization.")

# --- Custom Filters ---
@app.template_filter('format_time_12hr')
def format_time_12hr(time_str):
    if not time_str: return ""
    try:
        # Time strings are in HH:MM format from <input type="time">
        t = datetime.strptime(time_str, "%H:%M")
        return t.strftime("%I:%M %p").lstrip('0')
    except:
        return time_str


# Database Auto-Initialization
def auto_init_db():
    try:
        db.create_all()
        # Seed Break subject first
        if not Subject.query.filter_by(name='Break').first():
            db.session.add(Subject(name='Break'))
            db.session.commit()
            
        # Seed default data
        if not Stream.query.first():
            for s in ['Science', 'Commerce', 'Arts']:
                db.session.add(Stream(name=s))
        if not AcademicClass.query.first():
            for c in ['XI', 'XII']:
                db.session.add(AcademicClass(name=c))
        
        # Ensure admin exists
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin = User(
                username='admin', 
                password_hash=generate_password_hash('admin123'), 
                role='admin'
            )
            db.session.add(admin)
        db.session.commit()
        print("Database initialized successfully.")
    except Exception as e:
        db.session.rollback()
        print(f"Database init deferred or failed: {e}")

# Run initialization manually via /sync-database to avoid build-time crashes
# with app.app_context():
#     auto_init_db()

@app.route('/repair-database')
def repair_db():
    confirm = request.args.get('confirm')
    if confirm != 'true':
        return """
        <div style='font-family: sans-serif; padding: 2rem; border: 2px solid red; border-radius: 10px; max-width: 600px; margin: 5rem auto;'>
            <h1 style='color: red;'>⚠️ DANGER: Factory Reset</h1>
            <p>Visiting this page with confirmation will <b>ERASE ALL STUDENT DATA, FEES, AND TEACHERS</b> and reset the system.</p>
            <p>Only use this if the website is crashing and cannot be fixed otherwise.</p>
            <a href='/repair-database?confirm=true' style='background: red; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;'>I UNDERSTAND - WIPE AND REPAIR EVERYTHING</a>
            <br><br>
            <a href='/dashboard'>No, take me back to safety</a>
        </div>
        """
    try:
        # The Nuclear Option: Drop and Recreate
        db.drop_all()
        db.create_all()
        # ... [rest of the seeding logic] ...
        s1 = Stream(name='Science')
        s2 = Stream(name='Commerce')
        s3 = Stream(name='Arts')
        db.session.add_all([s1, s2, s3])
        db.session.commit()

        c1 = AcademicClass(name='XI')
        c2 = AcademicClass(name='XII')
        db.session.add_all([c1, c2])
        
        db.session.add(Subject(name='Physics', stream_id=s1.id))
        db.session.add(Subject(name='Chemistry', stream_id=s1.id))
        db.session.add(Subject(name='Accountancy', stream_id=s2.id))
        db.session.add(Subject(name='Economics', stream_id=s2.id))
        
        admin = User(
            username='admin', 
            password_hash=generate_password_hash('admin123'), 
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        return "Database Repaired! <a href='/login'>Go to Login</a>"
    except Exception as e:
        return f"Repair failed: {e}"

@app.route('/sync-database')
def sync_db():
    try:
        # 1. Create any missing tables (like student_subject or resource)
        db.create_all()
        
        # 2. Add missing columns safely using raw SQL
        # Using try-except for each to ignore if they already exist
        queries = [
            "ALTER TABLE subject ADD COLUMN IF NOT EXISTS is_compulsory BOOLEAN DEFAULT TRUE",
            "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS exit_time VARCHAR(20)",
            "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(255)",
            "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS academic_year VARCHAR(20)"
        ]
        
        for q in queries:
            try:
                db.session.execute(db.text(q))
            except:
                pass # Already exists
        
        db.session.commit()
        return """
        <div style='font-family: sans-serif; padding: 2rem; border: 2px solid green; border-radius: 10px; max-width: 600px; margin: 5rem auto; text-align: center;'>
            <h1 style='color: green;'>✅ Safe Sync Successful!</h1>
            <p>Your database has been upgraded with the latest features.</p>
            <p style='color: #166534; font-weight: bold;'>Status: ALL DATA PROTECTED & INTACT.</p>
            <a href='/dashboard' style='background: #4f46e5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;'>Go to Dashboard</a>
        </div>
        """
    except Exception as e:
        db.session.rollback()
        return f"<h1 style='color:red;'>Sync Failed</h1><p>{str(e)}</p>"

# Login required decorator
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/dashboard')
@login_required
def dashboard():
    total_students = Student.query.count()
    total_fees = db.session.query(db.func.sum(Fee.amount_paid)).scalar() or 0
    recent_students = Student.query.order_by(Student.admission_date.desc()).limit(5).all()
    return render_template('dashboard.html', 
                          total_students=total_students, 
                          total_fees=total_fees,
                          recent_students=recent_students)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Enquiry Route
@app.route('/enquire', methods=['POST'])
def submit_enquiry():
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    course = request.form.get('course')
    message = request.form.get('message')
    
    if name and phone:
        new_enquiry = Enquiry(
            name=name, email=email, phone=phone, course_interest=course, message=message
        )
        db.session.add(new_enquiry)
        db.session.commit()
        flash('Thank you for your enquiry! Our dedicated team will contact you shortly.', 'success')
    else:
        flash('Please provide at least your name and phone number.', 'error')
        
    return redirect(url_for('index', _anchor='contact'))

# Enrollment Routes
@app.route('/student/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_student(id):
    student = Student.query.get_or_404(id)
    if request.method == 'POST':
        student.name = request.form['name']
        student.contact = request.form['contact']
        student.parent_contact = request.form['parent_contact']
        student.email = request.form['email']
        student.address = request.form['address']
        student.class_id = request.form['class_id']
        student.stream_id = request.form['stream_id']
        
        # Handle Subjects
        selected_subject_ids = set(request.form.getlist('selected_subjects'))
        student.subjects = [] # Clear current
        for sid in selected_subject_ids:
            subj = Subject.query.get(sid)
            if subj:
                student.subjects.append(subj)

        # Files
        photo = request.files.get('photo')
        if photo and photo.filename != '':
            upload_result = cloudinary.uploader.upload(photo)
            student.photo_url = upload_result['secure_url']
            
        doc = request.files.get('document')
        if doc and doc.filename != '':
            upload_result = cloudinary.uploader.upload(doc)
            student.document_url = upload_result['secure_url']
            
        db.session.commit()
        flash('Student details updated!')
        return redirect(url_for('student_list'))
        
    streams = Stream.query.all()
    classes = AcademicClass.query.all()
    # Get IDs of current subjects for pre-checking
    current_subject_ids = [s.id for s in student.subjects]
    return render_template('students/edit.html', student=student, streams=streams, classes=classes, current_subject_ids=current_subject_ids)

@app.route('/student/delete/<int:id>', methods=['POST'])
@login_required
def delete_student(id):
    student = Student.query.get_or_404(id)
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted successfully.')
    return redirect(url_for('student_list'))

@app.route('/enroll', methods=['GET', 'POST'])
@login_required
def enroll():
    if request.method == 'POST':
        try:
            # Auto-generate Student ID if not provided
            stream_id = request.form.get('stream_id')
            class_id = request.form.get('class_id')
            
            assigned_id = request.form.get('student_id')
            if not assigned_id or assigned_id == "":
                class_obj = AcademicClass.query.get(class_id)
                class_name = class_obj.name if class_obj else "XX"
                year = datetime.now(timezone.utc).year
                prefix = f"JJC{class_name}{year}"
                count = Student.query.filter(Student.student_id.like(f"{prefix}%")).count()
                assigned_id = f"{prefix}{str(count + 1).zfill(3)}"

            new_student = Student(
                student_id=assigned_id,
                name=request.form.get('name', 'Unknown'),
                dob=request.form.get('dob'),
                gender=request.form.get('gender', 'Male'),
                stream_id=stream_id,
                class_id=class_id,
                base_fees=float(request.form.get('base_fees', 0) or 0),
                concession=float(request.form.get('concession', 0) or 0),
                total_fees=float(request.form.get('total_fees', 0) or 0),
                contact=request.form.get('contact', ''),
                email=request.form.get('email', ''),
                guardian_name=request.form.get('guardian_name', ''),
                address=request.form.get('address', '')
            )
            
            # Handle File Uploads via Cloudinary (Permanent Storage)
            photo = request.files.get('photo')
            if photo and photo.filename:
                upload_result = cloudinary.uploader.upload(photo, folder="student_photos")
                new_student.photo_url = upload_result['secure_url']
                
            doc = request.files.get('document')
            if doc and doc.filename:
                upload_result = cloudinary.uploader.upload(doc, folder="student_docs", resource_type="auto")
                new_student.document_url = upload_result['secure_url']

            # Handle Subject Selection
            # Use set() to remove duplicates (prevents UniqueViolation errors)
            selected_subject_ids = set(request.form.getlist('selected_subjects'))
            for sid in selected_subject_ids:
                subj = Subject.query.get(sid)
                if subj:
                    new_student.subjects.append(subj)

            db.session.add(new_student)
            db.session.commit()
            flash('Student enrolled successfully!', 'success')
            return redirect(url_for('student_list'))
        except Exception as e:
            db.session.rollback()
            # If development/debugging:
            return f"<div style='padding:2rem; border:2px solid red; font-family:sans-serif;'><h1>🚨 Enrollment System Diagnostic</h1><p>The system encountered this error:</p><code style='background:#fee2e2; padding:10px; display:block;'>{str(e)}</code><br><a href='/enroll'>Try Again</a></div>"
    
    try:
        streams = Stream.query.all()
        classes = AcademicClass.query.all()
    except Exception:
        streams = []
        classes = []
    return render_template('students/enroll.html', streams=streams, classes=classes)

@app.route('/api/next-student-id')
@login_required
def get_next_student_id():
    class_id = request.args.get('class_id')
    class_obj = AcademicClass.query.get(class_id)
    class_name = class_obj.name if class_obj else "XX"
    year = datetime.utcnow().year
    prefix = f"JJC{class_name}{year}"
    count = Student.query.filter(Student.student_id.like(f"{prefix}%")).count()
    return {"next_id": f"{prefix}{str(count + 1).zfill(3)}"}

@app.route('/masters', methods=['GET', 'POST'])
@login_required
def masters():
    if request.method == 'POST':
        master_type = request.form.get('type')
        if master_type == 'fee_matrix':
            cid = request.form.get('class_id')
            sid = request.form.get('stream_id')
            fees = float(request.form.get('base_fees', 0.0))
            # Overwrite if exists, otherwise create
            existing = ClassStreamFee.query.filter_by(class_id=cid, stream_id=sid).first()
            if existing:
                existing.base_fees = fees
            else:
                mapping = ClassStreamFee(class_id=cid, stream_id=sid, base_fees=fees)
                db.session.add(mapping)
            db.session.commit()
            flash("Fee Matrix updated successfully!")
            return redirect(url_for('masters'))
            
        name = request.form.get('name')
        if master_type == 'stream':
            db.session.add(Stream(name=name))
        elif master_type == 'class':
            base_fees = float(request.form.get('base_fees', 0) or 0)
            db.session.add(AcademicClass(name=name, base_fees=base_fees))
        db.session.commit()
        flash(f"{master_type.title()} added successfully!")
        return redirect(url_for('masters'))
        
    try:
        streams = Stream.query.all()
        classes = AcademicClass.query.all()
        fee_matrix = ClassStreamFee.query.all()
    except Exception:
        streams = Stream.query.all()
        classes = AcademicClass.query.all()
        fee_matrix = []
        
    return render_template('masters.html', streams=streams, classes=classes, fee_matrix=fee_matrix)

@app.route('/masters/fee-matrix/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_fee_matrix(id):
    fee = ClassStreamFee.query.get_or_404(id)
    if request.method == 'POST':
        fee.base_fees = float(request.form.get('base_fees', 0.0))
        db.session.commit()
        flash("Fees updated successfully!")
        return redirect(url_for('masters'))
    return render_template('edit_fee_matrix.html', fee=fee)

@app.route('/masters/class/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_master_class(id):
    obj = AcademicClass.query.get_or_404(id)
    if request.method == 'POST':
        obj.name = request.form['name']
        obj.base_fees = float(request.form.get('base_fees', 0) or 0)
        db.session.commit()
        flash('Class updated successfully!')
        return redirect(url_for('masters'))
    return render_template('edit_master_class.html', obj=obj)

@app.route('/api/class-fees/<int:class_id>')
def get_class_fees(class_id):
    stream_id = request.args.get('stream_id')
    
    # Try matrix first
    if stream_id:
        matrix = ClassStreamFee.query.filter_by(class_id=class_id, stream_id=stream_id).first()
        if matrix:
            return jsonify({"base_fees": matrix.base_fees})

    # Fallback to class default
    obj = AcademicClass.query.get(class_id)
    return jsonify({"base_fees": obj.base_fees if obj else 0.0})

@app.route('/masters/delete/<string:mtype>/<int:mid>', methods=['POST'])
@login_required
def delete_master(mtype, mid):
    if mtype == 'stream':
        obj = Stream.query.get(mid)
    else:
        obj = AcademicClass.query.get(mid)
    if obj:
        db.session.delete(obj)
        db.session.commit()
        flash(f"{mtype.title()} deleted successfully!")
    return redirect(url_for('masters'))

# Teacher & Subject Management
@app.route('/teachers', methods=['GET', 'POST'])
@login_required
def manage_teachers():
    if request.method == 'POST':
        teacher = Teacher(
            name=request.form.get('name', ''),
            email=request.form.get('email', ''),
            phone=request.form.get('phone', ''),
            qualification=request.form.get('qualification', ''),
            dob=request.form.get('dob', ''),
            join_date=request.form.get('join_date', '')
        )
        # Capture selected subjects
        subject_ids = request.form.getlist('subjects')
        for sid in subject_ids:
            subj = Subject.query.get(sid)
            if subj:
                teacher.subjects.append(subj)
                
        db.session.add(teacher)
        db.session.commit()
        flash('Teacher added successfully with assigned subjects!')
    teachers = Teacher.query.all()
    subjects = Subject.query.all()
    return render_template('teachers/manage.html', teachers=teachers, subjects=subjects)

@app.route('/teachers/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_teacher(id):
    teacher = Teacher.query.get_or_404(id)
    if request.method == 'POST':
        teacher.name = request.form.get('name', '')
        teacher.email = request.form.get('email', '')
        teacher.phone = request.form.get('phone', '')
        teacher.qualification = request.form.get('qualification', '')
        teacher.dob = request.form.get('dob', '')
        teacher.join_date = request.form.get('join_date', '')
        
        # Update subjects
        selected_subjects = request.form.getlist('subjects')
        teacher.subjects = [] # Clear and refill
        for sid in selected_subjects:
            subj = Subject.query.get(sid)
            if subj:
                teacher.subjects.append(subj)
        
        db.session.commit()
        flash('Teacher updated successfully!')
        return redirect(url_for('manage_teachers'))
        
    subjects = Subject.query.all()
    teacher_subject_ids = [s.id for s in teacher.subjects]
    return render_template('teachers/edit.html', teacher=teacher, subjects=subjects, teacher_subject_ids=teacher_subject_ids)

@app.route('/teachers/delete/<int:id>', methods=['GET', 'POST'])
@login_required
def delete_teacher(id):
    teacher = Teacher.query.get_or_404(id)
    db.session.delete(teacher)
    db.session.commit()
    flash('Teacher record deleted successfully.')
    return redirect(url_for('manage_teachers'))

@app.route('/subjects', methods=['GET', 'POST'])
@login_required
def manage_subjects():
    if request.method == 'POST':
        is_compulsory = 'is_compulsory' in request.form
        new_subject = Subject(
            name=request.form.get('name'), 
            stream_id=request.form.get('stream_id'),
            is_compulsory=is_compulsory
        )
        db.session.add(new_subject)
        db.session.commit()
        flash('Subject added successfully!')
    streams = Stream.query.all()
    subjects = Subject.query.all()
    return render_template('subjects/manage.html', streams=streams, subjects=subjects)

@app.route('/subjects/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_subject(id):
    subject = Subject.query.get_or_404(id)
    if request.method == 'POST':
        subject.name = request.form.get('name')
        subject.stream_id = request.form.get('stream_id')
        subject.is_compulsory = 'is_compulsory' in request.form
        db.session.commit()
        flash('Subject updated!')
        return redirect(url_for('manage_subjects'))
    streams = Stream.query.all()
    return render_template('subjects/edit_subject.html', subject=subject, streams=streams)

@app.route('/subjects/delete/<int:id>')
@login_required
def delete_subject(id):
    subject = Subject.query.get_or_404(id)
    db.session.delete(subject)
    db.session.commit()
    flash('Subject deleted successfully.')
    return redirect(url_for('manage_subjects'))

# Attendance Routes
@app.route('/attendance/mark', methods=['GET', 'POST'])
@login_required
def mark_attendance():
    selected_class = request.args.get('class_id')
    selected_stream = request.args.get('stream_id')
    date_str = request.args.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
    attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    if request.method == 'POST':
        for student_id, status in request.form.items():
            if student_id.startswith('status_'):
                real_student_id = student_id.replace('status_', '')
                # Check if attendance already exists for this day
                existing = Attendance.query.filter_by(student_id=real_student_id, date=attendance_date).first()
                if existing:
                    existing.status = status
                    existing.exit_time = request.form.get(f'exit_time_{real_student_id}')
                    existing.exit_reason = request.form.get(f'exit_reason_{real_student_id}')
                else:
                    new_att = Attendance(
                        student_id=real_student_id, 
                        date=attendance_date, 
                        status=status,
                        exit_time=request.form.get(f'exit_time_{real_student_id}'),
                        exit_reason=request.form.get(f'exit_reason_{real_student_id}')
                    )
                    db.session.add(new_att)
        db.session.commit()
        flash('Attendance updated successfully!')

    students = []
    if selected_class and selected_stream:
        students = Student.query.filter_by(class_id=selected_class, stream_id=selected_stream).all()
    
    classes = AcademicClass.query.all()
    streams = Stream.query.all()
    return render_template('attendance/mark.html', 
                         students=students, 
                         classes=classes, 
                         streams=streams,
                         selected_class=int(selected_class) if selected_class else None,
                         selected_stream=int(selected_stream) if selected_stream else None,
                         date_str=date_str)

@app.route('/attendance/report')
@login_required
def attendance_report():
    report_type = request.args.get('type', 'daily')
    date_str = request.args.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
    student_id = request.args.get('student_id')
    class_id = request.args.get('class_id')
    
    attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    report_data = []
    stats = {}
    
    if report_type == 'daily':
        report_data = Attendance.query.filter_by(date=attendance_date).all()
        # Calculate Class summary
        if class_id:
            total_students = Student.query.filter_by(class_id=class_id).count()
            present_count = Attendance.query.filter_by(date=attendance_date, status='Present').join(Student).filter(Student.class_id == class_id).count()
            stats['class_percentage'] = (present_count / total_students * 100) if total_students > 0 else 0
            stats['present'] = present_count
            stats['absent'] = total_students - present_count
    
    elif report_type == 'monthly' and student_id:
        # Calculate monthly percentage
        month = attendance_date.month
        year = attendance_date.year
        all_month_attendance = Attendance.query.filter(
            db.extract('month', Attendance.date) == month,
            db.extract('year', Attendance.date) == year,
            Attendance.student_id == student_id
        ).all()
        
        days_present = sum(1 for a in all_month_attendance if a.status == 'Present')
        total_days = len(all_month_attendance)
        stats['monthly_percentage'] = (days_present / total_days * 100) if total_days > 0 else 0
        report_data = all_month_attendance

    students = Student.query.all()
    classes = AcademicClass.query.all()
    return render_template('attendance/report.html', 
                          report_data=report_data, 
                          report_type=report_type,
                          students=students,
                          classes=classes,
                          stats=stats,
                          date_str=date_str)

@app.route('/attendance/early-exit/<int:id>', methods=['POST'])
@login_required
def early_exit(id):
    att = Attendance.query.get_or_404(id)
    att.exit_time = request.form.get('exit_time')
    att.exit_reason = request.form.get('exit_reason')
    db.session.commit()
    flash('Early exit recorded for student.')
    return redirect(request.referrer or url_for('mark_attendance'))

@app.route('/students')
@login_required
def student_list():
    students = Student.query.all()
    return render_template('students/list.html', students=students)

# Digital Library Routes
@app.route('/library')
@login_required
def library_list():
    resources = Resource.query.order_by(Resource.created_at.desc()).all()
    return render_template('library/list.html', resources=resources)

@app.route('/library/upload', methods=['GET', 'POST'])
@login_required
def upload_resource():
    if request.method == 'POST':
        title = request.form.get('title')
        res_file = request.files.get('file')
        
        if res_file and res_file.filename:
            # Upload to Cloudinary (Auto resource type for PDFs/Videos)
            upload_result = cloudinary.uploader.upload(res_file, folder="college_library", resource_type="auto")
            
            new_res = Resource(
                title=title,
                description=request.form.get('description'),
                file_url=upload_result['secure_url'],
                resource_type=request.form.get('resource_type'),
                class_id=request.form.get('class_id'),
                subject_id=request.form.get('subject_id'),
                teacher_id=request.form.get('teacher_id')
            )
            db.session.add(new_res)
            db.session.commit()
            flash('Educational resource added successfully to the digital library!')
            return redirect(url_for('library_list'))
            
    classes = AcademicClass.query.all()
    subjects = Subject.query.all()
    teachers = Teacher.query.all()
    return render_template('library/upload.html', classes=classes, subjects=subjects, teachers=teachers)

@app.route('/library/delete/<int:id>')
@login_required
def delete_resource(id):
    res = Resource.query.get_or_404(id)
    db.session.delete(res)
    db.session.commit()
    flash('Resource removed from library.')
    return redirect(url_for('library_list'))

@app.route('/api/subjects/<int:stream_id>')
def get_subjects_by_stream(stream_id):
    subjects = Subject.query.filter_by(stream_id=stream_id).all()
    return jsonify([{
        'id': s.id,
        'name': s.name,
        'is_compulsory': s.is_compulsory
    } for s in subjects])

# Teacher Routes
@app.route('/fees', methods=['GET', 'POST'])
@login_required
def collect_fees():
    if request.method == 'POST':
        fee = Fee(
            student_id=request.form['student_id'],
            amount_paid=float(request.form['amount']),
            payment_method=request.form['method'],
            remarks=request.form['remarks']
        )
        db.session.add(fee)
        db.session.commit()
        flash('Fee collected successfully!')
        return redirect(url_for('fee_receipt', id=fee.id))
    
    students = Student.query.all()
    recent_fees = Fee.query.order_by(Fee.payment_date.desc()).limit(10).all()
    return render_template('fees/collect.html', students=students, recent_fees=recent_fees)

@app.route('/fees/receipt/<int:id>')
@login_required
def fee_receipt(id):
    fee = Fee.query.get_or_404(id)
    student = Student.query.get(fee.student_id)
    return render_template('fees/receipt.html', fee=fee, student=student)

# Academic Routes
@app.route('/academics', methods=['GET', 'POST'])
@login_required
def academic_entry():
    if request.method == 'POST':
        exam = Exam(
            student_id=request.form['student_id'],
            subject=request.form['subject'],
            marks_obtained=float(request.form['marks']),
            total_marks=float(request.form['total_marks']),
            exam_type=request.form['exam_type']
        )
        db.session.add(exam)
        db.session.commit()
        flash('Marks entered successfully!')
    students = Student.query.all()
    return render_template('academics/enter_marks.html', students=students)

@app.route('/report-card/<int:student_id>')
@login_required
def report_card(student_id):
    student = Student.query.get_or_404(student_id)
    # Filter Prelims if class is XI
    exams = Exam.query.filter_by(student_id=student_id).all()
    # Logic to filter based on UI requirement or just display
    
    # Also fetch from new TestMark
    test_marks = TestMark.query.filter_by(student_id=student_id).all()
    
    return render_template('academics/report_card.html', student=student, exams=exams, test_marks=test_marks)

# --- Test Scheduler Module ---

@app.route('/academics/tests')
@login_required
def test_list():
    tests = ScheduledTest.query.order_by(ScheduledTest.test_date.desc()).all()
    return render_template('academics/test_list.html', tests=tests)

@app.route('/academics/tests/schedule', methods=['GET', 'POST'])
@login_required
def schedule_test():
    if request.method == 'POST':
        test = ScheduledTest(
            class_id=request.form['class_id'],
            stream_id=request.form['stream_id'],
            subject_id=request.form['subject_id'],
            exam_type=request.form['exam_type'],
            test_date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            total_marks=float(request.form['total_marks']),
            passing_marks=float(request.form['passing_marks'])
        )
        db.session.add(test)
        db.session.commit()
        flash('Test scheduled successfully!')
        return redirect(url_for('test_list'))
    
    classes = AcademicClass.query.all()
    streams = Stream.query.all()
    subjects = Subject.query.all()
    return render_template('academics/schedule_test.html', classes=classes, streams=streams, subjects=subjects)

@app.route('/academics/tests/record/<int:test_id>', methods=['GET', 'POST'])
@login_required
def record_test_marks(test_id):
    test = ScheduledTest.query.get_or_404(test_id)
    students = Student.query.filter_by(class_id=test.class_id, stream_id=test.stream_id).all()
    
    if request.method == 'POST':
        # Bulk mark entry
        for student in students:
            marks = request.form.get(f'marks_{student.id}')
            if marks:
                # Update existing or create new
                existing = TestMark.query.filter_by(test_id=test_id, student_id=student.id).first()
                if existing:
                    existing.marks_obtained = float(marks)
                else:
                    new_mark = TestMark(test_id=test_id, student_id=student.id, marks_obtained=float(marks))
                    db.session.add(new_mark)
        db.session.commit()
        flash('Marks recorded for the entire class!')
        return redirect(url_for('test_list'))
    
    # Pre-fetch existing marks for input population
    existing_marks = {m.student_id: m.marks_obtained for m in test.marks}
    return render_template('academics/record_marks.html', test=test, students=students, existing_marks=existing_marks)

@app.route('/academics/tests/analysis/<int:test_id>')
@login_required
def test_analysis(test_id):
    test = ScheduledTest.query.get_or_404(test_id)
    marks = test.marks
    
    if not marks:
        flash("No marks recorded for this test yet! Please record marks first.")
        return redirect(url_for('test_list'))
        
    stats = {}
    stats['total_appeared'] = len(marks)
    stats['passed'] = sum(1 for m in marks if m.marks_obtained >= test.passing_marks)
    stats['failed'] = stats['total_appeared'] - stats['passed']
    stats['pass_percentage'] = (stats['passed'] / stats['total_appeared'] * 100) if stats['total_appeared'] > 0 else 0
    
    obtained_marks = [m.marks_obtained for m in marks]
    stats['max_marks'] = max(obtained_marks) if obtained_marks else 0
    stats['min_marks'] = min(obtained_marks) if obtained_marks else 0
    stats['avg_marks'] = (sum(obtained_marks) / len(obtained_marks)) if obtained_marks else 0
    
    # Sort students by marks desc
    sorted_marks = sorted(marks, key=lambda x: x.marks_obtained, reverse=True)
    
    return render_template('academics/test_analysis.html', test=test, stats=stats, sorted_marks=sorted_marks)

# --- Timetable Module ---

@app.route('/timetable')
@login_required
def timetable_view():
    classes = AcademicClass.query.all()
    streams = Stream.query.all()
    class_id = request.args.get('class_id')
    stream_id = request.args.get('stream_id')
    
    entries = []
    if class_id and stream_id:
        # Sort by start_time string
        entries = TimetableEntry.query.filter_by(class_id=class_id, stream_id=stream_id).order_by(TimetableEntry.start_time).all()
        
    return render_template('timetable/view.html', entries=entries, classes=classes, streams=streams, selected_class=int(class_id) if class_id else None, selected_stream=int(stream_id) if stream_id else None)

@app.route('/timetable/manage', methods=['GET', 'POST'])
@login_required
def timetable_manage():
    if request.method == 'POST':
        days_to_apply = [request.form['day']]
        if 'apply_to_all' in request.form:
            days_to_apply = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        # Handle empty teacher_id for Breaks
        raw_teacher_id = request.form.get('teacher_id')
        teacher_id = int(raw_teacher_id) if raw_teacher_id and raw_teacher_id.strip() else None
            
        for day in days_to_apply:
            entry = TimetableEntry(
                class_id=request.form['class_id'],
                stream_id=request.form['stream_id'],
                day=day,
                start_time=request.form['start_time'],
                end_time=request.form['end_time'],
                subject_id=request.form['subject_id'],
                teacher_id=teacher_id
            )
            db.session.add(entry)
        db.session.commit()
        flash('Timetable updated!')
        return redirect(url_for('timetable_manage'))
        
    # Filtering logic for active slots
    f_class = request.args.get('f_class')
    f_subject = request.args.get('f_subject')
    f_day = request.args.get('f_day')
    
    query = TimetableEntry.query
    if f_class:
        query = query.filter_by(class_id=f_class)
    if f_subject:
        query = query.filter_by(subject_id=f_subject)
    if f_day:
        query = query.filter_by(day=f_day)
        
    from sqlalchemy import case
    day_order = case(
        {
            'Monday': 1,
            'Tuesday': 2,
            'Wednesday': 3,
            'Thursday': 4,
            'Friday': 5,
            'Saturday': 6
        },
        value=TimetableEntry.day
    )
    
    entries = query.order_by(day_order, TimetableEntry.start_time).all()
    
    classes = AcademicClass.query.all()
    streams = Stream.query.all()
    
    # Self-healing: Ensure 'Break' subject always exists
    if not Subject.query.filter_by(name='Break').first():
        db.session.add(Subject(name='Break'))
        db.session.commit()
        
    subjects = Subject.query.all()
    teachers = Teacher.query.all()
    
    return render_template('timetable/manage.html', entries=entries, classes=classes, streams=streams, subjects=subjects, teachers=teachers, 
                           f_class=int(f_class) if f_class else None, f_subject=int(f_subject) if f_subject else None, f_day=f_day)

@app.route('/timetable/delete/<int:id>')
@login_required
def delete_timetable_entry(id):
    entry = TimetableEntry.query.get_or_404(id)
    db.session.delete(entry)
    db.session.commit()
    flash('Slot removed!')
    return redirect(url_for('timetable_manage'))

@app.route('/timetable/export/csv')
@login_required
def timetable_export_csv():
    class_id = request.args.get('class_id')
    stream_id = request.args.get('stream_id')
    
    if not class_id or not stream_id:
        flash("Please filter by Class and Stream first to export!")
        return redirect(url_for('timetable_view'))
        
    entries = TimetableEntry.query.filter_by(class_id=class_id, stream_id=stream_id).order_by(TimetableEntry.day, TimetableEntry.start_time).all()
    
    import io, csv
    from flask import Response
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Day', 'Time', 'Subject', 'Teacher', 'Class'])
    
    for e in entries:
        t_range = f"{format_time_12hr(e.start_time)} - {format_time_12hr(e.end_time)}"
        writer.writerow([e.day, t_range, e.subject.name, e.teacher.name, e.academic_class.name])
        
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers.set("Content-Disposition", "attachment", filename=f"timetable_export.csv")
    return response

@app.route('/timetable/delete-all')
@login_required
def timetable_delete_all():
    class_id = request.args.get('class_id')
    stream_id = request.args.get('stream_id')
    
    if not class_id or not stream_id:
        flash("Invalid request.")
        return redirect(url_for('timetable_view'))
        
    TimetableEntry.query.filter_by(class_id=class_id, stream_id=stream_id).delete()
    db.session.commit()
    
    flash("Schedule for the selected class has been cleared!")
    return redirect(url_for('timetable_view'))

@app.route('/timetable/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_timetable_entry(id):
    entry = TimetableEntry.query.get_or_404(id)
    if request.method == 'POST':
        entry.class_id = request.form['class_id']
        entry.stream_id = request.form['stream_id']
        entry.day = request.form['day']
        entry.start_time = request.form['start_time']
        entry.end_time = request.form['end_time']
        entry.subject_id = request.form['subject_id']
        # Handle empty teacher_id for Breaks
        raw_teacher_id = request.form.get('teacher_id')
        entry.teacher_id = int(raw_teacher_id) if raw_teacher_id and raw_teacher_id.strip() else None
        
        db.session.commit()
        flash('Timetable slot updated!')
        return redirect(url_for('timetable_manage'))
        
    classes = AcademicClass.query.all()
    streams = Stream.query.all()
    subjects = Subject.query.all()
    teachers = Teacher.query.all()
    return render_template('timetable/edit.html', entry=entry, classes=classes, streams=streams, subjects=subjects, teachers=teachers)

@app.route('/api/get-subject-teacher/<int:subject_id>')
@login_required
def get_subject_teacher(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    # Get the first teacher associated with this subject
    teacher = subject.teachers[0] if subject.teachers else None
    if teacher:
        return jsonify({'id': teacher.id, 'name': teacher.name})
    return jsonify({'id': None, 'name': 'Not Assigned'})

if __name__ == '__main__':
    # Running on 0.0.0.0 for LAN deployment
    app.run(host='0.0.0.0', port=5000, debug=True)

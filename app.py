import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from models import db, User, Student, Fee, Exam, Enquiry, Stream, AcademicClass, Subject, Teacher, Attendance, Resource
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
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

db.init_app(app)

# Database Auto-Initialization
def auto_init_db():
    try:
        db.create_all()
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

# Run initialization once on startup
with app.app_context():
    auto_init_db()

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
@app.route('/enroll', methods=['GET', 'POST'])
@login_required
def enroll():
    if request.method == 'POST':
        # Auto-generate Student ID if not provided
        stream_id = request.form.get('stream_id')
        class_id = request.form.get('class_id')
        
        assigned_id = request.form.get('student_id')
        if not assigned_id:
            class_obj = AcademicClass.query.get(class_id)
            class_name = class_obj.name if class_obj else "XX"
            year = datetime.utcnow().year
            # Prefix search for count
            prefix = f"JJC{class_name}-{year}-"
            count = Student.query.filter(Student.student_id.like(f"{prefix}%")).count()
            assigned_id = f"{prefix}{str(count + 1).zfill(3)}"

        new_student = Student(
            student_id=assigned_id,
            name=request.form['name'],
            dob=request.form['dob'],
            gender=request.form['gender'],
            stream_id=stream_id,
            class_id=class_id,
            contact=request.form['contact'],
            email=request.form['email'],
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
        selected_subject_ids = request.form.getlist('selected_subjects')
        for sid in selected_subject_ids:
            subj = Subject.query.get(sid)
            if subj:
                new_student.subjects.append(subj)

        db.session.add(new_student)
        db.session.commit()
        flash('Student enrolled successfully!')
        return redirect(url_for('student_list'))
    
    streams = Stream.query.all()
    classes = AcademicClass.query.all()
    return render_template('students/enroll.html', streams=streams, classes=classes)

@app.route('/api/next-student-id')
@login_required
def get_next_student_id():
    class_id = request.args.get('class_id')
    class_obj = AcademicClass.query.get(class_id)
    class_name = class_obj.name if class_obj else "XX"
    year = datetime.utcnow().year
    prefix = f"JJC{class_name}-{year}-"
    count = Student.query.filter(Student.student_id.like(f"{prefix}%")).count()
    return {"next_id": f"{prefix}{str(count + 1).zfill(3)}"}

@app.route('/masters', methods=['GET', 'POST'])
@login_required
def masters():
    if request.method == 'POST':
        master_type = request.form.get('type')
        name = request.form.get('name')
        if master_type == 'stream':
            db.session.add(Stream(name=name))
        elif master_type == 'class':
            db.session.add(AcademicClass(name=name))
        db.session.commit()
        flash(f"{master_type.title()} added successfully!")
        return redirect(url_for('masters'))
        
    streams = Stream.query.all()
    classes = AcademicClass.query.all()
    return render_template('masters.html', streams=streams, classes=classes)

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
    exams = Exam.query.filter_by(student_id=student_id).all()
    return render_template('academics/report_card.html', student=student, exams=exams)

if __name__ == '__main__':
    # Running on 0.0.0.0 for LAN deployment
    app.run(host='0.0.0.0', port=5000, debug=True)

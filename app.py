import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from models import db, User, Student, Fee, Exam, Enquiry
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Database Configuration
# Use DATABASE_URL from environment (Postgres), fallback to SQLite for local development
db_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

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
        new_student = Student(
            student_id=request.form['student_id'],
            name=request.form['name'],
            dob=request.form['dob'],
            gender=request.form['gender'],
            student_class="",
            stream_id=request.form.get('stream_id'),
            class_id=request.form.get('class_id'),
            contact=request.form['contact'],
            email=request.form['email']
        )
        db.session.add(new_student)
        db.session.commit()
        flash('Student enrolled successfully!')
        return redirect(url_for('student_list'))
    
    streams = Stream.query.all()
    classes = AcademicClass.query.all()
    return render_template('students/enroll.html', streams=streams, classes=classes)

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

@app.route('/students')
@login_required
def student_list():
    students = Student.query.all()
    return render_template('students/list.html', students=students)

# Fee Routes
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
    students = Student.query.all()
    return render_template('fees/collect.html', students=students)

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

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone

db = SQLAlchemy()

# 1. Base Users
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='staff') # admin or staff

# 2. Junction Tables
teacher_subject = db.Table('teacher_subject',
    db.Column('teacher_id', db.Integer, db.ForeignKey('teacher.id'), primary_key=True),
    db.Column('subject_id', db.Integer, db.ForeignKey('subject.id'), primary_key=True)
)

student_subject = db.Table('student_subject',
    db.Column('student_id', db.Integer, db.ForeignKey('student.id'), primary_key=True),
    db.Column('subject_id', db.Integer, db.ForeignKey('subject.id'), primary_key=True)
)

# 3. Master Tables
class Stream(db.Model):
    __tablename__ = 'stream'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    students = db.relationship('Student', backref='stream', lazy=True)
    subjects = db.relationship('Subject', backref='stream', lazy=True)

class AcademicClass(db.Model):
    __tablename__ = 'academic_class'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    base_fees = db.Column(db.Float, default=0.0) # Fallback fee
    students = db.relationship('Student', backref='academic_class', lazy=True)

class ClassStreamFee(db.Model):
    __tablename__ = 'class_stream_fee'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('academic_class.id'), nullable=False)
    stream_id = db.Column(db.Integer, db.ForeignKey('stream.id'), nullable=False)
    base_fees = db.Column(db.Float, nullable=False, default=0.0)
    
    class_obj = db.relationship('AcademicClass', backref='stream_fees')
    stream_obj = db.relationship('Stream', backref='class_fees')

class Subject(db.Model):
    __tablename__ = 'subject'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    stream_id = db.Column(db.Integer, db.ForeignKey('stream.id'))
    is_compulsory = db.Column(db.Boolean, default=True)

class Teacher(db.Model):
    __tablename__ = 'teacher'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    qualification = db.Column(db.String(100))
    dob = db.Column(db.String(20))
    join_date = db.Column(db.String(20))
    subjects = db.relationship('Subject', secondary=teacher_subject, backref='teachers')

# 4. Core Records
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    dob = db.Column(db.String(20))
    gender = db.Column(db.String(10))
    student_class = db.Column(db.String(50)) 
    stream_id = db.Column(db.Integer, db.ForeignKey('stream.id'))
    class_id = db.Column(db.Integer, db.ForeignKey('academic_class.id'))
    base_fees = db.Column(db.Float, default=0.0)
    concession = db.Column(db.Float, default=0.0)
    total_fees = db.Column(db.Float, default=0.0)
    contact = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    guardian_name = db.Column(db.String(100)) # Deprecated, keep for old data
    caste = db.Column(db.String(50))
    mothers_name = db.Column(db.String(100))
    age_at_enrollment = db.Column(db.String(50))
    installments_allowed = db.Column(db.Integer, default=1)
    photo_url = db.Column(db.String(255)) # Path to student photograph
    document_url = db.Column(db.String(255)) # Path to uploaded PDF document
    admission_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    fees = db.relationship('Fee', backref='student', lazy=True)
    exams = db.relationship('Exam', backref='student', lazy=True)
    attendance = db.relationship('Attendance', backref='student', lazy=True)
    subjects = db.relationship('Subject', secondary=student_subject, backref='students')

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(10), nullable=False) # Present, Absent, Late
    exit_time = db.Column(db.String(20)) # Records if student left early
    exit_reason = db.Column(db.String(255))
    academic_year = db.Column(db.String(20))

class Resource(db.Model):
    __tablename__ = 'resource'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    file_url = db.Column(db.String(255), nullable=False)
    resource_type = db.Column(db.String(50)) # PDF, Video, Animation
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'))
    class_id = db.Column(db.Integer, db.ForeignKey('academic_class.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships for templates
    teacher = db.relationship('Teacher', backref='resources')
    subject = db.relationship('Subject', backref='resources')
    academic_class = db.relationship('AcademicClass', backref='resources')
    
    # Permissions
    is_public = db.Column(db.Boolean, default=False)

class Fee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50))
    remarks = db.Column(db.String(200))

class ScheduledTest(db.Model):
    __tablename__ = 'scheduled_test'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('academic_class.id'), nullable=False)
    stream_id = db.Column(db.Integer, db.ForeignKey('stream.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    exam_type = db.Column(db.String(50), nullable=False) # Unit Test, Prelim 1, etc.
    test_date = db.Column(db.Date, nullable=False)
    total_marks = db.Column(db.Float, default=25.0)
    passing_marks = db.Column(db.Float, default=9.0)
    duration = db.Column(db.String(50))
    start_time = db.Column(db.String(20))
    end_time = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    academic_class = db.relationship('AcademicClass', backref='tests')
    stream = db.relationship('Stream', backref='tests')
    subject_obj = db.relationship('Subject', backref='tests')
    marks = db.relationship('TestMark', backref='test', cascade="all, delete-orphan")
    supervisions = db.relationship('TestSupervision', backref='test', cascade="all, delete-orphan", order_by="TestSupervision.start_time")

class TestSupervision(db.Model):
    __tablename__ = 'test_supervision'
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('scheduled_test.id'), nullable=False)
    supervisor_name = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.String(20))
    end_time = db.Column(db.String(20))

class TestMark(db.Model):
    __tablename__ = 'test_mark'
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('scheduled_test.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    marks_obtained = db.Column(db.Float, nullable=False)
    
    student = db.relationship('Student', backref='test_marks')

class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    marks_obtained = db.Column(db.Float, nullable=False)
    total_marks = db.Column(db.Float, default=100.0)
    exam_type = db.Column(db.String(50))
    exam_date = db.Column(db.DateTime, default=datetime.utcnow)

class TimetableEntry(db.Model):
    __tablename__ = 'timetable'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('academic_class.id'), nullable=False)
    stream_id = db.Column(db.Integer, db.ForeignKey('stream.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    day = db.Column(db.String(20), nullable=False) # Monday, Tuesday...
    start_time = db.Column(db.String(10), nullable=False) # 09:00
    end_time = db.Column(db.String(10), nullable=False) # 10:00
    
    academic_class = db.relationship('AcademicClass', backref='timetable_slots')
    stream = db.relationship('Stream', backref='timetable_slots')
    subject = db.relationship('Subject', backref='timetable_slots')
    teacher = db.relationship('Teacher', backref='timetable_slots', foreign_keys=[teacher_id])

class Enquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    course_interest = db.Column(db.String(50))
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Topper(db.Model):
    __tablename__ = 'topper'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    percentage = db.Column(db.String(20), nullable=False)
    stream = db.Column(db.String(50), nullable=False)
    rank = db.Column(db.Integer, nullable=False) # 1, 2, or 3
    photo_url = db.Column(db.String(255))
    academic_year = db.Column(db.String(20), default='2023-24')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

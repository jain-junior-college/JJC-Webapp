from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='staff') # admin or staff

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    dob = db.Column(db.String(20))
    gender = db.Column(db.String(10))
    student_class = db.Column(db.String(50)) # Using student_class to avoid 'class' keyword conflict
    contact = db.Column(db.String(20))
    email = db.Column(db.String(100))
    admission_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    fees = db.relationship('Fee', backref='student', lazy=True)
    exams = db.relationship('Exam', backref='student', lazy=True)

class Fee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50))
    remarks = db.Column(db.String(200))

class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    marks_obtained = db.Column(db.Float, nullable=False)
    total_marks = db.Column(db.Float, default=100.0)
    exam_type = db.Column(db.String(50)) # Mid-term, Final, etc.
    exam_date = db.Column(db.DateTime, default=datetime.utcnow)

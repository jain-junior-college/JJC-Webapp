from app import app, db
from models import User, Student, Fee, Exam, Enquiry, Stream, AcademicClass
from werkzeug.security import generate_password_hash

def init_db():
    with app.app_context():
        db.create_all()
        
        # Create a default admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
        # Seed Streams
        streams = ['Science', 'Commerce', 'Arts']
        for s in streams:
            if not Stream.query.filter_by(name=s).first():
                db.session.add(Stream(name=s))

        # Seed Academic Classes
        classes = ['XI', 'XII']
        for c in classes:
            if not AcademicClass.query.filter_by(name=c).first():
                db.session.add(AcademicClass(name=c))
        
        db.session.commit()
        
        print("Database initialized, admin user created, and masters seeded.")

if __name__ == "__main__":
    init_db()

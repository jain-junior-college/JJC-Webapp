from app import app, db
from models import User, Student, Fee, Exam
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
            print("Database initialized and admin user created.")
        else:
            print("Database already initialized.")

if __name__ == "__main__":
    init_db()

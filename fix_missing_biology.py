from app import app, db
from models import Student, Subject

def fix_biology_links():
    with app.app_context():
        biology = Subject.query.filter_by(name='Biology').first()
        if not biology:
            print("Biology subject not found in the database.")
            return

        # Get all students in the Science stream
        science_students = [s for s in Student.query.all() if s.stream and s.stream.name == 'Science']
        
        fixed_count = 0
        for student in science_students:
            # If the student only has the 4 compulsory subjects, we assume they need Biology
            # You can also customize this if they need Mathematics instead.
            if len(student.subjects) == 4:
                print(f"Adding Biology to student: {student.name} (ID: {student.student_id})")
                student.subjects.append(biology)
                fixed_count += 1
                
        if fixed_count > 0:
            db.session.commit()
            print(f"Successfully added Biology to {fixed_count} students.")
        else:
            print("No students found with exactly 4 subjects who needed Biology added.")

if __name__ == '__main__':
    fix_biology_links()

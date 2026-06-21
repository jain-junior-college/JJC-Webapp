import sys
from app import app, db
from models import Student, Subject

def fix_missing_subject(subject_name):
    with app.app_context():
        subject = Subject.query.filter_by(name=subject_name).first()
        if not subject:
            print(f"Error: Subject '{subject_name}' not found in the database.")
            return

        # Get all students in the stream that this subject belongs to
        stream_name = subject.stream.name if subject.stream else None
        if not stream_name:
            print(f"Error: Subject '{subject_name}' is not linked to any stream.")
            return

        stream_students = [s for s in Student.query.all() if s.stream and s.stream.name == stream_name]
        
        fixed_count = 0
        for student in stream_students:
            # Check how many subjects the student currently has.
            # Usually, a student should have 6 subjects. If they have less (e.g. 4 or 5)
            # and they don't already have this subject, we can add it.
            if len(student.subjects) < 6 and subject not in student.subjects:
                print(f"Adding {subject_name} to student: {student.name} (ID: {student.student_id})")
                student.subjects.append(subject)
                fixed_count += 1
                
        if fixed_count > 0:
            db.session.commit()
            print(f"Successfully added {subject_name} to {fixed_count} students.")
        else:
            print(f"No students found who needed {subject_name} added.")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        subject_to_fix = sys.argv[1]
    else:
        subject_to_fix = 'Biology' # Default if no arg provided
        
    fix_missing_subject(subject_to_fix)

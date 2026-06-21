import sys
from app import app, db
from models import Student, Subject, Stream

def fix_all_optional_subjects():
    with app.app_context():
        # Get all optional subjects
        optional_subjects = Subject.query.filter_by(is_compulsory=False).all()
        
        if not optional_subjects:
            print("No optional subjects found in the database.")
            return

        for subject in optional_subjects:
            stream_name = subject.stream.name if subject.stream else "Unknown Stream"
            print(f"--- Processing Subject: {subject.name} (Stream: {stream_name}) ---")
            
            if not subject.stream:
                print("Skipping: Subject is not linked to any stream.\n")
                continue

            stream_students = [s for s in Student.query.all() if s.stream and s.stream.name == stream_name]
            
            fixed_count = 0
            for student in stream_students:
                # If they have fewer than 6 subjects and don't have this one yet, we append it.
                if len(student.subjects) < 6 and subject not in student.subjects:
                    print(f"  -> Adding {subject.name} to student: {student.name} (ID: {student.student_id})")
                    student.subjects.append(subject)
                    fixed_count += 1
                    
            if fixed_count > 0:
                db.session.commit()
                print(f"Successfully added {subject.name} to {fixed_count} students.\n")
            else:
                print(f"No missing links found for {subject.name}.\n")

if __name__ == '__main__':
    fix_all_optional_subjects()

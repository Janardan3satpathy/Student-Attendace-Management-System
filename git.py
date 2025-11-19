import streamlit as st
import json
import random
import string
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Date, ForeignKey, func
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from werkzeug.security import generate_password_hash, check_password_hash

# --- 1. CONFIGURATION AND DATABASE SETUP ---

# Define the database connection and session maker
DATABASE_URL = "sqlite:///attendify.db"
Base = declarative_base()

# Use Streamlit's resource cache to ensure the database engine is only created once
@st.cache_resource
def get_database_engine():
    """Initializes the SQLAlchemy engine."""
    return create_engine(DATABASE_URL)

@st.cache_resource
def get_session_maker(engine):
    """Creates a session maker bound to the engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

@st.cache_resource
def initialize_database():
    """Creates tables and seeds initial data if none exists."""
    engine = get_database_engine()
    SessionLocal = get_session_maker(engine)
    
    # Create all tables defined in Base
    Base.metadata.create_all(bind=engine)
    
    with SessionLocal() as session:
        # Check if Admin exists
        if not session.query(User).filter_by(role=User.ADMIN).first():
            # Seed Admin
            admin = User(
                full_name='Super Admin',
                enrollment_number='ADMIN001',
                role=User.ADMIN,
                fingerprint_data=json.dumps([f'Simulated Admin Finger {i}' for i in range(1, 6)])
            )
            admin.set_password('adminpass')
            session.add(admin)
            st.toast("Database tables created and Admin user seeded.", icon="🔒")

            # Seed Courses and Subjects
            branches = ['CSE', 'ECE', 'MECH', 'CIVIL']
            courses = ['B.Tech']
            
            for course in courses:
                for branch in branches:
                    for year in range(1, 5):
                        for semester in [1, 2]:
                            sem_num = (year - 1) * 2 + semester
                            subjects = [
                                Subject(course=course, branch=branch, name=f'{branch} - Subject A{sem_num}', code=f'SA{sem_num}{branch[:2]}', semester=sem_num),
                                Subject(course=course, branch=branch, name=f'{branch} - Subject B{sem_num}', code=f'SB{sem_num}{branch[:2]}', semester=sem_num)
                            ]
                            session.add_all(subjects)

            session.flush()

            # Seed a Teacher
            subject = session.query(Subject).filter_by(name='CSE - Subject A1').first()
            if subject:
                teacher = User(
                    full_name='Dr. Anjali Sharma',
                    enrollment_number='TCH101',
                    role=User.TEACHER,
                    subject_id=subject.id,
                    fingerprint_data=json.dumps([f'Simulated Teacher Finger {i}' for i in range(1, 6)])
                )
                teacher.set_password('teacherpass')
                session.add(teacher)

            # Seed a Student
            student = User(
                full_name='Priya Kumar',
                enrollment_number='STU2025001',
                role=User.STUDENT,
                course='B.Tech',
                branch='CSE',
                batch=2025,
                fathers_name='Rajesh Kumar',
                mothers_name='Pooja Kumar',
                dob=datetime(2003, 5, 15).date(),
                blood_group='A+',
                address='123, Tech Street',
                district='Bhopal',
                state='MP',
                pin_code='462001',
                contact_no='9876543210',
                fingerprint_data=json.dumps([f'Simulated Student Finger {i}' for i in range(1, 6)])
            )
            student.set_password('studentpass')
            session.add(student)
            
            session.commit()
            st.toast("Default Teacher and Student seeded.", icon="🧑‍🏫")

# --- 2. DATABASE MODELS (Reused) ---

class User(Base):
    __tablename__ = 'user'
    
    ADMIN, TEACHER, STUDENT = 1, 2, 3

    id = Column(Integer, primary_key=True)
    full_name = Column(String(100), nullable=False)
    enrollment_number = Column(String(20), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(Integer, nullable=False)
    
    course = Column(String(50))
    branch = Column(String(50))
    batch = Column(Integer)
    
    fathers_name = Column(String(100))
    mothers_name = Column(String(100))
    dob = Column(Date)
    blood_group = Column(String(10))
    address = Column(String(255))
    district = Column(String(50))
    state = Column(String(50))
    pin_code = Column(String(10))
    contact_no = Column(String(15))
    
    fingerprint_data = Column(String) 
    subject_id = Column(Integer, ForeignKey('subject.id'))
    subject = relationship('Subject', backref='teachers')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Subject(Base):
    __tablename__ = 'subject'
    id = Column(Integer, primary_key=True)
    course = Column(String(50), nullable=False)
    branch = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    semester = Column(Integer, nullable=False)

class Attendance(Base):
    __tablename__ = 'attendance'
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    subject_id = Column(Integer, ForeignKey('subject.id'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    punch_in_time = Column(DateTime, nullable=False)
    punch_out_time = Column(DateTime)
    status = Column(String(10), default='Present') 

    student = relationship('User', foreign_keys=[student_id], backref='student_attendance')
    teacher = relationship('User', foreign_keys=[teacher_id], backref='teacher_records')
    subject_rel = relationship('Subject', backref='subject_attendance')

# --- 3. HELPER FUNCTIONS ---

def get_role_name(role_id):
    if role_id == User.ADMIN: return 'Admin'
    if role_id == User.TEACHER: return 'Teacher'
    if role_id == User.STUDENT: return 'Student'
    return 'Unknown'

def generate_captcha():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def set_initial_state():
    """Initializes Streamlit session state variables."""
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'role' not in st.session_state:
        st.session_state.role = None
    if 'captcha' not in st.session_state:
        st.session_state.captcha = generate_captcha()

def logout():
    """Clears session state for logout."""
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.role = None
    st.session_state.captcha = generate_captcha()
    st.rerun()

# --- 4. STREAMLIT VIEWS ---

def view_login_register():
    """Renders the Login and Registration Forms."""
    
    st.markdown('<h1 style="text-align: center; color: #007bff; font-weight: 800;">WELCOME SHA-SHIB ATTENDEES</h1>', unsafe_allow_html=True)
    
    # Handle Navigation
    col_login, col_reg = st.columns([1, 1])
    
    with col_login:
        if st.session_state.get('show_register', False):
            if st.button("<< Back to Login", use_container_width=True):
                st.session_state.show_register = False
                st.rerun()
        else:
            st.header("Login")
            
            with st.form("login_form"):
                role = st.selectbox("Login As", options=[User.STUDENT, User.TEACHER, User.ADMIN], format_func=get_role_name)
                enrollment_number = st.text_input("Enrollment Number", key="login_enr")
                password = st.text_input("Password", type="password", key="login_pass")
                
                # Captcha Input
                col_cap_in, col_cap_disp = st.columns([2, 1])
                with col_cap_disp:
                    st.markdown(f'<div style="text-align: center; background-color: #f3f4f6; padding: 10px; border-radius: 5px; font-weight: bold; color: #1f2937;">{st.session_state.captcha}</div>', unsafe_allow_html=True)
                with col_cap_in:
                    captcha_input = st.text_input("Enter Captcha", key="login_captcha_input")
                
                if st.form_submit_button("Login", use_container_width=True):
                    # Check Captcha
                    if captcha_input.upper() != st.session_state.captcha.upper():
                        st.error("Invalid Captcha. Please try again.")
                        st.session_state.captcha = generate_captcha()
                        st.rerun()
                        
                    SessionLocal = get_session_maker(get_database_engine())
                    with SessionLocal() as session:
                        user = session.query(User).filter_by(enrollment_number=enrollment_number, role=role).first()

                        if user and user.check_password(password):
                            st.session_state.logged_in = True
                            st.session_state.user_id = user.id
                            st.session_state.role = user.role
                            st.session_state.captcha = generate_captcha() # Reset captcha after success
                            st.toast(f"Welcome back, {user.full_name}!", icon="👋")
                            st.rerun()
                        else:
                            st.error("Invalid Enrollment Number, Password, or Role combination.")
                            st.session_state.captcha = generate_captcha() # New captcha on failure
                            st.rerun()

    with col_reg:
        if st.session_state.get('show_register', False):
            # Display Registration form based on selected role
            if st.session_state.register_role:
                view_register_form(st.session_state.register_role)
            else:
                 st.header("Register As")
                 if st.button("Register as Student", use_container_width=True, key="reg_student"):
                    st.session_state.register_role = User.STUDENT
                    st.rerun()
                 if st.button("Register as Teacher", use_container_width=True, key="reg_teacher"):
                    st.session_state.register_role = User.TEACHER
                    st.rerun()
        else:
            if st.button("Register an account", use_container_width=True):
                st.session_state.show_register = True
                st.session_state.register_role = None
                st.rerun()

def view_register_form(role_id):
    """Handles the two-step registration process."""
    role_name = get_role_name(role_id)
    st.header(f"New {role_name} Registration")

    # Step 1: Core Registration
    if st.session_state.get('reg_step') != 2:
        st.session_state.reg_step = 1
        
        SessionLocal = get_session_maker(get_database_engine())
        with SessionLocal() as session:
            subjects = session.query(Subject).order_by(Subject.course, Subject.branch, Subject.semester).all()
            subject_options = {s.id: f"{s.name} ({s.branch} - Sem {s.semester})" for s in subjects}

        with st.form("register_step1_form"):
            name = st.text_input("Full Name", key="reg_name")
            enrollment = st.text_input("Enrollment Number", key="reg_enr")
            
            if role_id == User.STUDENT:
                col1, col2, col3 = st.columns(3)
                with col1: course = st.selectbox("Course", options=['B.Tech'])
                with col2: branch = st.selectbox("Branch", options=['CSE', 'ECE', 'MECH', 'CIVIL'])
                with col3: batch = st.number_input("Batch (Joining Year)", min_value=2000, max_value=datetime.now().year, value=datetime.now().year)
            else:
                subject_id = st.selectbox("Assigned Subject (Primary)", options=list(subject_options.keys()), format_func=lambda x: subject_options[x])

            password = st.text_input("Password", type="password", key="reg_pass1")
            confirm_password = st.text_input("Confirm Password", type="password", key="reg_pass2")
            
            if st.form_submit_button("Finish Registration" if role_id == User.TEACHER else "Next (Personal Details)", use_container_width=True):
                if password != confirm_password:
                    st.error("Passwords do not match.")
                
                SessionLocal = get_session_maker(get_database_engine())
                with SessionLocal() as session:
                    if session.query(User).filter_by(enrollment_number=enrollment).first():
                        st.error("Enrollment Number already registered.")
                    elif role_id == User.TEACHER or role_id == User.STUDENT:
                        
                        fingerprints = json.dumps([f'Simulated Finger {i} for {enrollment}' for i in range(1, 6)])
                        
                        new_user = User(
                            full_name=name,
                            enrollment_number=enrollment,
                            role=role_id,
                            fingerprint_data=fingerprints,
                            fathers_name='N/A' # Placeholder for student's next step
                        )
                        new_user.set_password(password)
                        
                        if role_id == User.STUDENT:
                            new_user.course, new_user.branch, new_user.batch = course, branch, batch
                            st.session_state.temp_user = new_user
                            st.session_state.reg_step = 2
                            st.rerun() # Move to step 2

                        elif role_id == User.TEACHER:
                            new_user.subject_id = subject_id
                            session.add(new_user)
                            session.commit()
                            st.success(f"{role_name} registered successfully! Please log in.")
                            st.session_state.show_register = False
                            st.session_state.reg_step = 1
                            st.rerun()

    # Step 2: Student Personal Details (Only if role is Student)
    if st.session_state.get('reg_step') == 2 and role_id == User.STUDENT:
        st.subheader("Step 2: Enter Personal Details")
        temp_user = st.session_state.temp_user
        
        with st.form("register_step2_form"):
            col1, col2 = st.columns(2)
            with col1: father = st.text_input("Father's Name", key="reg_father")
            with col2: mother = st.text_input("Mother's Name", key="reg_mother")
            col1, col2 = st.columns(2)
            with col1: dob = st.date_input("Date of Birth", min_value=datetime(1990, 1, 1).date(), max_value=datetime.now().date(), value=datetime(2003, 1, 1).date())
            with col2: blood = st.text_input("Blood Group", key="reg_blood")

            st.text_input("Address", key="reg_address")
            col1, col2, col3 = st.columns(3)
            with col1: dist = st.text_input("District", key="reg_dist")
            with col2: state = st.text_input("State", key="reg_state")
            with col3: pincode = st.text_input("Pin Code", key="reg_pin")
            st.text_input("Contact No.", key="reg_contact")
            
            st.warning("5 Fingerprints added successfully (Simulated).")
            
            if st.form_submit_button("Submit Personal Details and Finish", use_container_width=True):
                # Finalize User object
                temp_user.fathers_name = father
                temp_user.mothers_name = mother
                temp_user.dob = dob
                temp_user.blood_group = blood
                temp_user.address = st.session_state.reg_address
                temp_user.district = dist
                temp_user.state = state
                temp_user.pin_code = pincode
                temp_user.contact_no = st.session_state.reg_contact
                
                SessionLocal = get_session_maker(get_database_engine())
                with SessionLocal() as session:
                    session.add(temp_user)
                    session.commit()
                
                st.success("Student registered and details saved! Please log in.")
                st.session_state.show_register = False
                st.session_state.reg_step = 1
                st.session_state.temp_user = None
                st.rerun()

def view_student_dashboard(user):
    """Renders the Student Dashboard."""
    st.title(f"Welcome, {user.full_name} ({user.enrollment_number})")
    
    SessionLocal = get_session_maker(get_database_engine())
    with SessionLocal() as session:
        # 1. Attendance Calculation
        student_attendance_records = session.query(Attendance).filter_by(student_id=user.id).all()
        
        # 2. Get the latest user details (in case they were updated in the sidebar)
        user = session.query(User).get(user.id) 
        
        subject_attendance = {}
        total_attended = 0
        total_classes = 0

        for rec in student_attendance_records:
            sub_id = rec.subject_id
            
            # Fetch subject details for display
            subject = session.query(Subject).get(sub_id)
            if sub_id not in subject_attendance:
                subject_attendance[sub_id] = {'attended': 0, 'total': 0, 'subject': subject}

            # Count as attended only if the class record has a punch-out (is finalized)
            if rec.status in ['Present', 'Late'] and rec.punch_out_time is not None:
                subject_attendance[sub_id]['attended'] += 1
            
            # Count total class sessions (each record with a punch-out is a class session)
            if rec.punch_out_time is not None:
                 subject_attendance[sub_id]['total'] += 1
        
        # Calculate totals for overall summary
        for data in subject_attendance.values():
            data['percentage'] = (data['attended'] / data['total']) * 100 if data['total'] > 0 else 100
            total_attended += data['attended']
            total_classes += data['total']
            
        overall_percentage = (total_attended / total_classes) * 100 if total_classes > 0 else 100
        low_attendance = overall_percentage < 75
    
    if low_attendance:
        st.error(f"🚨 **ATTENDANCE ALERT:** Your overall attendance is below the mandatory 75% threshold. Current: {overall_percentage:.2f}%. Please attend all classes.")

    # Main Content Columns
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Academic Details")
        st.info(f"**Course/Branch:** {user.course} / {user.branch} | **Batch:** {user.batch}")

        # Subject-wise Attendance Table
        st.subheader("Subject-wise Attendance Breakdown")
        if subject_attendance:
            data = [
                {
                    'Subject': d['subject'].name,
                    'Semester': d['subject'].semester,
                    'Attended': d['attended'],
                    'Total Classes': d['total'],
                    'Percentage': f"{d['percentage']:.2f}%"
                }
                for d in subject_attendance.values()
            ]
            df = pd.DataFrame(data)
            
            # Style the table to highlight low attendance
            def color_cells(val):
                if isinstance(val, str) and val.endswith('%'):
                    percent = float(val.strip('%'))
                    if percent < 75:
                        return 'background-color: #fee2e2; color: #ef4444; font-weight: bold;'
                return ''

            st.dataframe(df.style.applymap(color_cells, subset=['Percentage']), use_container_width=True)
        else:
            st.info("No finalized attendance records found yet.")

    with col2:
        st.subheader("Attendance Summary")
        st.metric(label="Overall Percentage", value=f"{overall_percentage:.2f}%", delta=f"{total_attended} / {total_classes} Classes")

        st.subheader("Personal Details")
        details = {
            "Father's Name": user.fathers_name,
            "Mother's Name": user.mothers_name,
            "Date of Birth": user.dob,
            "Blood Group": user.blood_group,
            "Contact No": user.contact_no,
        }
        for k, v in details.items():
            st.markdown(f"**{k}:** {v or 'N/A'}")
        
        st.markdown(f"**Address:** {user.address or ''}, {user.district or ''}, {user.state or ''} - {user.pin_code or ''}")

        st.subheader("Registered Biometrics")
        fingerprints = json.loads(user.fingerprint_data)
        for fp in fingerprints:
            st.markdown(f"- {fp}")
        st.caption("Simulated data representing the 5 registered fingerprints.")
        
    # Personal Details Update Form (In Sidebar for cleaner look)
    with st.sidebar:
        st.subheader("Update Personal Details")
        
        with st.form("update_details_form"):
            st.markdown("**Contact Information**")
            up_father = st.text_input("Father's Name", value=user.fathers_name if user.fathers_name != 'N/A' else "")
            up_mother = st.text_input("Mother's Name", value=user.mothers_name if user.mothers_name != 'N/A' else "")
            up_dob = st.date_input("Date of Birth", value=user.dob if user.dob else datetime(2003, 1, 1).date())
            up_blood = st.text_input("Blood Group", value=user.blood_group if user.blood_group else "")
            
            st.markdown("**Address**")
            up_address = st.text_area("Address", value=user.address if user.address else "")
            up_district = st.text_input("District", value=user.district if user.district else "")
            up_state = st.text_input("State", value=user.state if user.state else "")
            up_pin_code = st.text_input("Pin Code", value=user.pin_code if user.pin_code else "")
            up_contact = st.text_input("Contact No.", value=user.contact_no if user.contact_no else "")
            
            if st.form_submit_button("Update Details"):
                SessionLocal = get_session_maker(get_database_engine())
                with SessionLocal() as session:
                    # Re-fetch user to avoid detached instance issues
                    current_user = session.query(User).get(user.id) 
                    
                    current_user.fathers_name = up_father
                    current_user.mothers_name = up_mother
                    current_user.dob = up_dob
                    current_user.blood_group = up_blood
                    current_user.address = up_address
                    current_user.district = up_district
                    current_user.state = up_state
                    current_user.pin_code = up_pin_code
                    current_user.contact_no = up_contact
                    
                    session.commit()
                    st.toast("Personal details updated!", icon="✅")
                    st.rerun()

def view_teacher_dashboard(user):
    """Renders the Teacher Dashboard with attendance graph."""
    st.title(f"Welcome, {user.full_name} (ID: {user.enrollment_number})")
    
    SessionLocal = get_session_maker(get_database_engine())
    with SessionLocal() as session:
        user_subject = session.query(Subject).get(user.subject_id)
        
        # 1. Get student count for the subject
        subject_students = session.query(User).filter(
            User.role == User.STUDENT, 
            User.course == user_subject.course, 
            User.branch == user_subject.branch
        ).all()
        total_students = len(subject_students)

        # 2. Calculate Attendance History (Session by Session)
        all_attendance = session.query(Attendance).filter_by(teacher_id=user.id, subject_id=user.subject_id).all()
        
        attendance_groups = {} # Key: (Date, Hour), Value: list of records
        
        # Group records into finalized sessions
        for rec in all_attendance:
            if rec.punch_out_time is not None:
                # Use the date and hour of punch-in as a stable session key (e.g., 2025-11-20 10)
                session_key = (rec.punch_in_time.date(), rec.punch_in_time.hour)
                
                if session_key not in attendance_groups:
                    attendance_groups[session_key] = []
                attendance_groups[session_key].append(rec)
        
        attendance_history = []
        total_present_overall = 0
        total_classes_count = 0

        for key, records in attendance_groups.items():
            session_date = key[0].strftime('%Y-%m-%d %H:%M')
            # Count students present (includes late punches)
            present_count = len([r for r in records if r.status in ['Present', 'Late']])
            
            session_percentage = (present_count / total_students) * 100 if total_students > 0 else 0
            
            attendance_history.append({
                'Session_Date': session_date,
                'Percentage': session_percentage
            })
            total_present_overall += present_count
            total_classes_count += 1
            
        total_classes = total_classes_count
        
        # Overall percentage: (Total successful punches) / (Total students * Total finalized sessions)
        total_presence_base = total_classes * total_students
        total_present_percentage = (total_present_overall / total_presence_base) * 100 if total_presence_base > 0 else 0

        # 3. Get the latest class attendance for the live table
        latest_punch_in = session.query(func.max(Attendance.punch_in_time)).filter_by(teacher_id=user.id, subject_id=user.subject_id).scalar()
        
        latest_attendance_records = []
        if latest_punch_in:
            time_window = latest_punch_in + timedelta(minutes=30)
            
            latest_attendance_records = session.query(Attendance).filter(
                Attendance.teacher_id == user.id,
                Attendance.subject_id == user.subject_id,
                Attendance.punch_in_time >= latest_punch_in - timedelta(minutes=5),
                Attendance.punch_in_time <= time_window
            ).join(User, Attendance.student_id == User.id).order_by(Attendance.punch_in_time.desc()).all()


    col1, col2 = st.columns([1, 2])
    
    # Left Column: Assignment and Summary
    with col1:
        st.subheader("Teaching Assignment")
        st.markdown(f"**Subject:** {user_subject.name}")
        st.markdown(f"**Course/Branch:** {user_subject.course} / {user_subject.branch}")
        st.markdown(f"**Semester:** {user_subject.semester}")
        
        st.subheader("Overall Subject Summary")
        st.metric(label=f"Total Students in {user_subject.branch}", value=total_students)
        st.metric(label="Total Classes Conducted (Finalized)", value=total_classes)
        
        # Download Report
        st.markdown("---")
        st.subheader("Attendance Report")
        
        # Create CSV data for download
        df_data = []
        for record in all_attendance:
            # Only include finalized records in the full CSV report
            if record.student and record.subject_rel and record.teacher and record.punch_out_time:
                df_data.append({
                    'Date': record.punch_in_time.strftime('%Y-%m-%d'),
                    'Subject Code': record.subject_rel.code,
                    'Enrollment Number': record.student.enrollment_number,
                    'Student Name': record.student.full_name,
                    'Punch In Time': record.punch_in_time.strftime('%H:%M:%S'),
                    'Punch Out Time': record.punch_out_time.strftime('%H:%M:%S'),
                    'Status': record.status
                })

        df = pd.DataFrame(df_data)
        csv_report = df.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="Download Attendance Report (CSV)",
            data=csv_report,
            file_name=f'attendance_report_{user_subject.code}_{datetime.now().strftime("%Y%m%d")}.csv',
            mime='text/csv',
            use_container_width=True
        )


    # Right Column: Live Attendance Management & History
    with col2:
        st.subheader("Attendance System (Biometric Simulation)")

        with st.form("punch_form"):
            enrollment_number = st.text_input("Enter Student Enrollment ID (Simulated Fingerprint Punch)")
            
            col_in, col_out = st.columns(2)
            with col_in:
                punch_in_submitted = st.form_submit_button("Punch In (Start Class)", use_container_width=True)
            with col_out:
                punch_out_submitted = st.form_submit_button("Punch Out (End Class)", use_container_width=True)
            
            st.caption("Punch In: Starts class/marks student present. Punch Out: Finalizes records for the entire class session.")
            
            if punch_in_submitted or punch_out_submitted:
                SessionLocal = get_session_maker(get_database_engine())
                with SessionLocal() as session:
                    student = session.query(User).filter_by(enrollment_number=enrollment_number, role=User.STUDENT).first()

                    if not student:
                        st.error(f'Error: User with ID {enrollment_number} not found or is not a student.')
                    else:
                        now = datetime.now()
                        latest_class_start = session.query(func.max(Attendance.punch_in_time)).filter_by(teacher_id=user.id, subject_id=user.subject_id).scalar()

                        if punch_in_submitted:
                            if latest_class_start and (now - latest_class_start).total_seconds() < 3600:
                                # Active session check
                                recent_record = session.query(Attendance).filter(
                                    Attendance.student_id == student.id,
                                    Attendance.teacher_id == user.id,
                                    Attendance.subject_id == user.subject_id,
                                    Attendance.punch_in_time >= latest_class_start,
                                ).first()

                                if recent_record:
                                    st.warning(f'{student.full_name}: Already punched in for the current session.')
                                else:
                                    status = 'Late' if (now - latest_class_start).total_seconds() > 300 else 'Present'
                                    new_punch_in = Attendance(
                                        student_id=student.id, subject_id=user.subject_id, teacher_id=user.id,
                                        punch_in_time=now, status=status
                                    )
                                    session.add(new_punch_in)
                                    session.commit()
                                    st.success(f'{student.full_name} PUNCH IN recorded as {status}.')
                            else:
                                # New class session start
                                new_session = Attendance(
                                    student_id=student.id, subject_id=user.subject_id, teacher_id=user.id,
                                    punch_in_time=now, status='Present'
                                )
                                session.add(new_session)
                                session.commit()
                                st.success(f'New Class Session STARTED. {student.full_name} PUNCH IN recorded.')
                        
                        elif punch_out_submitted:
                            if not latest_class_start:
                                st.error('Error: No active class session found to punch out from.')
                            else:
                                records_to_finalize = session.query(Attendance).filter(
                                    Attendance.teacher_id == user.id,
                                    Attendance.subject_id == user.subject_id,
                                    Attendance.punch_in_time >= latest_class_start - timedelta(minutes=5),
                                    Attendance.punch_out_time.is_(None)
                                ).all()
                                
                                for record in records_to_finalize:
                                    record.punch_out_time = now
                                
                                session.commit()
                                st.success(f'Class Session ENDED. {len(records_to_finalize)} attendance records finalized.')
                        st.rerun() # Rerun to update the live table

        # --- Attendance History Chart ---
        st.subheader("Attendance History by Session")
        st.metric(label="Overall Presence (%)", value=f"{total_present_percentage:.2f}%")
        
        if attendance_history:
            df_history = pd.DataFrame(attendance_history)
            df_history['Session_Date'] = pd.to_datetime(df_history['Session_Date'])
            df_history = df_history.set_index('Session_Date')
            
            st.bar_chart(df_history['Percentage'])
            st.caption("Chart showing the percentage of students present in each historical class session.")
        else:
            st.info("No finalized classes found to display history.")
            
        # Live Attendance Table
        st.subheader("Today's Class Attendance (Live/Latest Session)")
        if latest_attendance_records:
            live_data = [
                {
                    'Enrollment No.': rec.student.enrollment_number,
                    'Student Name': rec.student.full_name,
                    'Punch In Time': rec.punch_in_time.strftime('%H:%M:%S'),
                    'Punch Out Time': rec.punch_out_time.strftime('%H:%M:%S') if rec.punch_out_time else 'N/A',
                    'Status': rec.status
                } for rec in latest_attendance_records
            ]
            st.dataframe(pd.DataFrame(live_data), use_container_width=True)
        else:
            st.info("No active or recent class attendance records found.")

def view_admin_dashboard(user):
    """Renders the Admin Dashboard."""
    st.title(f"Admin Control Panel ({user.enrollment_number})")
    
    SessionLocal = get_session_maker(get_database_engine())
    with SessionLocal() as session:
        total_users = session.query(User).count()
        total_students = session.query(User).filter_by(role=User.STUDENT).count()
        total_teachers = session.query(User).filter_by(role=User.TEACHER).count()
        total_subjects = session.query(Subject).count()
        all_users = session.query(User).all()

    # System Overview
    st.subheader("System Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Users", total_users)
    col2.metric("Total Students", total_students)
    col3.metric("Total Teachers", total_teachers)
    col4.metric("Total Subjects", total_subjects)

    st.subheader("User Enrollment Details")
    if all_users:
        user_data = []
        for u in all_users:
            role_name = get_role_name(u.role)
            course_detail = u.course or (u.subject.branch if u.subject else 'N/A')
            user_data.append({
                'ID': u.enrollment_number,
                'Name': u.full_name,
                'Role': role_name,
                'Course/Branch': course_detail,
                'Contact': u.contact_no or 'N/A'
            })
        st.dataframe(pd.DataFrame(user_data), use_container_width=True, height=400)
    else:
        st.info("No users registered yet.")
        
    # Data Management
    st.subheader("Data Management")
    st.warning("PERMANENT ACTION: This deletes all attendance data from the system.")
    
    with st.form("delete_form"):
        confirm = st.text_input("Type 'CONFIRM DELETE' to permanently delete ALL Attendance records.")
        delete_submitted = st.form_submit_button("Permanently Delete Attendance Data")
        
        if delete_submitted:
            if confirm == 'CONFIRM DELETE':
                SessionLocal = get_session_maker(get_database_engine())
                with SessionLocal() as session:
                    try:
                        session.query(Attendance).delete()
                        session.commit()
                        st.success('SUCCESS: All attendance records have been permanently deleted.')
                        st.rerun()
                    except Exception as e:
                        st.error(f'ERROR: Could not delete data: {e}')
                        session.rollback()
            else:
                st.error("Deletion failed. Confirmation phrase was incorrect.")

# --- 5. MAIN APP EXECUTION ---

if __name__ == '__main__':
    st.set_page_config(layout="wide", page_title="Sha-Shib Attendify", page_icon="🏫")
    
    # Run database initialization and seeding once
    initialize_database()
    
    # Initialize session state
    set_initial_state()

    # Sidebar for logout
    if st.session_state.logged_in:
        st.sidebar.button("Logout", on_click=logout, type="primary", use_container_width=True)
        st.sidebar.markdown(f"**Logged in as:** {get_role_name(st.session_state.role)}")

    # Main Page Logic
    if not st.session_state.logged_in:
        view_login_register()
    else:
        SessionLocal = get_session_maker(get_database_engine())
        with SessionLocal() as session:
            user = session.query(User).get(st.session_state.user_id)
            
            if user:
                if user.role == User.ADMIN:
                    view_admin_dashboard(user)
                elif user.role == User.TEACHER:
                    view_teacher_dashboard(user)
                elif user.role == User.STUDENT:
                    view_student_dashboard(user)
            else:
                st.error("User not found. Logging out...")
                logout()
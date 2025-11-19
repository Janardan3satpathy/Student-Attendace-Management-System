import streamlit as st
import json
import random
import string
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from werkzeug.security import generate_password_hash, check_password_hash
import os

# Page configuration
st.set_page_config(
    page_title="Sha-Shib Attendify",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        color: #007bff;
        text-align: center;
        margin-bottom: 2rem;
    }
    .alert-box {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid #ef4444;
        background-color: #fef2f2;
        color: #ef4444;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid #10b981;
        background-color: #f0fdf4;
        color: #10b981;
    }
    .info-card {
        background-color: #f8fafc;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border: 1px solid #e2e8f0;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 0.5rem;
        color: white;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Database Setup
Base = declarative_base()

class User(Base):
    __tablename__ = 'user'
    
    # Role definitions
    ADMIN, TEACHER, STUDENT = 1, 2, 3
    
    id = Column(Integer, primary_key=True)
    full_name = Column(String(100), nullable=False)
    enrollment_number = Column(String(20), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(Integer, nullable=False)
    
    # Student specific
    course = Column(String(50))
    branch = Column(String(50))
    batch = Column(Integer)
    
    # Personal details
    fathers_name = Column(String(100))
    mothers_name = Column(String(100))
    dob = Column(Date)
    blood_group = Column(String(10))
    address = Column(String(255))
    district = Column(String(50))
    state = Column(String(50))
    pin_code = Column(String(10))
    contact_no = Column(String(15))
    
    fingerprint_data = Column(Text)
    
    # Teacher specific
    subject_id = Column(Integer, ForeignKey('subject.id'), nullable=True)
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

# Initialize Database
@st.cache_resource
def init_database():
    engine = create_engine('sqlite:///attendify.db', echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

def seed_database(session):
    """Seed initial data if not exists"""
    # Check if admin exists
    admin = session.query(User).filter_by(role=User.ADMIN).first()
    if not admin:
        admin = User(
            full_name='Super Admin',
            enrollment_number='ADMIN001',
            role=User.ADMIN,
            fingerprint_data=json.dumps([f'Simulated Admin Finger {i}' for i in range(1, 6)])
        )
        admin.set_password('adminpass')
        session.add(admin)
        session.commit()
    
    # Seed subjects
    if session.query(Subject).count() == 0:
        branches = ['CSE', 'ECE', 'MECH', 'CIVIL']
        courses = ['B.Tech']
        for course in courses:
            for branch in branches:
                for year in range(1, 5):
                    for semester in [1, 2]:
                        sem_num = (year - 1) * 2 + semester
                        for suffix in ['A', 'B']:
                            subject = Subject(
                                course=course,
                                branch=branch,
                                name=f'{branch} - Subject {suffix}{sem_num}',
                                code=f'S{suffix}{sem_num}{branch[:2]}',
                                semester=sem_num
                            )
                            session.add(subject)
        session.commit()
    
    # Seed a teacher
    if session.query(User).filter_by(role=User.TEACHER).count() == 0:
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
            session.commit()
    
    # Seed a student
    if session.query(User).filter_by(role=User.STUDENT).count() == 0:
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

# Helper Functions
def generate_captcha():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_role_name(role_id):
    if role_id == User.ADMIN: return 'Admin'
    if role_id == User.TEACHER: return 'Teacher'
    if role_id == User.STUDENT: return 'Student'
    return 'Unknown'

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_role = None
    st.session_state.captcha = generate_captcha()
    st.session_state.page = 'login'

# Initialize database
session = init_database()
seed_database(session)

# Main App Logic
def login_page():
    st.markdown('<h1 class="main-header">🎓 WELCOME SHA-SHIB ATTENDEES</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("login_form"):
            st.subheader("Login to Your Account")
            
            role = st.selectbox("Login As", 
                              options=[3, 2, 1],
                              format_func=lambda x: get_role_name(x))
            
            enrollment_number = st.text_input("Enrollment Number", placeholder="Enter your enrollment ID")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            col_a, col_b = st.columns(2)
            with col_a:
                captcha_input = st.text_input("Enter Captcha", placeholder="Enter the code")
            with col_b:
                st.text_input("Captcha Code", value=st.session_state.captcha, disabled=True)
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submit = st.form_submit_button("🔐 Login", use_container_width=True)
            with col_btn2:
                if st.form_submit_button("📝 Register", use_container_width=True):
                    st.session_state.page = 'register_select'
                    st.rerun()
            
            if submit:
                if captcha_input.upper() != st.session_state.captcha.upper():
                    st.error("❌ Invalid Captcha. Please try again.")
                    st.session_state.captcha = generate_captcha()
                else:
                    user = session.query(User).filter_by(
                        enrollment_number=enrollment_number,
                        role=role
                    ).first()
                    
                    if user and user.check_password(password):
                        st.session_state.logged_in = True
                        st.session_state.user_id = user.id
                        st.session_state.user_role = user.role
                        st.session_state.page = 'dashboard'
                        st.success(f"✅ Welcome back, {user.full_name}!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials. Please try again.")
                        st.session_state.captcha = generate_captcha()
        
        st.divider()
        st.info("**Demo Credentials:**\n\n- Admin: `ADMIN001` / `adminpass`\n- Teacher: `TCH101` / `teacherpass`\n- Student: `STU2025001` / `studentpass`")

def register_select_page():
    st.markdown('<h1 class="main-header">📋 Register New Account</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.subheader("Select Your Role")
        
        if st.button("👨‍🎓 Register as Student", use_container_width=True):
            st.session_state.page = 'register_student'
            st.rerun()
        
        if st.button("👨‍🏫 Register as Teacher", use_container_width=True):
            st.session_state.page = 'register_teacher'
            st.rerun()
        
        st.divider()
        
        if st.button("← Back to Login", use_container_width=True):
            st.session_state.page = 'login'
            st.rerun()

def register_page(role_id):
    role_name = get_role_name(role_id)
    st.markdown(f'<h1 class="main-header">New {role_name} Registration</h1>', unsafe_allow_html=True)
    
    with st.form("registration_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            full_name = st.text_input("Full Name", placeholder="Enter your full name")
        with col2:
            enrollment_number = st.text_input("Enrollment Number", placeholder="Enter enrollment ID")
        
        if role_id == User.STUDENT:
            col3, col4, col5 = st.columns(3)
            with col3:
                course = st.selectbox("Course", ["B.Tech"])
            with col4:
                branch = st.selectbox("Branch", ["CSE", "ECE", "MECH", "CIVIL"])
            with col5:
                batch = st.number_input("Batch Year", min_value=2000, max_value=datetime.now().year, value=datetime.now().year)
        
        if role_id == User.TEACHER:
            subjects = session.query(Subject).order_by(Subject.course, Subject.branch, Subject.semester).all()
            subject_options = {s.id: f"{s.name} ({s.branch} - Sem {s.semester})" for s in subjects}
            subject_id = st.selectbox("Assigned Subject", options=list(subject_options.keys()), format_func=lambda x: subject_options[x])
        
        col6, col7 = st.columns(2)
        with col6:
            password = st.text_input("Password", type="password", placeholder="Create a password")
        with col7:
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Re-enter password")
        
        col8, col9 = st.columns(2)
        with col8:
            submit = st.form_submit_button("✅ Complete Registration", use_container_width=True)
        with col9:
            if st.form_submit_button("← Back", use_container_width=True):
                st.session_state.page = 'register_select'
                st.rerun()
        
        if submit:
            if password != confirm_password:
                st.error("❌ Passwords do not match!")
            elif session.query(User).filter_by(enrollment_number=enrollment_number).first():
                st.error("❌ Enrollment Number already registered!")
            elif not full_name or not enrollment_number or not password:
                st.error("❌ Please fill all required fields!")
            else:
                try:
                    fingerprints = json.dumps([f'Simulated Finger {i} for {enrollment_number}' for i in range(1, 6)])
                    
                    new_user = User(
                        full_name=full_name,
                        enrollment_number=enrollment_number,
                        role=role_id,
                        fingerprint_data=fingerprints
                    )
                    new_user.set_password(password)
                    
                    if role_id == User.STUDENT:
                        new_user.course = course
                        new_user.branch = branch
                        new_user.batch = batch
                        new_user.fathers_name = 'N/A'
                    elif role_id == User.TEACHER:
                        new_user.subject_id = subject_id
                    
                    session.add(new_user)
                    session.commit()
                    st.success(f"✅ {role_name} registered successfully! Please login.")
                    st.session_state.page = 'login'
                    st.rerun()
                except Exception as e:
                    session.rollback()
                    st.error(f"❌ Registration failed: {e}")

def student_dashboard():
    user = session.query(User).get(st.session_state.user_id)
    
    # Sidebar
    with st.sidebar:
        st.title("👨‍🎓 Student Panel")
        st.write(f"**Name:** {user.full_name}")
        st.write(f"**ID:** {user.enrollment_number}")
        st.write(f"**Course:** {user.course}")
        st.write(f"**Branch:** {user.branch}")
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.page = 'login'
            st.rerun()
    
    # Main content
    st.markdown(f'<h1 class="main-header">Welcome, {user.full_name}!</h1>', unsafe_allow_html=True)
    
    # Calculate attendance
    attendance_records = session.query(Attendance).filter_by(student_id=user.id).all()
    
    subject_attendance = {}
    total_attended = 0
    total_classes = 0
    
    for rec in attendance_records:
        sub_id = rec.subject_id
        if sub_id not in subject_attendance:
            subject_attendance[sub_id] = {
                'attended': 0, 
                'total': 0, 
                'subject': rec.subject_rel
            }
        
        if rec.status == 'Present':
            subject_attendance[sub_id]['attended'] += 1
            total_attended += 1
        
        subject_attendance[sub_id]['total'] += 1
        total_classes += 1
    
    for sub_id, data in subject_attendance.items():
        data['percentage'] = (data['attended'] / data['total']) * 100 if data['total'] > 0 else 100
    
    overall_percentage = (total_attended / total_classes) * 100 if total_classes > 0 else 100
    
    # Alert for low attendance
    if overall_percentage < 75:
        st.markdown(f"""
        <div class="alert-box">
            <strong>⚠️ ATTENDANCE ALERT:</strong><br>
            Your overall attendance is below the mandatory 75% threshold. 
            Current: <strong>{overall_percentage:.2f}%</strong>. 
            Please attend all classes to avoid academic penalties.
        </div>
        """, unsafe_allow_html=True)
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Overall Attendance", f"{overall_percentage:.2f}%", 
                 delta=f"{overall_percentage - 75:.2f}%" if overall_percentage >= 75 else None,
                 delta_color="normal" if overall_percentage >= 75 else "inverse")
    with col2:
        st.metric("✅ Classes Attended", total_attended)
    with col3:
        st.metric("📚 Total Classes", total_classes)
    
    # Personal Details
    with st.expander("👤 Personal & Academic Details", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Father's Name:** {user.fathers_name or 'N/A'}")
            st.write(f"**Mother's Name:** {user.mothers_name or 'N/A'}")
            st.write(f"**Date of Birth:** {user.dob or 'N/A'}")
            st.write(f"**Blood Group:** {user.blood_group or 'N/A'}")
        with col2:
            st.write(f"**Contact No:** {user.contact_no or 'N/A'}")
            st.write(f"**Address:** {user.address or 'N/A'}")
            st.write(f"**District:** {user.district or 'N/A'}")
            st.write(f"**State:** {user.state or 'N/A'}")
        
        if st.button("✏️ Update Personal Details"):
            st.session_state.show_update_form = True
    
    if st.session_state.get('show_update_form', False):
        with st.form("update_details"):
            st.subheader("Update Personal Information")
            col1, col2 = st.columns(2)
            with col1:
                fathers_name = st.text_input("Father's Name", value=user.fathers_name or '')
                mothers_name = st.text_input("Mother's Name", value=user.mothers_name or '')
                dob = st.date_input("Date of Birth", value=user.dob if user.dob else datetime.now().date())
                blood_group = st.text_input("Blood Group", value=user.blood_group or '')
            with col2:
                address = st.text_input("Address", value=user.address or '')
                district = st.text_input("District", value=user.district or '')
                state = st.text_input("State", value=user.state or '')
                pin_code = st.text_input("Pin Code", value=user.pin_code or '')
                contact_no = st.text_input("Contact Number", value=user.contact_no or '')
            
            if st.form_submit_button("💾 Save Details"):
                user.fathers_name = fathers_name
                user.mothers_name = mothers_name
                user.dob = dob
                user.blood_group = blood_group
                user.address = address
                user.district = district
                user.state = state
                user.pin_code = pin_code
                user.contact_no = contact_no
                session.commit()
                st.success("✅ Details updated successfully!")
                st.session_state.show_update_form = False
                st.rerun()
    
    # Subject-wise Attendance
    st.subheader("📖 Subject-wise Attendance Breakdown")
    if subject_attendance:
        data = []
        for sub_id, info in subject_attendance.items():
            data.append({
                'Subject': f"{info['subject'].name} ({info['subject'].code})",
                'Semester': info['subject'].semester,
                'Attended': info['attended'],
                'Total': info['total'],
                'Percentage': f"{info['percentage']:.2f}%"
            })
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("📝 No attendance records found yet.")
    
    # Biometric Info
    with st.expander("🔐 Registered Fingerprints (Simulated)", expanded=False):
        fingerprints = json.loads(user.fingerprint_data)
        for i, fp in enumerate(fingerprints, 1):
            st.write(f"{i}. {fp}")
        st.caption("Note: Actual integration requires dedicated hardware and drivers.")

def teacher_dashboard():
    user = session.query(User).get(st.session_state.user_id)
    
    # Sidebar
    with st.sidebar:
        st.title("👨‍🏫 Teacher Panel")
        st.write(f"**Name:** {user.full_name}")
        st.write(f"**ID:** {user.enrollment_number}")
        if user.subject:
            st.write(f"**Subject:** {user.subject.name}")
            st.write(f"**Branch:** {user.subject.branch}")
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.page = 'login'
            st.rerun()
    
    # Main content
    st.markdown(f'<h1 class="main-header">Welcome, {user.full_name}!</h1>', unsafe_allow_html=True)
    
    if not user.subject:
        st.error("❌ No subject assigned to your account.")
        return
    
    # Calculate statistics
    subject_students = session.query(User).filter_by(
        role=User.STUDENT,
        course=user.subject.course,
        branch=user.subject.branch
    ).all()
    total_students = len(subject_students)
    
    all_attendance = session.query(Attendance).filter_by(
        teacher_id=user.id,
        subject_id=user.subject_id
    ).all()
    
    unique_class_sessions = set()
    for rec in all_attendance:
        session_key = (rec.punch_in_time.date(), rec.punch_in_time.hour)
        unique_class_sessions.add(session_key)
    
    total_classes = len(unique_class_sessions)
    total_present = len([rec for rec in all_attendance if rec.status == 'Present'])
    total_present_percentage = (total_present / (total_classes * total_students)) * 100 if total_classes * total_students > 0 else 0
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("👥 Total Students", total_students)
    with col2:
        st.metric("📅 Classes Held", total_classes)
    with col3:
        st.metric("✅ Total Present", total_present)
    with col4:
        st.metric("📊 Attendance %", f"{total_present_percentage:.2f}%")
    
    # Attendance Management
    st.subheader("🔐 Biometric Attendance System")
    
    with st.form("punch_form"):
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            enrollment_number = st.text_input("Student Enrollment ID", placeholder="Enter student ID")
        with col2:
            punch_in = st.form_submit_button("✅ Punch In", use_container_width=True)
        with col3:
            punch_out = st.form_submit_button("❌ Punch Out", use_container_width=True)
        
        st.caption("💡 Punch In starts the class. Students can punch in within 30 minutes. Punch Out finalizes attendance.")
        
        if punch_in or punch_out:
            student = session.query(User).filter_by(
                enrollment_number=enrollment_number,
                role=User.STUDENT
            ).first()
            
            if not student:
                st.error(f"❌ Student with ID '{enrollment_number}' not found!")
            else:
                now = datetime.now()
                latest_class_start = session.query(db.func.max(Attendance.punch_in_time)).filter_by(
                    teacher_id=user.id,
                    subject_id=user.subject_id
                ).scalar()
                
                if punch_in:
                    if latest_class_start and (now - latest_class_start).total_seconds() < 3600:
                        recent_record = session.query(Attendance).filter(
                            Attendance.student_id == student.id,
                            Attendance.teacher_id == user.id,
                            Attendance.subject_id == user.subject_id,
                            Attendance.punch_in_time >= latest_class_start
                        ).first()
                        
                        if recent_record:
                            st.error(f"❌ {student.full_name} is already punched in for this session!")
                        else:
                            status = 'Late' if (now - latest_class_start).total_seconds() > 300 else 'Present'
                            new_punch = Attendance(
                                student_id=student.id,
                                subject_id=user.subject_id,
                                teacher_id=user.id,
                                punch_in_time=now,
                                status=status
                            )
                            session.add(new_punch)
                            session.commit()
                            st.success(f"✅ {student.full_name} punched in at {now.strftime('%H:%M:%S')} - Status: {status}")
                            st.rerun()
                    else:
                        new_session_rec = Attendance(
                            student_id=student.id,
                            subject_id=user.subject_id,
                            teacher_id=user.id,
                            punch_in_time=now,
                            status='Present'
                        )
                        session.add(new_session_rec)
                        session.commit()
                        st.success(f"🎉 New class session started! {student.full_name} punched in at {now.strftime('%H:%M:%S')}")
                        st.rerun()
                
                elif punch_out:
                    if not latest_class_start:
                        st.error("❌ No active class session found!")
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
                        st.success(f"✅ Class ended! {len(records_to_finalize)} attendance records finalized at {now.strftime('%H:%M:%S')}")
                        st.rerun()
    
    # Latest Session Attendance
    st.subheader("📋 Today's Class Attendance (Latest Session)")
    
    latest_punch_in = session.query(db.func.max(Attendance.punch_in_time)).filter_by(
        teacher_id=user.id,
        subject_id=user.subject_id
    ).scalar()
    
    if latest_punch_in:
        time_window = latest_punch_in + timedelta(minutes=30)
        latest_attendance = session.query(Attendance).filter(
            Attendance.teacher_id == user.id,
            Attendance.subject_id == user.subject_id,
            Attendance.punch_in_time >= latest_punch_in - timedelta(minutes=5),
            Attendance.punch_in_time <= time_window
        ).all()
        
        if latest_attendance:
            data = []
            for rec in latest_attendance:
                data.append({
                    'Enrollment': rec.student.enrollment_number,
                    'Name': rec.student.full_name,
                    'Punch In': rec.punch_in_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'Punch Out': rec.punch_out_time.strftime('%Y-%m-%d %H:%M:%S') if rec.punch_out_time else 'N/A',
                    'Status': rec.status
                })
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("📝 No attendance records for the latest session.")
    else:
        st.info("📝 No class sessions recorded yet.")
    
    # Download Report
    st.divider()
    if st.button("📥 Download Attendance Report (CSV)", use_container_width=False):
        records = session.query(Attendance).filter_by(subject_id=user.subject_id).all()
        
        if records:
            data = []
            for rec in records:
                data.append({
                    'Date': rec.punch_in_time.strftime('%Y-%m-%d'),
                    'Subject Code': user.subject.code,
                    'Enrollment': rec.student.enrollment_number,
                    'Student Name': rec.student.full_name,
                    'Punch In': rec.punch_in_time.strftime('%H:%M:%S'),
                    'Punch Out': rec.punch_out_time.strftime('%H:%M:%S') if rec.punch_out_time else 'N/A',
                    'Status': rec.status
                })
            
            df = pd.DataFrame(data)
            csv = df.to_csv(index=False)
            st.download_button(
                label="💾 Download CSV",
                data=csv,
                file_name=f"attendance_report_{user.subject.code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.warning("⚠️ No attendance records to download.")

def admin_dashboard():
    user = session.query(User).get(st.session_state.user_id)
    
    # Sidebar
    with st.sidebar:
        st.title("👨‍💼 Admin Panel")
        st.write(f"**Name:** {user.full_name}")
        st.write(f"**ID:** {user.enrollment_number}")
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.page = 'login'
            st.rerun()
    
    # Main content
    st.markdown('<h1 class="main-header">🎯 Admin Control Panel</h1>', unsafe_allow_html=True)
    
    # System Overview
    total_users = session.query(User).count()
    total_students = session.query(User).filter_by(role=User.STUDENT).count()
    total_teachers = session.query(User).filter_by(role=User.TEACHER).count()
    total_subjects = session.query(Subject).count()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("👥 Total Users", total_users)
    with col2:
        st.metric("👨‍🎓 Students", total_students)
    with col3:
        st.metric("👨‍🏫 Teachers", total_teachers)
    with col4:
        st.metric("📚 Subjects", total_subjects)
    
    # User Management
    st.subheader("📊 User Management")
    
    tab1, tab2, tab3 = st.tabs(["All Users", "Students", "Teachers"])
    
    with tab1:
        all_users = session.query(User).all()
        data = []
        for u in all_users:
            data.append({
                'ID': u.enrollment_number,
                'Name': u.full_name,
                'Role': get_role_name(u.role),
                'Course/Subject': u.course if u.role == User.STUDENT else (u.subject.name if u.subject else 'N/A')
            })
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    
    with tab2:
        students = session.query(User).filter_by(role=User.STUDENT).all()
        data = []
        for s in students:
            data.append({
                'Enrollment': s.enrollment_number,
                'Name': s.full_name,
                'Course': s.course,
                'Branch': s.branch,
                'Batch': s.batch,
                'Contact': s.contact_no or 'N/A'
            })
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    
    with tab3:
        teachers = session.query(User).filter_by(role=User.TEACHER).all()
        data = []
        for t in teachers:
            data.append({
                'ID': t.enrollment_number,
                'Name': t.full_name,
                'Subject': t.subject.name if t.subject else 'N/A',
                'Branch': t.subject.branch if t.subject else 'N/A'
            })
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    
    # Attendance Management
    st.subheader("🗑️ Attendance Data Management")
    st.warning("⚠️ **Danger Zone**: The following action is irreversible!")
    
    with st.form("delete_form"):
        st.write("Delete all attendance records from the system.")
        confirm = st.text_input("Type 'CONFIRM DELETE' to proceed", placeholder="Type here...")
        
        if st.form_submit_button("🗑️ Permanently Delete All Attendance Data", type="primary"):
            if confirm == 'CONFIRM DELETE':
                try:
                    session.query(Attendance).delete()
                    session.commit()
                    st.success("✅ All attendance records have been permanently deleted.")
                    st.rerun()
                except Exception as e:
                    session.rollback()
                    st.error(f"❌ Error deleting data: {e}")
            else:
                st.error("❌ Deletion failed. Confirmation phrase was incorrect.")
    
    # Statistics
    st.subheader("📈 System Statistics")
    
    total_attendance = session.query(Attendance).count()
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"📊 **Total Attendance Records:** {total_attendance}")
    with col2:
        if total_attendance > 0:
            present_count = session.query(Attendance).filter_by(status='Present').count()
            st.info(f"✅ **Present Records:** {present_count} ({(present_count/total_attendance)*100:.2f}%)")

# Main Navigation
def main():
    if not st.session_state.logged_in:
        if st.session_state.page == 'login':
            login_page()
        elif st.session_state.page == 'register_select':
            register_select_page()
        elif st.session_state.page == 'register_student':
            register_page(User.STUDENT)
        elif st.session_state.page == 'register_teacher':
            register_page(User.TEACHER)
    else:
        if st.session_state.user_role == User.STUDENT:
            student_dashboard()
        elif st.session_state.user_role == User.TEACHER:
            teacher_dashboard()
        elif st.session_state.user_role == User.ADMIN:
            admin_dashboard()

if __name__ == '__main__':
    main()
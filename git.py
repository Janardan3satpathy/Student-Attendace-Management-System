import json
import random
import string
import csv
from io import StringIO
from datetime import datetime, timedelta
from flask import Flask, request, redirect, url_for, render_template_string, flash, session, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# --- 1. CONFIGURATION AND INITIALIZATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secure_secret_key_for_sessions'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendify.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- 2. DATABASE MODELS ---

class User(db.Model):
    # Role definitions
    ADMIN, TEACHER, STUDENT = 1, 2, 3

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    enrollment_number = db.Column(db.String(20), unique=True, nullable=False) # Used for login
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.Integer, nullable=False) # 1:Admin, 2:Teacher, 3:Student
    
    # Student specific details
    course = db.Column(db.String(50))
    branch = db.Column(db.String(50))
    batch = db.Column(db.Integer)
    
    # Personal details (for Students)
    fathers_name = db.Column(db.String(100))
    mothers_name = db.Column(db.String(100))
    dob = db.Column(db.Date)
    blood_group = db.Column(db.String(10))
    address = db.Column(db.String(255))
    district = db.Column(db.String(50))
    state = db.Column(db.String(50))
    pin_code = db.Column(db.String(10))
    contact_no = db.Column(db.String(15))
    
    # Biometric Simulation (5 fingerprint placeholders)
    fingerprint_data = db.Column(db.Text) # Stored as JSON string of 5 simulated entries

    # Teacher specific details (Assuming enrollment_number is also used as staff ID)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    subject = db.relationship('Subject', backref='teachers')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course = db.Column(db.String(50), nullable=False)
    branch = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    semester = db.Column(db.Integer, nullable=False) # 1 to 8 (4 years, 2 semesters/year)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    punch_in_time = db.Column(db.DateTime, nullable=False)
    punch_out_time = db.Column(db.DateTime)
    status = db.Column(db.String(10), default='Present') # Present, Late, Absent, etc.

    student = db.relationship('User', foreign_keys=[student_id], backref='student_attendance')
    teacher = db.relationship('User', foreign_keys=[teacher_id], backref='teacher_records')
    subject_rel = db.relationship('Subject', backref='subject_attendance')

# --- 3. HELPER FUNCTIONS AND DATA SEEDING ---

def get_current_user():
    user_id = session.get('user_id')
    return User.query.get(user_id) if user_id else None

def get_user_role_name(role_id):
    if role_id == User.ADMIN: return 'Admin'
    if role_id == User.TEACHER: return 'Teacher'
    if role_id == User.STUDENT: return 'Student'
    return 'Unknown'

def generate_captcha():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# FIX: Removed the deprecated @app.before_first_request decorator here.
# The function is correctly called using `with app.app_context():` in the main block below.
def create_db_and_seed():
    db.create_all()
    if not User.query.filter_by(role=User.ADMIN).first():
        admin = User(
            full_name='Super Admin',
            enrollment_number='ADMIN001',
            role=User.ADMIN,
            fingerprint_data=json.dumps([f'Simulated Admin Finger {i}' for i in range(1, 6)])
        )
        admin.set_password('adminpass')
        db.session.add(admin)
        db.session.commit()
    
    # Seed Courses and Subjects
    if not Subject.query.first():
        branches = ['CSE', 'ECE', 'MECH', 'CIVIL']
        courses = ['B.Tech']
        subjects_data = []
        for course in courses:
            for branch in branches:
                for year in range(1, 5):
                    for semester in [1, 2]:
                        sem_num = (year - 1) * 2 + semester
                        subjects_data.extend([
                            (course, branch, f'{branch} - Subject A{sem_num}', f'SA{sem_num}{branch[:2]}', sem_num),
                            (course, branch, f'{branch} - Subject B{sem_num}', f'SB{sem_num}{branch[:2]}', sem_num)
                        ])
        
        for course, branch, name, code, sem in subjects_data:
            db.session.add(Subject(course=course, branch=branch, name=name, code=code, semester=sem))
        
        db.session.commit()

    # Seed a Teacher
    if not User.query.filter_by(role=User.TEACHER).first():
        subject = Subject.query.filter_by(name='CSE - Subject A1').first()
        if subject:
            teacher = User(
                full_name='Dr. Anjali Sharma',
                enrollment_number='TCH101',
                role=User.TEACHER,
                subject_id=subject.id,
                fingerprint_data=json.dumps([f'Simulated Teacher Finger {i}' for i in range(1, 6)])
            )
            teacher.set_password('teacherpass')
            db.session.add(teacher)
            db.session.commit()

    # Seed a Student
    if not User.query.filter_by(role=User.STUDENT).first():
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
        db.session.add(student)
        db.session.commit()

# --- 4. TEMPLATE STRINGS (INLINE HTML/CSS/JS) ---

# Reusable Tailwind CSS components for aesthetics and responsiveness
TAILWIND_HEADER = """
<script src="https://cdn.tailwindcss.com"></script>
<style>
    /* Custom CSS for the required look */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap');
    body { font-family: 'Inter', sans-serif; }
    .title-banner {
        color: #007bff; /* Bold Blue */
        font-size: 2rem;
        font-weight: 800;
        text-align: center;
        margin-bottom: 2rem;
    }
    .card {
        background-color: white;
        padding: 2.5rem;
        border-radius: 1rem;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
        width: 100%;
        max-width: 448px; /* max-w-lg */
    }
    .alert-system {
        background-color: #fef2f2; /* Red 100 */
        border: 1px solid #fca5a5; /* Red 300 */
        color: #ef4444; /* Red 500 */
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1.5rem;
    }
</style>
"""

LOGIN_HTML = TAILWIND_HEADER + """
<title>Login - Sha-Shib Attendify</title>
<body class="bg-gray-100 flex items-center justify-center min-h-screen p-4">
    <div class="card">
        <h1 class="title-banner">WELCOME SHA-SHIB ATTENDEES</h1>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                <div class="p-3 mb-4 text-sm text-{{ 'red' if category == 'error' else 'green' }}-700 bg-{{ 'red' if category == 'error' else 'green' }}-100 rounded-lg" role="alert">
                    {{ message }}
                </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <form method="POST" action="{{ url_for('login') }}" class="space-y-6">
            <div class="space-y-2">
                <label for="role" class="block text-sm font-medium text-gray-700">Login As</label>
                <select name="role" id="role" required class="w-full p-3 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 shadow-sm">
                    <option value="3">Student</option>
                    <option value="2">Teacher</option>
                    <option value="1">Admin</option>
                </select>
            </div>
            <input type="text" name="enrollment_number" placeholder="Enrollment Number" required
                class="w-full p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500" />
            <input type="password" name="password" placeholder="Password" required
                class="w-full p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500" />
            
            <div class="flex items-center space-x-4">
                <input type="text" name="captcha_input" placeholder="Enter Captcha" required
                    class="w-2/3 p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500" />
                <div class="w-1/3 p-3 bg-gray-200 rounded-lg text-center font-bold text-gray-800 select-none" id="captcha-display">{{ captcha }}</div>
                <input type="hidden" id="captcha-value" name="captcha_value" value="{{ captcha }}" />
            </div>

            <div class="flex items-center justify-between">
                <button type="submit"
                    class="flex-1 mr-2 px-6 py-3 text-white bg-blue-600 rounded-lg font-semibold hover:bg-blue-700 transition duration-150 shadow-md">
                    Login
                </button>
                <a href="{{ url_for('register_select') }}"
                    class="flex-1 ml-2 text-center text-sm text-blue-600 hover:text-blue-800 font-medium">
                    Register an account
                </a>
            </div>
        </form>
    </div>
    <script>
        // Simple JS to ensure the user doesn't cheat the captcha easily (though not secure)
        document.querySelector('form').addEventListener('submit', function(e) {
            const input = document.querySelector('input[name="captcha_input"]').value;
            const value = document.getElementById('captcha-value').value;
            if (input.toUpperCase() !== value.toUpperCase()) {
                alert('Invalid Captcha. Please try again.');
                e.preventDefault();
            }
        });
    </script>
</body>
"""

REGISTER_SELECT_HTML = TAILWIND_HEADER + """
<title>Register - Sha-Shib Attendify</title>
<body class="bg-gray-100 flex items-center justify-center min-h-screen p-4">
    <div class="card">
        <h1 class="title-banner text-xl">REGISTER AS</h1>
        <div class="space-y-4">
            <a href="{{ url_for('register', role_id=3) }}" class="block w-full text-center px-6 py-3 text-white bg-green-500 rounded-lg font-semibold hover:bg-green-600 transition duration-150 shadow-md">
                Register as Student
            </a>
            <a href="{{ url_for('register', role_id=2) }}" class="block w-full text-center px-6 py-3 text-white bg-purple-500 rounded-lg font-semibold hover:bg-purple-600 transition duration-150 shadow-md">
                Register as Teacher
            </a>
            <p class="mt-4 text-center text-sm">
                Already have an account? <a href="{{ url_for('index') }}" class="text-blue-600 hover:underline">Go to Login</a>
            </p>
        </div>
    </div>
</body>
"""

REGISTRATION_FORM_HTML = TAILWIND_HEADER + """
<title>Register - {{ role_name }}</title>
<body class="bg-gray-100 flex items-center justify-center min-h-screen p-4">
    <div class="card max-w-2xl">
        <h1 class="title-banner text-xl">New {{ role_name }} Registration</h1>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                <div class="p-3 mb-4 text-sm text-{{ 'red' if category == 'error' else 'green' }}-700 bg-{{ 'red' if category == 'error' else 'green' }}-100 rounded-lg" role="alert">
                    {{ message }}
                </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <form method="POST" action="{{ url_for('register', role_id=role_id) }}" class="space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label for="full_name" class="block text-sm font-medium text-gray-700">Full Name</label>
                    <input type="text" name="full_name" id="full_name" required
                        class="w-full p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500" />
                </div>
                <div>
                    <label for="enrollment_number" class="block text-sm font-medium text-gray-700">Enrollment Number</label>
                    <input type="text" name="enrollment_number" id="enrollment_number" required
                        class="w-full p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500" />
                </div>
            </div>

            {% if role_id == 3 %}
            <!-- Student Specific Fields -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                    <label for="course" class="block text-sm font-medium text-gray-700">Course</label>
                    <select name="course" id="course" required class="w-full p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500">
                        <option value="B.Tech">B.Tech</option>
                    </select>
                </div>
                <div>
                    <label for="branch" class="block text-sm font-medium text-gray-700">Branch</label>
                    <select name="branch" id="branch" required class="w-full p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500">
                        <option value="CSE">CSE</option>
                        <option value="ECE">ECE</option>
                        <option value="MECH">MECH</option>
                        <option value="CIVIL">CIVIL</option>
                    </select>
                </div>
                <div>
                    <label for="batch" class="block text-sm font-medium text-gray-700">Batch (Joining Year)</label>
                    <input type="number" name="batch" id="batch" required min="2000" max="{{ datetime.now().year }}" value="{{ datetime.now().year }}"
                        class="w-full p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500" />
                </div>
            </div>
            {% endif %}

            {% if role_id == 2 %}
            <!-- Teacher Specific Field -->
            <div>
                <label for="subject_id" class="block text-sm font-medium text-gray-700">Assigned Subject (Primary)</label>
                <select name="subject_id" id="subject_id" required class="w-full p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500">
                    {% for subject in subjects %}
                        <option value="{{ subject.id }}">{{ subject.name }} ({{ subject.branch }} - Sem {{ subject.semester }})</option>
                    {% endfor %}
                </select>
            </div>
            {% endif %}

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label for="password" class="block text-sm font-medium text-gray-700">Password</label>
                    <input type="password" name="password" id="password" required
                        class="w-full p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500" />
                </div>
                <div>
                    <label for="confirm_password" class="block text-sm font-medium text-gray-700">Confirm Password</label>
                    <input type="password" name="confirm_password" id="confirm_password" required
                        class="w-full p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500" />
                </div>
            </div>

            <button type="submit"
                class="w-full px-6 py-3 text-white bg-blue-600 rounded-lg font-semibold hover:bg-blue-700 transition duration-150 shadow-md">
                Finish Registration
            </button>
        </form>
    </div>
</body>
"""

STUDENT_DASHBOARD_HTML = TAILWIND_HEADER + """
<title>Student Dashboard</title>
<body class="bg-gray-50 p-4 sm:p-8">
    <div class="max-w-7xl mx-auto">
        <header class="flex justify-between items-center py-4 border-b">
            <h1 class="text-3xl font-extrabold text-gray-900">Welcome, {{ user.full_name }} ({{ user.enrollment_number }})</h1>
            <a href="{{ url_for('logout') }}" class="px-4 py-2 text-sm text-white bg-red-500 rounded-lg hover:bg-red-600 transition">Logout</a>
        </header>

        {% if low_attendance %}
        <div class="alert-system mt-6">
            <p class="font-bold">ATTENDANCE ALERT:</p>
            <p>Your overall attendance is below the mandatory 75% threshold. Current: {{ attendance_summary.overall_percentage | round(2) }}%. Please attend all classes to avoid academic penalties.</p>
        </div>
        {% endif %}

        <main class="mt-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Details Card -->
            <div class="lg:col-span-2 bg-white p-6 rounded-xl shadow-lg">
                <h2 class="text-xl font-semibold border-b pb-2 mb-4 text-blue-600">Personal & Academic Details</h2>
                <div class="grid grid-cols-2 gap-4 text-sm">
                    <p><strong>Course/Branch:</strong> {{ user.course }} / {{ user.branch }}</p>
                    <p><strong>Batch:</strong> {{ user.batch }}</p>
                    <p><strong>Father's Name:</strong> {{ user.fathers_name or 'N/A' }}</p>
                    <p><strong>Mother's Name:</strong> {{ user.mothers_name or 'N/A' }}</p>
                    <p><strong>Date of Birth:</strong> {{ user.dob or 'N/A' }}</p>
                    <p><strong>Blood Group:</strong> {{ user.blood_group or 'N/A' }}</p>
                    <p><strong>Contact No:</strong> {{ user.contact_no or 'N/A' }}</p>
                    <p class="col-span-2"><strong>Address:</strong> {{ user.address or '' }}, {{ user.district or '' }}, {{ user.state or '' }} - {{ user.pin_code or '' }}</p>
                </div>
                <button onclick="document.getElementById('details-form').style.display='block'; this.style.display='none';" 
                    class="mt-4 px-4 py-2 text-sm text-white bg-green-500 rounded-lg hover:bg-green-600 transition">
                    Update Personal Details
                </button>
                <form id="details-form" method="POST" action="{{ url_for('update_student_details') }}" class="mt-4 p-4 border rounded-lg bg-gray-50" style="display:none;">
                    <h3 class="font-semibold mb-2">Update Details (Next Page of Registration)</h3>
                    <input type="text" name="fathers_name" placeholder="Father's Name" class="w-full p-2 border rounded-md mb-2" value="{{ user.fathers_name or '' }}" required>
                    <input type="text" name="mothers_name" placeholder="Mother's Name" class="w-full p-2 border rounded-md mb-2" value="{{ user.mothers_name or '' }}" required>
                    <input type="date" name="dob" placeholder="Date of Birth" class="w-full p-2 border rounded-md mb-2" value="{{ user.dob.isoformat() if user.dob else '' }}" required>
                    <input type="text" name="blood_group" placeholder="Blood Group (e.g., A+)" class="w-full p-2 border rounded-md mb-2" value="{{ user.blood_group or '' }}">
                    <input type="text" name="address" placeholder="Address" class="w-full p-2 border rounded-md mb-2" value="{{ user.address or '' }}" required>
                    <input type="text" name="district" placeholder="District" class="w-full p-2 border rounded-md mb-2" value="{{ user.district or '' }}" required>
                    <input type="text" name="state" placeholder="State" class="w-full p-2 border rounded-md mb-2" value="{{ user.state or '' }}" required>
                    <input type="text" name="pin_code" placeholder="Pin Code" class="w-full p-2 border rounded-md mb-2" value="{{ user.pin_code or '' }}" required>
                    <input type="text" name="contact_no" placeholder="Contact No." class="w-full p-2 border rounded-md mb-2" value="{{ user.contact_no or '' }}" required>
                    <button type="submit" class="w-full px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition">Submit Details</button>
                </form>
            </div>

            <!-- Fingerprint and Summary Card -->
            <div class="lg:col-span-1 bg-white p-6 rounded-xl shadow-lg">
                <h2 class="text-xl font-semibold border-b pb-2 mb-4 text-blue-600">Biometric & Attendance Summary</h2>
                <div class="space-y-3">
                    <p class="text-lg font-bold">Overall Attendance: <span class="text-blue-600">{{ attendance_summary.overall_percentage | round(2) }}%</span></p>
                    <p class="text-sm text-gray-600">Classes Attended: {{ attendance_summary.attended_classes }} / {{ attendance_summary.total_classes }}</p>
                </div>
                
                <h3 class="mt-6 text-lg font-medium border-t pt-4">Registered Fingerprints (Simulated)</h3>
                <ul class="list-disc list-inside mt-2 text-sm text-gray-700 space-y-1">
                    {% for fp in fingerprints %}
                        <li>{{ fp }}</li>
                    {% endfor %}
                </ul>
                <p class="text-xs mt-2 text-gray-500">Note: Actual integration requires dedicated hardware and drivers. This represents the data stored for authentication.</p>
            </div>
        </main>

        <!-- Subject-wise Attendance -->
        <div class="mt-8 bg-white p-6 rounded-xl shadow-lg">
            <h2 class="text-xl font-semibold border-b pb-2 mb-4 text-blue-600">Subject-wise Attendance Breakdown</h2>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subject</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Semester</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Classes Attended</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Total Classes</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Percentage</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                        {% for subject_id, data in subject_attendance.items() %}
                        <tr>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ data.subject.name }} ({{ data.subject.code }})</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ data.subject.semester }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ data.attended }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ data.total }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-bold {{ 'text-red-500' if data.percentage < 75 else 'text-green-600' }}">
                                {{ data.percentage | round(2) }}%
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% if not subject_attendance %}
            <p class="text-center py-4 text-gray-500">No attendance records found yet.</p>
            {% endif %}
        </div>
    </div>
</body>
"""

TEACHER_DASHBOARD_HTML = TAILWIND_HEADER + """
<title>Teacher Dashboard</title>
<body class="bg-gray-50 p-4 sm:p-8">
    <div class="max-w-7xl mx-auto">
        <header class="flex justify-between items-center py-4 border-b">
            <h1 class="text-3xl font-extrabold text-gray-900">Welcome, {{ user.full_name }} (Teacher ID: {{ user.enrollment_number }})</h1>
            <a href="{{ url_for('logout') }}" class="px-4 py-2 text-sm text-white bg-red-500 rounded-lg hover:bg-red-600 transition">Logout</a>
        </header>

        <main class="mt-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Details Card -->
            <div class="lg:col-span-1 bg-white p-6 rounded-xl shadow-lg">
                <h2 class="text-xl font-semibold border-b pb-2 mb-4 text-blue-600">Teaching Assignment</h2>
                <p><strong>Subject:</strong> {{ user.subject.name }}</p>
                <p><strong>Course/Branch:</strong> {{ user.subject.course }} / {{ user.subject.branch }}</p>
                <p><strong>Semester:</strong> {{ user.subject.semester }}</p>
                <h3 class="mt-6 text-lg font-medium border-t pt-4">Registered Fingerprints (Simulated)</h3>
                <ul class="list-disc list-inside mt-2 text-sm text-gray-700 space-y-1">
                    {% for fp in fingerprints %}
                        <li>{{ fp }}</li>
                    {% endfor %}
                </ul>
            </div>
            
            <!-- Attendance Management Card -->
            <div class="lg:col-span-2 bg-white p-6 rounded-xl shadow-lg">
                <h2 class="text-xl font-semibold border-b pb-2 mb-4 text-blue-600">Attendance System (Biometric Simulation)</h2>
                
                <form method="POST" action="{{ url_for('punch') }}" class="space-y-4">
                    <input type="hidden" name="teacher_id" value="{{ user.id }}">
                    <input type="hidden" name="subject_id" value="{{ user.subject_id }}">
                    <div class="flex items-end space-x-4">
                        <div class="flex-1">
                            <label for="enrollment_number" class="block text-sm font-medium text-gray-700">Student Enrollment ID</label>
                            <input type="text" name="enrollment_number" placeholder="Enter Student ID for Punch" required
                                class="w-full p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500" />
                        </div>
                        <button type="submit" name="action" value="punch_in"
                            class="px-6 py-3 text-white bg-green-600 rounded-lg font-semibold hover:bg-green-700 transition duration-150 shadow-md">
                            Punch In (Start Class)
                        </button>
                        <button type="submit" name="action" value="punch_out"
                            class="px-6 py-3 text-white bg-red-600 rounded-lg font-semibold hover:bg-red-700 transition duration-150 shadow-md">
                            Punch Out (End Class)
                        </button>
                    </div>
                    <p class="text-xs text-gray-500 mt-1">Punch In starts the class. All student punches within a 30-min window are counted. Punch Out ends the class and finalizes the attendance record.</p>
                </form>

                <div class="mt-6 border-t pt-4">
                    <h3 class="text-lg font-medium mb-2">Total Students in Subject: {{ total_students }}</h3>
                    <p class="text-2xl font-bold text-blue-600">{{ total_present }} / {{ total_classes }} ({{ total_present_percentage | round(2) }}%)</p>
                    <p class="text-sm text-gray-500">This is the total present count/percentage for your subject across all recorded sessions.</p>
                    
                    <a href="{{ url_for('download_report', subject_id=user.subject_id) }}" 
                       class="mt-4 inline-block px-4 py-2 text-sm text-white bg-teal-500 rounded-lg hover:bg-teal-600 transition shadow-md">
                        Download Attendance Report (CSV/Excel)
                    </a>
                </div>
            </div>
        </main>
        
        <!-- Live Attendance Table -->
        <div class="mt-8 bg-white p-6 rounded-xl shadow-lg">
            <h2 class="text-xl font-semibold border-b pb-2 mb-4 text-blue-600">Today's Class Attendance (Live/Latest Session)</h2>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Enrollment No.</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Student Name</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Punch In Time</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Punch Out Time</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                        {% for record in latest_attendance %}
                        <tr>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ record.student.enrollment_number }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700">{{ record.student.full_name }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ record.punch_in_time.strftime('%Y-%m-%d %H:%M:%S') }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ record.punch_out_time.strftime('%Y-%m-%d %H:%M:%S') if record.punch_out_time else 'N/A' }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-bold text-green-600">{{ record.status }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% if not latest_attendance %}
            <p class="text-center py-4 text-gray-500">No active or recent class attendance records found for your subject.</p>
            {% endif %}
        </div>
    </div>
</body>
"""

ADMIN_DASHBOARD_HTML = TAILWIND_HEADER + """
<title>Admin Dashboard</title>
<body class="bg-gray-50 p-4 sm:p-8">
    <div class="max-w-7xl mx-auto">
        <header class="flex justify-between items-center py-4 border-b">
            <h1 class="text-3xl font-extrabold text-gray-900">Admin Control Panel</h1>
            <a href="{{ url_for('logout') }}" class="px-4 py-2 text-sm text-white bg-red-500 rounded-lg hover:bg-red-600 transition">Logout</a>
        </header>

        <main class="mt-8 grid grid-cols-1 md:grid-cols-3 gap-8">
            <div class="bg-white p-6 rounded-xl shadow-lg">
                <h2 class="text-xl font-semibold border-b pb-2 mb-4 text-blue-600">System Overview</h2>
                <p>Total Users: <span class="font-bold">{{ total_users }}</span></p>
                <p>Total Students: <span class="font-bold">{{ total_students }}</span></p>
                <p>Total Teachers: <span class="font-bold">{{ total_teachers }}</span></p>
                <p>Total Subjects: <span class="font-bold">{{ total_subjects }}</span></p>
            </div>
            <div class="bg-white p-6 rounded-xl shadow-lg md:col-span-2">
                <h2 class="text-xl font-semibold border-b pb-2 mb-4 text-blue-600">Student Enrollment Details</h2>
                <div class="overflow-x-auto h-96 overflow-y-scroll">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Course</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Role</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
                            {% for u in users %}
                            <tr>
                                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ u.enrollment_number }}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700">{{ u.full_name }}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700">{{ u.course or u.subject.branch if u.subject else 'N/A' }}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm font-bold text-blue-600">{{ get_role_name(u.role) }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </main>
        
        <!-- Attendance Data Management (Simulated Delete) -->
        <div class="mt-8 bg-white p-6 rounded-xl shadow-lg">
            <h2 class="text-xl font-semibold border-b pb-2 mb-4 text-red-600">Manage Attendance Records</h2>
            <form method="POST" action="{{ url_for('admin_delete_data') }}" class="space-y-4">
                <p class="text-sm text-gray-600">Use this to delete all attendance data. This action is irreversible.</p>
                <div class="flex items-center space-x-4">
                    <input type="text" name="confirm" placeholder="Type 'CONFIRM DELETE' to proceed" required
                        class="flex-1 p-3 border border-red-300 rounded-lg shadow-sm focus:ring-red-500 focus:border-red-500" />
                    <button type="submit"
                        class="px-6 py-3 text-white bg-red-700 rounded-lg font-semibold hover:bg-red-800 transition duration-150 shadow-md">
                        Permanently Delete All Attendance Data
                    </button>
                </div>
            </form>
        </div>
    </div>
</body>
"""

# --- 5. ROUTES ---

# General Routes
@app.route('/')
def index():
    """Login Page"""
    # If already logged in, redirect to dashboard
    user = get_current_user()
    if user:
        if user.role == User.ADMIN: return redirect(url_for('admin_dashboard'))
        if user.role == User.TEACHER: return redirect(url_for('teacher_dashboard'))
        if user.role == User.STUDENT: return redirect(url_for('student_dashboard'))
    
    session['captcha'] = generate_captcha()
    return render_template_string(LOGIN_HTML, captcha=session['captcha'])

@app.route('/login', methods=['POST'])
def login():
    """Handle Login Logic"""
    enrollment_number = request.form.get('enrollment_number')
    password = request.form.get('password')
    role_id = int(request.form.get('role'))
    captcha_input = request.form.get('captcha_input')
    captcha_value = request.form.get('captcha_value')

    if captcha_input.upper() != captcha_value.upper():
        flash('Invalid Captcha. Please try again.', 'error')
        return redirect(url_for('index'))
    
    user = User.query.filter_by(enrollment_number=enrollment_number, role=role_id).first()

    if user and user.check_password(password):
        session['user_id'] = user.id
        flash(f'Welcome back, {user.full_name}!', 'success')
        if user.role == User.ADMIN: return redirect(url_for('admin_dashboard'))
        if user.role == User.TEACHER: return redirect(url_for('teacher_dashboard'))
        if user.role == User.STUDENT: return redirect(url_for('student_dashboard'))
    else:
        flash('Invalid Enrollment Number, Password, or Role combination.', 'error')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

@app.route('/register')
def register_select():
    """Page to select role for registration"""
    return render_template_string(REGISTER_SELECT_HTML)

@app.route('/register/<int:role_id>', methods=['GET', 'POST'])
def register(role_id):
    """Handle Registration Logic"""
    role_name = get_user_role_name(role_id)
    subjects = Subject.query.order_by(Subject.course, Subject.branch, Subject.semester).all()

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        enrollment_number = request.form.get('enrollment_number')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register', role_id=role_id))

        if User.query.filter_by(enrollment_number=enrollment_number).first():
            flash('Enrollment Number already registered.', 'error')
            return redirect(url_for('register', role_id=role_id))

        # Initial Fingerprint Setup (Simulated)
        fingerprints = json.dumps([f'Simulated Finger {i} for {enrollment_number}' for i in range(1, 6)])

        try:
            new_user = User(
                full_name=full_name,
                enrollment_number=enrollment_number,
                role=role_id,
                fingerprint_data=fingerprints
            )
            new_user.set_password(password)

            if role_id == User.STUDENT:
                new_user.course = request.form.get('course')
                new_user.branch = request.form.get('branch')
                new_user.batch = request.form.get('batch')
                
                # Student initial details are set to null until 'next page' is filled
                new_user.fathers_name = 'N/A'
                
            elif role_id == User.TEACHER:
                new_user.subject_id = request.form.get('subject_id')

            db.session.add(new_user)
            db.session.commit()
            flash(f'{role_name} registered successfully! Please log in.', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during registration: {e}', 'error')
            return redirect(url_for('register', role_id=role_id))

    return render_template_string(REGISTRATION_FORM_HTML, role_id=role_id, role_name=role_name, subjects=subjects, datetime=datetime)

# --- Student Routes ---
@app.route('/dashboard/student')
def student_dashboard():
    user = get_current_user()
    if not user or user.role != User.STUDENT:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))

    # 1. Personal Details / Fingerprints
    fingerprints = json.loads(user.fingerprint_data)

    # 2. Attendance Calculation
    student_attendance_records = Attendance.query.filter_by(student_id=user.id).all()
    
    subject_attendance = {}
    total_attended = 0
    total_classes = 0

    for rec in student_attendance_records:
        sub_id = rec.subject_id
        if sub_id not in subject_attendance:
            subject_attendance[sub_id] = {'attended': 0, 'total': 0, 'subject': rec.subject_rel}

        # Count as attended only if punched in and the class record has a punch-out (is finalized)
        if rec.status == 'Present':
            subject_attendance[sub_id]['attended'] += 1
            total_attended += 1
        
        subject_attendance[sub_id]['total'] += 1
        total_classes += 1
    
    # Calculate percentages
    for sub_id, data in subject_attendance.items():
        data['percentage'] = (data['attended'] / data['total']) * 100 if data['total'] > 0 else 100

    overall_percentage = (total_attended / total_classes) * 100 if total_classes > 0 else 100
    
    attendance_summary = {
        'overall_percentage': overall_percentage,
        'attended_classes': total_attended,
        'total_classes': total_classes
    }

    # 3. Alert System (below 75%)
    low_attendance = overall_percentage < 75
    
    return render_template_string(STUDENT_DASHBOARD_HTML, 
                                  user=user, 
                                  fingerprints=fingerprints,
                                  subject_attendance=subject_attendance,
                                  attendance_summary=attendance_summary,
                                  low_attendance=low_attendance)

@app.route('/student/update_details', methods=['POST'])
def update_student_details():
    user = get_current_user()
    if not user or user.role != User.STUDENT:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))

    try:
        user.fathers_name = request.form.get('fathers_name')
        user.mothers_name = request.form.get('mothers_name')
        user.dob = datetime.strptime(request.form.get('dob'), '%Y-%m-%d').date()
        user.blood_group = request.form.get('blood_group')
        user.address = request.form.get('address')
        user.district = request.form.get('district')
        user.state = request.form.get('state')
        user.pin_code = request.form.get('pin_code')
        user.contact_no = request.form.get('contact_no')
        
        db.session.commit()
        flash('Personal details updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating details: {e}', 'error')

    return redirect(url_for('student_dashboard'))


# --- Teacher Routes & Attendance Logic ---
@app.route('/dashboard/teacher')
def teacher_dashboard():
    user = get_current_user()
    if not user or user.role != User.TEACHER or not user.subject:
        flash('Access denied or no subject assigned.', 'error')
        return redirect(url_for('index'))

    fingerprints = json.loads(user.fingerprint_data)

    # Calculate overall subject attendance for dashboard summary
    subject_students = User.query.filter_by(role=User.STUDENT, course=user.subject.course, branch=user.subject.branch).all()
    total_students = len(subject_students)

    # Total recorded classes (unique punch-in records by this teacher for this subject)
    all_attendance = Attendance.query.filter_by(teacher_id=user.id, subject_id=user.subject_id).all()
    
    unique_class_sessions = set()
    for rec in all_attendance:
        # Group by date and hour (approximate session start)
        session_key = (rec.punch_in_time.date(), rec.punch_in_time.hour)
        unique_class_sessions.add(session_key)
        
    total_classes = len(unique_class_sessions)
    total_present = len([rec for rec in all_attendance if rec.status == 'Present'])
    
    total_present_percentage = (total_present / (total_classes * total_students)) * 100 if total_classes * total_students > 0 else 0

    # Get the latest class attendance for the live table
    latest_punch_in = db.session.query(db.func.max(Attendance.punch_in_time)).filter_by(teacher_id=user.id, subject_id=user.subject_id).scalar()
    
    latest_attendance = []
    if latest_punch_in:
        # Find all attendance records for the students who punched in close to this time
        time_window = latest_punch_in + timedelta(minutes=30)
        
        latest_attendance = Attendance.query.filter(
            Attendance.teacher_id == user.id,
            Attendance.subject_id == user.subject_id,
            Attendance.punch_in_time >= latest_punch_in - timedelta(minutes=5), # Account for minor variations
            Attendance.punch_in_time <= time_window # Students can punch in up to 30 mins later
        ).join(User, Attendance.student_id == User.id).order_by(Attendance.punch_in_time.desc()).all()


    return render_template_string(TEACHER_DASHBOARD_HTML,
                                  user=user,
                                  fingerprints=fingerprints,
                                  total_students=total_students,
                                  total_classes=total_classes,
                                  total_present=total_present,
                                  total_present_percentage=total_present_percentage,
                                  latest_attendance=latest_attendance)

@app.route('/attendance/punch', methods=['POST'])
def punch():
    """Simulated Biometric Punch-in/Punch-out System"""
    teacher_id = request.form.get('teacher_id')
    subject_id = request.form.get('subject_id')
    enrollment_number = request.form.get('enrollment_number')
    action = request.form.get('action') # 'punch_in' or 'punch_out'
    now = datetime.now()

    student = User.query.filter_by(enrollment_number=enrollment_number, role=User.STUDENT).first()

    if not student:
        flash(f'Error: User with ID {enrollment_number} not found or is not a student.', 'error')
        return redirect(url_for('teacher_dashboard'))

    # Check for a recent class start time by this teacher for this subject (within 5 mins)
    latest_class_start = Attendance.query.with_entities(db.func.max(Attendance.punch_in_time)).filter_by(teacher_id=teacher_id, subject_id=subject_id).scalar()
    
    if action == 'punch_in':
        # Rule: Only create a new session if the last punch-out was over 1 hour ago
        if latest_class_start and (now - latest_class_start).total_seconds() < 3600:
            # Check if student is already marked for this session
            recent_record = Attendance.query.filter(
                Attendance.student_id == student.id,
                Attendance.teacher_id == teacher_id,
                Attendance.subject_id == subject_id,
                Attendance.punch_in_time >= latest_class_start,
            ).first()

            if recent_record:
                flash(f'{student.full_name}: You are already punched in for the current session.', 'error')
                return redirect(url_for('teacher_dashboard'))
            
            # Student is punching into an *active* class (within 30 mins of the teacher's latest start time)
            new_punch_in = Attendance(
                student_id=student.id,
                subject_id=subject_id,
                teacher_id=teacher_id,
                punch_in_time=now,
                status='Late' if (now - latest_class_start).total_seconds() > 300 else 'Present'
            )
            db.session.add(new_punch_in)
            flash(f'{student.full_name} PUNCH IN recorded at {now.strftime("%H:%M:%S")}.', 'success')
        
        else:
            # Teacher is starting a new class session
            new_session = Attendance(
                student_id=student.id, # Record the teacher's initial punch-in for the session start time
                subject_id=subject_id,
                teacher_id=teacher_id,
                punch_in_time=now,
                status='Present'
            )
            db.session.add(new_session)
            flash(f'New Class Session STARTED. {student.full_name} PUNCH IN recorded at {now.strftime("%H:%M:%S")}.', 'success')

        db.session.commit()
        
    elif action == 'punch_out':
        # Rule: Finalize the entire attendance record for the class that started most recently
        if not latest_class_start:
            flash('Error: No active class session found to punch out from.', 'error')
            return redirect(url_for('teacher_dashboard'))

        # Find all attendance records that belong to the latest class session and haven't been punched out
        records_to_finalize = Attendance.query.filter(
            Attendance.teacher_id == teacher_id,
            Attendance.subject_id == subject_id,
            Attendance.punch_in_time >= latest_class_start - timedelta(minutes=5), # Records around the start time
            Attendance.punch_out_time.is_(None)
        ).all()
        
        for record in records_to_finalize:
            record.punch_out_time = now
            # Note: The student who initiated the punch-out doesn't need a new record, just their existing one finalized.

        db.session.commit()
        flash(f'Class Session ENDED. All {len(records_to_finalize)} attendance records finalized at {now.strftime("%H:%M:%S")}.', 'success')
        
    return redirect(url_for('teacher_dashboard'))

@app.route('/download_report/<int:subject_id>')
def download_report(subject_id):
    """Generates and serves the CSV report for a subject"""
    user = get_current_user()
    if not user or user.role != User.TEACHER or user.subject_id != subject_id:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))

    subject = Subject.query.get(subject_id)
    if not subject:
        flash('Subject not found.', 'error')
        return redirect(url_for('teacher_dashboard'))

    # Fetch all attendance records for this subject
    records = Attendance.query.filter_by(subject_id=subject_id).join(User, Attendance.student_id == User.id).order_by(Attendance.punch_in_time.desc()).all()

    # Create CSV data
    output = StringIO()
    writer = csv.writer(output)

    # Header Row
    header = ['Date', 'Subject Code', 'Enrollment Number', 'Student Name', 'Punch In Time', 'Punch Out Time', 'Status']
    writer.writerow(header)

    # Data Rows
    for record in records:
        row = [
            record.punch_in_time.strftime('%Y-%m-%d'),
            subject.code,
            record.student.enrollment_number,
            record.student.full_name,
            record.punch_in_time.strftime('%H:%M:%S'),
            record.punch_out_time.strftime('%H:%M:%S') if record.punch_out_time else 'N/A',
            record.status
        ]
        writer.writerow(row)

    # Prepare response
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=attendance_report_{subject.code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response.headers["Content-type"] = "text/csv"
    return response

# --- Admin Routes ---
@app.route('/dashboard/admin')
def admin_dashboard():
    user = get_current_user()
    if not user or user.role != User.ADMIN:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))

    # System Overview Data
    total_users = User.query.count()
    total_students = User.query.filter_by(role=User.STUDENT).count()
    total_teachers = User.query.filter_by(role=User.TEACHER).count()
    total_subjects = Subject.query.count()
    
    # All users for detailed viewing
    all_users = User.query.all()
    
    return render_template_string(ADMIN_DASHBOARD_HTML,
                                  users=all_users,
                                  get_role_name=get_user_role_name,
                                  total_users=total_users,
                                  total_students=total_students,
                                  total_teachers=total_teachers,
                                  total_subjects=total_subjects)

@app.route('/admin/delete_data', methods=['POST'])
def admin_delete_data():
    user = get_current_user()
    if not user or user.role != User.ADMIN:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    confirm = request.form.get('confirm')
    
    if confirm == 'CONFIRM DELETE':
        try:
            # Delete all attendance records
            db.session.query(Attendance).delete()
            db.session.commit()
            flash('SUCCESS: All attendance records have been permanently deleted.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'ERROR: Could not delete data: {e}', 'error')
    else:
        flash('Deletion failed. Confirmation phrase was incorrect.', 'error')

    return redirect(url_for('admin_dashboard'))


# --- 6. RUN THE APP ---
if __name__ == '__main__':
    # Initialize the database and seed initial data
    with app.app_context():
        create_db_and_seed()
    # Run the application
    app.run(debug=True)
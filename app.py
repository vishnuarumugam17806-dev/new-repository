"""
SMART DB — Automated Database Design & Schema Engineering Service
Main Flask application entry point.
"""
import os
from flask import Flask, render_template
from flask_login import LoginManager

# ── Load env & config ──────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()
import config as cfg

# ── Flask App Initialization ──────────────────────────────────────────────────
app = Flask(__name__, template_folder='static/templates', static_folder='static')
app.secret_key = cfg.SECRET_KEY

app.config['SQLALCHEMY_DATABASE_URI']        = cfg.DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS']      = {'pool_pre_ping': True}

# ── Database & Models ─────────────────────────────────────────────────────────
from models import (
    db, User, SharedDatabase, DownloadLog, IndustryTemplate
)
db.init_app(app)

# ── Flask-Login Setup ─────────────────────────────────────────────────────────
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ── Register Blueprints ───────────────────────────────────────────────────────
from blueprints.auth import auth_bp
from blueprints.generator import generator_bp
from blueprints.marketplace import marketplace_bp
from blueprints.analytics import analytics_bp
from blueprints.api import api_bp
from blueprints.crud import crud_bp

app.register_blueprint(auth_bp)
app.register_blueprint(generator_bp)
app.register_blueprint(marketplace_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(api_bp)
app.register_blueprint(crud_bp)

# ── Seed Data Helper ──────────────────────────────────────────────────────────
def _seed_templates():
    """Seed industry templates on first run and fix non-fontawesome icons."""
    icon_map = {
        'Healthcare': 'fa-hospital',
        'E-commerce': 'fa-cart-shopping',
        'Education': 'fa-graduation-cap',
        'HR': 'fa-users-gear',
        'Finance': 'fa-piggy-bank',
        'Library': 'fa-book-bookmark'
    }
    
    if IndustryTemplate.query.count() > 0:
        # Normalize any existing template icons from emojis to FontAwesome classes
        updated = False
        for tmpl in IndustryTemplate.query.all():
            if not tmpl.icon or not tmpl.icon.startswith('fa-'):
                tmpl.icon = icon_map.get(tmpl.category, 'fa-layer-group')
                updated = True
        if updated:
            db.session.commit()
        return

    # Imports translated SQL helper
    from utils import translate_sql

    templates = [
        IndustryTemplate(
            name='Hospital Management System', category='Healthcare', icon='fa-hospital',
            is_featured=True,
            description='Complete hospital management with patients, doctors, appointments, billing, departments and wards.',
            requirements='Hospital management system with patients, doctors, appointments, departments, billing, and wards.',
            tags='healthcare,hospital,medical,patients,doctors',
            sql_code="""-- Hospital Management System

CREATE TABLE departments (
    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    code VARCHAR(20) UNIQUE,
    head_doctor_id INTEGER,
    phone VARCHAR(20),
    location VARCHAR(200)
);

CREATE TABLE doctors (
    doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    specialization VARCHAR(200),
    license_number VARCHAR(50) UNIQUE,
    phone VARCHAR(20),
    department_id INTEGER,
    available_from TIME,
    available_to TIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

CREATE TABLE patients (
    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    dob DATE,
    gender VARCHAR(10),
    phone VARCHAR(20),
    email VARCHAR(255),
    address TEXT,
    blood_type VARCHAR(5),
    emergency_contact VARCHAR(100),
    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE appointments (
    appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    doctor_id INTEGER NOT NULL,
    department_id INTEGER,
    appointment_date DATETIME NOT NULL,
    status VARCHAR(50) DEFAULT 'scheduled',
    reason TEXT,
    diagnosis TEXT,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id),
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

CREATE TABLE bills (
    bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    appointment_id INTEGER,
    total_amount DECIMAL(12,2) NOT NULL,
    paid_amount DECIMAL(12,2) DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending',
    issued_date DATE DEFAULT CURRENT_DATE,
    due_date DATE,
    payment_method VARCHAR(50),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id)
);""",
            er_diagram_mmd="""erDiagram
    DEPARTMENTS {
        int department_id PK
        string name
        string code
        string location
    }
    DOCTORS {
        int doctor_id PK
        string first_name
        string last_name
        string specialization
        int department_id FK
    }
    PATIENTS {
        int patient_id PK
        string first_name
        string last_name
        date dob
        string blood_type
    }
    APPOINTMENTS {
        int appointment_id PK
        int patient_id FK
        int doctor_id FK
        date appointment_date
        string status
    }
    BILLS {
        int bill_id PK
        int patient_id FK
        decimal total_amount
        string status
    }
    DEPARTMENTS ||--o{ DOCTORS : employs
    DOCTORS ||--o{ APPOINTMENTS : conducts
    PATIENTS ||--o{ APPOINTMENTS : books
    PATIENTS ||--o{ BILLS : receives"""
        ),
        IndustryTemplate(
            name='E-Commerce Platform', category='E-commerce', icon='fa-cart-shopping',
            is_featured=True,
            description='Full e-commerce schema with products, orders, customers, reviews, cart and inventory.',
            requirements='E-commerce platform with products, customers, orders, shopping cart, reviews, categories, and inventory.',
            tags='ecommerce,shop,products,orders,customers,inventory',
            sql_code="""-- E-Commerce Platform Schema

CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(200) UNIQUE,
    description TEXT,
    parent_id INTEGER,
    FOREIGN KEY (parent_id) REFERENCES categories(category_id)
);

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(20),
    password_hash VARCHAR(255),
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(300) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    compare_price DECIMAL(10,2),
    sku VARCHAR(100) UNIQUE,
    stock_quantity INTEGER DEFAULT 0,
    category_id INTEGER,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    total_amount DECIMAL(12,2) NOT NULL,
    shipping_address TEXT,
    payment_method VARCHAR(50),
    payment_status VARCHAR(50) DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    customer_id INTEGER,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    title VARCHAR(300),
    body TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);""",
            er_diagram_mmd="""erDiagram
    CATEGORIES { int category_id PK; string name; int parent_id FK }
    CUSTOMERS { int customer_id PK; string email; string first_name }
    PRODUCTS { int product_id PK; string name; decimal price; int category_id FK }
    ORDERS { int order_id PK; int customer_id FK; string status; decimal total_amount }
    ORDER_ITEMS { int item_id PK; int order_id FK; int product_id FK; int quantity }
    REVIEWS { int review_id PK; int product_id FK; int customer_id FK; int rating }
    CATEGORIES ||--o{ PRODUCTS : contains
    CUSTOMERS ||--o{ ORDERS : places
    ORDERS ||--o{ ORDER_ITEMS : contains
    PRODUCTS ||--o{ ORDER_ITEMS : included_in
    PRODUCTS ||--o{ REVIEWS : receives
    CUSTOMERS ||--o{ REVIEWS : writes"""
        ),
        IndustryTemplate(
            name='University Learning Management', category='Education', icon='fa-graduation-cap',
            is_featured=True,
            description='University LMS with students, courses, faculty, enrollments, grades and assignments.',
            requirements='University learning management system with students, courses, instructors, enrollments, grades, and assignments.',
            tags='education,university,students,courses,lms,grades',
            sql_code="""-- University Learning Management System

CREATE TABLE departments (
    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    code VARCHAR(20) UNIQUE,
    faculty VARCHAR(200)
);

CREATE TABLE instructors (
    instructor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    department_id INTEGER,
    title VARCHAR(100),
    phone VARCHAR(20),
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

CREATE TABLE students (
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    student_number VARCHAR(20) UNIQUE,
    dob DATE,
    department_id INTEGER,
    enrollment_year INTEGER,
    gpa DECIMAL(3,2) DEFAULT 0.00,
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

CREATE TABLE courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code VARCHAR(20) UNIQUE NOT NULL,
    title VARCHAR(300) NOT NULL,
    description TEXT,
    credits INTEGER DEFAULT 3,
    department_id INTEGER,
    instructor_id INTEGER,
    max_students INTEGER DEFAULT 40,
    semester VARCHAR(50),
    FOREIGN KEY (department_id) REFERENCES departments(department_id),
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id)
);

CREATE TABLE enrollments (
    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    enrolled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    grade DECIMAL(4,2),
    grade_letter VARCHAR(5),
    status VARCHAR(50) DEFAULT 'active',
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id)
);

CREATE TABLE assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    title VARCHAR(300) NOT NULL,
    description TEXT,
    due_date DATETIME,
    max_score DECIMAL(6,2) DEFAULT 100,
    FOREIGN KEY (course_id) REFERENCES courses(course_id)
);""",
            er_diagram_mmd="""erDiagram
    DEPARTMENTS { int department_id PK; string name; string code }
    INSTRUCTORS { int instructor_id PK; string first_name; int department_id FK }
    STUDENTS { int student_id PK; string student_number; decimal gpa }
    COURSES { int course_id PK; string course_code; int instructor_id FK }
    ENROLLMENTS { int enrollment_id PK; int student_id FK; int course_id FK; decimal grade }
    ASSIGNMENTS { int assignment_id PK; int course_id FK; date due_date }
    DEPARTMENTS ||--o{ INSTRUCTORS : employs
    DEPARTMENTS ||--o{ STUDENTS : enrolls
    DEPARTMENTS ||--o{ COURSES : offers
    INSTRUCTORS ||--o{ COURSES : teaches
    STUDENTS ||--o{ ENROLLMENTS : has
    COURSES ||--o{ ENROLLMENTS : has
    COURSES ||--o{ ASSIGNMENTS : has"""
        ),
        IndustryTemplate(
            name='Employee HR Management', category='HR', icon='fa-users-gear',
            is_featured=False,
            description='HR system with employees, departments, leave management, payroll and performance reviews.',
            requirements='HR management system with employees, departments, payroll, leave tracking, and performance reviews.',
            tags='hr,employees,payroll,leave,departments,performance',
            sql_code="""-- HR Management System

CREATE TABLE departments (
    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    code VARCHAR(20) UNIQUE,
    manager_id INTEGER,
    budget DECIMAL(15,2),
    location VARCHAR(200)
);

CREATE TABLE employees (
    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    hire_date DATE NOT NULL,
    position VARCHAR(150),
    department_id INTEGER,
    salary DECIMAL(12,2),
    employment_type VARCHAR(50) DEFAULT 'full-time',
    status VARCHAR(50) DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

CREATE TABLE leave_requests (
    leave_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    leave_type VARCHAR(100) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    days_count INTEGER,
    reason TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    approved_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

CREATE TABLE payroll (
    payroll_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    pay_period_start DATE NOT NULL,
    pay_period_end DATE NOT NULL,
    basic_salary DECIMAL(12,2),
    allowances DECIMAL(12,2) DEFAULT 0,
    deductions DECIMAL(12,2) DEFAULT 0,
    net_salary DECIMAL(12,2),
    payment_date DATE,
    payment_status VARCHAR(50) DEFAULT 'pending',
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

CREATE TABLE performance_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    reviewer_id INTEGER,
    review_date DATE NOT NULL,
    performance_score DECIMAL(4,2),
    strengths TEXT,
    improvements TEXT,
    goals TEXT,
    status VARCHAR(50) DEFAULT 'completed',
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);""",
            er_diagram_mmd="""erDiagram
    DEPARTMENTS { int department_id PK; string name; decimal budget }
    EMPLOYEES { int employee_id PK; string email; decimal salary; int department_id FK }
    LEAVE_REQUESTS { int leave_id PK; int employee_id FK; date start_date; string status }
    PAYROLL { int payroll_id PK; int employee_id FK; decimal net_salary }
    PERFORMANCE_REVIEWS { int review_id PK; int employee_id FK; decimal performance_score }
    DEPARTMENTS ||--o{ EMPLOYEES : contains
    EMPLOYEES ||--o{ LEAVE_REQUESTS : submits
    EMPLOYEES ||--o{ PAYROLL : receives
    EMPLOYEES ||--o{ PERFORMANCE_REVIEWS : has"""
        ),
        IndustryTemplate(
            name='Banking & Finance System', category='Finance', icon='fa-piggy-bank',
            is_featured=False,
            description='Banking system with accounts, transactions, loans, cards and customers.',
            requirements='Banking system with customers, accounts, transactions, loans, and credit cards.',
            tags='finance,banking,accounts,transactions,loans',
            sql_code="""-- Banking & Finance System

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20),
    national_id VARCHAR(50) UNIQUE,
    address TEXT,
    dob DATE,
    kyc_verified BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE accounts (
    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    account_number VARCHAR(20) UNIQUE NOT NULL,
    account_type VARCHAR(50) NOT NULL,
    balance DECIMAL(18,2) DEFAULT 0.00,
    currency VARCHAR(10) DEFAULT 'USD',
    status VARCHAR(50) DEFAULT 'active',
    opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    amount DECIMAL(18,2) NOT NULL,
    balance_after DECIMAL(18,2),
    description TEXT,
    reference_number VARCHAR(100) UNIQUE,
    status VARCHAR(50) DEFAULT 'completed',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
);

CREATE TABLE loans (
    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    loan_type VARCHAR(100),
    principal_amount DECIMAL(18,2) NOT NULL,
    interest_rate DECIMAL(5,2),
    tenure_months INTEGER,
    monthly_emi DECIMAL(12,2),
    outstanding_balance DECIMAL(18,2),
    status VARCHAR(50) DEFAULT 'active',
    disbursed_at DATE,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);""",
            er_diagram_mmd="""erDiagram
    CUSTOMERS { int customer_id PK; string email; string national_id }
    ACCOUNTS { int account_id PK; string account_number; decimal balance; int customer_id FK }
    TRANSACTIONS { int transaction_id PK; int account_id FK; decimal amount; string type }
    LOANS { int loan_id PK; int customer_id FK; decimal principal_amount; string status }
    CUSTOMERS ||--o{ ACCOUNTS : owns
    ACCOUNTS ||--o{ TRANSACTIONS : has
    CUSTOMERS ||--o{ LOANS : applies_for"""
        ),
        IndustryTemplate(
            name='Library Management System', category='Library', icon='fa-book-bookmark',
            is_featured=False,
            description='Library system with books, members, borrowing, returns, fines and catalogue.',
            requirements='Library system with books, authors, members, borrowing records, returns, and fines.',
            tags='library,books,members,borrowing,catalogue',
            sql_code="""-- Library Management System

CREATE TABLE authors (
    author_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    bio TEXT,
    nationality VARCHAR(100),
    born_date DATE
);

CREATE TABLE books (
    book_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(300) NOT NULL,
    isbn VARCHAR(20) UNIQUE,
    author_id INTEGER,
    publisher VARCHAR(200),
    published_year INTEGER,
    genre VARCHAR(100),
    total_copies INTEGER DEFAULT 1,
    available_copies INTEGER DEFAULT 1,
    price DECIMAL(8,2),
    FOREIGN KEY (author_id) REFERENCES authors(author_id)
);

CREATE TABLE members (
    member_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20),
    address TEXT,
    membership_type VARCHAR(50) DEFAULT 'basic',
    membership_expiry DATE,
    max_books_allowed INTEGER DEFAULT 3,
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE borrowings (
    borrow_id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    borrow_date DATE DEFAULT CURRENT_DATE,
    due_date DATE NOT NULL,
    return_date DATE,
    status VARCHAR(50) DEFAULT 'borrowed',
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (book_id) REFERENCES books(book_id)
);

CREATE TABLE fines (
    fine_id INTEGER PRIMARY KEY AUTOINCREMENT,
    borrow_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    fine_amount DECIMAL(8,2) NOT NULL,
    reason VARCHAR(200),
    paid BOOLEAN DEFAULT 0,
    issued_date DATE DEFAULT CURRENT_DATE,
    paid_date DATE,
    FOREIGN KEY (borrow_id) REFERENCES borrowings(borrow_id),
    FOREIGN KEY (member_id) REFERENCES members(member_id)
);""",
            er_diagram_mmd="""erDiagram
    AUTHORS { int author_id PK; string first_name; string nationality }
    BOOKS { int book_id PK; string title; string isbn; int author_id FK }
    MEMBERS { int member_id PK; string email; string membership_type }
    BORROWINGS { int borrow_id PK; int member_id FK; int book_id FK; date due_date }
    FINES { int fine_id PK; int borrow_id FK; decimal fine_amount }
    AUTHORS ||--o{ BOOKS : writes
    BOOKS ||--o{ BORROWINGS : borrowed_in
    MEMBERS ||--o{ BORROWINGS : makes
    BORROWINGS ||--o| FINES : generates"""
        ),
    ]
    for t in templates:
        db.session.add(t)
    db.session.commit()


# ── Home Landing Route ────────────────────────────────────────────────────────
@app.route('/')
def index():
    total_schemas  = SharedDatabase.query.count()
    total_downloads = DownloadLog.query.count()
    return render_template('index.html', total_schemas=total_schemas,
                           total_downloads=total_downloads, ai_enabled=cfg.AI_ENABLED)


# ── Favicon Handlers ──────────────────────────────────────────────────────────
@app.route('/favicon.ico')
def favicon():
    return '', 204


# ── Main Entry ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # Bootstrap the metadata database in SQL Server if it doesn't exist
    from services.sqlserver_service import SqlServerService
    SqlServerService.init_system_db()
    
    with app.app_context():
        db.create_all()
        _seed_templates()
    app.run(debug=cfg.DEBUG, host='127.0.0.1', port=cfg.PORT)

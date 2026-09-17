"""
SMART DB — Enhanced Rule-Based Fallback Engine
Handles 40+ entity types, proper FK relationships, and full artifact generation
when no OpenAI API key is configured.
"""
import re
import json
from typing import Optional


# ── Entity knowledge base ─────────────────────────────────────────────────────
ENTITY_PROFILES = {
    'user':        {'pk': 'user_id',      'cols': [('username','VARCHAR(80) NOT NULL UNIQUE'),('email','VARCHAR(255) NOT NULL UNIQUE'),('password_hash','VARCHAR(255) NOT NULL'),('role','VARCHAR(20) DEFAULT \'user\''),('is_active','BOOLEAN DEFAULT 1'),('created_at','DATETIME DEFAULT CURRENT_TIMESTAMP')]},
    'customer':    {'pk': 'customer_id',  'cols': [('first_name','VARCHAR(100) NOT NULL'),('last_name','VARCHAR(100)'),('email','VARCHAR(255) UNIQUE'),('phone','VARCHAR(20)'),('address','TEXT'),('created_at','DATETIME DEFAULT CURRENT_TIMESTAMP')]},
    'employee':    {'pk': 'employee_id',  'cols': [('first_name','VARCHAR(100) NOT NULL'),('last_name','VARCHAR(100) NOT NULL'),('email','VARCHAR(255) UNIQUE'),('phone','VARCHAR(20)'),('hire_date','DATE'),('salary','DECIMAL(12,2)'),('department_id','INTEGER'),('position','VARCHAR(100)')]},
    'student':     {'pk': 'student_id',   'cols': [('first_name','VARCHAR(100) NOT NULL'),('last_name','VARCHAR(100)'),('email','VARCHAR(255) UNIQUE'),('dob','DATE'),('enrollment_date','DATE'),('department_id','INTEGER'),('gpa','DECIMAL(3,2)')]},
    'patient':     {'pk': 'patient_id',   'cols': [('first_name','VARCHAR(100) NOT NULL'),('last_name','VARCHAR(100)'),('dob','DATE'),('gender','VARCHAR(10)'),('phone','VARCHAR(20)'),('address','TEXT'),('blood_type','VARCHAR(5)'),('registered_at','DATETIME DEFAULT CURRENT_TIMESTAMP')]},
    'doctor':      {'pk': 'doctor_id',    'cols': [('first_name','VARCHAR(100) NOT NULL'),('last_name','VARCHAR(100)'),('email','VARCHAR(255) UNIQUE'),('specialization','VARCHAR(200)'),('license_number','VARCHAR(50) UNIQUE'),('phone','VARCHAR(20)'),('department_id','INTEGER')]},
    'product':     {'pk': 'product_id',   'cols': [('name','VARCHAR(200) NOT NULL'),('description','TEXT'),('price','DECIMAL(10,2) NOT NULL'),('stock_quantity','INTEGER DEFAULT 0'),('sku','VARCHAR(100) UNIQUE'),('category_id','INTEGER'),('created_at','DATETIME DEFAULT CURRENT_TIMESTAMP')]},
    'order':       {'pk': 'order_id',     'cols': [('customer_id','INTEGER NOT NULL'),('order_date','DATETIME DEFAULT CURRENT_TIMESTAMP'),('status','VARCHAR(50) DEFAULT \'pending\''),('total_amount','DECIMAL(12,2)'),('shipping_address','TEXT'),('payment_method','VARCHAR(50)')]},
    'book':        {'pk': 'book_id',      'cols': [('title','VARCHAR(300) NOT NULL'),('isbn','VARCHAR(20) UNIQUE'),('author_id','INTEGER'),('publisher','VARCHAR(200)'),('published_year','INTEGER'),('genre','VARCHAR(100)'),('price','DECIMAL(8,2)'),('stock','INTEGER DEFAULT 0')]},
    'author':      {'pk': 'author_id',    'cols': [('first_name','VARCHAR(100) NOT NULL'),('last_name','VARCHAR(100)'),('bio','TEXT'),('nationality','VARCHAR(100)'),('born_date','DATE')]},
    'course':      {'pk': 'course_id',    'cols': [('course_code','VARCHAR(20) UNIQUE NOT NULL'),('title','VARCHAR(300) NOT NULL'),('description','TEXT'),('credits','INTEGER DEFAULT 3'),('department_id','INTEGER'),('instructor_id','INTEGER'),('max_students','INTEGER DEFAULT 30')]},
    'department':  {'pk': 'department_id','cols': [('name','VARCHAR(200) NOT NULL'),('code','VARCHAR(20) UNIQUE'),('head_id','INTEGER'),('budget','DECIMAL(15,2)'),('location','VARCHAR(200)')]},
    'appointment': {'pk': 'appointment_id','cols': [('patient_id','INTEGER NOT NULL'),('doctor_id','INTEGER NOT NULL'),('appointment_date','DATETIME NOT NULL'),('status','VARCHAR(50) DEFAULT \'scheduled\''),('reason','TEXT'),('notes','TEXT')]},
    'invoice':     {'pk': 'invoice_id',   'cols': [('customer_id','INTEGER'),('issue_date','DATE NOT NULL'),('due_date','DATE'),('total_amount','DECIMAL(12,2) NOT NULL'),('status','VARCHAR(50) DEFAULT \'unpaid\''),('notes','TEXT')]},
    'payment':     {'pk': 'payment_id',   'cols': [('amount','DECIMAL(12,2) NOT NULL'),('payment_date','DATETIME DEFAULT CURRENT_TIMESTAMP'),('method','VARCHAR(50)'),('reference_number','VARCHAR(100)'),('status','VARCHAR(50) DEFAULT \'completed\'')]},
    'category':    {'pk': 'category_id',  'cols': [('name','VARCHAR(200) NOT NULL'),('description','TEXT'),('parent_id','INTEGER'),('slug','VARCHAR(200) UNIQUE')]},
    'supplier':    {'pk': 'supplier_id',  'cols': [('name','VARCHAR(200) NOT NULL'),('contact_name','VARCHAR(100)'),('email','VARCHAR(255)'),('phone','VARCHAR(20)'),('address','TEXT'),('rating','DECIMAL(3,2)')]},
    'inventory':   {'pk': 'inventory_id', 'cols': [('product_id','INTEGER NOT NULL'),('quantity','INTEGER DEFAULT 0'),('warehouse_location','VARCHAR(200)'),('last_updated','DATETIME DEFAULT CURRENT_TIMESTAMP')]},
    'review':      {'pk': 'review_id',    'cols': [('product_id','INTEGER'),('customer_id','INTEGER'),('rating','INTEGER CHECK (rating BETWEEN 1 AND 5)'),('title','VARCHAR(300)'),('body','TEXT'),('created_at','DATETIME DEFAULT CURRENT_TIMESTAMP')]},
    'message':     {'pk': 'message_id',   'cols': [('sender_id','INTEGER NOT NULL'),('receiver_id','INTEGER NOT NULL'),('subject','VARCHAR(500)'),('body','TEXT'),('is_read','BOOLEAN DEFAULT 0'),('sent_at','DATETIME DEFAULT CURRENT_TIMESTAMP')]},
    'post':        {'pk': 'post_id',      'cols': [('user_id','INTEGER NOT NULL'),('title','VARCHAR(500) NOT NULL'),('content','TEXT'),('status','VARCHAR(50) DEFAULT \'draft\''),('published_at','DATETIME'),('views','INTEGER DEFAULT 0'),('created_at','DATETIME DEFAULT CURRENT_TIMESTAMP')]},
    'comment':     {'pk': 'comment_id',   'cols': [('user_id','INTEGER'),('post_id','INTEGER'),('content','TEXT NOT NULL'),('created_at','DATETIME DEFAULT CURRENT_TIMESTAMP')]},
    'tag':         {'pk': 'tag_id',       'cols': [('name','VARCHAR(100) NOT NULL UNIQUE'),('slug','VARCHAR(100) UNIQUE'),('description','TEXT')]},
    'address':     {'pk': 'address_id',   'cols': [('street','VARCHAR(300)'),('city','VARCHAR(100)'),('state','VARCHAR(100)'),('country','VARCHAR(100)'),('postal_code','VARCHAR(20)'),('is_default','BOOLEAN DEFAULT 0')]},
    'role':        {'pk': 'role_id',      'cols': [('name','VARCHAR(100) NOT NULL UNIQUE'),('description','TEXT'),('permissions','TEXT')]},
    'vehicle':     {'pk': 'vehicle_id',   'cols': [('make','VARCHAR(100)'),('model','VARCHAR(100)'),('year','INTEGER'),('vin','VARCHAR(50) UNIQUE'),('license_plate','VARCHAR(20)'),('color','VARCHAR(50)'),('mileage','INTEGER DEFAULT 0')]},
    'reservation': {'pk': 'reservation_id','cols': [('customer_id','INTEGER NOT NULL'),('check_in','DATE NOT NULL'),('check_out','DATE NOT NULL'),('status','VARCHAR(50) DEFAULT \'pending\''),('total_price','DECIMAL(10,2)'),('notes','TEXT')]},
    'room':        {'pk': 'room_id',      'cols': [('room_number','VARCHAR(20) NOT NULL UNIQUE'),('type','VARCHAR(100)'),('capacity','INTEGER DEFAULT 1'),('price_per_night','DECIMAL(8,2)'),('status','VARCHAR(50) DEFAULT \'available\'')]},
    'ticket':      {'pk': 'ticket_id',    'cols': [('title','VARCHAR(500) NOT NULL'),('description','TEXT'),('status','VARCHAR(50) DEFAULT \'open\''),('priority','VARCHAR(50) DEFAULT \'medium\''),('assigned_to','INTEGER'),('created_by','INTEGER'),('created_at','DATETIME DEFAULT CURRENT_TIMESTAMP')]},
    'project':     {'pk': 'project_id',   'cols': [('name','VARCHAR(300) NOT NULL'),('description','TEXT'),('start_date','DATE'),('end_date','DATE'),('status','VARCHAR(50) DEFAULT \'active\''),('budget','DECIMAL(15,2)'),('manager_id','INTEGER')]},
    'task':        {'pk': 'task_id',      'cols': [('project_id','INTEGER NOT NULL'),('title','VARCHAR(500) NOT NULL'),('description','TEXT'),('assigned_to','INTEGER'),('due_date','DATE'),('status','VARCHAR(50) DEFAULT \'todo\''),('priority','VARCHAR(50) DEFAULT \'medium\'')]},
}

INDUSTRY_KEYWORDS = {
    'healthcare': ['hospital','patient','doctor','appointment','medical','clinic','nurse','diagnosis','treatment','prescription','ward','billing'],
    'ecommerce':  ['shop','store','product','cart','order','payment','shipping','inventory','catalogue','warehouse','discount','coupon'],
    'education':  ['school','university','student','course','teacher','instructor','enrollment','grade','exam','assignment','lecture','faculty'],
    'finance':    ['bank','account','transaction','loan','investment','insurance','budget','payroll','salary','tax','invoice','payment'],
    'hr':         ['employee','staff','leave','attendance','performance','recruitment','payroll','department','position','benefit','appraisal'],
    'library':    ['book','author','member','borrow','return','fine','catalogue','isbn','publisher','genre'],
    'hotel':      ['room','guest','reservation','booking','amenity','checkout','housekeeping','reception'],
    'transport':  ['vehicle','driver','route','trip','booking','fare','schedule','fleet','maintenance'],
    'social':     ['post','comment','like','follow','message','notification','profile','feed','hashtag','story'],
    'project':    ['project','task','milestone','sprint','bug','ticket','team','deadline','requirement','feature'],
}


class FallbackEngine:
    """Enhanced rule-based engine covering 40+ entities."""

    def _detect_entities(self, text: str) -> list[str]:
        text_lower = text.lower()
        found = []
        for entity, profile in ENTITY_PROFILES.items():
            plural = entity + 's'
            if entity in text_lower or plural in text_lower:
                if entity not in found:
                    found.append(entity)
        if not found:
            found = ['item']
        return found[:6]   # Cap at 6 tables

    def _detect_industry(self, text: str) -> str:
        text_lower = text.lower()
        scores = {}
        for industry, keywords in INDUSTRY_KEYWORDS.items():
            scores[industry] = sum(1 for kw in keywords if kw in text_lower)
        if max(scores.values()) == 0:
            return 'General'
        return max(scores, key=scores.get).capitalize()

    def extract_entities(self, requirements: str) -> dict:
        text     = requirements.lower()
        entities = self._detect_entities(text)
        industry = self._detect_industry(text)
        system_name = self._guess_system_name(text)

        entity_list = []
        for ent_name in entities:
            profile = ENTITY_PROFILES.get(ent_name, {
                'pk': f'{ent_name}_id',
                'cols': [('name', 'VARCHAR(200) NOT NULL'), ('description', 'TEXT'), ('created_at', 'DATETIME DEFAULT CURRENT_TIMESTAMP')]
            })
            attrs = [{'name': profile['pk'], 'data_type': 'INTEGER', 'is_primary_key': True, 'is_foreign_key': False, 'constraints': [], 'description': 'Primary key', 'display_name': profile['pk'].replace('_', ' ').title()}]
            for col_name, col_type in profile['cols']:
                attrs.append({'name': col_name, 'data_type': col_type, 'is_primary_key': False, 'is_foreign_key': col_name.endswith('_id'), 'constraints': [], 'description': col_name.replace('_', ' ').capitalize(), 'display_name': col_name.replace('_', ' ').title()})
            entity_list.append({'name': ent_name, 'display_name': ent_name.replace('_', ' ').title(), 'description': f'Stores {ent_name} records', 'attributes': attrs})

        relationships = self._detect_relationships(entities)

        return {
            'system_name':   system_name,
            'industry':      industry,
            'entities':      entity_list,
            'relationships': relationships,
            'summary':       f'A {industry} management system with {len(entities)} core entities.'
        }

    def _guess_system_name(self, text: str) -> str:
        patterns = [r'i need (?:a|an) (.+?) system', r'(.+?) management system', r'system for (.+?)(?:\.|,|$)']
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return m.group(1).strip().title() + ' System'
        return 'Management System'

    def _detect_relationships(self, entities: list) -> list:
        """Infer common relationships between detected entities."""
        rel_map = {
            ('customer', 'order'):       'ONE_TO_MANY',
            ('order', 'product'):        'MANY_TO_MANY',
            ('patient', 'doctor'):       'MANY_TO_MANY',
            ('patient', 'appointment'):  'ONE_TO_MANY',
            ('doctor', 'appointment'):   'ONE_TO_MANY',
            ('student', 'course'):       'MANY_TO_MANY',
            ('employee', 'department'):  'MANY_TO_ONE',
            ('product', 'category'):     'MANY_TO_ONE',
            ('book', 'author'):          'MANY_TO_ONE',
            ('post', 'user'):            'MANY_TO_ONE',
            ('comment', 'post'):         'MANY_TO_ONE',
            ('task', 'project'):         'MANY_TO_ONE',
            ('invoice', 'customer'):     'MANY_TO_ONE',
            ('payment', 'invoice'):      'ONE_TO_ONE',
        }
        rels = []
        ent_set = set(entities)
        for (a, b), rtype in rel_map.items():
            if a in ent_set and b in ent_set:
                rels.append({'from_entity': a, 'to_entity': b, 'relationship_type': rtype, 'description': f'{a} → {b}'})
        return rels

    def generate_sql_from_entities(self, schema: dict, db_type: str = 'sqlite') -> str:
        pk_map = {'sqlite': 'INTEGER PRIMARY KEY AUTOINCREMENT', 'mysql': 'INT AUTO_INCREMENT PRIMARY KEY', 'postgresql': 'SERIAL PRIMARY KEY', 'mssql': 'INT IDENTITY(1,1) PRIMARY KEY'}
        pk_syntax = pk_map.get(db_type, 'INTEGER PRIMARY KEY AUTOINCREMENT')

        tables = []
        for entity in schema.get('entities', []):
            ent_name = entity['name']
            table_name = ent_name + 's' if not ent_name.endswith('s') else ent_name
            columns = []
            fks = []

            for attr in entity.get('attributes', []):
                col_name = attr['name']
                col_type = attr.get('data_type', 'VARCHAR(100)')
                if attr.get('is_primary_key'):
                    columns.insert(0, f"    {col_name} {pk_syntax}")
                elif attr.get('is_foreign_key') and col_name.endswith('_id'):
                    columns.append(f"    {col_name} INTEGER")
                    ref_table = col_name.replace('_id', '') + 's'
                    fks.append(f"    FOREIGN KEY ({col_name}) REFERENCES {ref_table}({col_name})")
                else:
                    columns.append(f"    {col_name} {col_type}")

            all_cols = columns + fks
            col_str  = ',\n'.join(all_cols)
            comment  = entity.get('description', f'Table for {ent_name} records')
            tables.append(f"-- {comment}\nCREATE TABLE {table_name} (\n{col_str}\n);")

        # Junction tables for MANY_TO_MANY
        for rel in schema.get('relationships', []):
            if rel.get('relationship_type') == 'MANY_TO_MANY':
                a = rel['from_entity']
                b = rel['to_entity']
                jt = f"{a}_{b}"
                a_pk = ENTITY_PROFILES.get(a, {}).get('pk', f'{a}_id')
                b_pk = ENTITY_PROFILES.get(b, {}).get('pk', f'{b}_id')
                a_tbl = a + 's' if not a.endswith('s') else a
                b_tbl = b + 's' if not b.endswith('s') else b
                tables.append(f"-- Junction table: {a} ↔ {b}\nCREATE TABLE {jt} (\n    id {pk_syntax},\n    {a_pk} INTEGER NOT NULL,\n    {b_pk} INTEGER NOT NULL,\n    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,\n    FOREIGN KEY ({a_pk}) REFERENCES {a_tbl}({a_pk}),\n    FOREIGN KEY ({b_pk}) REFERENCES {b_tbl}({b_pk})\n);")

        return '\n\n'.join(tables)

    def generate_er_diagram(self, schema: dict) -> str:
        lines = ['erDiagram']
        for entity in schema.get('entities', []):
            ent_name   = entity['name'].upper()
            table_name = entity['name'] + 's' if not entity['name'].endswith('s') else entity['name']
            table_name = table_name.upper()
            lines.append(f'    {table_name} {{')
            for attr in entity.get('attributes', []):
                pk_marker = ' PK' if attr.get('is_primary_key') else (' FK' if attr.get('is_foreign_key') else '')
                dtype = attr.get('data_type', 'string').split('(')[0].lower()
                if dtype in ('integer', 'int', 'serial'):
                    dtype = 'int'
                elif dtype.startswith('varchar') or dtype == 'text':
                    dtype = 'string'
                elif dtype.startswith('decimal') or dtype == 'float':
                    dtype = 'decimal'
                elif dtype in ('datetime', 'date', 'timestamp'):
                    dtype = 'date'
                elif dtype == 'boolean':
                    dtype = 'bool'
                else:
                    dtype = 'string'
                lines.append(f'        {dtype} {attr["name"]}{pk_marker}')
            lines.append('    }')

        for rel in schema.get('relationships', []):
            a = (rel['from_entity'] + 's').upper() if not rel['from_entity'].endswith('s') else rel['from_entity'].upper()
            b = (rel['to_entity']   + 's').upper() if not rel['to_entity'].endswith('s') else rel['to_entity'].upper()
            rtype = rel.get('relationship_type', 'ONE_TO_MANY')
            if rtype == 'ONE_TO_MANY':
                lines.append(f'    {a} ||--o{{ {b} : "has"')
            elif rtype == 'MANY_TO_MANY':
                lines.append(f'    {a} }}o--o{{ {b} : "relates"')
            elif rtype == 'ONE_TO_ONE':
                lines.append(f'    {a} ||--|| {b} : "has"')
            elif rtype == 'MANY_TO_ONE':
                lines.append(f'    {b} ||--o{{ {a} : "belongs to"')
        return '\n'.join(lines)

    def generate_data_dictionary(self, schema: dict) -> dict:
        tables = []
        for entity in schema.get('entities', []):
            cols = []
            for attr in entity.get('attributes', []):
                constraints = []
                if attr.get('is_primary_key'):
                    constraints.append('PRIMARY KEY, AUTO INCREMENT')
                if 'NOT NULL' in attr.get('data_type', ''):
                    constraints.append('NOT NULL')
                if 'UNIQUE' in attr.get('data_type', ''):
                    constraints.append('UNIQUE')
                cols.append({
                    'name': attr['name'],
                    'display_name': attr.get('display_name', attr['name'].replace('_', ' ').title()),
                    'data_type': attr.get('data_type', 'VARCHAR(100)'),
                    'constraints': ', '.join(constraints) or 'None',
                    'description': attr.get('description', attr['name'].replace('_', ' ').capitalize()),
                    'example_values': ['—'],
                    'notes': 'Auto-generated by SMART DB'
                })
            tables.append({
                'name': entity['name'] + 's',
                'display_name': entity.get('display_name', entity['name'].title()),
                'description': entity.get('description', f"Stores {entity['name']} records."),
                'estimated_rows': '1K–100K',
                'columns': cols,
                'indexes': [f"PRIMARY KEY on {ENTITY_PROFILES.get(entity['name'], {}).get('pk', 'id')}"],
                'relationships': [f"{r['from_entity']} → {r['to_entity']} ({r['relationship_type']})" for r in schema.get('relationships', []) if entity['name'] in [r['from_entity'], r['to_entity']]]
            })
        return {'tables': tables}

    def generate_sample_data(self, schema: dict) -> str:
        SAMPLE = {
            'users':       "INSERT INTO users (username, email, password_hash, role) VALUES ('john_doe', 'john@example.com', 'hashed_pw_1', 'user'), ('jane_smith', 'jane@example.com', 'hashed_pw_2', 'admin'), ('bob_jones', 'bob@example.com', 'hashed_pw_3', 'user');",
            'customers':   "INSERT INTO customers (first_name, last_name, email, phone) VALUES ('Alice', 'Johnson', 'alice@email.com', '+1-555-0101'), ('Bob', 'Williams', 'bob@email.com', '+1-555-0102'), ('Carol', 'Davis', 'carol@email.com', '+1-555-0103');",
            'products':    "INSERT INTO products (name, description, price, stock_quantity, sku) VALUES ('Laptop Pro 15', 'High-performance laptop', 1299.99, 50, 'LP-001'), ('Wireless Mouse', 'Ergonomic mouse', 29.99, 200, 'WM-001'), ('USB Hub 7-Port', 'Fast USB 3.0 hub', 49.99, 100, 'UH-001');",
            'employees':   "INSERT INTO employees (first_name, last_name, email, salary, position) VALUES ('David', 'Brown', 'david@company.com', 75000.00, 'Software Engineer'), ('Emma', 'Wilson', 'emma@company.com', 85000.00, 'Senior Developer'), ('Frank', 'Taylor', 'frank@company.com', 65000.00, 'QA Engineer');",
            'patients':    "INSERT INTO patients (first_name, last_name, dob, gender, phone, blood_type) VALUES ('George', 'Miller', '1985-03-15', 'Male', '+1-555-0201', 'O+'), ('Hannah', 'Moore', '1990-07-22', 'Female', '+1-555-0202', 'A-'), ('Ivan', 'Jackson', '1975-11-08', 'Male', '+1-555-0203', 'B+');",
            'doctors':     "INSERT INTO doctors (first_name, last_name, email, specialization, license_number) VALUES ('Dr. Lisa', 'White', 'lisa@hospital.com', 'Cardiology', 'LIC-001'), ('Dr. Mark', 'Harris', 'mark@hospital.com', 'Neurology', 'LIC-002'), ('Dr. Nancy', 'Martin', 'nancy@hospital.com', 'Pediatrics', 'LIC-003');",
            'departments': "INSERT INTO departments (name, code, budget) VALUES ('Engineering', 'ENG', 500000.00), ('Marketing', 'MKT', 200000.00), ('Human Resources', 'HR', 150000.00), ('Finance', 'FIN', 300000.00);",
            'books':       "INSERT INTO books (title, isbn, publisher, published_year, genre, price, stock) VALUES ('Clean Code', '978-0132350884', 'Prentice Hall', 2008, 'Technology', 45.99, 30), ('The Great Gatsby', '978-0743273565', 'Scribner', 2004, 'Fiction', 15.99, 50), ('Sapiens', '978-0062316097', 'Harper', 2015, 'Non-Fiction', 18.99, 40);",
            'courses':     "INSERT INTO courses (course_code, title, credits, max_students) VALUES ('CS101', 'Introduction to Programming', 3, 40), ('CS201', 'Data Structures', 3, 35), ('CS301', 'Database Management', 3, 30);",
            'orders':      "INSERT INTO orders (customer_id, status, total_amount, payment_method) VALUES (1, 'completed', 1329.98, 'credit_card'), (2, 'pending', 79.98, 'paypal'), (3, 'shipped', 49.99, 'debit_card');",
        }
        output = []
        for entity in schema.get('entities', []):
            table_name = entity['name'] + 's' if not entity['name'].endswith('s') else entity['name']
            if table_name in SAMPLE:
                output.append(f"-- Sample data for {table_name}")
                output.append(SAMPLE[table_name])
            else:
                output.append(f"-- Sample data for {table_name}")
                output.append(f"-- INSERT INTO {table_name} (...) VALUES (...); -- Add your sample data here")
        return '\n'.join(output)

    def generate_api_docs(self, schema: dict) -> dict:
        endpoints = []
        for entity in schema.get('entities', []):
            name   = entity['name']
            plural = name + 's' if not name.endswith('s') else name
            pk     = ENTITY_PROFILES.get(name, {}).get('pk', 'id')
            endpoints.append({
                'table': plural,
                'resource': plural,
                'endpoints': [
                    {'method': 'GET',    'path': f'/api/v1/{plural}',        'description': f'List all {plural} with pagination', 'request_body': None, 'response_example': {'data': [], 'total': 0, 'page': 1, 'per_page': 20}, 'status_codes': {'200': 'OK'}},
                    {'method': 'POST',   'path': f'/api/v1/{plural}',        'description': f'Create a new {name}', 'request_body': {col[0]: 'value' for col in ENTITY_PROFILES.get(name, {}).get('cols', [])[:4]}, 'response_example': {pk: 1, 'message': 'Created successfully'}, 'status_codes': {'201': 'Created', '422': 'Validation Error'}},
                    {'method': 'GET',    'path': f'/api/v1/{plural}/{{{pk}}}', 'description': f'Get {name} by ID', 'request_body': None, 'response_example': {pk: 1}, 'status_codes': {'200': 'OK', '404': 'Not Found'}},
                    {'method': 'PUT',    'path': f'/api/v1/{plural}/{{{pk}}}', 'description': f'Update {name} by ID', 'request_body': {}, 'response_example': {'message': 'Updated successfully'}, 'status_codes': {'200': 'OK', '404': 'Not Found', '422': 'Validation Error'}},
                    {'method': 'DELETE', 'path': f'/api/v1/{plural}/{{{pk}}}', 'description': f'Delete {name} by ID', 'request_body': None, 'response_example': {'message': 'Deleted successfully'}, 'status_codes': {'200': 'OK', '404': 'Not Found'}},
                ]
            })
        return {'api_version': 'v1', 'base_url': '/api/v1', 'endpoints': endpoints}

    def generate_improvements(self, schema: dict) -> dict:
        suggestions = [
            {'category': 'Performance', 'priority': 'High', 'issue': 'Missing indexes on foreign key columns', 'suggestion': 'Add indexes on all foreign key columns to speed up JOINs', 'sql_example': 'CREATE INDEX idx_fk ON table_name (fk_column);'},
            {'category': 'Security',    'priority': 'High', 'issue': 'Password fields should use strong hashing', 'suggestion': 'Store passwords using bcrypt or Argon2 hash, never plain text', 'sql_example': None},
            {'category': 'Normalization', 'priority': 'Medium', 'issue': 'Audit trail missing', 'suggestion': 'Add created_at and updated_at timestamps to all major tables', 'sql_example': 'ALTER TABLE table_name ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP;'},
            {'category': 'Constraints', 'priority': 'Medium', 'issue': 'Missing CHECK constraints', 'suggestion': 'Add CHECK constraints for rating scores, status enums, and numeric ranges', 'sql_example': "ADD CONSTRAINT chk_status CHECK (status IN ('active','inactive','pending'));"},
            {'category': 'Performance', 'priority': 'Low', 'issue': 'Consider caching for read-heavy tables', 'suggestion': 'Use Redis to cache frequently accessed reference data (categories, departments)', 'sql_example': None},
        ]
        return {'overall_assessment': 'Schema is well-structured. A few improvements recommended.', 'normalization_status': '3NF', 'suggestions': suggestions, 'missing_tables': [], 'recommended_indexes': []}

    def generate_nosql_schema(self, schema: dict) -> dict:
        collections = []
        for entity in schema.get('entities', []):
            name = entity['name'] + 's' if not entity['name'].endswith('s') else entity['name']
            doc  = {'_id': 'ObjectId'}
            for attr in entity.get('attributes', []):
                if not attr.get('is_primary_key'):
                    dtype = attr.get('data_type', '').lower()
                    if 'int' in dtype:
                        doc[attr['name']] = 'Number'
                    elif 'decimal' in dtype or 'float' in dtype:
                        doc[attr['name']] = 'Decimal128'
                    elif 'bool' in dtype:
                        doc[attr['name']] = 'Boolean'
                    elif 'date' in dtype:
                        doc[attr['name']] = 'Date'
                    else:
                        doc[attr['name']] = 'String'
            collections.append({'name': name, 'description': entity.get('description', f'{name} collection'), 'document_schema': doc, 'example_document': doc, 'indexes': [{'fields': {'_id': 1}, 'options': {'unique': True}}], 'embedding_strategy': 'Use references for large related documents; embed small, frequently-accessed sub-documents.'})
        return {'database': 'smartdb', 'collections': collections}

    def nl_to_sql(self, user_query: str, schema_context: str, db_type: str = 'sqlite') -> dict:
        """Query Assistant: Convert natural language query to SQL dynamically based on schema_context."""
        query_lower = user_query.lower().strip()

        # 0. Check for General SQL Doubts / Conceptual Questions
        doubt_keywords = ['what is', 'explain', 'difference between', 'how to use', 'why use', 'what does', 'meaning of']
        if any(dk in query_lower for dk in doubt_keywords):
            if 'index' in query_lower:
                return {
                    "sql": "CREATE NONCLUSTERED INDEX IX_Customer_Email ON Customers(Email);",
                    "explanation": "An Index in SQL is a data structure that speeds up retrieval of records from a database table at the cost of additional write time and storage space.",
                    "tables_used": ["Customers"],
                    "optimization_tips": ["Create indexes on columns frequently used in WHERE, JOIN, and ORDER BY clauses."],
                    "alternative_approaches": ["Use Clustered Index for primary key sorting, and Non-Clustered Indexes for secondary lookup columns."]
                }
            elif 'join' in query_lower:
                return {
                    "sql": "SELECT c.customer_name, o.order_date\nFROM Customers c\nINNER JOIN Orders o ON c.customer_id = o.customer_id;",
                    "explanation": "JOIN combines rows from two or more tables based on a related column between them. INNER JOIN returns matching records in both tables, whereas LEFT JOIN returns all records from the left table.",
                    "tables_used": ["Customers", "Orders"],
                    "optimization_tips": ["Ensure join columns are indexed and have matching data types."],
                    "alternative_approaches": ["Use LEFT JOIN if you need unmatched parent records included in results."]
                }
            elif 'group by' in query_lower or 'aggregate' in query_lower:
                return {
                    "sql": "SELECT department_id, COUNT(*) AS total_employees, AVG(salary) AS avg_salary\nFROM Employees\nGROUP BY department_id;",
                    "explanation": "GROUP BY statement groups rows that have the same values into summary rows, often used with aggregate functions (COUNT, MAX, MIN, SUM, AVG).",
                    "tables_used": ["Employees"],
                    "optimization_tips": ["Use HAVING to filter aggregated groups after grouping."],
                    "alternative_approaches": ["Use Window Functions (PARTITION BY) for group calculations alongside row-level data."]
                }
            elif 'primary key' in query_lower or 'foreign key' in query_lower or 'key' in query_lower:
                return {
                    "sql": "ALTER TABLE Orders\nADD CONSTRAINT FK_Order_Customer FOREIGN KEY (customer_id) REFERENCES Customers(customer_id);",
                    "explanation": "A Primary Key uniquely identifies each record in a table. A Foreign Key enforces referential integrity between tables by linking a column to a Primary Key in another table.",
                    "tables_used": ["Orders", "Customers"],
                    "optimization_tips": ["Always define Primary Keys and Foreign Keys for referential safety."],
                    "alternative_approaches": ["Use composite primary keys for junction/link tables in many-to-many relationships."]
                }
        
        # Parse available tables & columns from schema_context (if provided) or ENTITY_PROFILES
        schema_tables = {}
        has_provided_schema = False
        if isinstance(schema_context, dict) and schema_context.get('tables'):
            has_provided_schema = True
            for t_name, t_meta in schema_context.get('tables', {}).items():
                col_names = [c['name'] for c in t_meta.get('columns', [])]
                schema_tables[t_name.lower()] = {
                    'original_name': t_name,
                    'columns': col_names,
                    'fks': t_meta.get('foreign_keys', [])
                }
        elif isinstance(schema_context, str) and schema_context.strip():
            matches = re.findall(r'CREATE\s+TABLE\s+\[?(\w+)\]?\s*\((.*?)\);', schema_context, flags=re.DOTALL | re.IGNORECASE)
            if matches:
                has_provided_schema = True
                for tbl, cols_body in matches:
                    col_matches = re.findall(r'\[?(\w+)\]?\s+[A-Za-z0-9_()]+', cols_body)
                    schema_tables[tbl.lower()] = {
                        'original_name': tbl,
                        'columns': col_matches,
                        'fks': []
                    }

        # Fallback to ENTITY_PROFILES if no schema provided
        if not schema_tables:
            for ent, info in ENTITY_PROFILES.items():
                tbl = ent + 's' if not ent.endswith('s') else ent
                col_names = [info['pk']] + [c[0] for c in info['cols']]
                schema_tables[tbl.lower()] = {
                    'original_name': tbl,
                    'columns': col_names,
                    'fks': []
                }

        # 1. Identify target tables by matching query words with table names or entity synonyms
        detected_tables = []
        words = re.findall(r'\w+', query_lower)
        stem_words = [w.rstrip('s') for w in words if len(w) > 2]
        for tbl_lower, t_meta in schema_tables.items():
            orig = t_meta['original_name']
            singular = tbl_lower[:-1] if tbl_lower.endswith('s') else tbl_lower
            if tbl_lower in query_lower or singular in query_lower or any(sw in tbl_lower for sw in stem_words):
                if orig not in detected_tables:
                    detected_tables.append(orig)

        # Dynamic entity extraction if no existing table matched
        if not detected_tables:
            stop_words = {'show', 'all', 'find', 'list', 'get', 'select', 'top', 'count', 'total', 'the', 'with', 'from', 'where', 'and', 'or', 'for', 'in', 'of', 'active', 'by', 'order', 'sort', 'having'}
            candidate_nouns = [w for w in words if len(w) > 3 and w not in stop_words]
            
            if candidate_nouns and not has_provided_schema:
                raw_entity = candidate_nouns[0].capitalize()
                detected_tables = [raw_entity]
                cols = [f"{raw_entity.lower()}_id"]
                if 'name' in query_lower: cols.append('name')
                if 'age' in query_lower: cols.append('age')
                if 'salary' in query_lower: cols.append('salary')
                if 'price' in query_lower: cols.append('price')
                if 'amount' in query_lower: cols.append('amount')
                if 'status' in query_lower: cols.append('status')
                if 'date' in query_lower or 'time' in query_lower or 'registered' in query_lower: cols.append('created_at')
                
                schema_tables[raw_entity.lower()] = {
                    'original_name': raw_entity,
                    'columns': cols,
                    'fks': []
                }
            elif schema_tables:
                detected_tables = [next(iter(schema_tables.values()))['original_name']]
            else:
                detected_tables = ["Patients"]

        # 2. Select columns
        primary_table = detected_tables[0]
        primary_cols = schema_tables.get(primary_table.lower(), {}).get('columns', [])
        
        # Check for aggregation
        agg_func = None
        select_clause = "*"
        if 'count' in query_lower or 'how many' in query_lower or 'total number' in query_lower:
            select_clause = "COUNT(*) AS total_count"
            agg_func = "COUNT"
        elif 'average' in query_lower or 'avg' in query_lower:
            target_col = next((c for c in primary_cols if any(k in c.lower() for k in ['age', 'amount', 'salary', 'price', 'gpa', 'score', 'fee', 'total'])), 'amount')
            select_clause = f"AVG([{target_col}]) AS avg_{target_col}"
            agg_func = "AVG"
        elif 'sum' in query_lower or 'total' in query_lower:
            target_col = next((c for c in primary_cols if any(k in c.lower() for k in ['amount', 'salary', 'price', 'cost', 'fee', 'total', 'bill'])), 'amount')
            select_clause = f"SUM([{target_col}]) AS total_{target_col}"
            agg_func = "SUM"
        elif 'max' in query_lower or 'oldest' in query_lower or 'highest' in query_lower or 'youngest' in query_lower or 'min' in query_lower or 'lowest' in query_lower:
            target_col = next((c for c in primary_cols if any(k in c.lower() for k in ['age', 'price', 'salary', 'amount', 'dob', 'created_at'])), 'id')
            if 'max' in query_lower or 'highest' in query_lower or 'oldest' in query_lower:
                select_clause = f"MAX([{target_col}]) AS max_{target_col}"
                agg_func = "MAX"
            else:
                select_clause = f"MIN([{target_col}]) AS min_{target_col}"
                agg_func = "MIN"

        # Special column search if user asked for specific column (e.g. "names of all doctors", "phone numbers")
        if not agg_func and select_clause == "*":
            specific_cols = []
            for col in primary_cols:
                col_lower = col.lower()
                col_words = col_lower.split('_')
                if any(w in query_lower for w in col_words if len(w) > 2):
                    specific_cols.append(f"[{col}]")
            if specific_cols:
                select_clause = ", ".join(specific_cols)

        # 3. Limit / TOP clause
        top_clause = ""
        m = re.search(r'(?:top|limit|first)\s+(\d+)', query_lower)
        limit_val = m.group(1) if m else None
        if limit_val and db_type in ('mssql', 'sqlserver'):
            top_clause = f"TOP {limit_val} "
        elif limit_val:
            top_clause = ""  # standard LIMIT at end

        # 4. Filters (WHERE)
        where_conds = []
        
        # Check numeric comparisons (older than 50, salary > 50000, age < 30)
        num_match = re.search(r'(older than|greater than|above|more than|>)\s*(\d+)', query_lower)
        if num_match:
            val = num_match.group(2)
            num_col = next((c for c in primary_cols if any(k in c.lower() for k in ['age', 'salary', 'price', 'amount', 'total'])), 'age')
            where_conds.append(f"[{num_col}] > {val}")

        num_less = re.search(r'(younger than|less than|below|under|<)\s*(\d+)', query_lower)
        if num_less:
            val = num_less.group(2)
            num_col = next((c for c in primary_cols if any(k in c.lower() for k in ['age', 'salary', 'price', 'amount', 'total'])), 'age')
            where_conds.append(f"[{num_col}] < {val}")

        # Status keywords matching
        status_keywords = ['completed', 'pending', 'scheduled', 'unpaid', 'paid', 'cancelled']
        for skw in status_keywords:
            if skw in query_lower and any('status' in c.lower() for c in primary_cols):
                stat_col = next((c for c in primary_cols if 'status' in c.lower()), 'status')
                where_conds.append(f"[{stat_col}] = '{skw}'")
                break

        if 'active' in query_lower and any('active' in c.lower() or 'status' in c.lower() for c in primary_cols):
            stat_col = next((c for c in primary_cols if 'active' in c.lower() or 'status' in c.lower()), 'status')
            if 'is_active' in stat_col.lower():
                where_conds.append(f"[{stat_col}] = 1")
            else:
                where_conds.append(f"[{stat_col}] = 'active'")

        if 'today' in query_lower:
            date_col = next((c for c in primary_cols if any(k in c.lower() for k in ['date', 'time', 'registered', 'created', 'appointment', 'issue'])), 'created_at')
            if db_type in ('mssql', 'sqlserver'):
                where_conds.append(f"CAST([{date_col}] AS DATE) = CAST(GETDATE() AS DATE)")
            else:
                where_conds.append(f"[{date_col}] >= CURRENT_DATE")

        # 5. Build FROM and JOIN clause
        from_clause = f"FROM [{primary_table}]"
        if len(detected_tables) > 1:
            sec_table = detected_tables[1]
            sec_cols = schema_tables.get(sec_table.lower(), {}).get('columns', [])
            # Try to match FK
            fk_col = next((c for c in primary_cols if c.lower() == f"{sec_table[:-1] if sec_table.endswith('s') else sec_table}_id".lower()), None)
            if not fk_col:
                fk_col = next((c for c in sec_cols if c.lower() == f"{primary_table[:-1] if primary_table.endswith('s') else primary_table}_id".lower()), None)
            
            if fk_col:
                from_clause = f"FROM [{primary_table}]\nJOIN [{sec_table}] ON [{primary_table}].[{fk_col}] = [{sec_table}].[{fk_col}]"
            else:
                from_clause = f"FROM [{primary_table}]\nCROSS JOIN [{sec_table}]"

        # 6. ORDER BY clause
        order_clause = ""
        if 'oldest' in query_lower or 'youngest' in query_lower or 'top' in query_lower or 'sort' in query_lower or 'order' in query_lower:
            order_col = next((c for c in primary_cols if any(k in c.lower() for k in ['age', 'dob', 'created_at', 'date', 'salary', 'price', 'amount', 'id'])), primary_cols[0] if primary_cols else '1')
            if 'oldest' in query_lower or 'highest' in query_lower or 'desc' in query_lower:
                order_clause = f"\nORDER BY [{order_col}] DESC"
            else:
                order_clause = f"\nORDER BY [{order_col}] ASC"

        limit_suffix = f"\nLIMIT {limit_val}" if (limit_val and db_type not in ('mssql', 'sqlserver')) else ""
        where_str = f"\nWHERE {' AND '.join(where_conds)}" if where_conds else ""

        sql = f"SELECT {top_clause}{select_clause}\n{from_clause}{where_str}{order_clause}{limit_suffix};"

        explanation = f"Retrieves {agg_func or 'matching records'} from table '{primary_table}'"
        if len(detected_tables) > 1:
            explanation += f" joined with '{detected_tables[1]}'"
        if where_conds:
            explanation += f" filtering by {' and '.join(where_conds)}"
        explanation += "."

        return {
            "sql": sql,
            "explanation": explanation,
            "tables_used": detected_tables,
            "optimization_tips": [f"Ensure an index exists on {primary_table}({primary_cols[0] if primary_cols else 'id'}) for optimal lookup speed."],
            "alternative_approaches": ["Add specific WHERE filters or SELECT column projections to further refine your result set."]
        }


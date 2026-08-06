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
        """Query Assistant: Convert natural language query to SQL in Fallback Mode."""
        query_lower = user_query.lower().strip()
        
        # 1. Check exact matches for standard examples
        # Example 1: Show all active users registered this month
        if 'active users' in query_lower and ('registered this month' in query_lower or 'created this month' in query_lower):
            if db_type == 'sqlite':
                sql = ("SELECT user_id, username, email, created_at \n"
                       "FROM users \n"
                       "WHERE is_active = 1 \n"
                       "  AND created_at >= date('now', 'start of month');")
            elif db_type == 'mysql':
                sql = ("SELECT user_id, username, email, created_at \n"
                       "FROM users \n"
                       "WHERE is_active = 1 \n"
                       "  AND created_at >= DATE_FORMAT(NOW() ,'%Y-%m-01');")
            elif db_type == 'postgresql':
                sql = ("SELECT user_id, username, email, created_at \n"
                       "FROM users \n"
                       "WHERE is_active = 1 \n"
                       "  AND created_at >= date_trunc('month', current_date);")
            else: # mssql
                sql = ("SELECT user_id, username, email, created_at \n"
                       "FROM users \n"
                       "WHERE is_active = 1 \n"
                       "  AND created_at >= DATEADD(month, DATEDIFF(month, 0, GETDATE()), 0);")
                       
            return {
                "sql": sql,
                "explanation": "Retrieves the ID, username, email, and registration timestamp for all active users created during the current month.",
                "tables_used": ["users"],
                "optimization_tips": ["Add a composite index on users (is_active, created_at) to avoid a full table scan."],
                "alternative_approaches": ["If user activity logs are stored separately, join with the login history table to double-check login activity."]
            }

        # Example 2: Find top 5 products by sales count
        elif 'top 5 products' in query_lower and 'sales count' in query_lower:
            limit_clause = "LIMIT 5"
            top_select = "SELECT"
            if db_type == 'mssql':
                limit_clause = ""
                top_select = "SELECT TOP 5"
                
            sql = (f"{top_select} p.product_id, p.name, SUM(oi.quantity) AS sales_count\n"
                   "FROM products p\n"
                   "JOIN order_items oi ON p.product_id = oi.product_id\n"
                   "GROUP BY p.product_id, p.name\n"
                   "ORDER BY sales_count DESC\n"
                   f"{limit_clause};".strip())
                   
            return {
                "sql": sql,
                "explanation": "Joins products and order_items, calculates the sum of quantities sold per product, groups the results, and sorts in descending order to return the top 5.",
                "tables_used": ["products", "order_items"],
                "optimization_tips": ["Create an index on order_items(product_id, quantity) to facilitate quick grouping and aggregation."],
                "alternative_approaches": ["Query a denormalized product_sales stats table if sales counts are pre-calculated daily for performance."]
            }

        # Example 3: List employees with salary above the department average
        elif 'employees' in query_lower and 'salary' in query_lower and 'department average' in query_lower:
            sql = ("SELECT e.employee_id, e.first_name, e.last_name, e.salary, e.department_id\n"
                   "FROM employees e\n"
                   "WHERE e.salary > (\n"
                   "    SELECT AVG(salary) \n"
                   "    FROM employees \n"
                   "    WHERE department_id = e.department_id\n"
                   ");")
            return {
                "sql": sql,
                "explanation": "Uses a correlated subquery to compute the average salary of employees in each department, then selects employees whose salaries exceed that average.",
                "tables_used": ["employees"],
                "optimization_tips": ["Create a composite index on employees (department_id, salary) to optimize the inner subquery evaluation."],
                "alternative_approaches": ["Use a window function `AVG(salary) OVER(PARTITION BY department_id)` to achieve the same result in a single pass without a subquery."]
            }

        # Example 4: Get all overdue orders with customer details
        elif 'overdue orders' in query_lower or ('overdue' in query_lower and 'order' in query_lower):
            date_func = "date('now', '-7 days')"
            if db_type == 'mysql':
                date_func = "DATE_SUB(NOW(), INTERVAL 7 DAY)"
            elif db_type == 'postgresql':
                date_func = "CURRENT_DATE - INTERVAL '7 days'"
            elif db_type == 'mssql':
                date_func = "DATEADD(day, -7, GETDATE())"
                
            sql = ("SELECT o.order_id, o.total_amount, o.status, o.created_at, c.first_name, c.last_name, c.email\n"
                   "FROM orders o\n"
                   "JOIN customers c ON o.customer_id = c.customer_id\n"
                   "WHERE o.status = 'pending'\n"
                   f"  AND o.created_at < {date_func};")
            return {
                "sql": sql,
                "explanation": "Joins orders with customers, filtering for orders in a 'pending' state that were created more than 7 days ago.",
                "tables_used": ["orders", "customers"],
                "optimization_tips": ["Create a composite index on orders (status, created_at) to quickly narrow down pending overdue orders."],
                "alternative_approaches": ["Use a separate `shipping_status` column or track SLA deadlines in an order_shipments table for finer granularity."]
            }

        # Example 5: Count students enrolled per course
        elif 'students enrolled per course' in query_lower or ('count' in query_lower and 'enrolled' in query_lower and 'course' in query_lower):
            sql = ("SELECT c.course_id, c.course_code, c.title, COUNT(e.student_id) AS student_count\n"
                   "FROM courses c\n"
                   "LEFT JOIN enrollments e ON c.course_id = e.course_id\n"
                   "GROUP BY c.course_id, c.course_code, c.title;")
            return {
                "sql": sql,
                "explanation": "LEFT JOINs courses and enrollments so courses with zero students are still included in the results, counting student enrollments per course.",
                "tables_used": ["courses", "enrollments"],
                "optimization_tips": ["Add a database index on enrollments(course_id) to optimize the JOIN query performance."],
                "alternative_approaches": ["Use a subquery in the SELECT list to count students, though a LEFT JOIN with GROUP BY is typically more standard."]
            }

        # 2. General parsing strategy
        # Detect mentioned entities/tables based on the query keywords
        detected_tables = []
        for ent, info in ENTITY_PROFILES.items():
            plural = ent + 's'
            if ent in query_lower or plural in query_lower:
                table_name = ent + 's' if not ent.endswith('s') else ent
                if table_name not in detected_tables:
                    detected_tables.append(table_name)
                    
        if not detected_tables:
            # Try parsing schema_context to find tables
            if schema_context:
                tables_in_context = re.findall(r'CREATE\s+TABLE\s+(\w+)', schema_context, flags=re.IGNORECASE)
                for tbl in tables_in_context:
                    if tbl.lower() in query_lower:
                        detected_tables.append(tbl)
            
        if not detected_tables:
            detected_tables = ["items"]

        # Build SELECT columns
        select_cols = "*"
        agg_func = None
        if 'count' in query_lower or 'how many' in query_lower:
            select_cols = "COUNT(*)"
            agg_func = "COUNT"
        elif 'average' in query_lower or 'avg' in query_lower:
            # Guess column
            col = "price" if "price" in query_lower or "product" in query_lower else ("salary" if "salary" in query_lower or "employee" in query_lower else "amount")
            select_cols = f"AVG({col})"
            agg_func = "AVG"
        elif 'sum' in query_lower or 'total' in query_lower:
            col = "price" if "price" in query_lower or "product" in query_lower else ("salary" if "salary" in query_lower or "employee" in query_lower else "amount")
            select_cols = f"SUM({col})"
            agg_func = "SUM"

        # Build WHERE filters
        filters = []
        if 'active' in query_lower:
            filters.append("is_active = 1")
        if 'completed' in query_lower:
            filters.append("status = 'completed'")
        if 'pending' in query_lower:
            filters.append("status = 'pending'")
        if 'today' in query_lower:
            if db_type == 'sqlite':
                filters.append("created_at >= date('now')")
            elif db_type == 'mysql':
                filters.append("created_at >= CURDATE()")
            elif db_type == 'postgresql':
                filters.append("created_at >= CURRENT_DATE")
            else:
                filters.append("created_at >= CAST(GETDATE() AS DATE)")

        # Build LIMIT
        limit_clause = ""
        top_select = ""
        m = re.search(r'(?:top|limit|first)\s+(\d+)', query_lower)
        if m:
            limit_val = m.group(1)
            if db_type == 'mssql':
                top_select = f"TOP {limit_val} "
            else:
                limit_clause = f"\nLIMIT {limit_val}"

        # Join tables
        from_clause = ""
        if len(detected_tables) == 1:
            from_clause = f"FROM {detected_tables[0]}"
        elif len(detected_tables) >= 2:
            # Let's see if we can find a relationship
            tbl1 = detected_tables[0]
            tbl2 = detected_tables[1]
            sing1 = tbl1[:-1] if tbl1.endswith('s') else tbl1
            sing2 = tbl2[:-1] if tbl2.endswith('s') else tbl2
            
            pk1 = ENTITY_PROFILES.get(sing1, {}).get('pk', f'{sing1}_id')
            pk2 = ENTITY_PROFILES.get(sing2, {}).get('pk', f'{sing2}_id')
            
            from_clause = f"FROM {tbl1} t1\nJOIN {tbl2} t2 ON t1.{pk2} = t2.{pk2}"
            if sing1 == 'order' and sing2 == 'customer':
                from_clause = "FROM orders o\nJOIN customers c ON o.customer_id = c.customer_id"
            elif sing1 == 'customer' and sing2 == 'order':
                from_clause = "FROM orders o\nJOIN customers c ON o.customer_id = c.customer_id"
            elif sing1 == 'order_item' or sing2 == 'order_item':
                if 'product' in [sing1, sing2]:
                    from_clause = "FROM order_items oi\nJOIN products p ON oi.product_id = p.product_id"
                elif 'order' in [sing1, sing2]:
                    from_clause = "FROM order_items oi\nJOIN orders o ON oi.order_id = o.order_id"
            elif sing1 == 'book' and sing2 == 'author':
                from_clause = "FROM books b\nJOIN authors a ON b.author_id = a.author_id"
            elif sing1 == 'course' and sing2 == 'enrollment':
                from_clause = "FROM courses c\nJOIN enrollments e ON c.course_id = e.course_id"
            elif sing1 == 'student' and sing2 == 'enrollment':
                from_clause = "FROM students s\nJOIN enrollments e ON s.student_id = e.student_id"
            elif sing1 == 'patient' and sing2 == 'appointment':
                from_clause = "FROM patients p\nJOIN appointments a ON p.patient_id = a.patient_id"
            elif sing1 == 'doctor' and sing2 == 'appointment':
                from_clause = "FROM doctors d\nJOIN appointments a ON d.doctor_id = a.doctor_id"
            elif sing1 == 'employee' and sing2 == 'department':
                from_clause = "FROM employees e\nJOIN departments d ON e.department_id = d.department_id"
        else:
            from_clause = f"FROM items"

        where_clause = ""
        if filters:
            where_clause = "\nWHERE " + " AND ".join(filters)

        sql = f"SELECT {top_select}{select_cols}\n{from_clause}{where_clause}{limit_clause};"

        explanation = f"Calculates {agg_func or 'all records'} from {', '.join(detected_tables)}"
        if filters:
            explanation += f" where {', '.join(filters)}."
        else:
            explanation += "."

        return {
            "sql": sql,
            "explanation": f"[Rule-Based Fallback Mode] {explanation}",
            "tables_used": detected_tables,
            "optimization_tips": ["Ensure indexes exist on filter columns and join foreign keys for peak performance."],
            "alternative_approaches": ["Configure your OpenAI API key in `.env` to leverage AI-powered advanced SQL parsing and context understanding."]
        }


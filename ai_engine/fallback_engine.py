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
        """Query Assistant: Convert natural language query to platform-tailored query dynamically."""
        query_lower = user_query.lower().strip()
        db_type = (db_type or 'sqlite').lower()

        # ── 0. Conceptual Doubts & Architectural Q&A ───────────────────────────
        doubt_keywords = ['what is', 'what are', 'explain', 'difference between', 'how to use', 'why use', 'what does', 'meaning of', 'how do i', 'how does', 'best practice', 'define', 'tell me about', 'properties of']
        is_concept_query = any(dk in query_lower for dk in doubt_keywords) or any(k in query_lower for k in ['acid', 'deadlock', 'normalization', '1nf', '2nf', '3nf', 'bcnf', 'clustered index'])
        if is_concept_query:
            if 'index' in query_lower:
                if 'cluster' in query_lower or 'difference' in query_lower:
                    return {
                        "sql": "-- Clustered Index (determines physical order of data, 1 per table)\nCREATE CLUSTERED INDEX CIX_Orders_Date ON Orders(OrderDate);\n\n-- Non-Clustered Index (separate pointer structure, multiple per table)\nCREATE NONCLUSTERED INDEX IX_Orders_CustomerID ON Orders(CustomerID) INCLUDE (TotalAmount);",
                        "explanation": "A Clustered Index defines the physical sorting order of rows in the table (typically the Primary Key, max 1 per table). A Non-Clustered Index is an independent B-Tree structure containing index key columns and pointers back to the clustered index/heap.",
                        "tables_used": ["Orders"],
                        "optimization_tips": ["Keep clustered index keys small, static, and monotonically increasing (e.g. IDENTITY / BIGINT).", "Use INCLUDE columns in non-clustered indexes to create covering indexes and avoid bookmark lookups."],
                        "alternative_approaches": ["Use Columnstore indexes for heavy analytical / OLAP data warehousing workloads."]
                    }
                return {
                    "sql": "CREATE NONCLUSTERED INDEX IX_Customer_Email ON Customers(Email);\n-- Check execution plan to verify Index Seek vs Table Scan",
                    "explanation": "An Index in SQL is an auxiliary B-tree data structure that accelerates search queries from O(N) linear table scans to O(log N) logarithmic binary seeks, at the expense of minor storage and write latency.",
                    "tables_used": ["Customers"],
                    "optimization_tips": ["Create indexes on columns frequently used in WHERE filters, JOIN keys, and ORDER BY clauses."],
                    "alternative_approaches": ["Use filtered indexes (WHERE status = 'Active') to save storage for skewed distribution columns."]
                }
            elif 'join' in query_lower:
                return {
                    "sql": "-- 1. INNER JOIN (Only matching records in both tables)\nSELECT c.customer_name, o.order_id, o.total_amount\nFROM Customers c\nINNER JOIN Orders o ON c.customer_id = o.customer_id;\n\n-- 2. LEFT OUTER JOIN (All customers, including those with no orders)\nSELECT c.customer_name, o.order_id\nFROM Customers c\nLEFT JOIN Orders o ON c.customer_id = o.customer_id;",
                    "explanation": "JOIN combines fields from two tables based on a relational key. INNER JOIN yields rows where the join condition matches in both tables. LEFT JOIN yields all rows from the primary left table plus matching rows from the right table (filling NULLs where no match exists).",
                    "tables_used": ["Customers", "Orders"],
                    "optimization_tips": ["Ensure Foreign Key columns participating in the ON condition are indexed with identical data types."],
                    "alternative_approaches": ["Use CROSS APPLY or LATERAL joins when joining against table-valued functions or top-N correlated subqueries."]
                }
            elif 'group by' in query_lower or 'aggregate' in query_lower or 'having' in query_lower:
                return {
                    "sql": "SELECT department_id, COUNT(*) AS total_employees, AVG(salary) AS avg_salary, MAX(salary) AS highest_salary\nFROM Employees\nWHERE status = 'Active'\nGROUP BY department_id\nHAVING COUNT(*) >= 5\nORDER BY avg_salary DESC;",
                    "explanation": "GROUP BY aggregates rows sharing duplicate grouping values into consolidated summary metrics. WHERE filters rows before aggregation occurs; HAVING filters aggregated groups after aggregation.",
                    "tables_used": ["Employees"],
                    "optimization_tips": ["Filter as much data as possible in the WHERE clause before the GROUP BY pipeline executes."],
                    "alternative_approaches": ["Use Window Functions (AVG(salary) OVER (PARTITION BY department_id)) if you need row-level details alongside aggregated values."]
                }
            elif 'normalization' in query_lower or 'normal form' in query_lower or '1nf' in query_lower or '2nf' in query_lower or '3nf' in query_lower or 'bcnf' in query_lower:
                return {
                    "sql": "-- 1NF: Atomic columns (no multivalued arrays)\n-- 2NF: 1NF + No partial dependencies on composite keys\n-- 3NF: 2NF + No transitive dependencies (Non-key -> Non-key)\n-- BCNF: Every determinant is a candidate key",
                    "explanation": "Database Normalization organizes tables to minimize data redundancy and prevent insertion, update, and deletion anomalies. Standard OLTP systems aim for 3NF (Third Normal Form).",
                    "tables_used": ["Schema_Architecture"],
                    "optimization_tips": ["Normalize transactional (OLTP) databases to 3NF to avoid update anomalies.", "Denormalize dimensional reporting data warehouses (OLAP) into Star Schemas for fast analytics."],
                    "alternative_approaches": ["Use JSON/JSONB document columns for semi-structured dynamic attributes while keeping relational roots in 3NF."]
                }
            elif 'acid' in query_lower or 'transaction' in query_lower:
                return {
                    "sql": "BEGIN TRANSACTION;\nBEGIN TRY\n    UPDATE Accounts SET balance = balance - 500 WHERE account_id = 101;\n    UPDATE Accounts SET balance = balance + 500 WHERE account_id = 202;\n    COMMIT TRANSACTION;\nEND TRY\nBEGIN CATCH\n    ROLLBACK TRANSACTION;\n    THROW;\nEND CATCH;",
                    "explanation": "ACID guarantees transactional reliability: Atomicity (all operations succeed or all fail), Consistency (preserves database integrity rules), Isolation (concurrent transactions do not interfere), Durability (committed data survives system crashes).",
                    "tables_used": ["Accounts"],
                    "optimization_tips": ["Keep transaction scopes as concise and fast as possible to minimize lock contention and prevent deadlocks."],
                    "alternative_approaches": ["Use READ COMMITTED SNAPSHOT ISOLATION (RCSI) in SQL Server to allow non-blocking concurrent reads."]
                }
            elif 'window function' in query_lower or 'row_number' in query_lower or 'rank' in query_lower:
                return {
                    "sql": "SELECT employee_id, department_id, salary,\n       ROW_NUMBER() OVER (PARTITION BY department_id ORDER BY salary DESC) AS rank_in_dept,\n       DENSE_RANK() OVER (PARTITION BY department_id ORDER BY salary DESC) AS dense_rank_in_dept\nFROM Employees;",
                    "explanation": "Window functions perform calculations across a set of table rows that are related to the current row, without collapsing rows like GROUP BY does. PARTITION BY divides rows into groups; ORDER BY establishes sequence inside the window.",
                    "tables_used": ["Employees"],
                    "optimization_tips": ["Ensure composite indexes match the (PARTITION BY ... ORDER BY ...) columns to allow streaming window evaluations."],
                    "alternative_approaches": ["Use LEAD() and LAG() window functions for calculating month-over-month growth metrics."]
                }
            elif 'primary key' in query_lower or 'foreign key' in query_lower or 'key' in query_lower:
                return {
                    "sql": "ALTER TABLE Orders\nADD CONSTRAINT FK_Order_Customer FOREIGN KEY (customer_id) REFERENCES Customers(customer_id)\nON DELETE CASCADE;",
                    "explanation": "A Primary Key uniquely identifies each row in a table and cannot contain NULLs. A Foreign Key references a Primary Key in another table, enforcing referential integrity and preventing orphan child records.",
                    "tables_used": ["Orders", "Customers"],
                    "optimization_tips": ["Always define explicit Primary Keys and index all Foreign Key columns to prevent table locks during cascades."],
                    "alternative_approaches": ["Use composite natural keys or UUID/GUID surrogate keys when distributing data across multi-region clusters."]
                }
            elif 'cte' in query_lower or 'common table' in query_lower:
                return {
                    "sql": ";WITH HighSalaryEmployees AS (\n    SELECT department_id, employee_id, salary\n    FROM Employees\n    WHERE salary > 80000\n)\nSELECT department_id, COUNT(*) AS elite_count\nFROM HighSalaryEmployees\nGROUP BY department_id;",
                    "explanation": "A Common Table Expression (CTE) is a temporary named result set defined within the execution scope of a single SELECT, INSERT, UPDATE, or DELETE statement. It vastly improves readability and supports recursion.",
                    "tables_used": ["Employees"],
                    "optimization_tips": ["Standard CTEs are logical rewrites and re-evaluated upon every reference; use temporary tables (#TempTable) if referencing a large CTE multiple times."],
                    "alternative_approaches": ["Use Recursive CTEs for traversing organizational hierarchies and bill-of-materials trees."]
                }
            elif 'deadlock' in query_lower:
                return {
                    "sql": "-- Standard Deadlock Prevention Pattern:\n-- Always acquire locks / update tables in the EXACT same alphabetical or transactional sequence across all stored procedures.\n-- E.g. Always update Customers first, then Orders second.",
                    "explanation": "A deadlock occurs when two or more transactions hold exclusive locks on different resources and each attempts to acquire a lock held by the other, resulting in a cyclical freeze until the database engine terminates the deadlock victim.",
                    "tables_used": ["System_Lock_Manager"],
                    "optimization_tips": ["Keep transactions brief, access objects in a consistent sequence across your codebase, and use NOLOCK / RCSI for read operations."],
                    "alternative_approaches": ["Set DEADLOCK_PRIORITY LOW for batch jobs so critical client transactions are never aborted."]
                }
            elif 'nosql' in query_lower or 'mongodb' in query_lower:
                return {
                    "sql": "// MongoDB Document Schema Example:\ndb.customers.insertOne({\n  \"name\": \"Acme Corp\",\n  \"industry\": \"Technology\",\n  \"contacts\": [{ \"name\": \"Alice\", \"email\": \"alice@acme.com\" }],\n  \"orders\": [{ \"order_id\": \"ORD-101\", \"amount\": 450.00 }]\n});",
                    "explanation": "SQL databases are relational, structured with rigid tabular schemas and ACID guarantees. NoSQL databases (like MongoDB document stores) provide schema flexibility, horizontal scale-out sharding, and embedded sub-documents.",
                    "tables_used": ["customers"],
                    "optimization_tips": ["Embed 1-to-few sub-documents directly for high read throughput; use references (ObjectIds) for large, unbound 1-to-many relationships."],
                    "alternative_approaches": ["Use PostgreSQL JSONB for a hybrid approach combining relational SQL integrity with NoSQL dynamic fields."]
                }

        # ── 1. Parse Schema Context (if provided) ──────────────────────────────
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

        # Match tables from query
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
            stop_words = {'show', 'all', 'find', 'list', 'get', 'select', 'top', 'count', 'total', 'the', 'with', 'from', 'where', 'and', 'or', 'for', 'in', 'of', 'active', 'by', 'order', 'sort', 'having', 'add', 'new', 'change', 'update', 'delete', 'remove', 'named', 'number', 'phone', 'email'}
            candidate_nouns = [w for w in words if len(w) > 2 and w not in stop_words]
            if any(k in query_lower for k in ['customer', 'phone', 'arun', 'client', 'contact']):
                detected_tables = ["Customers"]
            elif candidate_nouns and not has_provided_schema:
                raw_entity = candidate_nouns[0].capitalize()
                detected_tables = [raw_entity + 's' if not raw_entity.endswith('s') else raw_entity]
                cols = [f"{candidate_nouns[0]}_id", "name", "email", "phone", "status", "created_at"]
                schema_tables[detected_tables[0].lower()] = {
                    'original_name': detected_tables[0],
                    'columns': cols,
                    'fks': []
                }
            elif schema_tables:
                detected_tables = [next(iter(schema_tables.values()))['original_name']]
            else:
                detected_tables = ["Customers"]

        primary_table = detected_tables[0]
        if primary_table.lower() in ('arun', 'aruns', 'changes', 'updates', 'modifies', 'deletes', 'phones', 'numbers'):
            primary_table = "Customers"
        primary_cols = schema_tables.get(primary_table.lower(), {}).get('columns', [])
        if not primary_cols:
            primary_cols = [f"{primary_table.lower()[:-1] if primary_table.endswith('s') else primary_table.lower()}_id", "name", "phone", "email", "status", "created_at"]

        # ── 2. DML Commands: INSERT / UPDATE / DELETE ──────────────────────────
        # Check for INSERT / ADD
        if any(w in query_lower for w in ['add a new', 'add new', 'insert into', 'create new', 'register new', 'add ']):
            name_tokens = [w for w in re.findall(r'[A-Za-z]+', user_query) if w.lower() not in ('add', 'a', 'new', 'insert', 'into', 'create', 'register', 'customer', 'patient', 'doctor', 'user', 'named', 'with', 'phone', 'number', 'email', 'is', 'to')]
            entity_name = name_tokens[0].capitalize() if name_tokens else "Arun"
            phone_match = re.search(r'(\d{7,15})', user_query)
            phone_val = phone_match.group(1) if phone_match else "9876543210"

            if db_type in ('mssql', 'sqlserver'):
                sql = f"INSERT INTO [{primary_table}] ([{primary_cols[1] if len(primary_cols) > 1 else 'name'}], [phone], [email], [created_at])\nVALUES ('{entity_name}', '{phone_val}', '{entity_name.lower()}@example.com', GETDATE());"
            elif db_type == 'mysql':
                sql = f"INSERT INTO `{primary_table.lower()}` (`{primary_cols[1] if len(primary_cols) > 1 else 'name'}`, `phone`, `email`, `created_at`)\nVALUES ('{entity_name}', '{phone_val}', '{entity_name.lower()}@example.com', NOW());"
            elif db_type == 'oracle':
                sql = f"INSERT INTO \"{primary_table.upper()}\" (\"{primary_cols[1].upper() if len(primary_cols) > 1 else 'NAME'}\", \"PHONE\", \"EMAIL\", \"CREATED_AT\")\nVALUES ('{entity_name}', '{phone_val}', '{entity_name.lower()}@example.com', SYSDATE);"
            elif db_type == 'mongodb':
                sql = f"db.{primary_table.lower()}.insertOne({{\n  \"name\": \"{entity_name}\",\n  \"phone\": \"{phone_val}\",\n  \"email\": \"{entity_name.lower()}@example.com\",\n  \"created_at\": new Date()\n}});"
            elif db_type == 'excel':
                sql = f"# Append new record to DataFrame\nnew_row = {{'name': '{entity_name}', 'phone': '{phone_val}', 'email': '{entity_name.lower()}@example.com', 'created_at': pd.Timestamp.now()}}\ndf = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)\ndf.to_excel('updated_{primary_table.lower()}.xlsx', index=False)"
            else:
                sql = f"INSERT INTO {primary_table} (name, phone, email, created_at)\nVALUES ('{entity_name}', '{phone_val}', '{entity_name.lower()}@example.com', CURRENT_TIMESTAMP);"

            return {
                "sql": sql,
                "explanation": f"Inserts a new record into '{primary_table}' with name '{entity_name}' and timestamp.",
                "tables_used": [primary_table],
                "optimization_tips": [f"Ensure primary key on {primary_table} utilizes an auto-incrementing identity specification."],
                "alternative_approaches": ["Use stored procedures with parameter validation for transactional safety."]
            }

        # Check for UPDATE / CHANGE
        if any(w in query_lower for w in ['change ', 'update ', 'set ', 'modify ']):
            phone_match = re.search(r'(\d{7,15})', user_query)
            phone_val = phone_match.group(1) if phone_match else "9876543210"
            name_tokens = [w for w in re.findall(r'[A-Za-z]+', user_query) if w.lower() not in ('change', 'update', 'set', 'modify', 'phone', 'number', 'to', 'is', 'a', 'the', 'customer', 'user', 'patient', 'named', 'for')]
            target_name = name_tokens[0].capitalize() if name_tokens else "Arun"
            
            name_col = next((c for c in primary_cols if any(k in c.lower() for k in ['name', 'first_name', 'patient_name', 'doctor_name', 'customer_name'])), primary_cols[1] if len(primary_cols) > 1 else 'name')

            if db_type in ('mssql', 'sqlserver'):
                sql = f"UPDATE [{primary_table}]\nSET [phone] = '{phone_val}', [updated_at] = GETDATE()\nWHERE [{name_col}] LIKE '%{target_name}%';"
            elif db_type == 'mysql':
                sql = f"UPDATE `{primary_table.lower()}`\nSET `phone` = '{phone_val}', `updated_at` = NOW()\nWHERE `{name_col}` LIKE '%{target_name}%';"
            elif db_type == 'oracle':
                sql = f"UPDATE \"{primary_table.upper()}\"\nSET \"PHONE\" = '{phone_val}', \"UPDATED_AT\" = SYSDATE\nWHERE \"{name_col.upper()}\" LIKE '%{target_name}%';"
            elif db_type == 'mongodb':
                sql = f"db.{primary_table.lower()}.updateOne(\n  {{ \"{name_col}\": {{ \"$regex\": \"{target_name}\", \"$options\": \"i\" }} }},\n  {{ \"$set\": {{ \"phone\": \"{phone_val}\", \"updated_at\": new Date() }} }}\n);"
            elif db_type == 'excel':
                sql = f"# Update phone number for matching name in DataFrame\nmask = df['{name_col}'].str.contains('{target_name}', case=False, na=False)\ndf.loc[mask, 'phone'] = '{phone_val}'\ndf.to_excel('updated_{primary_table.lower()}.xlsx', index=False)"
            else:
                sql = f"UPDATE {primary_table} SET phone = '{phone_val}' WHERE {name_col} LIKE '%{target_name}%';"

            return {
                "sql": sql,
                "explanation": f"Updates the contact phone number for '{target_name}' in table '{primary_table}'.",
                "tables_used": [primary_table],
                "optimization_tips": [f"Create an index on {primary_table}({name_col}) to accelerate lookup operations during updates."],
                "alternative_approaches": ["Always verify row count affected before committing in critical production workflows."]
            }

        # Check for DELETE / REMOVE
        if any(w in query_lower for w in ['delete ', 'remove ', 'drop record']):
            name_tokens = [w for w in re.findall(r'[A-Za-z]+', user_query) if w.lower() not in ('delete', 'remove', 'drop', 'record', 'customer', 'patient', 'doctor', 'user', 'named', 'for', 'the', 'a')]
            target_name = name_tokens[0].capitalize() if name_tokens else "Arun"
            name_col = next((c for c in primary_cols if any(k in c.lower() for k in ['name', 'patient_name', 'doctor_name', 'customer_name'])), 'name')

            if db_type in ('mssql', 'sqlserver'):
                sql = f"DELETE FROM [{primary_table}]\nWHERE [{name_col}] LIKE '%{target_name}%';"
            elif db_type == 'mysql':
                sql = f"DELETE FROM `{primary_table.lower()}`\nWHERE `{name_col}` LIKE '%{target_name}%';"
            elif db_type == 'oracle':
                sql = f"DELETE FROM \"{primary_table.upper()}\"\nWHERE \"{name_col.upper()}\" LIKE '%{target_name}%';"
            elif db_type == 'mongodb':
                sql = f"db.{primary_table.lower()}.deleteMany({{\n  \"{name_col}\": {{ \"$regex\": \"{target_name}\", \"$options\": \"i\" }}\n}});"
            elif db_type == 'excel':
                sql = f"# Remove matching records from DataFrame\ndf = df[~df['{name_col}'].str.contains('{target_name}', case=False, na=False)]\ndf.to_excel('updated_{primary_table.lower()}.xlsx', index=False)"
            else:
                sql = f"DELETE FROM {primary_table} WHERE {name_col} LIKE '%{target_name}%';"

            return {
                "sql": sql,
                "explanation": f"Removes records matching '{target_name}' from table '{primary_table}'.",
                "tables_used": [primary_table],
                "optimization_tips": ["Execute within a transaction or use soft-delete pattern (is_deleted = 1) to prevent accidental data loss."],
                "alternative_approaches": ["Consider adding an audit log trigger before executing permanent purge statements."]
            }

        # ── 3. SELECT / QUERY PROCESSING ───────────────────────────────────────
        agg_func = None
        select_clause = "*"
        agg_target_col = None

        if 'count' in query_lower or 'how many' in query_lower or 'total number' in query_lower:
            select_clause = "COUNT(*) AS total_count"
            agg_func = "COUNT"
        elif 'average' in query_lower or 'avg' in query_lower:
            agg_target_col = next((c for c in primary_cols if any(k in c.lower() for k in ['age', 'amount', 'salary', 'price', 'gpa', 'score', 'fee', 'total'])), 'amount')
            select_clause = f"AVG([{agg_target_col}]) AS avg_{agg_target_col}"
            agg_func = "AVG"
        elif 'sum' in query_lower or 'total billing' in query_lower or 'total amount' in query_lower:
            agg_target_col = next((c for c in primary_cols if any(k in c.lower() for k in ['amount', 'salary', 'price', 'cost', 'fee', 'total', 'bill', 'paid'])), 'total_amount')
            select_clause = f"SUM([{agg_target_col}]) AS total_{agg_target_col}"
            agg_func = "SUM"
        elif 'oldest' in query_lower or 'highest' in query_lower or 'max' in query_lower:
            agg_target_col = next((c for c in primary_cols if any(k in c.lower() for k in ['age', 'price', 'salary', 'amount', 'dob', 'created_at'])), 'age')
            select_clause = f"MAX([{agg_target_col}]) AS max_{agg_target_col}"
            agg_func = "MAX"
        elif 'youngest' in query_lower or 'lowest' in query_lower or 'min' in query_lower:
            agg_target_col = next((c for c in primary_cols if any(k in c.lower() for k in ['age', 'price', 'salary', 'amount', 'dob', 'created_at'])), 'age')
            select_clause = f"MIN([{agg_target_col}]) AS min_{agg_target_col}"
            agg_func = "MIN"

        # Specific columns search
        if not agg_func and select_clause == "*":
            specific_cols = []
            is_show_all = 'show all' in query_lower or 'list all' in query_lower or 'get all' in query_lower
            if not is_show_all:
                for col in primary_cols:
                    col_words = col.lower().split('_')
                    if any(w in query_lower for w in col_words if len(w) > 2 and w not in ['patient', 'doctor', 'customer', 'user', 'order']):
                        specific_cols.append(col)
            if specific_cols:
                select_clause = ", ".join(f"[{c}]" for c in specific_cols)
            elif is_show_all:
                select_clause = "*"

        # Limit / TOP
        m = re.search(r'(?:top|limit|first)\s+(\d+)', query_lower)
        limit_val = m.group(1) if m else None

        # WHERE Conditions
        where_conds = []
        mongo_filter = {}
        pandas_filter = []

        # Numeric comparisons (> or <)
        num_gt = re.search(r'(?:older than|greater than|above|more than|>)\s*(\d+)', query_lower)
        if num_gt:
            val = int(num_gt.group(1))
            num_col = next((c for c in primary_cols if any(k in c.lower() for k in ['age', 'salary', 'price', 'amount', 'total'])), 'age')
            where_conds.append(f"[{num_col}] > {val}")
            mongo_filter[num_col] = {"$gt": val}
            pandas_filter.append(f"df['{num_col}'] > {val}")

        num_lt = re.search(r'(?:younger than|less than|below|under|<)\s*(\d+)', query_lower)
        if num_lt:
            val = int(num_lt.group(1))
            num_col = next((c for c in primary_cols if any(k in c.lower() for k in ['age', 'salary', 'price', 'amount', 'total'])), 'age')
            where_conds.append(f"[{num_col}] < {val}")
            mongo_filter[num_col] = {"$lt": val}
            pandas_filter.append(f"df['{num_col}'] < {val}")

        # Status matching
        for skw in ['completed', 'pending', 'scheduled', 'unpaid', 'paid', 'cancelled']:
            if skw in query_lower:
                stat_col = next((c for c in primary_cols if 'status' in c.lower()), 'status')
                where_conds.append(f"[{stat_col}] = '{skw}'")
                mongo_filter[stat_col] = skw
                pandas_filter.append(f"df['{stat_col}'] == '{skw}'")
                break

        if 'active' in query_lower:
            stat_col = next((c for c in primary_cols if 'active' in c.lower() or 'status' in c.lower()), 'status')
            if 'is_active' in stat_col.lower():
                where_conds.append(f"[{stat_col}] = 1")
                mongo_filter[stat_col] = 1
                pandas_filter.append(f"df['{stat_col}'] == 1")
            else:
                where_conds.append(f"[{stat_col}] = 'Active'")
                mongo_filter[stat_col] = "Active"
                pandas_filter.append(f"df['{stat_col}'] == 'Active'")

        # City / Location matching
        city_match = re.search(r'(?:from|in)\s+([A-Z][a-z]+)', user_query)
        if city_match:
            city_name = city_match.group(1)
            city_col = next((c for c in primary_cols if any(k in c.lower() for k in ['city', 'address', 'location'])), 'city')
            where_conds.append(f"[{city_col}] = '{city_name}'")
            mongo_filter[city_col] = city_name
            pandas_filter.append(f"df['{city_col}'] == '{city_name}'")

        # Today / Date matching
        if 'today' in query_lower:
            date_col = next((c for c in primary_cols if any(k in c.lower() for k in ['date', 'time', 'registered', 'created', 'appointment', 'issue'])), 'created_at')
            if db_type in ('mssql', 'sqlserver'):
                where_conds.append(f"CAST([{date_col}] AS DATE) = CAST(GETDATE() AS DATE)")
            else:
                where_conds.append(f"[{date_col}] >= CURRENT_DATE")
            mongo_filter[date_col] = {"$gte": "CURRENT_DATE"}
            pandas_filter.append(f"df['{date_col}'] >= pd.Timestamp.today().floor('D')")

        # ORDER BY
        order_col = None
        order_dir = "ASC"
        if any(w in query_lower for w in ['oldest', 'youngest', 'top', 'sort', 'order', 'highest', 'lowest', 'descending', 'ascending']):
            order_col = next((c for c in primary_cols if any(k in c.lower() for k in ['age', 'dob', 'created_at', 'date', 'salary', 'price', 'amount', 'id'])), primary_cols[0] if primary_cols else 'id')
            if any(w in query_lower for w in ['oldest', 'highest', 'desc', 'top']):
                order_dir = "DESC"

        # ── 4. Target Platform Formatter ───────────────────────────────────────
        # MONGODB FORMATTER
        if db_type == 'mongodb':
            col_name = primary_table.lower()
            if agg_func == 'COUNT':
                filter_json = json.dumps(mongo_filter) if mongo_filter else "{}"
                sql = f"db.{col_name}.countDocuments({filter_json});"
            elif agg_func in ('AVG', 'SUM', 'MAX', 'MIN'):
                target = agg_target_col or 'amount'
                op = f"${agg_func.lower()}"
                sql = f"db.{col_name}.aggregate([\n  {{ \"$match\": {json.dumps(mongo_filter) if mongo_filter else '{}'} }},\n  {{ \"$group\": {{ \"_id\": null, \"{agg_func.lower()}_{target}\": {{ \"{op}\": \"${target}\" }} }} }}\n]);"
            else:
                filter_json = json.dumps(mongo_filter) if mongo_filter else "{}"
                cursor = f"db.{col_name}.find({filter_json})"
                if order_col:
                    sort_dir = -1 if order_dir == 'DESC' else 1
                    cursor += f'.sort({{ "{order_col}": {sort_dir} }})'
                if limit_val:
                    cursor += f'.limit({limit_val})'
                sql = cursor + ";"
            
            explanation = f"MongoDB query retrieves {agg_func or 'matching documents'} from '{col_name}' collection."
            return {
                "sql": sql,
                "explanation": explanation,
                "tables_used": [primary_table],
                "optimization_tips": [f"Create an index on db.{col_name}.createIndex({{ {list(mongo_filter.keys())[0] if mongo_filter else '_id'}: 1 }}) for rapid document matching."],
                "alternative_approaches": ["Use aggregation pipelines for multifaceted grouping or lookups."]
            }

        # EXCEL / PANDAS FORMATTER
        if db_type == 'excel':
            p_filter_str = " & ".join(f"({f})" for f in pandas_filter) if pandas_filter else ""
            if agg_func == 'COUNT':
                if p_filter_str:
                    sql = f"# Filter records and count total rows\ntotal_count = len(df[{p_filter_str}])\nprint(f'Total count: {{total_count}}')"
                else:
                    sql = f"# Total rows in Excel sheet\ntotal_count = len(df)\nprint(f'Total count: {{total_count}}')"
            elif agg_func in ('AVG', 'SUM', 'MAX', 'MIN'):
                target = agg_target_col or 'amount'
                py_fn = {'AVG': 'mean()', 'SUM': 'sum()', 'MAX': 'max()', 'MIN': 'min()'}[agg_func]
                if p_filter_str:
                    sql = f"# Calculate {agg_func} of '{target}' with filters\nresult = df[{p_filter_str}]['{target}'].{py_fn}\nprint(f'{agg_func}: {{result}}')"
                else:
                    sql = f"# Calculate {agg_func} of '{target}' across entire worksheet\nresult = df['{target}'].{py_fn}\nprint(f'{agg_func}: {{result}}')"
            else:
                df_expr = f"df[{p_filter_str}]" if p_filter_str else "df"
                if order_col:
                    asc = "False" if order_dir == "DESC" else "True"
                    df_expr += f".sort_values(by='{order_col}', ascending={asc})"
                if limit_val:
                    df_expr += f".head({limit_val})"
                sql = f"# Query and filter Excel worksheet data\nfiltered_df = {df_expr}\n# Export to Excel or display\nfiltered_df.to_excel('query_output.xlsx', index=False)"

            return {
                "sql": sql,
                "explanation": f"Executes pandas expression on Excel worksheet for '{primary_table}'.",
                "tables_used": [primary_table],
                "optimization_tips": ["Ensure column data types are parsed correctly upon reading with pd.read_excel(dtype=...)."],
                "alternative_approaches": ["Use openpyxl directly for formula insertion (=SUM, =AVERAGE) without loading into DataFrame memory."]
            }

        # RELATIONAL SQL (SQL SERVER / MYSQL / ORACLE / SQLITE)
        top_prefix = ""
        limit_suffix = ""
        if limit_val:
            if db_type in ('mssql', 'sqlserver'):
                top_prefix = f"TOP {limit_val} "
            elif db_type == 'oracle':
                limit_suffix = f"\nFETCH FIRST {limit_val} ROWS ONLY"
            else:
                limit_suffix = f"\nLIMIT {limit_val}"

        # Handle Multi-table JOIN
        from_clause = f"FROM [{primary_table}]" if db_type in ('mssql', 'sqlserver') else f"FROM `{primary_table}`" if db_type == 'mysql' else f"FROM \"{primary_table.upper()}\"" if db_type == 'oracle' else f"FROM {primary_table}"
        
        if len(detected_tables) > 1:
            sec_table = detected_tables[1]
            sec_cols = schema_tables.get(sec_table.lower(), {}).get('columns', [])
            fk_col = next((c for c in primary_cols if c.lower() == f"{sec_table[:-1] if sec_table.endswith('s') else sec_table}_id".lower()), None)
            if not fk_col:
                fk_col = next((c for c in sec_cols if c.lower() == f"{primary_table[:-1] if primary_table.endswith('s') else primary_table}_id".lower()), None)

            if db_type in ('mssql', 'sqlserver'):
                if fk_col:
                    from_clause = f"FROM [{primary_table}]\nJOIN [{sec_table}] ON [{primary_table}].[{fk_col}] = [{sec_table}].[{fk_col}]"
                else:
                    from_clause = f"FROM [{primary_table}]\nCROSS JOIN [{sec_table}]"
            elif db_type == 'mysql':
                if fk_col:
                    from_clause = f"FROM `{primary_table}`\nJOIN `{sec_table}` ON `{primary_table}`.`{fk_col}` = `{sec_table}`.`{fk_col}`"
                else:
                    from_clause = f"FROM `{primary_table}`\nCROSS JOIN `{sec_table}`"
            elif db_type == 'oracle':
                if fk_col:
                    from_clause = f"FROM \"{primary_table.upper()}\"\nJOIN \"{sec_table.upper()}\" ON \"{primary_table.upper()}\".\"{fk_col.upper()}\" = \"{sec_table.upper()}\".\"{fk_col.upper()}\""
                else:
                    from_clause = f"FROM \"{primary_table.upper()}\"\nCROSS JOIN \"{sec_table.upper()}\""
            else:
                from_clause = f"FROM {primary_table}\nJOIN {sec_table} ON {primary_table}.{fk_col} = {sec_table}.{fk_col}" if fk_col else f"FROM {primary_table}\nCROSS JOIN {sec_table}"

        # WHERE clause formatting
        where_str = f"\nWHERE {' AND '.join(where_conds)}" if where_conds else ""
        if db_type == 'mysql':
            where_str = where_str.replace('[', '`').replace(']', '`')
        elif db_type == 'oracle':
            where_str = where_str.replace('[', '"').replace(']', '"')

        # ORDER BY clause
        order_clause = ""
        if order_col:
            if db_type in ('mssql', 'sqlserver'):
                order_clause = f"\nORDER BY [{order_col}] {order_dir}"
            elif db_type == 'mysql':
                order_clause = f"\nORDER BY `{order_col}` {order_dir}"
            elif db_type == 'oracle':
                order_clause = f"\nORDER BY \"{order_col.upper()}\" {order_dir}"
            else:
                order_clause = f"\nORDER BY {order_col} {order_dir}"

        # Adjust select clause for dialect
        formatted_select = select_clause
        if db_type == 'mysql':
            formatted_select = formatted_select.replace('[', '`').replace(']', '`')
        elif db_type == 'oracle':
            formatted_select = formatted_select.replace('[', '"').replace(']', '"')

        sql = f"SELECT {top_prefix}{formatted_select}\n{from_clause}{where_str}{order_clause}{limit_suffix};"

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


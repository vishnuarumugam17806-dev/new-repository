# DB VITHRA — API Documentation

This document outlines the REST API endpoints provided by the **DB VITHRA** platform.

---

## Authentication Endpoints

### 1. User Registration
* **Endpoint:** `POST /register`
* **Content-Type:** `application/x-www-form-urlencoded`
* **Form Parameters:**
  * `username` (string, required): Alphanumerics & underscores only.
  * `email` (string, required): Valid email address.
  * `password` (string, required): Must be at least 6 characters.
* **Response:** Redirects to `/login` on success, or back to `/register` with flash message on error.

### 2. User Login
* **Endpoint:** `POST /login`
* **Content-Type:** `application/x-www-form-urlencoded`
* **Form Parameters:**
  * `username` (string, required)
  * `password` (string, required)
* **Response:** Redirects to index or the requested `next` URL.

### 3. User Logout
* **Endpoint:** `GET /logout`
* **Authentication Required:** Yes
* **Response:** Redirects to index.

---

## AI Generation Endpoints

### 1. Schema Generation Page
* **Endpoint:** `POST /create`
* **Content-Type:** `application/x-www-form-urlencoded`
* **Form Parameters:**
  * `project_name` (string, required): The database name.
  * `requirements` (string, optional): Requirement descriptions for AI generation.
  * `columns_spec` (string, optional): Raw column specification if creating directly.
  * `table_name` (string, optional): Custom table name for column specs.
  * `db_type` (string, default: `sqlite`): target DBMS (`sqlite`, `mysql`, `postgresql`, `mssql`, `oracle`, `mongodb`, `excel`).
* **Response:** Redirects to `/database/<db_id>` on successful generation.

---

## Query Assistant Endpoints

### 1. Natural Language to SQL Translation
* **Endpoint:** `POST /api/nl-to-sql`
* **Content-Type:** `application/json`
* **JSON Parameters:**
  * `query` (string, required): The plain English question.
  * `schema_id` (integer, optional): Context schema ID.
  * `db_type` (string, default: `sqlite`): target DBMS dialect.
* **Request Example:**
```json
{
  "query": "Find all patients admitted in June 2024",
  "schema_id": 1,
  "db_type": "mysql"
}
```
* **Response Example:**
```json
{
  "sql": "SELECT * FROM patients JOIN appointments ON patients.patient_id = appointments.patient_id WHERE appointments.appointment_date BETWEEN '2024-06-01' AND '2024-06-30';",
  "explanation": "Joins the patients and appointments tables on patient_id, filtering for appointment dates in June 2024.",
  "tables_used": ["patients", "appointments"],
  "optimization_tips": ["Ensure indexes exist on appointments.appointment_date and appointments.patient_id."],
  "alternative_approaches": ["Use EXTRACT(MONTH FROM appointment_date) = 6 AND EXTRACT(YEAR FROM appointment_date) = 2024"]
}
```

---

## Marketplace & Social Endpoints

### 1. Toggle Schema Like
* **Endpoint:** `POST /schema/<int:db_id>/like`
* **Response:**
```json
{
  "likes": 42
}
```

### 2. Submit Rating
* **Endpoint:** `POST /schema/<int:db_id>/rate`
* **Content-Type:** `application/x-www-form-urlencoded`
* **Parameters:**
  * `score` (integer, required): Value between 1 and 5.

### 3. Post Comment
* **Endpoint:** `POST /schema/<int:db_id>/comment`
* **Content-Type:** `application/x-www-form-urlencoded`
* **Parameters:**
  * `author_name` (string, optional): Default "Anonymous" (ignored if logged in).
  * `content` (string, required): Content of the comment.

---

## Analytics Endpoints

### 1. Fetch Stats API
* **Endpoint:** `GET /api/analytics/stats`
* **Response Example:**
```json
{
  "total_schemas": 24,
  "total_downloads": 110,
  "ai_schemas": 18,
  "trend": [
    {"date": "Jun 06", "count": 2},
    {"date": "Jun 07", "count": 5}
  ],
  "industries": [
    {"name": "Healthcare", "count": 8},
    {"name": "E-commerce", "count": 12}
  ]
}
```

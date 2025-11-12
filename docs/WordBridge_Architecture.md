# WordBridge System Architecture (Visual Flow Overview)

## 1. System Overview

WordBridge is a fully Python-based cloud application deployed on AWS. It automates vocabulary gap detection and word recommendations for middle school students using GPT-4o, with educator and student dashboards rendered directly from the backend.

---

## 2. High-Level Architecture Diagram

```
                        +-----------------------------+
                        |        AWS Cloud            |
                        +-----------------------------+
                                   |
                                   |
             +-------------------------------------------------+
             |                                                 |
     +------------------+                          +------------------+
     |  Educator Client |                          |  Student Client  |
     |  (Web Browser)   |                          |  (Web Browser)   |
     +--------+----------+                          +---------+--------+
              |                                             |
              |  HTTPS Requests (Login, Upload, Dashboard)  |
              +-------------------------+-------------------+
                                        |
                              +-------------------------+
                              |    Python Web Server    |
                              | (Flask or FastAPI App)  |
                              +-----------+-------------+
                                          |
              +---------------------------+--------------------------+
              |                           |                          |
     +-------------------+    +-----------------------+    +-------------------+
     |   AI Processor    |    |  PostgreSQL Database  |    |  AWS S3 Storage  |
     | (GPT-4o via API)  |    | (Users, Words, Stats) |    | (Text Uploads)   |
     +-------------------+    +-----------------------+    +-------------------+
              |                           |
              |                  +------------------+
              |                  |   Job Queue      |
              |                  | (AWS SQS/Celery) |
              |                  +------------------+
              |
              |   Vocabulary Extraction, Gap Analysis, Recommendations
              |
     +------------------------------------------------+
     |               Recommendation Engine            |
     |  - Word filtering (age-appropriate, profanity) |
     |  - Difficulty scoring & rationale generation   |
     |  - Educator review list management             |
     +------------------------------------------------+
```

---

## 3. Component Breakdown

### **Frontend (Server-Rendered via Python)**

- HTML templates served via Jinja2.
- Routes:
  - `/login` (with role selection: Educator/Student)
  - `/signup` (educator only)
  - `/educator/dashboard`
  - `/educator/add-student` (create student accounts)
  - `/educator/students/<id>` (student detail view)
  - `/educator/upload` (with student association)
  - `/educator/recommendations` (approve/reject queue)
  - `/student/dashboard`
  - `/student/words` (approved vocabulary list)
  - `/quiz`
- Displays dynamic data (vocabulary recommendations, progress stats, XP, badges).
- **Interactive States:**
  - Buttons: default, hover, active, disabled, loading (with spinner)
  - Forms: validation on blur, inline error messages, success confirmation
  - Modals: backdrop dismiss, ESC key closes, focus trap
  - Notifications: toast-style, 5s auto-dismiss, positioned top-right

### **Backend (Python – Flask or FastAPI)**

- Handles routing, API logic, and data persistence.
- Triggers **asynchronous AI processing** upon file upload via job queue.
- Integrates GPT-4o through OpenAI API for text analysis and recommendations.
- Endpoints:
  - `/api/auth/signup` – Educator registration
  - `/api/auth/login` – Role-based login (email or username)
  - `/api/students/create` – Create student account
  - `/api/upload` – Handles text submissions with student association
  - `/api/recommendations` – Returns word recommendations for approval
  - `/api/recommendations/approve` – Approve words for student
  - `/api/recommendations/reject` – Reject recommendations
  - `/api/quiz` – Manages gamified quiz flow
  - `/api/progress` – Fetches dashboard data
  - `/api/job-status/<id>` – Check async processing status
  - `/api/educator/export` – Export all students as CSV
  - `/api/educator/export/grade/<grade_level>` – Export students by grade level (6, 7, or 8)
  - `/api/educator/export/class/<grade_level>/<class_number>` – Export students by specific class

### **Educator Dashboard Features**

The educator dashboard (`/educator/dashboard`) provides:

- **Summary Cards:**

  - Total Students count
  - Pending Recommendations count
  - (Removed: Average Class Proficiency, Active Streaks)

- **Class Overview:**

  - Students grouped hierarchically: Grade → Class → Students
  - Per-class average proficiency displayed in class metadata
  - Each class shows student count and average vocabulary level

- **Filtering:**

  - Client-side filtering by grade (6th, 7th, 8th, or All)
  - Client-side filtering by class (dynamically populated based on selected grade)
  - Filter state persisted in URL parameters for bookmarking/sharing
  - Instant filtering without page reloads

- **CSV Export:**
  - Export all students (main export button)
  - Export by grade level (button next to each grade heading)
  - Export by class (button next to each class heading)
  - All exports include: id, name, grade_level, class_number, vocabulary_level, pending_words, last_upload_at
  - Filenames include timestamp: `wordbridge_{type}_{identifier}_{timestamp}.csv`
  - CSV formula injection protection (escapes values starting with `=`, `+`, `-`, `@`)

### **Database (PostgreSQL on AWS RDS)**

#### **Core Tables:**

**users**

- `id` (primary key)
- `email` (unique)
- `username` (unique)
- `password_hash`
- `role` (enum: 'educator', 'student')
- `name`
- `created_at`

**student_profiles**

- `student_id` (foreign key → users.id)
- `educator_id` (foreign key → users.id)
- `grade_level` (6, 7, or 8)
- `class_number` (integer, e.g., 601, 602, 701, 802 - first digit matches grade)
- `vocabulary_level` (computed score)
- `last_analyzed_at`

**uploads**

- `id` (primary key)
- `educator_id` (foreign key → users.id)
- `student_id` (foreign key → users.id)
- `file_path` (S3 URL)
- `filename`
- `status` (enum: 'pending', 'processing', 'completed', 'failed')
- `processed_at`
- `created_at`

**baseline_words**

- `id` (primary key)
- `word`
- `definition`
- `difficulty`
- `grade_level` (6, 7, or 8)

**recommendations**

- `id` (primary key)
- `student_id` (foreign key → users.id)
- `word`
- `definition`
- `rationale` (AI-generated explanation)
- `difficulty_score` (1-10)
- `example_sentence`
- `status` (enum: 'pending', 'approved', 'rejected')
- `pinned` (boolean, for educator priority)
- `created_at`

**word_mastery**

- `student_id` (foreign key → users.id)
- `word_id` (foreign key → recommendations.id)
- `mastery_stage` (enum: 'practicing', 'nearly_mastered', 'mastered')
- `correct_count` (0-3+)
- `last_practiced_at`

**quiz_attempts**

- `id` (primary key)
- `student_id` (foreign key → users.id)
- `word_id` (foreign key → recommendations.id)
- `correct` (boolean)
- `attempted_at`

**student_progress**

- `student_id` (primary key, foreign key → users.id)
- `xp` (integer, default 0)
- `level` (computed from XP)
- `streak_count` (integer, default 0)
- `last_quiz_at` (timestamp)

**badges**

- `id` (primary key)
- `student_id` (foreign key → users.id)
- `badge_type` (enum: '10_words', '50_words', '100_words')
- `earned_at`

#### **Indexes for Performance:**

- `users.email`, `users.username`
- `student_profiles.educator_id`, `student_profiles.student_id`
- `uploads.student_id`, `uploads.status`
- `recommendations.student_id`, `recommendations.status`
- `quiz_attempts.student_id`, `quiz_attempts.attempted_at`

### **AI Engine (GPT-4o)**

- Performs NLP-driven vocabulary analysis:
  - Extracts current vocabulary usage
  - Detects proficiency level and gaps
  - Suggests new words with rationales and difficulty ratings
- **Processing Mode:** Asynchronous via job queue
- **Minimum Input:** 200 words for initial analysis, 100 words for updates
- **Error Handling:**
  - Retry up to 3 times with exponential backoff
  - On failure, queue for manual review and notify educator
  - Never expose API errors to users

### **Storage (AWS S3)**

- Stores uploaded files (PDF, DOCX, TXT, CSV).
- File naming convention: `uploads/{educator_id}/{student_id}/{timestamp}_{filename}`
- Provides event triggers to invoke backend processing.

### **Job Queue (AWS SQS or Celery)**

- Handles asynchronous AI processing tasks.
- Tracks job status: `queued` → `processing` → `completed` / `failed`
- Allows users to check processing status via polling or notifications.

### **Hosting**

- AWS Lambda or EC2 hosts the backend application.
- AWS RDS for PostgreSQL database.
- AWS S3 for storage and static assets.
- AWS API Gateway for routing HTTPS traffic.
- AWS Application Load Balancer for HTTPS enforcement.

---

## 4. Data Flow (End-to-End)

```
[1] Educator creates student account (name, grade, username, email, password)
        ↓
[2] Student profile created with grade-level baseline vocabulary
        ↓
[3] Educator uploads file and associates it with student
        ↓
[4] File saved to S3 and registered in PostgreSQL
        ↓
[5] Job queued for asynchronous AI processing
        ↓
[6] Background worker triggers GPT-4o AI processing
        ↓
[7] GPT-4o analyzes vocabulary gaps and generates recommendations
        ↓
[8] Recommendations stored in PostgreSQL with status='pending'
        ↓
[9] Educator Dashboard fetches pending recommendations
        ↓
[10] Educator approves/rejects recommendations
        ↓
[11] Approved words appear in Student Dashboard
        ↓
[12] Student takes quiz on approved words
        ↓
[13] Quiz results update XP, streak, mastery stage
        ↓
[14] After 3 correct answers (spaced), word marked as 'mastered'
        ↓
[15] Badges awarded at milestones (10, 50, 100 words)
```

---

## 5. Example Sequence (Educator Workflow)

1. Educator signs up → `/signup` (name, username, email, password, confirm password)
2. Educator logs in → `/login` (selects "Educator" role, enters email/username + password)
3. Educator creates student accounts → `/educator/add-student` (3 students: 6th, 7th, 8th grade)
4. Uploads student writing samples → `/educator/upload` (multi-file, tagged with student IDs)
5. Files stored in S3 → async job queued
6. AI processing completes → recommendations added to database (status='pending')
7. Educator dashboard shows pending recommendations → `/educator/recommendations`
8. Educator reviews and approves words (bulk action available)
9. Approved words appear in student dashboard → `/student/dashboard`
10. Students take quizzes → XP and streaks update

---

## 6. Example Sequence (Student Workflow)

1. Student logs in → `/login` (selects "Student" role, enters credentials)
2. Student dashboard displays:
   - XP progress bar, level, streak counter
   - Approved vocabulary words with rationales
   - "Start Quiz" button (if ≥5 words approved)
3. Student starts quiz → 10 questions (70% recent, 30% older words)
4. Immediate feedback on each answer (color-coded)
5. Completion modal shows XP gained, streak maintained, performance summary
6. Word mastery stages update based on correct answers
7. Badges earned at milestones

---

## 7. Security and Compliance

### **Authentication**

- **Method:** Session-based via Flask-Login
- **Cookies:** Secure, httpOnly, sameSite flags enabled
- **Login:** Email or username supported; role-based access control
- **Role Enforcement:** Students cannot access educator routes; educators cannot access student routes

### **Data Privacy**

- **PII Scrubbing:** Regex-based removal of emails, phone numbers, full names before AI processing
- All API calls served over **HTTPS** (TLS 1.2+) via AWS Application Load Balancer
- **Data Retention:** 2-year policy; anonymize or delete afterward
- Basic **FERPA/COPPA** compliance maintained (no third-party data sharing)

### **Content Filtering**

- Word filters exclude profanity, mature, and culturally sensitive terms
- AI outputs reviewed by educators before student visibility

---

## 8. Scalability and Performance

- **Horizontal scaling** via AWS Lambda concurrency or EC2 auto-scaling
- **S3 event-driven processing** for efficient ingestion
- **Asynchronous AI requests** using job queue (AWS SQS or Celery)
- **Connection pooling** for PostgreSQL to handle concurrent dashboard users
- **Caching:** Redis (optional) for frequent dashboard queries

---

## 9. Error Handling Strategy

### **AI Processing Failures**

- Queue for manual retry (up to 3 attempts with exponential backoff)
- Notify educator via dashboard notification
- Log errors to CloudWatch for debugging

### **File Parsing Errors**

- Display clear error message: "Unable to process file. Please ensure it's a valid .txt, .docx, .pdf, or .csv file."
- Suggested action: "Try re-uploading or contact support."

### **Database Connection Errors**

- Retry 3 times with exponential backoff
- Show user-friendly message: "We're experiencing technical difficulties. Please try again in a moment."

### **Rate Limiting (OpenAI API)**

- Queue requests and process in order
- Show estimated time to completion in UI

### **User-Facing Errors**

- Always show friendly messages
- Never expose stack traces or technical details

---

## 10. Summary

WordBridge is an entirely Python-based cloud application with a modular architecture optimized for rapid development, AI-driven analysis, and scalability.

The system is designed to process educator-uploaded text in an asynchronous workflow, produce personalized vocabulary recommendations through GPT‑4o, and deliver a user-friendly experience through educator and student dashboards rendered directly by the backend.

**Key Features:**

- Role-based authentication with strict access control
- Asynchronous AI processing with status tracking
- Educator-controlled approval workflow for recommendations
- Gamified learning with XP, streaks, and badges
- Comprehensive error handling and data privacy measures

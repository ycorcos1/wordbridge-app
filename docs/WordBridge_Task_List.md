# WordBridge Task List

Each PR focuses on a single, concrete feature or system milestone.  
All testing is baked into individual PRs, with a final PR for full-system testing and deployment verification.

---

## PR #1: Setup and Initialization

### Tasks

- Initialize a new Python project environment.
- Create the folder structure (`/app`, `/templates`, `/static`, `/config`, `/models`, `/tests`).
- Set up a virtual environment and install dependencies:
  - `Flask` or `FastAPI`, `Flask-Login`, `psycopg2`, `boto3`, `requests`, `openai`, `bcrypt`, `pytest`, `python-dotenv`
- Configure environment variables for local development:
  - `OPENAI_API_KEY`
  - `DATABASE_URL`
  - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET_NAME`
  - `SECRET_KEY` (for session management)
- Initialize a Git repository and `.env` file (add to `.gitignore`).
- Create a base route (`/`) to confirm the app runs locally.
- Set up PostgreSQL database (local or AWS RDS test instance).

### Testing

- **Unit Tests:** Verify environment variables load correctly.
- **Integration Tests:** Confirm database connection successful.
- **Manual Test:** Run app locally and access `localhost:5000`.

### Acceptance Criteria

- The app runs locally on `localhost:5000` (or similar).
- Environment variables load successfully.
- Verified connection to the PostgreSQL database (local or AWS RDS test instance).
- Project structure documented in README.

---

## PR #2: User Authentication (Educator & Student)

### Tasks

- Implement **educator signup** route (`/signup`) with form validation:
  - Fields: name, username (unique), email (unique), password, confirm password
  - Password hashing via `bcrypt`
- Implement **login route** (`/login`) with role selection (Educator/Student):
  - Support email OR username for login
  - Role-based authentication: validate credentials against user's registered role
  - Session management via `Flask-Login`
- Create database tables: `users` (id, email, username, password_hash, role, name, created_at)
- Implement **logout** route (`/logout`)
- Create login/signup templates with inline validation and error handling
- Implement role-based routing:
  - Educators → `/educator/dashboard`
  - Students → `/student/dashboard`
  - Block cross-role access (students cannot access educator routes)

### Testing

- **Unit Tests:**
  - Test password hashing and verification
  - Test role validation logic
- **Integration Tests:**
  - Create educator account, log in, verify redirect to educator dashboard
  - Attempt student login with educator credentials → should fail
  - Test email and username login variants
- **Manual Test:** Sign up, log out, log in with different roles

### Acceptance Criteria

- Educators can sign up, log in, and log out.
- Students can log in (accounts created by educators).
- Role-based access control enforced (students cannot access educator pages).
- Authentication persists across sessions.
- Inline form validation with user-friendly error messages.

---

## PR #3: Student Account Creation (Educator Feature)

### Tasks

- Create **Add Student page** (`/educator/add-student`) for educators:
  - Form fields: name, grade (6th/7th/8th dropdown), username (unique), email, password
  - Validation: ensure username and email uniqueness
- Implement **student creation API** (`/api/students/create`):
  - Insert into `users` table with role='student'
  - Create `student_profiles` entry linked to educator
  - Load grade-level baseline vocabulary from database
- Create `student_profiles` table (student_id, educator_id, grade_level, vocabulary_level, last_analyzed_at)
- Create `baseline_words` table and load JSON data (6th, 7th, 8th grade vocabulary):
  - Source: Common Core + Oxford 3000 intersection (500-800 words per grade)
  - Store: id, word, definition, difficulty, grade_level
- Add **success notification** after student creation
- Add "Create Another Student" and "Return to Dashboard" options

### Testing

- **Unit Tests:**
  - Test username/email uniqueness validation
  - Test baseline vocabulary loading
- **Integration Tests:**
  - Create 3 students (grades 6, 7, 8)
  - Verify `student_profiles` entries created
  - Verify baseline words associated correctly
- **Manual Test:** Create students via UI, check database entries

### Acceptance Criteria

- Educators can create student accounts via dedicated page.
- Student profiles initialized with grade-level baseline vocabulary.
- Form validation prevents duplicate usernames/emails.
- Success messages displayed after creation.
- Database tables populated correctly.

---

## PR #4: File Upload and Text Ingestion

### Tasks

- Create **Upload page** (`/educator/upload`) for educators:
  - Student selection dropdown (required)
  - Multi-file drag-and-drop zone
  - Supported formats: TXT, DOCX, PDF, CSV
  - Visual file list with remove option
  - Upload progress indicator
- Implement **upload API** (`/api/upload`):
  - Validate file types and sizes
  - Save files to AWS S3 with naming convention: `uploads/{educator_id}/{student_id}/{timestamp}_{filename}`
  - Store metadata in `uploads` table (id, educator_id, student_id, file_path, filename, status='pending', created_at)
  - Queue async job for AI processing
- Create `uploads` table (id, educator_id, student_id, file_path, filename, status, processed_at, created_at)
- Set up **job queue** (AWS SQS or Celery) for async processing
- Add **job status endpoint** (`/api/job-status/<id>`)
- Display upload confirmation and processing status in UI

### Testing

- **Unit Tests:**
  - Test file validation (type, size)
  - Test S3 upload helper functions
- **Integration Tests:**
  - Upload files via API, verify S3 storage
  - Verify database entries created correctly
  - Test job queuing mechanism
- **Manual Test:** Upload multiple files via UI, check S3 bucket and database

### Acceptance Criteria

- Uploads support TXT, DOCX, PDF, CSV formats.
- Files saved to S3 with correct naming and metadata.
- Database tracks file associations per educator/student.
- Async job queued for each upload.
- UI shows upload progress and completion status.

---

## PR #5: AI Vocabulary Recommendation Engine (GPT‑4o Integration)

### Tasks

- Implement **background job processor** to handle queued upload jobs
- Connect to **GPT‑4o via OpenAI API**
- Implement **text extraction** from uploaded files:
  - TXT: direct read
  - DOCX: python-docx library
  - PDF: PyPDF2 or pdfplumber
  - CSV: pandas
- Implement **PII scrubbing** (regex-based removal of emails, phone numbers, names)
- Implement **vocabulary analysis logic**:
  - Extract tokens and lemmas from text
  - Compare against baseline vocabulary and corpus frequency
  - Identify "growth words" (underused or missing)
  - Minimum text length: 200 words for initial analysis, 100 for updates
- Generate **recommendations via GPT-4o**:
  - Prompt engineering to extract: word, definition, rationale, difficulty (1-10), example sentence
  - Batch recommendations (5-10 words per upload)
- Implement **content filtering** (profanity, sensitive terms)
- Store recommendations in `recommendations` table (id, student_id, word, definition, rationale, difficulty_score, example_sentence, status='pending', created_at)
- Update upload status to 'completed' or 'failed'
- Implement **error handling and retry logic** (3 attempts with exponential backoff)

### Testing

- **Unit Tests:**
  - Test text extraction from each file type
  - Test PII scrubbing (verify emails/names removed)
  - Test content filtering
- **Integration Tests:**
  - Process uploaded files with GPT-4o
  - Verify recommendations stored correctly
  - Test error handling (mock API failures)
- **Manual Test:** Upload sample texts, verify recommendations generated

### Acceptance Criteria

- AI generates at least 5 vocabulary recommendations per text input (≥200 words).
- Each recommendation includes word, definition, rationale, difficulty, example sentence.
- Sensitive/profane words excluded via filtering.
- Recommendations persist in database with status='pending'.
- Error handling implemented with retry logic and user notifications.

---

## PR #6: Educator Dashboard

### Tasks

- Create **Educator Dashboard template** (`/educator/dashboard`):
  - Summary cards: Total Students, Pending Recommendations, Average Class Proficiency, Active Streaks
  - Table of students with columns: Name, Grade, Vocabulary Level, Pending Words, Last Upload, Actions
  - Actions: "View Profile", "Upload Work", "View Recommendations"
- Implement **dashboard data API** (`/api/educator/dashboard`):
  - Fetch student list with associated stats
  - Calculate average proficiency per student
  - Count pending recommendations
- Add **student detail view** (`/educator/students/<id>`):
  - Student profile, upload history, vocabulary progress, quiz performance
- Style dashboard with cards, tables, responsive layout per Design Spec

### Testing

- **Unit Tests:** Test dashboard data aggregation logic
- **Integration Tests:**
  - Create multiple students with varied data
  - Verify dashboard displays correct stats
- **Manual Test:** Navigate dashboard, click actions, verify data accuracy

### Acceptance Criteria

- Educator can view all student progress and vocabulary recommendations.
- Dashboard displays accurate stats (pending recs, proficiency, streaks).
- Responsive layout works on desktop and tablet.
- Student detail view accessible via table actions.

---

## PR #7: Educator Recommendations Page (Approval Workflow)

### Tasks

- Create **Recommendations Page** (`/educator/recommendations`):
  - Filter options: by student, by difficulty, by date
  - Card-based layout for each recommendation: word, student name, rationale, difficulty meter, example sentence
  - Action buttons: "Approve", "Reject", "Edit Rationale", "Pin"
  - Bulk selection with checkboxes
  - Bulk action buttons: "Approve Selected", "Reject Selected"
- Implement **recommendation APIs**:
  - `/api/recommendations` (GET) – Fetch pending recommendations with filters
  - `/api/recommendations/approve` (POST) – Update status='approved'
  - `/api/recommendations/reject` (POST) – Update status='rejected'
  - `/api/recommendations/edit` (POST) – Update rationale
  - `/api/recommendations/pin` (POST) – Set pinned=true
- Add **notification system** (toast notifications) for action confirmations
- Update `recommendations` table with `pinned` (boolean) and `status` fields

### Testing

- **Unit Tests:** Test API endpoints for approve/reject/edit/pin
- **Integration Tests:**
  - Approve recommendations, verify status update
  - Bulk approve, verify multiple updates
  - Edit rationale, verify change persists
- **Manual Test:** Use recommendations page, test all actions and filters

### Acceptance Criteria

- Educator can view all pending recommendations.
- Approve/reject actions update status correctly.
- Bulk actions work for multiple recommendations.
- Edit rationale persists changes.
- Pin functionality prioritizes words in student view.
- Toast notifications confirm all actions.

---

## PR #8: Student Dashboard

### Tasks

- Create **Student Dashboard template** (`/student/dashboard`):
  - Top section: XP progress bar, level display, streak counter with flame icon, badge display
  - Middle section: "Your Vocabulary Words" card with approved words list
    - Each word shows: definition, rationale tooltip, mastery indicator, progress dots (e.g., ●○○ for 1/3 correct)
  - Bottom section: "Start Quiz" button (disabled if <5 approved words), recent quiz performance
- Implement **student dashboard API** (`/api/student/dashboard`):
  - Fetch approved recommendations (status='approved')
  - Fetch student progress (XP, level, streak, badges)
  - Fetch quiz history
- Create `student_progress` table (student_id, xp, level, streak_count, last_quiz_at)
- Create `badges` table (id, student_id, badge_type, earned_at)
- Create `word_mastery` table (student_id, word_id, mastery_stage, correct_count, last_practiced_at)
- Implement **level calculation logic** (level = XP // 500)
- Style dashboard per Design Spec with progress bars, icons, cards

### Testing

- **Unit Tests:** Test level calculation, XP aggregation
- **Integration Tests:**
  - Approve words, verify they appear in student dashboard
  - Test quiz button enabled/disabled logic
- **Manual Test:** Log in as student, verify dashboard displays correctly

### Acceptance Criteria

- Student dashboard displays approved vocabulary words with rationales.
- XP, level, streak, and badges displayed accurately.
- Word mastery indicators show progress (Practicing/Nearly Mastered/Mastered).
- Quiz button disabled until ≥5 words approved (with tooltip).
- Dashboard data persists across sessions.

---

## PR #9: Gamification & Quizzes

### Tasks

- Create **Quiz Page** (`/quiz`) for students:
  - Progress indicator: "Question X of 10"
  - Question card with word-based questions (multiple-choice or fill-in-the-blank)
  - Immediate feedback (green for correct, red for incorrect with explanation)
  - "Next Question" button after feedback
  - Completion modal: XP gained, streak status, score, "View Dashboard" button
- Implement **quiz generation API** (`/api/quiz/generate`):
  - Pull 10 questions from approved, not-yet-mastered words
  - 70% recent words, 30% older words (spaced repetition)
  - Generate multiple-choice options or fill-in-the-blank prompts
- Implement **quiz submission API** (`/api/quiz/submit`):
  - Record each answer in `quiz_attempts` table
  - Update `word_mastery` table: increment correct_count for correct answers
  - Auto-mark as "Mastered" after 3 correct answers (spaced)
  - Update `student_progress`: add XP (+10 per correct, +50 bonus for ≥70% completion)
  - Update streak: maintain if quiz taken today, reset if >24 hours passed
- Create `quiz_attempts` table (id, student_id, word_id, correct, attempted_at)
- Implement **badge awarding logic**: Award badges at 10, 50, 100 mastered words
- Implement **streak logic**:
  - Day resets at midnight (student's local timezone)
  - 24-hour grace period before streak breaks
  - Update streak_count and last_quiz_at in student_progress
- Style quiz page per Design Spec with animations for feedback

### Testing

- **Unit Tests:**
  - Test quiz question generation (word selection, spaced repetition logic)
  - Test XP calculation
  - Test streak logic (same day, next day, missed day)
  - Test badge awarding conditions
- **Integration Tests:**
  - Complete quiz, verify XP/streak/mastery updates
  - Take multiple quizzes, verify word mastery progression
  - Test badge awarding at milestones
- **Manual Test:** Take quizzes as student, verify all UI feedback and data updates

### Acceptance Criteria

- Quiz flow operates smoothly (next question, submit, feedback, finish).
- Immediate color-coded feedback on answers.
- XP, streak, and badge tracking accurate and persistent.
- Word mastery stages update correctly (3 correct → Mastered).
- Completion modal displays correct stats.
- Educator dashboard reflects updated student progress.

---

## PR #10: Cold‑Start Calibration & Profile Refinement

### Tasks

- Implement **initial profile creation** on student signup:
  - Assign grade-level baseline vocabulary from `baseline_words` table
  - Set initial vocabulary_level score
- Implement **profile refinement** after first upload (≥200 words):
  - Trigger GPT-4o to analyze student writing against baseline
  - Adjust vocabulary_level score based on detected proficiency
  - Store refined profile in `student_profiles`
- Implement **incremental updates** on subsequent uploads:
  - Update vocabulary_level dynamically
  - Adjust recommendation difficulty based on progress
- Add **profile update timestamp** (last_analyzed_at) in student_profiles

### Testing

- **Unit Tests:** Test baseline assignment logic per grade
- **Integration Tests:**
  - Create student, verify baseline loaded
  - Upload first text (≥200 words), verify profile refined
  - Upload subsequent texts, verify incremental updates
- **Manual Test:** Create new student, upload texts, check profile evolution

### Acceptance Criteria

- Each new student receives grade-level baseline vocabulary automatically.
- First upload (≥200 words) refines vocabulary profile and adjusts recommendations.
- Subsequent uploads update profile incrementally.
- Cold‑start flow verified through mock student data (3 students, one per grade).

---

## PR #11: Data Privacy, Filtering & Explainability Layer

### Tasks

- Implement **pre‑AI PII scrubbing**:
  - Regex patterns to remove: emails, phone numbers, full names (common patterns)
  - Apply before sending text to GPT-4o
- Implement **post‑AI content filtering**:
  - Profanity filter using word list (e.g., better-profanity library)
  - Culturally sensitive terms filter
  - Remove flagged words from recommendations
- Add **explainability tooltips** in student dashboard:
  - "Why this word?" tooltip shows rationale
  - Difficulty meter with visual representation (1-10 scale)
- Add **privacy settings** in educator dashboard:
  - Option to view anonymized data
  - Data export functionality (CSV/PDF)
- Document **FERPA/COPPA compliance measures** in README

### Testing

- **Unit Tests:**
  - Test PII scrubbing (emails, phone numbers removed)
  - Test profanity filtering
- **Integration Tests:**
  - Process text with PII, verify scrubbing
  - Generate recommendations, verify no profane words
- **Manual Test:** Upload texts with PII, check AI inputs; verify tooltips in student dashboard

### Acceptance Criteria

- All AI calls are anonymized (PII removed).
- No sensitive, profane, or banned words appear in final recommendations.
- Rationale and difficulty explanation visible for each recommendation in student view.
- Educator can export data in compliant format.

---

## PR #12: System Testing & Integration Verification

### Tasks

- **End-to-end testing** of all features:
  - Educator signup → student creation → upload → AI processing → approval → student quiz
- **Regression testing:** Verify all previous PRs still work together
- **Performance testing:** Upload multiple files simultaneously, check processing times
- **Error handling testing:**
  - Invalid file uploads
  - Failed AI requests
  - Database connection errors
  - Bad login attempts
- **Accessibility testing:**
  - Keyboard navigation
  - Screen reader compatibility
  - Color contrast verification
- **Cross-browser testing:** Chrome, Firefox, Safari
- **Data persistence testing:** Verify data survives server restarts
- **Load testing:** Simulate multiple concurrent users (optional)
- Create **test data set**: 1 educator, 3 students (6th, 7th, 8th grade), 10+ text samples
- Document **known issues** and edge cases

### Testing

- **Automated Test Suite:** Run all unit and integration tests
- **E2E Tests:** Selenium or Playwright for critical flows
- **Manual Test Scenarios:** Follow user stories from PRD
- **Test Coverage Report:** Aim for >80% code coverage

### Acceptance Criteria

- All endpoints return expected results with no unhandled errors.
- Dashboards accurately reflect stored and updated data.
- All AI features operate correctly with sample inputs.
- Accessibility standards met (WCAG 2.2 AA).
- No critical bugs or blockers identified.

---

## PR #13: Deployment Setup (AWS)

### Tasks

- Configure AWS resources:
  - S3 bucket for uploads with proper naming convention
  - RDS PostgreSQL instance with connection pooling
  - Lambda or EC2 for backend hosting
  - API Gateway for routing HTTPS traffic
  - Application Load Balancer for HTTPS enforcement
  - SQS queue or Celery setup for async jobs
- Set environment variables securely via AWS Secrets Manager or Parameter Store
- Set up production environment file storage paths
- Generate logs and basic monitoring (CloudWatch)
- Configure auto-scaling policies (if using EC2)
- Set up database migrations for production

### Testing

- **Integration Tests:** Deploy to staging environment first
- **Smoke Tests:** Verify all endpoints accessible
- **Security Tests:** Verify HTTPS enforcement, PII scrubbing
- **Performance Tests:** Load test with concurrent users

### Acceptance Criteria

- All AWS resources deployed and connected successfully.
- Backend accessible via public API endpoint with HTTPS.
- Database, storage, and AI integrations function in live environment.
- Monitoring and logging operational.
- Auto-scaling configured (if applicable).

---

## PR #14: Deployment Verification & Final Testing

### Tasks

- Deploy latest code version to AWS production
- Run integration tests in production environment
- Verify full flow:
  - Educator signup → student creation → upload → AI processing → approval → student quiz → XP/streak update
- Confirm no data loss between sessions
- Test error recovery (restart services, verify data persistence)
- Perform final accessibility audit
- Document deployment process and troubleshooting steps
- Create user documentation (educator guide, student guide)
- Document any deployment issues or fixes applied

### Testing

- **Production Smoke Tests:** Verify all critical paths work
- **User Acceptance Testing:** Follow real-world scenarios
- **Performance Monitoring:** Check response times under load
- **Security Audit:** Verify all compliance measures in place

### Acceptance Criteria

- Application is fully deployed and functional on AWS.
- All key features verified in production environment.
- No major bugs or blockers remain.
- User documentation complete.
- MVP considered complete and ready for use.

---

## Summary

**Total PRs:** 14  
**Estimated Timeline:** 12-24 hours (depending on parallel work and testing depth)  
**Testing Strategy:** Unit tests (>80% coverage) + Integration tests + E2E tests + Manual verification  
**Deployment Target:** AWS (Lambda/EC2 + RDS + S3 + SQS)

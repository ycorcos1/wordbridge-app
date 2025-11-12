# AI Implementation Log

This document tracks prompting strategies, implementation decisions, and progress for each PR in the WordBridge project.

**Note:** This log will be updated as we begin implementing the Task List (PR #1 onwards).

---

## Overview

- **Project:** WordBridge
- **Start Date:** November 10, 2025
- **Last Updated:** November 10, 2025 (PR #5 completed)

---

## PR Implementation Log

### PR #1: Setup and Initialization

**Status:** ✅ Completed  
**Date Started:** November 10, 2025  
**Date Completed:** November 10, 2025

**Prompting Strategy:**

- Used structured implementation prompt with clear goal, modified files, acceptance criteria, and diff plan
- Generated complete file structure upfront before implementation
- Iterative problem-solving for Python 3.14 compatibility and port conflicts

**Implementation Notes:**

- **Project Structure:** Created all required directories (`app/`, `templates/`, `static/`, `config/`, `models/`, `tests/`)
- **Dependencies:** Installed Flask 3.0.3, Flask-Login, psycopg (v3), boto3, requests, openai, bcrypt, python-dotenv, pytest
- **Python Version Compatibility:** Encountered Python 3.14 compatibility issue with `psycopg2-binary`. Switched to `psycopg[binary]==3.2.12` (psycopg v3) which has better Python 3.14 support
- **Port Conflict:** macOS AirPlay Receiver uses port 5000 by default. Changed Flask app to run on port 5001 to avoid conflicts
- **Environment Configuration:** Created `.env.example` template and `config/settings.py` with dataclass-based settings management
- **Flask App Factory:** Implemented factory pattern in `app/__init__.py` with proper template and static folder configuration
- **Base Routes:** Created `/` (index) and `/health` (JSON health check) routes
- **Testing:** Created unit test for environment variable loading and integration test for database connectivity (uses psycopg v3 API)
- **Git:** Initialized repository with proper `.gitignore` for Python projects
- **Favicon:** Added SVG favicon to eliminate 404 errors in browser console

**Key Decisions:**

- **psycopg v3 over psycopg2:** Chose `psycopg[binary]==3.2.12` instead of `psycopg2-binary` for Python 3.14 compatibility. This requires updating database connection code to use psycopg v3 API (context manager pattern) instead of psycopg2 API
- **Port 5001:** Changed default port from 5000 to 5001 to avoid macOS AirPlay Receiver conflict. Updated `wsgi.py` and README accordingly
- **Template/Static Paths:** Configured Flask to use project root directories for templates and static files (not relative to `app/` package) for clearer project structure
- **Debug Mode:** Enabled debug mode by default in `wsgi.py` for development (auto-reload on code changes)
- **Settings Pattern:** Used dataclass-based settings with `python-dotenv` for type-safe environment variable access

---

### PR #2: User Authentication (Educator & Student)

**Status:** ✅ Completed  
**Date Started:** November 10, 2025  
**Date Completed:** November 10, 2025

**Prompting Strategy:**

- Generated structured implementation prompt from Task List requirements
- Used step-by-step approach: data layer → routes → templates → tests
- Iterative refinement based on user feedback (removed SQLAlchemy dependency, simplified database layer)

**Implementation Notes:**

- **Database Layer (`models/__init__.py`):**

  - Implemented dual-backend support: SQLite (default) and PostgreSQL
  - Created `User` class implementing Flask-Login's `UserMixin`
  - Database connection singleton pattern with automatic backend detection
  - Functions: `get_user_by_id()`, `get_user_by_identifier()` (email or username), `create_user()`
  - `init_db()` creates `users` table with columns: id, email, username, password_hash, role, name, created_at
  - Role constraint: CHECK (role IN ('educator', 'student'))
  - Removed SQLAlchemy dependency to avoid external package issues; used raw SQL with psycopg/sqlite3

- **Security Module (`app/security.py`):**

  - `hash_password()`: Uses bcrypt with automatic salt generation
  - `verify_password()`: Validates plaintext against stored hash with error handling

- **Authentication Routes (`app/routes.py`):**

  - `/signup` (GET/POST): Educator-only signup with validation (name, username, email, password, confirm password)
  - `/login` (GET/POST): Role-based login supporting email OR username, validates role match
  - `/logout` (GET): Session termination with flash message
  - `/educator/dashboard` (GET): Protected route with `@role_required('educator')`
  - `/student/dashboard` (GET): Protected route with `@role_required('student')`
  - `/` (GET): Homepage that redirects authenticated users to their dashboard
  - Implemented `role_required()` decorator for route protection
  - Inline form validation with user-friendly error messages
  - Flash messages for success/error feedback

- **Flask-Login Integration (`app/__init__.py`):**

  - Initialized `LoginManager` with `login_view = "core.login"`
  - Session protection set to "strong"
  - User loader function connects Flask-Login to database

- **Templates:**

  - `login.html`: Role selection (Educator/Student), email/username input, password field, inline error display
  - `signup.html`: Educator registration form with password confirmation, real-time validation feedback
  - `educator_dashboard.html`: Placeholder dashboard (to be expanded in PR #6)
  - `student_dashboard.html`: Placeholder dashboard (to be expanded in PR #8)
  - `index.html`: Professional marketing homepage with hero section, features, and CTAs (redirects authenticated users)

- **Testing:**
  - `test_auth_password.py`: Unit tests for password hashing and verification
  - `test_auth_role.py`: Unit tests for role-based access control decorator
  - `test_auth_integration.py`: Integration tests for signup/login flow, role mismatch handling, email/username login variants
  - All tests passing (8 passed, 1 skipped)

**Key Decisions:**

- **Dual Database Backend:** Implemented support for both SQLite (dev) and PostgreSQL (production) with automatic detection based on `DATABASE_URL` format. This allows flexible development without requiring PostgreSQL setup initially
- **No ORM Dependency:** Chose raw SQL with psycopg/sqlite3 instead of SQLAlchemy to avoid dependency issues and keep the stack lightweight
- **Email OR Username Login:** Implemented flexible identifier lookup allowing users to log in with either email or username for better UX
- **Role Validation at Login:** Enforces role selection matches stored user role to prevent cross-role access attempts
- **Homepage Design:** Created professional marketing-style homepage (not just a redirect) to improve first impression and user onboarding
- **Inline Validation:** Form errors displayed immediately below fields with preserved input values for better UX
- **Session Management:** Used Flask-Login's strong session protection for security

---

### PR #3: Student Account Creation (Educator Feature)

**Status:** ✅ Completed  
**Date Started:** November 10, 2025  
**Date Completed:** November 10, 2025

**Prompting Strategy:**

- Generated structured implementation prompt from Task List requirements with clear goal, modified files, acceptance criteria, and diff plan
- Used step-by-step approach: database schema → model functions → routes → templates → tests
- Implemented baseline vocabulary seeding with fallback mechanism for missing JSON files

**Implementation Notes:**

- **Database Schema (`models/__init__.py`):**

  - Created `student_profiles` table: student_id (PK, FK to users), educator_id (FK to users), grade_level (6/7/8), vocabulary_level (default 0), last_analyzed_at (nullable)
  - Created `baseline_words` table: id (PK), word, definition, difficulty, grade_level (6/7/8)
  - Added indexes on `baseline_words.grade_level` and `student_profiles.educator_id` for query performance
  - Foreign key constraints with CASCADE delete for data integrity
  - Dual-backend support (SQLite and PostgreSQL) with appropriate syntax differences

- **Model Functions (`models/__init__.py`):**

  - `ensure_baseline_words_loaded()`: Idempotent function that loads baseline vocabulary from JSON files if table is empty
  - Falls back to minimal seed data (2 words per grade) if JSON files are missing or invalid
  - `count_baseline_words_for_grade(grade_level)`: Returns count of baseline words for a specific grade
  - `create_student_profile()`: Creates student profile entry linked to educator with grade level
  - Baseline vocabulary files stored in `data/baseline/` directory (6th_grade.json, 7th_grade.json, 8th_grade.json)

- **Routes (`app/routes.py`):**

  - `/educator/add-student` (GET/POST): Form-based student creation page for educators
  - `/api/students/create` (POST): JSON API endpoint for programmatic student creation
  - Shared validation function `_validate_student_submission()` used by both form and API routes
  - Validates: name, grade (6/7/8), username, email, password (min 8 chars)
  - Handles duplicate username/email with user-friendly error messages
  - Automatically calls `ensure_baseline_words_loaded()` on first student creation
  - Creates user account with `role='student'` and linked `student_profiles` entry

- **Templates:**

  - `educator_add_student.html`: New form template with fields for name, grade dropdown (6th/7th/8th), username, email, password
  - Success state displays confirmation message with "Create Another Student" and "Return to Dashboard" action buttons
  - Inline validation errors displayed below each field
  - Matches existing design system (colors, typography, spacing)
  - `educator_dashboard.html`: Added "Add Student" button in header linking to add-student page

- **Baseline Vocabulary Data:**

  - Created `data/baseline/` directory with JSON files for each grade level
  - Each file contains array of word objects: `{word, definition, difficulty, grade_level}`
  - Initial seed: 5 words per grade (expandable to 500-800 words per grade as specified in PRD)
  - JSON structure allows easy expansion with additional vocabulary data

- **Testing (`tests/test_student_creation.py`):**
  - `test_educator_add_student_form_success`: Verifies form-based student creation, profile creation, and baseline word loading
  - `test_duplicate_username_via_form_shows_error`: Tests duplicate username validation via form
  - `test_api_create_student_success`: Verifies JSON API endpoint returns 201 with correct payload
  - `test_api_validation_error_returns_400`: Tests validation error handling via API
  - `test_api_duplicate_returns_conflict`: Tests duplicate username returns 409 status code
  - All tests passing (13 passed, 1 skipped total test suite)

**Key Decisions:**

- **Idempotent Baseline Loading:** `ensure_baseline_words_loaded()` checks if table is empty before loading, preventing duplicate inserts on multiple calls. This allows safe calling from multiple routes without race conditions
- **Fallback Seed Data:** Implemented minimal fallback vocabulary (2 words per grade) if JSON files are missing, ensuring tests and development can proceed even without full vocabulary datasets
- **Shared Validation Logic:** Created `_validate_student_submission()` helper function used by both form and API routes to ensure consistent validation rules and reduce code duplication
- **Automatic Baseline Initialization:** Baseline vocabulary is loaded automatically on first student creation attempt, eliminating need for separate migration step
- **Dual Endpoint Strategy:** Provided both form-based (`/educator/add-student`) and JSON API (`/api/students/create`) endpoints to support both UI interactions and potential future programmatic integrations
- **Success State Management:** Form template uses `success` flag to display different UI states (form vs. success confirmation), improving UX with clear feedback
- **Grade Level Validation:** Strict validation ensures grade_level is exactly 6, 7, or 8 (no other values accepted) to match PRD requirements
- **Profile-User Relationship:** Student profile is created immediately after user account creation, ensuring data consistency and enabling future vocabulary tracking features

---

### PR #4: File Upload and Text Ingestion

**Status:** ✅ Completed  
**Date Started:** November 10, 2025  
**Date Completed:** November 10, 2025

**Prompting Strategy:**

- Generated structured implementation prompt from Task List with clear goal, modified files, acceptance criteria, and diff plan
- Used step-by-step approach: database schema → model functions → routes → templates → tests
- Implemented S3 integration with optional SQS job queue support

**Implementation Notes:**

- **Database Schema (`models/__init__.py`):**

  - Created `uploads` table: id (PK), educator_id (FK), student_id (FK), file_path (S3 URL), filename, status (pending/processing/completed/failed), processed_at (nullable), created_at
  - Added indexes on `uploads.student_id` and `uploads.status` for query performance
  - Foreign key constraints with CASCADE delete for data integrity
  - Dual-backend support (SQLite and PostgreSQL) with appropriate syntax differences
  - Status enum constraint: CHECK (status IN ('pending', 'processing', 'completed', 'failed'))

- **Model Functions (`models/__init__.py`):**

  - `list_students_for_educator(educator_id)`: Returns students belonging to an educator ordered by name (for upload page dropdown)
  - `create_upload_record()`: Inserts upload metadata and returns upload_id
  - `update_upload_status()`: Updates status and optionally processed_at timestamp
  - `get_upload_status()`: Returns current status string for an upload_id

- **Configuration (`config/settings.py`):**

  - Added `AWS_SQS_QUEUE_URL` to Settings dataclass for optional job queue integration
  - Maintains backward compatibility (queue URL is optional)

- **Routes (`app/routes.py`):**

  - `/educator/upload` (GET): Upload page with student selection dropdown and drag-and-drop file zone
  - `/api/upload` (POST): Multi-file upload endpoint with validation, S3 storage, database tracking, and optional SQS job enqueueing
  - `/api/job-status/<int:upload_id>` (GET): Returns current processing status for an upload
  - File validation: Supports TXT, DOCX, PDF, CSV formats; max 10MB per file
  - S3 key naming: `uploads/{educator_id}/{student_id}/{timestamp}_{filename}`
  - Returns 207 Multi-Status when some files succeed and others fail
  - Uses `secure_filename()` from Werkzeug for filename sanitization

- **S3 Integration:**

  - `_make_boto_client()`: Creates boto3 clients (S3, SQS) with optional credential injection
  - `_enqueue_upload_job()`: Sends SQS message with upload_id attribute (no-op if queue URL not configured)
  - Graceful handling when AWS credentials or bucket name not configured

- **Templates:**

  - `educator_upload.html`: Drag-and-drop upload interface with file list, remove functionality, and progress feedback
  - Student dropdown populated from `list_students_for_educator()`
  - Visual file list with remove buttons
  - Upload progress indicator and JSON result display
  - Matches design spec (colors, typography, spacing)
  - `educator_dashboard.html`: Added "Upload Work" button linking to upload page

- **Testing (`tests/test_upload_api.py`):**

  - `test_upload_creates_record_and_queues_job`: Verifies S3 upload, database record creation, and SQS job enqueueing with fake clients
  - `test_upload_rejects_invalid_extension`: Tests file type validation
  - `test_job_status_not_found_returns_404`: Tests error handling for missing uploads
  - All tests passing (18 passed, 1 skipped total test suite)

- **Dependencies (`requirements.txt`):**

  - Added text extraction libraries for PR #5 preparation:
    - `python-docx==1.2.0` (for DOCX file extraction)
    - `pdfplumber==0.11.8` (for PDF file extraction)
    - `pandas==2.3.3` (for CSV file processing)
  - All packages installed and verified importable

**Key Decisions:**

- **Optional SQS Integration:** SQS queue URL is optional; if not configured, job enqueueing is skipped but upload still succeeds. This allows development/testing without full AWS setup while maintaining production-ready architecture
- **Multi-File Upload Support:** Single endpoint handles multiple files in one request, returning per-file results. Uses 207 Multi-Status HTTP code when partial success occurs
- **Status Tracking:** Upload status progresses: 'pending' → 'processing' → 'completed'/'failed'. Background worker (PR #5) will update status during processing
- **File Size Validation:** 10MB limit per file enforced before S3 upload to prevent large file processing issues
- **S3 Key Structure:** Hierarchical naming (`uploads/{educator_id}/{student_id}/{timestamp}_{filename}`) enables easy organization and cleanup by educator/student
- **Dual-Backend Support:** Upload table schema works with both SQLite (dev) and PostgreSQL (production) without code changes
- **Error Handling:** Network/boto errors caught per-file, allowing other files to succeed even if one fails
- **Security:** Uses `secure_filename()` to sanitize filenames, preventing path traversal and special character issues
- **Text Extraction Libraries:** Pre-installed libraries needed for PR #5 to enable immediate implementation of background job processor

---

### PR #5: AI Vocabulary Recommendation Engine (GPT‑4o Integration)

**Status:** ✅ Completed  
**Date Started:** November 10, 2025  
**Date Completed:** November 10, 2025

**Prompting Strategy:**

- Generated structured implementation prompt from Task List requirements with goal, modified files, acceptance criteria, and diff plan
- Implemented in logical layers: dependencies → data access → services → worker → routes → tests
- Used repository pattern for data access abstraction
- Comprehensive test coverage for all components

**Implementation Notes:**

- **Dependencies (`requirements.txt`):**

  - Added `better-profanity==0.7.0` (updated from 0.1.6 due to version availability)
  - All other required libraries already present: `openai`, `python-docx`, `pdfplumber`, `pandas`

- **Settings Extension (`config/settings.py`):**

  - Added `MIN_INITIAL_ANALYSIS_WORDS` (200) and `MIN_UPDATE_ANALYSIS_WORDS` (100)
  - Added `AI_MAX_RETRIES` (3), `AI_RETRY_BACKOFF_BASE` (1.5), `AI_RETRY_BACKOFF_CAP` (60)
  - Added `JOB_POLL_INTERVAL_SECONDS` (5) for worker polling
  - Added `ENABLE_CONTENT_FILTER` (True) toggle

- **Database Schema (`models/__init__.py`):**

  - Created `recommendations` table with all required fields:
    - `id`, `student_id`, `upload_id`, `word`, `definition`, `rationale`, `difficulty_score` (1-10), `example_sentence`, `status` ('pending'/'approved'/'rejected'), `pinned`, `created_at`
  - Added indexes on `student_id` and `upload_id` for performance
  - Functions: `create_recommendations()`, `list_recommendations_for_upload()`, `delete_recommendations_for_upload()`

- **Text Extraction Service (`app/services/text_extraction.py`):**

  - Supports TXT (direct read), DOCX (python-docx), PDF (pdfplumber), CSV (pandas)
  - `extract_text()`: Unified interface for all file types
  - `word_count()`: Helper for minimum word validation
  - Raises `UnsupportedFileTypeError` for invalid formats

- **PII Scrubbing Service (`app/services/pii.py`):**

  - Regex-based removal of emails, phone numbers, and common name patterns
  - `scrub_pii()`: Main function that applies all scrubbing rules
  - `contains_pii()`: Detection helper for testing

- **Content Filtering Service (`app/services/content_filter.py`):**

  - Uses `better-profanity` library for profanity filtering
  - Filters recommendations by word and definition fields
  - Normalizes difficulty scores to 1-10 range with defaults
  - Removes any recommendations containing profane or sensitive terms

- **OpenAI Client Service (`app/services/openai_client.py`):**

  - Thin wrapper around OpenAI API with proper error handling
  - `OpenAIConfigurationError`: Raised when API key missing
  - `OpenAIResponseError`: Raised for API failures
  - Configurable model (defaults to GPT-4o)

- **Recommendations Service (`app/services/recommendations.py`):**

  - `generate_recommendations()`: Main function that orchestrates GPT-4o call
  - Prompt engineering includes student profile, writing sample, baseline words
  - Parses JSON response with validation
  - Ensures minimum 5 recommendations per batch
  - Raises `RecommendationParseError` for invalid responses

- **Job Queue System (`app/jobs/queue.py`):**

  - Dual-mode support: AWS SQS (production) or local in-memory queue (development)
  - `enqueue_upload_job()`: Adds jobs to queue
  - `dequeue_upload_job()`: Retrieves jobs with timeout
  - `ack_job()`: Marks jobs as processed
  - Automatic fallback to local queue if SQS not configured

- **Background Worker (`app/jobs/worker.py`):**

  - `process_upload_job()`: Processes single upload with retry logic
  - `run_worker_loop()`: Continuous polling loop for job processing
  - Workflow: Mark processing → Extract text → Validate word count → Scrub PII → Generate recommendations → Filter content → Store recommendations → Mark completed/failed
  - Implements `PermanentJobError` for non-retryable failures (invalid input, missing files)
  - Graceful signal handling (SIGINT, SIGTERM) for shutdown
  - Main entry point: `python -m app.jobs.worker`

- **Repository Layer:**

  - `app/repositories/uploads_repo.py`: Upload status management
  - `app/repositories/recommendations_repo.py`: Recommendation CRUD operations
  - `app/repositories/student_profiles_repo.py`: Profile fetching and baseline word loading

- **Retry Utility (`app/utils/retry.py`):**

  - `execute_with_retry()`: Exponential backoff with jitter
  - Configurable max attempts, base delay, cap
  - Supports non-retryable exception types

- **Routes Integration (`app/routes.py`):**

  - Upload route already enqueues jobs via `enqueue_upload_job()`
  - `/api/job-status/<id>` endpoint returns upload processing status

- **Testing:**

  - `tests/test_text_extraction.py`: Tests for all file types
  - `tests/test_pii_scrubbing.py`: PII detection and removal
  - `tests/test_content_filter.py`: Profanity filtering and normalization
  - `tests/test_recommendation_flow.py`: End-to-end upload → processing → recommendations
  - All 27 tests passing

- **Documentation (`README.md`):**
  - Added "Running the Background Worker" section with instructions
  - Documented required environment variables for worker
  - Updated project structure to include `app/jobs/` directory

**Key Decisions:**

- **Repository Pattern:** Used repository abstraction layer to separate data access from business logic, making code more testable and maintainable
- **Dual Queue Backend:** Implemented local in-memory queue as fallback when SQS not configured, enabling development without AWS setup
- **Permanent vs Retryable Errors:** Distinguished between errors that should retry (API failures, network issues) vs permanent failures (invalid input, missing files)
- **Minimum Recommendation Count:** Enforced minimum 5 recommendations after filtering to ensure quality output
- **Worker Entry Point:** Added `if __name__ == "__main__"` block to enable running worker as standalone script
- **Content Filtering:** Applied filtering after AI generation rather than in prompt to catch edge cases
- **Word Count Validation:** Different thresholds for initial analysis (200 words) vs updates (100 words) based on student profile state
- **Error Handling:** Comprehensive error handling with logging at each stage, never exposing stack traces to users

**Lessons Learned:**

- **Version Compatibility:** `better-profanity` version 0.1.6 doesn't exist; had to update to 0.7.0. Always verify package versions before specifying exact versions.
- **Worker Lifecycle:** Background workers need proper signal handling and graceful shutdown mechanisms for production deployment
- **Testing Async Jobs:** Used `stop_after` parameter in worker loop for testability, allowing controlled job processing in tests
- **PII Scrubbing:** Regex-based scrubbing is effective but may have false positives/negatives; consider more sophisticated NLP-based approaches for production
- **Content Filtering:** Filtering after generation is safer than relying on AI to avoid profanity, but adds processing overhead

---

### PR #6: Educator Dashboard

**Status:** Not Started  
**Date Started:** TBD  
**Date Completed:** TBD

**Prompting Strategy:**

- TBD

**Implementation Notes:**

- TBD

**Key Decisions:**

- TBD

---

### PR #7: Educator Recommendations Page (Approval Workflow)

**Status:** Not Started  
**Date Started:** TBD  
**Date Completed:** TBD

**Prompting Strategy:**

- TBD

**Implementation Notes:**

- TBD

**Key Decisions:**

- TBD

---

### PR #8: Student Dashboard

**Status:** Not Started  
**Date Started:** TBD  
**Date Completed:** TBD

**Prompting Strategy:**

- TBD

**Implementation Notes:**

- TBD

**Key Decisions:**

- TBD

---

### PR #9: Gamification & Quizzes

**Status:** Not Started  
**Date Started:** TBD  
**Date Completed:** TBD

**Prompting Strategy:**

- TBD

**Implementation Notes:**

- TBD

**Key Decisions:**

- TBD

---

### PR #10: Cold‑Start Calibration & Profile Refinement

**Status:** Not Started  
**Date Started:** TBD  
**Date Completed:** TBD

**Prompting Strategy:**

- TBD

**Implementation Notes:**

- TBD

**Key Decisions:**

- TBD

---

### PR #11: Data Privacy, Filtering & Explainability Layer

**Status:** ✅ Completed  
**Date Started:** November 10, 2025  
**Date Completed:** November 10, 2025

**Prompting Strategy:**

- Generated structured implementation prompt from Task List with clear goal, modified files, acceptance criteria, and diff plan
- Focused on privacy enhancements, content filtering, and UI explainability features
- Implemented in phases: configuration → services → routes → templates → tests → documentation

**Implementation Notes:**

- **PII Scrubbing (`app/services/pii.py`):**

  - Enhanced email regex pattern matching
  - Phone number regex with multiple format support (including `+1 555.123.4567`)
  - Labeled name patterns (Name:, Student:, Teacher:, etc.)
  - Unlabeled full name detection via `FULL_NAME_REGEX` (2-3 capitalized words)
  - `scrub_pii()` function replaces all PII with `[REDACTED_*]` tokens
  - `contains_pii()` detection function for validation

- **Content Filtering (`app/services/content_filter.py`):**

  - Profanity filtering via `better_profanity` library
  - Custom sensitive terms wordlist support from `CONTENT_FILTER_EXTRA_WORDS_PATH`
  - Lazy loading of extra words on first use
  - Filters word, definition, and example_sentence fields
  - Normalizes difficulty scores (clamps to 1-10 range)
  - Graceful handling when wordlist file missing or unreadable

- **Student Dashboard Explainability (`templates/student_dashboard.html`):**

  - Info icon tooltip (blue circular badge with "i") showing rationale on hover
  - Visual difficulty meter with gradient (green → yellow → red) representing 1-10 scale
  - Accessible implementation with ARIA attributes
  - Rationale displayed inline as "Why this word:" section
  - Difficulty meter positioned below word title for visual clarity

- **Educator Privacy Controls (`templates/educator_dashboard.html`, `app/routes.py`):**

  - Anonymization toggle checkbox in dashboard header
  - JavaScript toggles URL parameter and reloads page
  - CSV export endpoint (`/api/educator/export`) with anonymization support
  - Anonymized dashboard view via `?anonymized=true` query parameter
  - Export URL properly handles query parameters (fixed to use dict unpacking)
  - Student names masked as "Student #<id>" when anonymized

- **Configuration (`config/settings.py`):**

  - `CONTENT_FILTER_EXTRA_WORDS_PATH` setting (optional file path)
  - `PRIVACY_DEFAULT_ANONYMIZED` setting (defaults to `false`)
  - Environment variable support with safe defaults

- **Documentation (`README.md`):**

  - Added "Privacy & Compliance" section
  - Documented PII scrubbing patterns and content filtering approach
  - FERPA/COPPA compliance notes
  - Environment variable documentation for new settings

- **Testing:**

  - `tests/test_pii_scrubbing.py`: Email/phone/labeled/unlabeled name scrubbing tests
  - `tests/test_content_filter.py`: Profanity filtering, extra wordlist filtering, difficulty normalization
  - `tests/test_privacy_educator_api.py`: Dashboard anonymization, CSV export anonymization, default behavior
  - All tests passing

- **Supporting Files:**
  - `static/wordlists/sensitive_terms.txt`: Sample sensitive terms wordlist (violence, self-harm, weapon)
  - Directory structure created for future customization

**Key Decisions:**

- **PII Scrubbing Timing:** Applied before AI calls in background worker (`app/jobs/worker.py`) to ensure no PII reaches OpenAI API
- **Content Filtering Location:** Post-AI filtering (after generation) is safer than relying on AI prompts to avoid profanity
- **Full Name Detection:** Conservative regex pattern (2-3 capitalized words) to minimize false positives; may need refinement for production
- **Anonymization Default:** Defaults to `false` to maintain usability; educators can opt-in for compliance scenarios
- **Export Format:** CSV chosen over PDF for easier data manipulation and FERPA compliance
- **UI Explainability:** Tooltips and visual meters provide context without cluttering interface
- **Extra Wordlist Loading:** Lazy loading prevents startup failures if file path misconfigured

**Lessons Learned:**

- **Flask url_for with None:** Passing `None` as query parameter value can cause issues; better to conditionally include parameters using dict unpacking
- **PII Regex False Positives:** Full name regex may match common phrases; consider more sophisticated NLP approaches for production
- **Content Filter Performance:** Loading extra wordlist on first use adds minimal overhead but improves maintainability
- **Accessibility:** Info icons need both `title` attribute and ARIA labels for screen reader compatibility

---

### PR #12: System Testing & Integration Verification

**Status:** Not Started  
**Date Started:** TBD  
**Date Completed:** TBD

**Prompting Strategy:**

- TBD

**Implementation Notes:**

- TBD

**Key Decisions:**

- TBD

---

### PR #13: Deployment Setup (AWS)

**Status:** Not Started  
**Date Started:** TBD  
**Date Completed:** TBD

**Prompting Strategy:**

- TBD

**Implementation Notes:**

- TBD

**Key Decisions:**

- TBD

---

### PR #14: Deployment Verification & Final Testing

**Status:** Not Started  
**Date Started:** TBD  
**Date Completed:** TBD

**Prompting Strategy:**

- TBD

**Implementation Notes:**

- TBD

**Key Decisions:**

- TBD

---

### Feature: Class Number Support (Post-PR #12 Enhancement)

**Status:** Completed  
**Date Started:** November 11, 2025  
**Date Completed:** November 11, 2025

**Prompting Strategy:**

- User requested ability to organize students into multiple classes per grade (e.g., 601, 602 for 6th grade)
- Requested dashboard grouping by grade → class for better organization

**Implementation Notes:**

- **Database Schema (`models/__init__.py`):**

  - Added `class_number` INTEGER NOT NULL column to `student_profiles` table (both SQLite and PostgreSQL)
  - Added composite index on `(educator_id, grade_level, class_number)` for query performance
  - Class numbers follow pattern: first digit matches grade (6XX, 7XX, 8XX), range X01-X99

- **Model Functions (`models/__init__.py`):**

  - Updated `create_student_profile()` to accept and store `class_number` parameter
  - Updated all query functions to include `class_number` in SELECT statements:
    - `list_students_for_educator()` - Added class_number to SELECT
    - `list_students_with_stats_for_educator()` - Added class_number, updated ORDER BY to sort by grade, class, name
    - `get_student_profile()` - Added class_number to SELECT
    - `get_student_overview()` - Added class_number to SELECT and return dict

- **Routes (`app/routes.py`):**

  - Updated `_validate_student_submission()` to validate class_number:
    - Required field
    - Must be integer
    - First digit must match grade_level (6XX for grade 6, etc.)
    - Range validation: X01 to X99
  - Updated `educator_add_student()` to handle class_number in form data
  - Updated `api_create_student()` to handle class_number in JSON payload
  - Updated `educator_dashboard()` to group students by grade → class_number
  - Updated `api_educator_dashboard()` to include class_number in serialization
  - Updated `api_educator_export()` to include class_number in CSV export

- **Templates:**

  - `educator_add_student.html`: Added class_number input field with auto-fill JavaScript (updates when grade changes)
  - `educator_dashboard.html`: Redesigned to show nested structure (Grade → Class → Students), removed grade column from table
  - `educator_student_detail.html`: Added class_number display in student snapshot
  - `educator_upload.html`: Updated dropdown to show class number
  - `educator_recommendations.html`: Updated dropdown to show class number

- **Tests:**
  - Updated all test helper functions to include class_number parameter
  - Updated all direct `create_student_profile()` calls (17+ locations) to include class_number
  - Updated form submission tests to include class_number in test data
  - Updated CSV export test to expect class_number column

**Key Decisions:**

- Class number format: 3-digit integer where first digit matches grade (601-699, 701-799, 801-899)
- Default class_number in helper functions: grade \* 100 + 1 (601, 701, 801)
- Dashboard grouping: Nested structure (grade → class → students) for better organization
- Validation: Strict enforcement that class_number prefix matches grade_level

---

### Feature: Enhanced Dashboard with Class/Grade Filtering & Export (Post-PR #12 Enhancement)

**Status:** Completed  
**Date Started:** November 11, 2025  
**Date Completed:** November 11, 2025

**Prompting Strategy:**

- User requested removal of top-level "Average Class Proficiency" and "Active Streaks" cards
- User requested per-class average proficiency display
- User requested multi-level CSV export (all students, per-grade, per-class)
- User requested client-side filtering by grade and class
- User requested removal of anonymization toggle

**Implementation Notes:**

- **Model Functions (`models/__init__.py`):**

  - Added `average_vocabulary_level_for_class(educator_id, grade_level, class_number)` - Calculate average proficiency for specific class
  - Added `average_vocabulary_level_for_grade(educator_id, grade_level)` - Calculate average proficiency for entire grade
  - Added `list_students_with_stats_for_grade(educator_id, grade_level)` - Filter students by grade level
  - Added `list_students_with_stats_for_class(educator_id, grade_level, class_number)` - Filter students by grade and class
  - All functions support both SQLite and PostgreSQL backends

- **Routes (`app/routes.py`):**

  - Updated `educator_dashboard()`:
    - Removed anonymization logic and toggle support
    - Removed `active_streaks` and top-level `average_proficiency` from summary
    - Calculate per-class proficiency and structure data as nested dict: `{grade: {class: {students, avg_proficiency, count}}}`
  - Updated `api_educator_dashboard()`:
    - Removed `active_streaks` and `average_proficiency` from API response
  - Updated `api_educator_export()`:
    - Removed anonymization logic
    - Added CSV formula injection protection via `_csv_safe()` helper
  - Added `api_educator_export_grade(grade_level)`:
    - New route: `/api/educator/export/grade/<int:grade_level>`
    - Validates grade_level is 6, 7, or 8
    - Returns CSV with filename: `wordbridge_grade{grade}_{timestamp}.csv`
  - Added `api_educator_export_class(grade_level, class_number)`:
    - New route: `/api/educator/export/class/<int:grade_level>/<int:class_number>`
    - Validates class_number matches grade pattern (6XX, 7XX, 8XX)
    - Returns CSV with filename: `wordbridge_class{class_number}_{timestamp}.csv`
  - Added helper functions:
    - `_build_students_csv(students)` - Shared CSV generation logic
    - `_csv_safe(value)` - Escapes CSV formula injection characters

- **Templates (`templates/educator_dashboard.html`):**

  - Removed anonymization toggle and all related JavaScript
  - Removed "Average Class Proficiency" and "Active Streaks" summary cards
  - Added filter bar with grade and class dropdowns, reset button
  - Added "Export All Students CSV" button in filter bar
  - Updated class overview structure:
    - Added `data-grade` and `data-class` attributes for JavaScript filtering
    - Added grade-level export buttons next to grade headings
    - Added class-level export buttons next to class headings
    - Display per-class average proficiency in class metadata
  - Added comprehensive JavaScript filtering:
    - Client-side show/hide of grade and class sections
    - Dynamic class dropdown population based on selected grade
    - URL parameter persistence for filter state
    - Reset filters functionality
  - Updated CSS:
    - Added `.filter-bar`, `.filter-controls`, `.grade-header`, `.class-header` styles
    - Updated `.summary-grid` to 2-column layout (max-width: 600px)
    - Added responsive styles for mobile devices

- **Tests:**

  - Updated `tests/test_educator_dashboard.py`:
    - Removed assertions for `active_streaks` and `average_proficiency`
    - Updated test expectations to match new summary structure
  - Updated `tests/test_privacy_educator_api.py`:
    - Removed anonymization-related tests
    - Added comprehensive export tests:
      - `test_export_all_students_includes_all_names` - Verifies all-student export
      - `test_export_grade_filters_students` - Verifies grade-level export filters correctly
      - `test_export_grade_invalid_returns_error` - Verifies invalid grade returns 400
      - `test_export_class_filters_students` - Verifies class-level export filters correctly
      - `test_export_class_invalid_returns_error` - Verifies invalid class returns 400

**Key Decisions:**

- **Client-side filtering**: Used JavaScript for instant filtering without page reloads, matching existing anonymization toggle pattern
- **Per-class proficiency**: Calculated server-side during dashboard rendering for efficiency
- **Export URLs**: RESTful pattern `/api/educator/export/grade/{grade}` and `/api/educator/export/class/{grade}/{class}`
- **CSV security**: Added formula injection protection by escaping values starting with `=`, `+`, `-`, `@`
- **Filter state**: Persisted in URL parameters for bookmarking/sharing
- **Anonymization removal**: Completely removed from dashboard (still available in other routes if needed)

---

## General Implementation Patterns

**Common Prompting Strategies:**

- TBD (will be documented as patterns emerge)

**Reusable Code Patterns:**

- TBD (will be documented as patterns emerge)

**Lessons Learned:**

- TBD (will be documented throughout implementation)

---

## Notes

This log will be actively maintained during the implementation phase. Each PR entry will include:

- The specific prompts used to guide implementation
- Key implementation decisions and rationale
- Any deviations from the original plan
- Lessons learned and reusable patterns

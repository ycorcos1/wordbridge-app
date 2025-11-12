# WordBridge Manual Testing Plan - PR #12

**Date:** [Fill in date]  
**Tester:** [Fill in name]  
**Environment:** [Local/Staging/Production]  
**Browser:** [Chrome/Firefox/Safari/Edge]

---

## Pre-Testing Setup

### Prerequisites Checklist

- [ ] Application is running locally or accessible via URL
- [ ] Database is initialized and accessible
- [ ] Background worker is running (for AI processing)
- [ ] OpenAI API key is configured (or using mock/test mode)
- [ ] AWS S3 bucket is configured (or using local storage)
- [ ] Test files prepared (see Test Data section below)

### Test Data Preparation

Test data files are located in `test_data/` directory:

- [ ] `sample_essay_6th.txt` - ~250 words, 6th grade level content
- [ ] `sample_essay_7th.txt` - ~250 words, 7th grade level content
- [ ] `sample_essay_8th.txt` - ~250 words, 8th grade level content
- [ ] `short_text.txt` - ~50 words (for error testing)
- [ ] `large_text.txt` - >10MB (for error testing)
- [ ] `sample_essay.docx` - DOCX format, ~200 words
- [ ] `sample_data.csv` - CSV format with text content

---

## 1. Authentication & Access Control Testing

### 1.1 Educator Signup

**Objective:** Verify educator account creation works correctly.

**Steps:**

1. Navigate to `/signup` page
2. Fill in the form:
   - Name: "Test Educator"
   - Username: "test_educator"
   - Email: "test_educator@example.com"
   - Password: "TestPass123!"
   - Confirm Password: "TestPass123!"
3. Click "Create Account"

**Expected Results:**

- [ ] Success message displayed: "Educator account created successfully"
- [ ] Redirected to login page
- [ ] No errors in browser console
- [ ] Account can be used to log in

**Error Cases:**

- [ ] Try duplicate username → Error message displayed
- [ ] Try duplicate email → Error message displayed
- [ ] Try password < 8 characters → Validation error
- [ ] Try mismatched passwords → Validation error
- [ ] Try invalid email format → Validation error

---

### 1.2 Login - Educator

**Objective:** Verify educator login and role-based routing.

**Steps:**

1. Navigate to `/login` page
2. Select "Educator" role
3. Enter credentials (username or email)
4. Enter password
5. Click "Log In"

**Expected Results:**

- [ ] Successfully logged in
- [ ] Redirected to `/educator/dashboard`
- [ ] Educator dashboard displays correctly
- [ ] No errors in browser console

**Error Cases:**

- [ ] Wrong password → Error message: "Invalid credentials"
- [ ] Wrong username/email → Error message: "Invalid credentials"
- [ ] Select "Student" role with educator credentials → Error: "Role mismatch"

---

### 1.3 Login - Student

**Objective:** Verify student login and role-based routing.

**Steps:**

1. Navigate to `/login` page
2. Select "Student" role
3. Enter student credentials
4. Enter password
5. Click "Log In"

**Expected Results:**

- [ ] Successfully logged in
- [ ] Redirected to `/student/dashboard`
- [ ] Student dashboard displays correctly
- [ ] Cannot access educator routes (test `/educator/dashboard` → should get 403)

**Error Cases:**

- [ ] Wrong password → Error message displayed
- [ ] Select "Educator" role with student credentials → Error: "Role mismatch"

---

### 1.4 Role-Based Access Control

**Objective:** Verify students cannot access educator routes and vice versa.

**Test as Student:**

- [ ] Try accessing `/educator/dashboard` → 403 Forbidden or redirect
- [ ] Try accessing `/educator/add-student` → 403 Forbidden or redirect
- [ ] Try accessing `/educator/upload` → 403 Forbidden or redirect
- [ ] Try accessing `/educator/recommendations` → 403 Forbidden or redirect

**Test as Educator:**

- [ ] Try accessing `/student/dashboard` → 403 Forbidden or redirect
- [ ] Try accessing `/quiz` → 403 Forbidden or redirect

---

### 1.5 Logout

**Objective:** Verify logout functionality.

**Steps:**

1. While logged in, click "Logout" button
2. Verify session is cleared

**Expected Results:**

- [ ] Logged out successfully
- [ ] Redirected to login page
- [ ] Cannot access protected routes without logging in again
- [ ] Session cookie cleared

---

## 2. Student Account Creation (Educator Feature)

### 2.1 Create Student - Single

**Objective:** Verify educator can create student accounts.

**Steps:**

1. Log in as educator
2. Navigate to `/educator/add-student`
3. Fill in form:
   - Name: "Test Student 6"
   - Grade: "6th"
   - Class Number: "601" (auto-filled when grade is selected)
   - Username: "test_student_6"
   - Email: "test_student_6@example.com"
   - Password: "StudentPass123!"
4. Click "Create Student Account"

**Expected Results:**

- [ ] Success message: "Student account created successfully!"
- [ ] Form resets or shows "Create Another Student" option
- [ ] Student appears in educator dashboard
- [ ] Student can log in with created credentials

**Repeat for:**

- [ ] Create student for 7th grade
- [ ] Create student for 8th grade

**Error Cases:**

- [ ] Try duplicate username → Error message
- [ ] Try duplicate email → Error message
- [ ] Try invalid grade → Validation error
- [ ] Try password < 8 characters → Validation error
- [ ] Try class_number that doesn't match grade (e.g., 701 for grade 6) → Validation error
- [ ] Try class_number outside valid range (e.g., 600, 700) → Validation error
- [ ] Try empty class_number → Validation error

---

### 2.2 Create Student - API

**Objective:** Verify student creation via API endpoint.

**Steps:**

1. Log in as educator
2. Use API endpoint: `POST /api/students/create`
3. Send JSON payload with student data (including `class_number`)

**Expected Results:**

- [ ] Returns 201 Created status
- [ ] Returns student ID, grade_level, and class_number
- [ ] Student appears in dashboard

---

### 2.3 Create Multiple Students in Different Classes

**Objective:** Verify students are grouped by grade and class on dashboard.

**Steps:**

1. Log in as educator
2. Create students in different classes:
   - Student A: Grade 6, Class 601
   - Student B: Grade 6, Class 602
   - Student C: Grade 7, Class 701
   - Student D: Grade 8, Class 801
3. Navigate to `/educator/dashboard`

**Expected Results:**

- [ ] Dashboard shows nested structure:
  - [ ] 6th Grade section
    - [ ] Class 601 subsection with Student A
    - [ ] Class 602 subsection with Student B
  - [ ] 7th Grade section
    - [ ] Class 701 subsection with Student C
  - [ ] 8th Grade section
    - [ ] Class 801 subsection with Student D
- [ ] Each class shows student count
- [ ] Students are sorted by name within each class

---

## 2.4 Educator Dashboard - Filtering & Export

### 2.4.1 Dashboard Summary Cards

**Objective:** Verify summary cards display correctly after removing old metrics.

**Steps:**

1. Log in as educator
2. Navigate to `/educator/dashboard`
3. Review the summary section at the top

**Expected Results:**

- [ ] Only 2 summary cards are displayed:
  - [ ] "Total Students" card with correct count
  - [ ] "Pending Recommendations" card with correct count
- [ ] "Average Class Proficiency" card is NOT present
- [ ] "Active Streaks" card is NOT present
- [ ] Anonymization toggle is NOT present

---

### 2.4.2 Per-Class Proficiency Display

**Objective:** Verify each class shows its average proficiency.

**Steps:**

1. Log in as educator with multiple students in different classes
2. Navigate to `/educator/dashboard`
3. Review each class section

**Expected Results:**

- [ ] Each class heading shows: "Class XXX • N students • Avg proficiency: XXX.X"
- [ ] Average proficiency value matches the average of vocabulary_level for students in that class
- [ ] Values are formatted to one decimal place (e.g., "475.5")

---

### 2.4.3 Grade Filtering

**Objective:** Verify grade filter works correctly.

**Steps:**

1. Log in as educator with students in multiple grades (6th, 7th, 8th)
2. Navigate to `/educator/dashboard`
3. Use the "Filter by grade" dropdown

**Expected Results:**

- [ ] Default shows "All grades" - all grade sections visible
- [ ] Select "6th grade" → Only 6th grade section visible, 7th and 8th hidden
- [ ] Select "7th grade" → Only 7th grade section visible
- [ ] Select "8th grade" → Only 8th grade section visible
- [ ] Filtering happens instantly (no page reload)
- [ ] URL updates with `?grade=6` parameter (shareable/bookmarkable)
- [ ] Class filter dropdown becomes enabled when grade is selected

---

### 2.4.4 Class Filtering

**Objective:** Verify class filter works correctly.

**Steps:**

1. Log in as educator with students in multiple classes within same grade
2. Navigate to `/educator/dashboard`
3. Use the filtering controls

**Expected Results:**

- [ ] Select a grade (e.g., "6th grade")
- [ ] Class filter dropdown populates with classes in that grade (e.g., "Class 601", "Class 602")
- [ ] Select "All classes" → All classes in selected grade visible
- [ ] Select specific class (e.g., "Class 601") → Only that class visible
- [ ] Filtering happens instantly (no page reload)
- [ ] URL updates with `?grade=6&class=601` parameters
- [ ] Reset filters button clears both filters and shows all grades/classes

---

### 2.4.5 Export All Students CSV

**Objective:** Verify export of all students works correctly.

**Steps:**

1. Log in as educator with multiple students
2. Navigate to `/educator/dashboard`
3. Click "Export all students CSV" button

**Expected Results:**

- [ ] CSV file downloads with filename: `wordbridge_all_students_YYYYMMDD_HHMMSS.csv`
- [ ] CSV contains all students regardless of grade/class
- [ ] CSV headers: `id, name, grade_level, class_number, vocabulary_level, pending_words, last_upload_at`
- [ ] All student data is present and correct
- [ ] Student names are NOT anonymized (real names shown)

---

### 2.4.6 Export Grade-Level CSV

**Objective:** Verify grade-level export works correctly.

**Steps:**

1. Log in as educator with students in multiple grades
2. Navigate to `/educator/dashboard`
3. Find a grade section (e.g., "6th Grade")
4. Click "Export 6th grade CSV" button next to the grade heading

**Expected Results:**

- [ ] CSV file downloads with filename: `wordbridge_grade6_YYYYMMDD_HHMMSS.csv`
- [ ] CSV contains ONLY students from that grade
- [ ] Students from other grades are NOT included
- [ ] CSV headers match standard format
- [ ] All data is correct for filtered students

**Repeat for:**

- [ ] Export 7th grade CSV
- [ ] Export 8th grade CSV

---

### 2.4.7 Export Class-Level CSV

**Objective:** Verify class-level export works correctly.

**Steps:**

1. Log in as educator with students in multiple classes
2. Navigate to `/educator/dashboard`
3. Find a class section (e.g., "Class 601")
4. Click "Export class CSV" button next to the class heading

**Expected Results:**

- [ ] CSV file downloads with filename: `wordbridge_class601_YYYYMMDD_HHMMSS.csv`
- [ ] CSV contains ONLY students from that specific class
- [ ] Students from other classes are NOT included
- [ ] CSV headers match standard format
- [ ] All data is correct for filtered students

**Repeat for:**

- [ ] Export different classes (602, 701, 801, etc.)

---

### 2.4.8 Export Error Handling

**Objective:** Verify export endpoints handle invalid requests correctly.

**Steps:**

1. Log in as educator
2. Try accessing invalid export URLs directly

**Expected Results:**

- [ ] `/api/educator/export/grade/9` → Returns 400 Bad Request with error message
- [ ] `/api/educator/export/grade/5` → Returns 400 Bad Request
- [ ] `/api/educator/export/class/6/999` → Returns 400 Bad Request (class doesn't match grade pattern)
- [ ] `/api/educator/export/class/6/501` → Returns 400 Bad Request (class prefix doesn't match grade)
- [ ] Error messages are clear and helpful

---

### 2.4.9 Filter State Persistence

**Objective:** Verify filter state persists in URL and can be shared.

**Steps:**

1. Log in as educator
2. Navigate to `/educator/dashboard`
3. Apply filters (e.g., select "6th grade" and "Class 601")
4. Copy the URL from browser address bar
5. Open URL in new tab/window

**Expected Results:**

- [ ] URL contains filter parameters: `?grade=6&class=601`
- [ ] Opening URL in new tab shows the same filtered view
- [ ] Filters are correctly applied when page loads
- [ ] Can bookmark filtered views

---

### 2.4.10 Mobile Responsiveness

**Objective:** Verify dashboard works on mobile devices.

**Steps:**

1. Log in as educator
2. Navigate to `/educator/dashboard`
3. Resize browser window to mobile size (<768px) or use mobile device

**Expected Results:**

- [ ] Filter controls stack vertically on mobile
- [ ] Export buttons wrap appropriately
- [ ] Grade and class headers stack vertically
- [ ] Tables remain scrollable horizontally
- [ ] All functionality works on mobile

---

## 3. File Upload & Processing

### 3.1 Upload Single File - TXT

**Objective:** Verify file upload works for TXT files.

**Steps:**

1. Log in as educator
2. Navigate to `/educator/upload`
3. Select a student from dropdown
4. Upload `test_data/sample_essay_6th.txt` (drag-and-drop or file picker)
5. Click "Upload and Process"

**Expected Results:**

- [ ] File uploads successfully
- [ ] Success message displayed
- [ ] Upload status shows "pending" or "processing"
- [ ] File appears in upload history
- [ ] Background worker processes the file (check status endpoint)

**Verify:**

- [ ] File is stored in S3 (or local storage)
- [ ] Upload record created in database
- [ ] Job queued for processing

---

### 3.2 Upload Multiple Files

**Objective:** Verify multi-file upload capability.

**Steps:**

1. Log in as educator
2. Navigate to `/educator/upload`
3. Select a student
4. Upload multiple files simultaneously:
   - `test_data/sample_essay_6th.txt`
   - `test_data/sample_essay.docx`
   - `test_data/sample_essay_7th.txt`
5. Click "Upload and Process"

**Expected Results:**

- [ ] All files upload successfully
- [ ] Each file shows in file list
- [ ] Can remove individual files before upload
- [ ] All files processed independently

---

### 3.3 Upload Different File Types

**Objective:** Verify support for all file formats.

**Test each format:**

- [ ] **TXT file** (`test_data/sample_essay_6th.txt`) → Uploads and processes correctly
- [ ] **DOCX file** (`test_data/sample_essay.docx`) → Uploads and processes correctly
- [ ] **PDF file** (create manually or use test file) → Uploads and processes correctly
- [ ] **CSV file** (`test_data/sample_data.csv`) → Uploads and processes correctly

**Expected Results:**

- [ ] All supported formats work
- [ ] Text extracted correctly from each format
- [ ] Recommendations generated for each

---

### 3.4 Upload Error Cases

**Objective:** Verify error handling for invalid uploads.

**Test Cases:**

- [ ] **No file selected** → Error: "No files provided"
- [ ] **Unsupported file type** (e.g., `.exe`, `.zip`) → Error: "Unsupported file type"
- [ ] **File too large** (`test_data/large_text.txt` >10MB) → Error: "File exceeds 10MB limit"
- [ ] **No student selected** → Error: "student_id is required"
- [ ] **S3 not configured** → Error message displayed (if applicable)

**Expected Results:**

- [ ] Clear, user-friendly error messages
- [ ] No stack traces exposed to user
- [ ] Application remains stable

---

### 3.5 Job Status Tracking

**Objective:** Verify upload processing status can be checked.

**Steps:**

1. Upload a file
2. Note the upload ID
3. Check status via API: `GET /api/job-status/<upload_id>`

**Expected Results:**

- [ ] Status endpoint returns current status
- [ ] Status progresses: `pending` → `processing` → `completed` (or `failed`)
- [ ] Status updates in real-time (polling or refresh)

---

## 4. AI Processing & Recommendations

### 4.1 Initial Profile Creation

**Objective:** Verify AI generates recommendations for first upload.

**Steps:**

1. Create a new student (6th grade)
2. Upload `test_data/sample_essay_6th.txt` (≥200 words)
3. Wait for background worker to process
4. Check recommendations page

**Expected Results:**

- [ ] Processing completes successfully
- [ ] At least 5 recommendations generated
- [ ] Recommendations have status "pending"
- [ ] Each recommendation includes:
  - [ ] Word
  - [ ] Definition
  - [ ] Rationale
  - [ ] Difficulty score (1-10)
  - [ ] Example sentence
- [ ] Student profile vocabulary_level updated

---

### 4.2 Profile Refinement

**Objective:** Verify subsequent uploads refine the profile.

**Steps:**

1. Upload second file for same student (`test_data/sample_essay_7th.txt`, ≥100 words)
2. Wait for processing
3. Check recommendations

**Expected Results:**

- [ ] New recommendations generated
- [ ] Vocabulary level adjusted based on new data
- [ ] Profile updated incrementally

---

### 4.3 Minimum Word Count Requirements

**Objective:** Verify word count validation.

**Test Cases:**

- [ ] **First upload < 200 words** (`test_data/short_text.txt`) → Error: "Upload has X words; 200 required"
- [ ] **Subsequent upload < 100 words** → Error: "Upload has X words; 100 required"
- [ ] **First upload ≥ 200 words** → Processes successfully
- [ ] **Subsequent upload ≥ 100 words** → Processes successfully

---

### 4.4 Content Filtering

**Objective:** Verify profanity and sensitive terms are filtered.

**Steps:**

1. Upload text containing profanity (if possible in test environment)
2. Check recommendations

**Expected Results:**

- [ ] No profane words in recommendations
- [ ] No sensitive terms in recommendations
- [ ] Filtering happens automatically

---

### 4.5 PII Scrubbing

**Objective:** Verify PII is removed before AI processing.

**Steps:**

1. Upload text containing:
   - Email addresses
   - Phone numbers
   - Full names
2. Check what is sent to AI (if accessible in logs)

**Expected Results:**

- [ ] PII removed before AI call
- [ ] Recommendations still generated correctly
- [ ] No PII in AI request payload

---

## 5. Educator Dashboard

### 5.1 Dashboard Overview

**Objective:** Verify dashboard displays correct information.

**Steps:**

1. Log in as educator
2. Navigate to `/educator/dashboard`

**Expected Results:**

- [ ] **Summary Cards Display:**
  - [ ] Total Students count
  - [ ] Pending Recommendations count (clickable)
  - [ ] Average Class Proficiency score
  - [ ] Active Streaks count
- [ ] **Student Table Shows:**
  - [ ] Student Name
  - [ ] Grade Level
  - [ ] Vocabulary Level
  - [ ] Pending Words count
  - [ ] Last Upload timestamp
  - [ ] Action buttons (View Profile, Upload Work, View Recommendations)

---

### 5.2 Student Detail View

**Objective:** Verify student profile page works.

**Steps:**

1. From dashboard, click "View Profile" for a student
2. Review student detail page

**Expected Results:**

- [ ] Student profile information displayed
- [ ] Upload history shown
- [ ] Vocabulary progress visible
- [ ] Quiz performance metrics (if available)

---

### 5.3 Dashboard Data Accuracy

**Objective:** Verify dashboard stats are accurate.

**Verification:**

- [ ] Total students count matches actual students
- [ ] Pending recommendations count matches actual pending recs
- [ ] Average proficiency calculated correctly
- [ ] Last upload timestamps are accurate

---

### 5.4 Dashboard Export

**Objective:** Verify CSV export functionality.

**Steps:**

1. Navigate to dashboard
2. Click export button or use API: `GET /api/educator/export`
3. Download CSV file

**Expected Results:**

- [ ] CSV file downloads
- [ ] Contains all student data
- [ ] Properly formatted
- [ ] Anonymized option works (if tested)

---

## 6. Recommendations Management

### 6.1 View Recommendations

**Objective:** Verify recommendations page displays correctly.

**Steps:**

1. Log in as educator
2. Navigate to `/educator/recommendations`
3. Review recommendations list

**Expected Results:**

- [ ] All pending recommendations displayed
- [ ] Each recommendation shows:
  - [ ] Word (large, bold)
  - [ ] Student name
  - [ ] Rationale
  - [ ] Difficulty meter/score
  - [ ] Example sentence
- [ ] Action buttons visible: Approve, Reject, Edit Rationale, Pin

---

### 6.2 Filter Recommendations

**Objective:** Verify filtering works correctly.

**Test Filters:**

- [ ] **Filter by student** → Only that student's recommendations shown
- [ ] **Filter by difficulty** → Only recommendations in range shown
- [ ] **Filter by date** → Only recommendations in date range shown
- [ ] **Filter by status** → Only recommendations with that status shown

**Expected Results:**

- [ ] Filters apply correctly
- [ ] Results update dynamically
- [ ] Filter state persists (if applicable)

---

### 6.3 Approve Recommendations

**Objective:** Verify approval workflow.

**Steps:**

1. Navigate to recommendations page
2. Click "Approve" on a recommendation
3. Verify status updates

**Expected Results:**

- [ ] Recommendation status changes to "approved"
- [ ] Word appears in student dashboard
- [ ] Toast notification confirms action
- [ ] Recommendation removed from pending list (or marked as approved)

---

### 6.4 Reject Recommendations

**Objective:** Verify rejection workflow.

**Steps:**

1. Click "Reject" on a recommendation
2. Verify status updates

**Expected Results:**

- [ ] Recommendation status changes to "rejected"
- [ ] Word does NOT appear in student dashboard
- [ ] Toast notification confirms action

---

### 6.5 Bulk Actions

**Objective:** Verify bulk approve/reject works.

**Steps:**

1. Select multiple recommendations using checkboxes
2. Click "Approve Selected" or "Reject Selected"

**Expected Results:**

- [ ] All selected recommendations updated
- [ ] Bulk action completes successfully
- [ ] Toast notification shows count of updated items

---

### 6.6 Edit Rationale

**Objective:** Verify rationale editing works.

**Steps:**

1. Click "Edit Rationale" on a recommendation
2. Modify the rationale text
3. Save changes

**Expected Results:**

- [ ] Rationale updates successfully
- [ ] Changes persist
- [ ] Updated rationale visible in student view

---

### 6.7 Pin Recommendations

**Objective:** Verify pin functionality works.

**Steps:**

1. Click "Pin" on a recommendation
2. Verify it's pinned

**Expected Results:**

- [ ] Recommendation marked as pinned
- [ ] Pinned words appear first in student dashboard
- [ ] Pin status persists

---

## 7. Student Dashboard

### 7.1 Dashboard Overview

**Objective:** Verify student dashboard displays correctly.

**Steps:**

1. Log in as student
2. Navigate to `/student/dashboard`

**Expected Results:**

- [ ] **Top Section:**
  - [ ] XP progress bar with current level
  - [ ] Streak counter with flame icon
  - [ ] Badge display (if earned)
- [ ] **Middle Section:**
  - [ ] "Your Vocabulary Words" card
  - [ ] List of approved words
  - [ ] Each word shows:
    - [ ] Word + definition
    - [ ] Rationale tooltip ("Why this word?")
    - [ ] Mastery indicator (Practicing/Nearly Mastered/Mastered)
    - [ ] Progress dots (e.g., ●○○ for 1/3 correct)
- [ ] **Bottom Section:**
  - [ ] "Start Quiz" button
  - [ ] Recent quiz performance summary

---

### 7.2 Approved Words Display

**Objective:** Verify approved words appear correctly.

**Prerequisites:** Educator has approved at least 5 words

**Expected Results:**

- [ ] All approved words visible
- [ ] Pinned words appear first
- [ ] Words sorted by creation date (newest first, unless pinned)
- [ ] Rationale accessible via tooltip or click
- [ ] Difficulty score visible

---

### 7.3 Quiz Button State

**Objective:** Verify quiz button enabled/disabled logic.

**Test Cases:**

- [ ] **< 5 approved words** → Button disabled with tooltip explaining why
- [ ] **≥ 5 approved words** → Button enabled
- [ ] Tooltip text is clear and helpful

---

### 7.4 Dashboard Data Persistence

**Objective:** Verify data persists across sessions.

**Steps:**

1. View dashboard
2. Log out
3. Log back in
4. View dashboard again

**Expected Results:**

- [ ] XP, level, streak persist
- [ ] Approved words still visible
- [ ] Mastery progress maintained
- [ ] Badges still displayed

---

## 8. Quiz System

### 8.1 Quiz Generation

**Objective:** Verify quiz generation works correctly.

**Steps:**

1. Log in as student with ≥5 approved words
2. Click "Start Quiz"
3. Review quiz questions

**Expected Results:**

- [ ] 10 questions generated (or configured amount)
- [ ] Questions pulled from approved, not-yet-mastered words
- [ ] Mix of recent (70%) and older (30%) words
- [ ] Each question shows:
  - [ ] Word
  - [ ] Multiple choice options OR fill-in-the-blank prompt
- [ ] Progress indicator: "Question X of 10"

---

### 8.2 Quiz Answering

**Objective:** Verify quiz answering flow works.

**Steps:**

1. Answer each question
2. Submit answer
3. Review feedback

**Expected Results:**

- [ ] **Correct Answer:**
  - [ ] Green highlight
  - [ ] "Correct! +10 XP" message
  - [ ] "Next Question" button appears
- [ ] **Incorrect Answer:**
  - [ ] Red highlight
  - [ ] "Not quite. The correct answer is..." message
  - [ ] Explanation shown
  - [ ] "Next Question" button appears

---

### 8.3 Quiz Completion

**Objective:** Verify quiz completion modal works.

**Steps:**

1. Complete all 10 questions
2. Review completion modal

**Expected Results:**

- [ ] Modal displays:
  - [ ] "Quiz Complete!" message
  - [ ] XP gained (e.g., "+80 XP")
  - [ ] Streak status ("5-day streak maintained!" or "New streak started!")
  - [ ] Score (e.g., "8 out of 10 correct")
- [ ] "View Dashboard" button works
- [ ] Modal can be dismissed

---

### 8.4 Quiz Scoring & XP

**Objective:** Verify XP calculation is correct.

**Test Cases:**

- [ ] **Correct answer** → +10 XP
- [ ] **Quiz completion ≥70%** → +50 bonus XP
- [ ] **Quiz completion <70%** → No bonus XP
- [ ] **Total XP** → Sum of correct answers + bonus (if applicable)

**Expected Results:**

- [ ] XP calculated correctly
- [ ] XP updates in real-time
- [ ] Level updates when XP threshold reached (every 500 XP)

---

### 8.5 Word Mastery Progression

**Objective:** Verify word mastery stages update correctly.

**Steps:**

1. Answer same word correctly 3 times (across multiple quizzes)
2. Check mastery status

**Expected Results:**

- [ ] **1 correct** → "Practicing" stage, correct_count = 1
- [ ] **2 correct** → "Nearly Mastered" stage, correct_count = 2
- [ ] **3 correct** → "Mastered" stage, correct_count = 3
- [ ] Mastered words no longer appear in quiz generation

---

### 8.6 Streak System

**Objective:** Verify streak calculation works correctly.

**Test Cases:**

- [ ] **First quiz** → Streak = 1
- [ ] **Quiz same day** → Streak maintained
- [ ] **Quiz next day** → Streak increments
- [ ] **Miss >24 hours** → Streak resets to 1

**Expected Results:**

- [ ] Streak counter updates correctly
- [ ] Streak persists across sessions
- [ ] 24-hour grace period works

---

### 8.7 Badge System

**Objective:** Verify badges are awarded at milestones.

**Test Cases:**

- [ ] **10 words mastered** → "10_words" badge awarded
- [ ] **50 words mastered** → "50_words" badge awarded
- [ ] **100 words mastered** → "100_words" badge awarded

**Expected Results:**

- [ ] Badges awarded at correct milestones
- [ ] Badges displayed on dashboard
- [ ] Badges persist across sessions
- [ ] No duplicate badges awarded

---

## 9. Error Handling & Edge Cases

### 9.1 Network Errors

**Objective:** Verify graceful handling of network issues.

**Test Cases:**

- [ ] **Slow network** → Loading indicators shown
- [ ] **Network timeout** → Error message displayed
- [ ] **Connection lost** → User-friendly error message

---

### 9.2 AI Processing Failures

**Objective:** Verify AI failures are handled gracefully.

**Test Cases:**

- [ ] **OpenAI API error** → Upload marked as "failed"
- [ ] **Retry logic** → System retries up to 3 times
- [ ] **Permanent failure** → Error message to educator
- [ ] **No stack traces** → User-friendly messages only

---

### 9.3 Database Errors

**Objective:** Verify database errors don't crash the app.

**Test Cases:**

- [ ] **Connection error** → Error message displayed
- [ ] **Query timeout** → Error message displayed
- [ ] **No stack traces** → User-friendly messages only

---

### 9.4 Invalid Input Handling

**Objective:** Verify validation works for all inputs.

**Test Cases:**

- [ ] **Empty fields** → Validation errors
- [ ] **Invalid email format** → Validation error
- [ ] **SQL injection attempts** → Sanitized/rejected
- [ ] **XSS attempts** → Sanitized/rejected

---

## 10. Performance Testing

### 10.1 Page Load Times

**Objective:** Verify pages load within acceptable time.

**Test Pages:**

- [ ] **Login page** → Loads in < 2 seconds
- [ ] **Dashboard** → Loads in < 3 seconds
- [ ] **Recommendations page** → Loads in < 3 seconds
- [ ] **Student dashboard** → Loads in < 3 seconds

---

### 10.2 Concurrent Users

**Objective:** Verify system handles multiple users.

**Test Cases:**

- [ ] **Multiple educators** → Can log in simultaneously
- [ ] **Multiple students** → Can log in simultaneously
- [ ] **Mixed usage** → System remains responsive

---

### 10.3 File Upload Performance

**Objective:** Verify upload performance is acceptable.

**Test Cases:**

- [ ] **Small file (<1MB)** → Uploads in < 5 seconds
- [ ] **Medium file (1-5MB)** → Uploads in < 30 seconds
- [ ] **Large file (5-10MB)** → Uploads in < 60 seconds

---

### 10.4 AI Processing Time

**Objective:** Verify AI processing completes in reasonable time.

**Test Cases:**

- [ ] **200-word text** → Processes in < 30 seconds
- [ ] **500-word text** → Processes in < 60 seconds
- [ ] **1000-word text** → Processes in < 120 seconds

---

## 11. Accessibility Testing

### 11.1 Keyboard Navigation

**Objective:** Verify all features accessible via keyboard.

**Test Cases:**

- [ ] **Tab navigation** → All interactive elements accessible
- [ ] **Enter/Space** → Activates buttons
- [ ] **Escape** → Closes modals
- [ ] **Arrow keys** → Navigate dropdowns/selects
- [ ] **Focus indicators** → Visible on all focused elements

---

### 11.2 Screen Reader Compatibility

**Objective:** Verify screen reader support.

**Test Cases:**

- [ ] **Form labels** → Read correctly
- [ ] **Button text** → Read correctly
- [ ] **Error messages** → Announced
- [ ] **Success messages** → Announced
- [ ] **ARIA labels** → Present where needed

---

### 11.3 Color Contrast

**Objective:** Verify WCAG 2.2 AA compliance.

**Test Cases:**

- [ ] **Text on background** → Contrast ratio ≥ 4.5:1
- [ ] **Large text** → Contrast ratio ≥ 3:1
- [ ] **Interactive elements** → Contrast ratio ≥ 3:1

**Tools:** Use browser extensions or online contrast checkers

---

### 11.4 Responsive Design

**Objective:** Verify layout works on different screen sizes.

**Test Cases:**

- [ ] **Desktop (≥1200px)** → Full layout displayed
- [ ] **Tablet (768-1199px)** → Layout adapts, sidebar collapses
- [ ] **Mobile (<768px)** → Stacked layout, bottom navigation

---

## 12. Cross-Browser Testing

### 12.1 Chrome

**Objective:** Verify functionality in Chrome.

**Test:**

- [ ] All features work correctly
- [ ] No console errors
- [ ] Layout displays correctly

---

### 12.2 Firefox

**Objective:** Verify functionality in Firefox.

**Test:**

- [ ] All features work correctly
- [ ] No console errors
- [ ] Layout displays correctly

---

### 12.3 Safari

**Objective:** Verify functionality in Safari.

**Test:**

- [ ] All features work correctly
- [ ] No console errors
- [ ] Layout displays correctly

---

### 12.4 Edge (Optional)

**Objective:** Verify functionality in Edge.

**Test:**

- [ ] All features work correctly
- [ ] No console errors
- [ ] Layout displays correctly

---

## 13. Data Persistence Testing

### 13.1 Server Restart

**Objective:** Verify data persists after server restart.

**Steps:**

1. Create test data (students, uploads, recommendations)
2. Restart server
3. Verify data still exists

**Expected Results:**

- [ ] All data persists
- [ ] Users can log in
- [ ] Dashboards show correct data
- [ ] No data loss

---

### 13.2 Database Persistence

**Objective:** Verify database transactions work correctly.

**Test Cases:**

- [ ] **Create student** → Persists after page refresh
- [ ] **Upload file** → Persists after page refresh
- [ ] **Approve recommendation** → Persists after page refresh
- [ ] **Complete quiz** → XP/streak persist after page refresh

---

## 14. Security Testing

### 14.1 Session Management

**Objective:** Verify session security.

**Test Cases:**

- [ ] **Session timeout** → Logs out after inactivity
- [ ] **Session cookies** → HttpOnly, Secure, SameSite flags set
- [ ] **CSRF protection** → Forms protected (if implemented)

---

### 14.2 Input Sanitization

**Objective:** Verify inputs are sanitized.

**Test Cases:**

- [ ] **XSS attempts** → Sanitized/rejected
- [ ] **SQL injection** → Sanitized/rejected
- [ ] **Path traversal** → Rejected

---

### 14.3 PII Protection

**Objective:** Verify PII is protected.

**Test Cases:**

- [ ] **PII scrubbing** → Works before AI calls
- [ ] **Anonymized export** → Masks student names
- [ ] **No PII in logs** → Check application logs

---

## 15. Integration Testing

### 15.1 Complete Workflow

**Objective:** Verify end-to-end workflow works.

**Steps:**

1. Educator signs up
2. Educator creates 3 students (one per grade)
3. Educator uploads files for each student
4. Wait for AI processing
5. Educator approves recommendations
6. Students log in
7. Students view approved words
8. Students take quizzes
9. Verify XP/streak/mastery updates

**Expected Results:**

- [ ] Complete workflow executes without errors
- [ ] All data flows correctly
- [ ] No data loss or corruption

---

### 15.2 Multiple Students Workflow

**Objective:** Verify system handles multiple students.

**Steps:**

1. Create 3 students
2. Upload files for all 3
3. Process all uploads
4. Approve recommendations for all
5. Verify each student sees only their words

**Expected Results:**

- [ ] Data isolation between students
- [ ] No cross-student data leakage
- [ ] Each student's dashboard shows only their data

---

## 16. Regression Testing

### 16.1 Previous Features

**Objective:** Verify previous PRs still work.

**Test:**

- [ ] All features from PRs #1-11 still functional
- [ ] No breaking changes introduced
- [ ] Existing functionality preserved

---

## Test Completion Summary

### Test Results

- **Total Test Cases:** [Fill in count]
- **Passed:** [Fill in count]
- **Failed:** [Fill in count]
- **Blocked:** [Fill in count]
- **Skipped:** [Fill in count]

### Critical Issues Found

1. [List any critical bugs]
2. [List any blockers]

### Minor Issues Found

1. [List minor bugs]
2. [List UI/UX improvements]

### Recommendations

1. [List recommendations for improvements]
2. [List suggestions for future testing]

---

## Sign-Off

**Tester Name:** **\*\*\*\***\_**\*\*\*\***  
**Date:** **\*\*\*\***\_**\*\*\*\***  
**Status:** ☐ Pass ☐ Fail ☐ Conditional Pass  
**Notes:** **\*\*\*\***\_**\*\*\*\***

---

**End of Manual Testing Plan**

# Product Requirements Document (PRD) – WordBridge (Updated v1.2)

## 1. Overview

**Project Name:** WordBridge  
**Organization:** Flourish Schools  
**Objective:** Automate the identification of vocabulary gaps and provide personalized, age-appropriate vocabulary recommendations for middle school students using GPT-4o and AWS-hosted infrastructure.

WordBridge bridges the gap between student language use and their potential vocabulary growth by analyzing their written and conversational text. The system automatically builds a profile of each student's vocabulary proficiency, identifies missing or underused words, and generates targeted recommendations for both students and educators. It provides dashboards for tracking progress and includes gamified learning elements to promote engagement.

---

## 2. Problem Statement

Educators struggle with the manual effort of analyzing each student's written work to identify vocabulary weaknesses. This process is inconsistent, time-consuming, and often fails to provide personalized recommendations that suit each student's reading level and learning pace.

WordBridge eliminates this bottleneck by automating vocabulary analysis and delivering actionable recommendations — empowering teachers to focus on teaching and helping students grow their language skills faster and more effectively.

---

## 3. Goals & Success Metrics

**Primary Goal:**  
Automate the identification of vocabulary gaps and provide personalized vocabulary recommendations for middle school students.

**Success Metrics:**

- Increase in the rate of _novel words properly used_ by students over time.
- Reduction in _educator time spent_ manually identifying vocabulary gaps.
- Positive educator feedback on the _usefulness and accuracy_ of vocabulary recommendations.
- Improved _student retention_ and _daily engagement_ through gamified activities.

---

## 4. User Roles & Core User Stories

### **Primary Users**

**Middle School Educators (English/Writing Teachers)**

- Need efficient, automated vocabulary insights per student.
- Desire a clear dashboard summarizing class progress and individual needs.
- Create and manage student accounts.
- Upload and associate student writing samples.

**Middle School Students**

- Need personalized, level-appropriate vocabulary recommendations.
- Want an engaging, game-like way to practice and retain new words.
- Cannot upload their own work (educator-managed workflow).

### **Account Management**

- **Educators create student accounts** via dedicated "Add Student" page with fields: name, grade (6th/7th/8th), username, email, password.
- **Educator signup** requires: name, username, email, password, confirm password.
- **Login** supports both email and username authentication.
- **Role-based login:** Users must select "Educator" or "Student" at login; credentials are validated against their registered role (students cannot log in as educators and vice versa).
- **Student-Educator relationship:** 1:many (each student has one educator; each educator has multiple students).
- **Test accounts:** 1 educator, 3 students (one per grade: 6th, 7th, 8th).

### **Core User Stories**

1. As a **middle school educator**, I want to receive a list of vocabulary words tailored to each student's proficiency level so that I can efficiently enhance their language skills.
2. As a **middle school student**, I want to be challenged with new vocabulary words that I can realistically learn and use effectively, so that I can improve my language proficiency.

### **Feature-Specific User Stories**

- **Educator Dashboard:**
  - As an educator, I want to see each student's vocabulary level, recent uploads, and recommended words so I can monitor progress and provide feedback.
- **Student Dashboard:**
  - As a student, I want to view my word list, track my streaks, and take quizzes so I can reinforce what I've learned.
- **Student Account Creation:**
  - As an educator, I want to create student accounts quickly so I can onboard my class efficiently.

---

## 5. Functional Requirements

### **P0: Must-Have**

- **Educator creates student accounts** via dedicated UI (name, grade, username, email, password).
- System builds a vocabulary profile for each student from educator-uploaded text (essays, writing samples, transcripts).
- GPT-4o identifies vocabulary gaps and suggests appropriate new words per student.
- System maintains a dynamic list of recommendations for educators.
- Support for multiple file formats: `.txt`, `.docx`, `.pdf`, `.csv`.
- Real-time ingestion pipeline for text uploads with **file-to-student association** (educators tag files with student IDs during upload).
- **Multi-file upload** capability for batch processing.
- **Asynchronous AI processing** with status tracking and user notifications.

### **P1: Should-Have**

- **Educator Dashboard** for viewing student profiles, recommended words, and progress metrics.
- **Student Dashboard** for viewing assigned/recommended words, XP, streaks, and badges.
- **Explainability Layer:** each recommendation includes rationale, difficulty level, and usage evidence.
- **Educator approval workflow:** recommendations go to educator queue first; educators approve/reject before students see them.
- Integration layer for optional import of classroom text (Google Classroom, CSV).

### **P2: Nice-to-Have**

- **Gamified Quizzes** to reinforce learned vocabulary.
- **Daily Streaks, XP, and Badge System** to encourage consistent practice.
- **Educator Word Controls:** teachers can ban, approve, or pin words globally or per student.
- **Bulk approve/reject** actions for recommendations.

---

## 6. Vocabulary & Recommendation Engine

### **AI Core (GPT-4o)**

- GPT-4o will analyze each text submission to:
  1. Extract all tokens and lemmas from student writing.
  2. Compare vocabulary use to grade-level and corpus frequency benchmarks.
  3. Identify underused or missing "growth words."
  4. Recommend words at the optimal challenge level.
  5. Generate rationales and contextual examples (e.g., "recommended because the student writes frequently about science topics but avoids 'hypothesis' and 'variable'").

### **Text Analysis Requirements**

- **Minimum text length:** 200 words for initial profile, 100 words for profile updates.
- **First upload:** Generates baseline + initial recommendations immediately.
- **Subsequent uploads:** Refine profile incrementally in real-time.
- **Processing mode:** Asynchronous with job queue (AWS SQS or Celery).

### **Source of Truth**

The system draws from multiple combined sources:

- **Tier-2 Academic Vocabulary Lists**
- **Word Frequency/Zipf Scale** (via COCA/SUBTLEX)
- **Open Educational Corpora (WordNet, Oxford 3000)**

Filters automatically remove:

- Profanity and slang
- Sensitive or culturally inappropriate terms
- Words above maturity threshold

### **Recommendation Workflow**

1. Educator uploads text and associates it with a student.
2. File saved to S3; metadata stored in PostgreSQL.
3. Background job triggers AI processing.
4. AI extracts known and candidate words.
5. Words are classified into: _Known_, _Emerging_, and _Growth Opportunities_.
6. GPT-4o recommends a batch of new words, each with:
   - Rationale
   - Difficulty score
   - Example sentence
7. **Recommendations go to educator queue** (not visible to students yet).
8. Educator reviews and approves/rejects recommendations.
9. **Only approved words** appear in student dashboard.
10. Students practice approved words via quizzes.

### **Educator Actions on Recommendations**

- **Approve:** Word becomes visible to student and available in quizzes.
- **Reject:** Word is hidden and not shown to student.
- **Edit Rationale:** Educator can customize the explanation.
- **Pin:** Mark word as priority (appears first in student's list).
- **Bulk Actions:** Approve/reject multiple words at once.

---

## 7. Dashboard KPIs

### **Educator Dashboard**

- Average vocabulary proficiency score per student.
- Number of pending word recommendations (awaiting approval).
- Student adoption rate (percent of approved words mastered).
- Gamified engagement overview (XP, streaks, quiz completion).
- Export class progress summary (CSV/PDF).
- **Class Management:** View aggregate statistics across all students.

### **Student Dashboard**

- XP, level, and streak tracker.
- Words learned vs. words recommended.
- Quiz performance and completion history.
- "Next Recommended Words" section with AI rationale and example sentences.
- **Word Progress Indicators:** "Practicing" → "Nearly Mastered" → "Mastered"

---

## 8. Cold-Start Calibration

To personalize results even for new students:

**Hybrid Approach (Implemented):**

- Each grade (6th, 7th, 8th) starts with a baseline vocabulary level derived from public corpora.
- **Baseline Data Source:** JSON files (6th_grade.json, 7th_grade.json, 8th_grade.json) containing 500-800 words per grade from Common Core + Oxford 3000 intersection.
- **Storage:** Loaded into PostgreSQL during initial migration.
- After the first writing sample (≥200 words), GPT-4o refines the student's vocabulary profile based on detected strengths and gaps.

For demo/testing:

- 1 educator account
- 3 student accounts (one per grade level: 6th, 7th, 8th).

---

## 9. Technical Requirements

- **System Architecture:** Fully AWS-hosted deployment (frontend + backend).
  - Frontend: Server-rendered HTML/CSS via Flask or FastAPI (Python + Jinja2).
  - Backend: AWS Lambda (API) or EC2 running Flask/FastAPI backend.
  - Database: AWS RDS PostgreSQL for user data, vocabulary profiles, and progress tracking.
  - Job Queue: AWS SQS or Celery for async AI processing.
- **Programming Language:** Python (single-language stack).
- **AI Framework:** GPT-4o via OpenAI API.
- **Integrations:** Use publicly available APIs for text processing and analysis (optional LMS imports).
- **Data Requirements:** Use open-source corpora and mock student data for testing and validation.

---

## 10. Non-Functional Requirements

- **Performance:** Real-time ingestion and analysis of full-day transcripts or writing data.
- **Scalability:** Must scale to hundreds of simultaneous uploads without degradation.
- **Security:** Implement PII scrubbing before AI calls; enforce basic FERPA/COPPA compliance.
- **Reliability:** 99.9% uptime target.
- **Accessibility:** WCAG 2.2 AA compliance, clear UI for all technical levels.
- **Error Handling:** Graceful failures with user-friendly messages; retry logic for AI/database failures.

---

## 11. Data Privacy & Guardrails

- **PII Scrubbing:** Regex-based removal of emails, phone numbers, full names before AI processing.
- Exclude profanity, mature, or sensitive topics from recommendations.
- Ensure educator oversight for all word approvals.
- **Authentication:** Session-based (Flask-Login) with secure, httpOnly, sameSite cookies.
- **HTTPS:** Enforced via AWS Application Load Balancer with redirect rules.
- **Data Retention:** 2-year policy; then anonymize or delete.

---

## 12. Gamification Logic

### **XP System**

- **+10 XP** per correct quiz answer.
- **+50 XP bonus** for quiz completion with ≥70% correct.
- **Levels:** Every 500 XP (Level 1 = 0-499 XP, Level 2 = 500-999 XP, etc.).

### **Streak System**

- Maintained by completing **≥1 quiz per day**.
- Day resets at **midnight in student's local timezone**.
- **24-hour grace period** before streak breaks.
- Streak counter displayed prominently on dashboard.

### **Badges**

- Awarded for milestones: **10, 50, 100 words mastered**.

### **Quizzes**

- **10 questions per quiz** (configurable).
- Pull from "approved but not yet mastered" words.
- **Available when ≥5 words are approved** for a student.
- **Can retake after 24 hours** (for streak maintenance).
- **Question mix:** 70% recent words + 30% older words (spaced repetition).
- **Question types:** Multiple-choice and fill-in-the-blank formats.
- **Immediate feedback:** Color-coded correct/incorrect during quiz.
- **Completion summary modal:** Shows XP gained, streak status, and performance.
- No leaderboards, no social or chat features.

### **Word Mastery Criteria**

- Words progress through stages: **"Practicing" → "Nearly Mastered" → "Mastered"**.
- Auto-mark as **"Mastered"** after **3 correct quiz answers** (spaced over time).
- Students **cannot manually mark words** as learned (prevents gaming).

---

## 13. Assumptions & Constraints

- Text data will be pre-processed; no speech-to-text required.
- All AI processing relies on GPT-4o through OpenAI API.
- No parent or admin roles in MVP.
- No mobile app or offline mode required.
- Students have only one educator (English/Writing teacher).
- Educators upload all student work; students cannot self-upload.
- Deployment deadline: **Midday tomorrow (MVP completion).**

---

## 14. Out of Scope

- Real-time audio ingestion or live transcription.
- Advanced analytics dashboards for admins or school networks.
- Multi-tenant district deployment (can be added later).
- Password reset functionality (MVP).
- Student self-upload of work.
- Multiple educators per student.

---

## 15. Success Criteria

The WordBridge MVP is considered complete and successful when:

- The system accurately builds per-student vocabulary profiles.
- GPT-4o generates personalized word recommendations with rationale.
- Educator and student dashboards function as specified.
- Quizzes, XP, and streaks are operational and persist in PostgreSQL.
- Educator approval workflow functions correctly.
- The project is deployed on AWS with live functionality verified via mock data.

---

**End of PRD (Python-Only Architecture)**  
**Document Version:** 1.2  
**Date:** November 10, 2025  
**Prepared for:** Development & Deployment via Cursor

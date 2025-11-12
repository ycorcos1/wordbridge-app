# WordBridge — AI-Powered Vocabulary Learning Platform

**An automated system that identifies vocabulary gaps in student writing and provides personalized, age-appropriate vocabulary recommendations using AI-powered insights.**

---

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Introduction](#introduction)
- [Core Features](#core-features)
- [AI Tools & How It's Used](#ai-tools--how-its-used)
- [Setup Instructions](#setup-instructions)
- [Deployment Instructions](#deployment-instructions)
- [Future Developments](#future-developments)

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** (recommended)
- **PostgreSQL** instance (or SQLite for development)
- **OpenAI API key** (for AI vocabulary recommendations)
- **AWS Account** (for S3 storage and SQS queue - optional for development)
- **Git** for cloning the repository

### Complete Setup Instructions

Follow these steps to get the project running on your local machine:

#### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/wordbridge-app.git
cd wordbridge-app
```

#### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 4. Set Up Environment Variables

Create a `.env` file in the root directory:

```bash
touch .env
```

Add the following variables to `.env`:

```bash
# Required: Database connection
DATABASE_URL=postgresql://user:password@localhost/wordbridge
# Or for SQLite (development only):
# DATABASE_URL=sqlite:///wordbridge_dev.sqlite

# Required: Flask secret key (generate with: openssl rand -hex 32)
SECRET_KEY=your-secret-key-here

# Required: OpenAI API key for vocabulary recommendations
# Get your key from: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-xxxx

# Required for file uploads: AWS S3 configuration
AWS_S3_BUCKET_NAME=wordbridge-uploads-your-bucket-name
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key

# Optional: AWS SQS queue for background job processing
# If not set, uses in-memory queue (development only)
AWS_SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/wordbridge-upload-jobs

# Optional: Content filtering
CONTENT_FILTER_ENABLED=true
CONTENT_FILTER_EXTRA_WORDS_PATH=static/wordlists/sensitive_terms.txt

# Optional: Privacy settings
PRIVACY_DEFAULT_ANONYMIZED=false
```

**Notes**:

- **`DATABASE_URL`** is required. Use PostgreSQL for production, SQLite for development.
- **`SECRET_KEY`** is required for Flask session security. Generate a strong random string.
- **`OPENAI_API_KEY`** is required for AI vocabulary recommendations.
- **`AWS_S3_BUCKET_NAME`** is required for file uploads. See [AWS Setup Guide](./docs/AWS_SETUP.md) for instructions.
- **`AWS_SQS_QUEUE_URL`** is optional for development (uses in-memory queue) but required for production.

#### 5. Initialize Database

The database will be automatically initialized on first run. For manual initialization:

```bash
python -c "from models import init_db; init_db()"
```

#### 6. Start Development Server

```bash
python wsgi.py
```

The app will be available at `http://localhost:5001/`. A JSON health check is available at `http://localhost:5001/health`.

#### 7. Run Background Worker

In a separate terminal, start the background worker to process file uploads and generate AI recommendations:

```bash
source venv/bin/activate  # Activate virtual environment
python -m app.jobs.worker
```

The worker will:

- Continuously poll the job queue (local queue or AWS SQS)
- Process uploaded files asynchronously
- Generate vocabulary recommendations via GPT-4o-mini
- Update upload status to 'completed' or 'failed'

**Note:** For production deployment, run this as a systemd service, supervisor process, or similar process manager to ensure it stays running.

#### 8. Create Your First Account

1. Navigate to `http://localhost:5001/signup`
2. Create an educator account
3. Log in and create student accounts via the "Add Student" page
4. Upload student writing samples to generate vocabulary recommendations

### Available Scripts

```bash
python wsgi.py              # Start development server
python -m app.jobs.worker   # Start background worker
pytest                      # Run all tests
pytest --cov=app --cov=config --cov-report=html  # Run tests with coverage
```

### First Steps After Setup

1. **Create Educator Account**: Sign up as an educator
2. **Add Students**: Create student accounts with grade levels (6th, 7th, or 8th)
3. **Upload Writing Samples**: Upload student essays, writing samples, or transcripts (TXT, DOCX, PDF, CSV)
4. **Review Recommendations**: Check the recommendations page to approve/reject AI-generated vocabulary words
5. **Student Practice**: Students can view approved words and take quizzes to practice

---

## Introduction

**WordBridge** is an AI-powered vocabulary learning platform designed to help middle school educators identify vocabulary gaps in student writing and provide personalized, age-appropriate vocabulary recommendations. The system analyzes student writing samples, identifies missing or underused words, and generates targeted recommendations that match each student's reading level and learning pace.

### What Problem Does It Solve?

Middle school educators face significant challenges:

- **Manual vocabulary analysis is time-consuming** — Teachers spend hours reviewing each student's written work to identify vocabulary weaknesses
- **Inconsistent recommendations** — Manual analysis often fails to provide personalized recommendations that suit each student's reading level
- **Limited scalability** — It's difficult to provide individualized vocabulary support for large classes
- **Lack of engagement** — Students need engaging, game-like ways to practice and retain new vocabulary

WordBridge addresses these issues by:

1. **Automating Vocabulary Analysis**: AI analyzes student writing to identify vocabulary gaps automatically
2. **Personalized Recommendations**: GPT-4o-mini generates age-appropriate vocabulary words tailored to each student's proficiency level
3. **Educator Oversight**: All recommendations require educator approval before students see them
4. **Gamified Learning**: Students practice vocabulary through quizzes, earn XP, maintain streaks, and unlock badges
5. **Scalable Solution**: Handles multiple students and uploads efficiently with background job processing

### Why Was It Built?

WordBridge was built to bridge the gap between student language use and their potential vocabulary growth. By automating the tedious process of vocabulary gap identification, educators can focus on teaching while students receive personalized vocabulary recommendations that help them grow their language skills faster and more effectively.

### Who Is It For?

**Primary Users:**

- **Middle School Educators (English/Writing Teachers)**: Need efficient, automated vocabulary insights per student. They create student accounts, upload writing samples, review AI-generated recommendations, and approve words for student practice.
- **Middle School Students (6th, 7th, 8th Grade)**: Need personalized, level-appropriate vocabulary recommendations. They view approved words, take quizzes to practice, track their progress through XP and streaks, and earn badges for milestones.

---

## Core Features

### 1. **AI-Powered Vocabulary Recommendations**

- **Automated Analysis**: GPT-4o-mini analyzes student writing samples to identify vocabulary gaps
- **Personalized Recommendations**: Each recommendation includes:
  - Word and definition
  - Rationale explaining why the student should learn the word
  - Difficulty score (1-10) based on student's current level
  - Age-appropriate example sentence
- **Minimum Word Requirements**: 200 words for initial analysis, 100 words for profile updates
- **Batch Processing**: Generates 5-10 vocabulary recommendations per upload
- **Content Filtering**: Automatically filters profanity and sensitive terms

### 2. **Educator Approval Workflow**

- **Pending Queue**: All AI-generated recommendations start in "pending" status
- **Review Interface**: Educators can view, filter, and manage recommendations by student, difficulty, date, or status
- **Bulk Actions**: Approve or reject multiple recommendations at once
- **Customization**: Educators can edit rationale text before approving
- **Pin Feature**: Pin important words for easy reference
- **Student Visibility**: Only approved words appear in student dashboards

### 3. **Student Gamification (XP, Streaks, Quizzes)**

- **XP System**:
  - +10 XP per correct quiz answer
  - +50 XP bonus for quiz completion with ≥70% correct
  - Levels: Every 500 XP (Level 1 = 0-499 XP, Level 2 = 500-999 XP, etc.)
- **Streak System**:
  - Maintained by completing ≥1 quiz per day
  - 24-hour grace period before streak breaks
  - Streak counter displayed prominently on dashboard
- **Badges**: Awarded for milestones (10, 50, 100 words mastered)
- **Quizzes**:
  - 10 questions per quiz (configurable)
  - Pulls from approved, not-yet-mastered words
  - 70% recent words + 30% older words (spaced repetition)
  - Multiple-choice and fill-in-the-blank formats
  - Immediate feedback with color-coded correct/incorrect responses
  - Completion summary with XP gained and streak status
- **Word Mastery**: Words progress through stages (Practicing → Nearly Mastered → Mastered) after 3 correct quiz answers

### 4. **File Upload Support**

- **Multiple Formats**: Supports TXT, DOCX, PDF, and CSV files
- **Multi-File Upload**: Upload multiple files in a single batch
- **File Size Limit**: 10MB per file
- **Asynchronous Processing**: Files are processed in the background via job queue
- **Status Tracking**: Real-time upload status (pending → processing → completed/failed)
- **S3 Storage**: Files stored securely in AWS S3
- **PII Scrubbing**: Automatically removes emails, phone numbers, and names before AI processing
- **Text Extraction**: Extracts text from various file formats automatically

### 5. **Educator Dashboard**

- **Student Overview**: View all students organized by grade and class
- **Progress Tracking**: See vocabulary levels, pending recommendations, and last upload dates
- **Filtering**: Filter students by grade level and class number
- **CSV Export**: Export student data (all students, by grade, or by class)
- **Student Detail Pages**: View individual student progress, uploads, and recommendations
- **Per-Class Statistics**: Average proficiency levels per class

### 6. **Student Dashboard**

- **Approved Words List**: View all approved vocabulary words with definitions, rationales, and difficulty scores
- **Progress Tracking**: Display XP, level, and current streak
- **Badge Collection**: View earned badges for vocabulary milestones
- **Word Mastery Status**: See which words are Practicing, Nearly Mastered, or Mastered
- **Quiz Access**: Start quizzes when ≥5 words are approved
- **Visual Feedback**: Difficulty meters and rationale tooltips for better understanding

### 7. **Privacy & Compliance**

- **PII Scrubbing**: Emails, phone numbers, and names are redacted before AI processing
- **Content Filtering**: Profanity and sensitive terms are removed from recommendations
- **Educator Review Gate**: Recommendations remain pending until educator approval
- **FERPA/COPPA Compliance**: Supports anonymized reporting for compliance scenarios

---

## AI Tools & How It's Used

### Primary AI Model: OpenAI GPT-4o-mini

**Why GPT-4o-mini?**

- Cost-effective for generating vocabulary recommendations at scale
- Fast response times for real-time processing
- Reliable structured output (JSON format)
- Excellent at understanding context and generating age-appropriate content

### How AI Is Used in WordBridge

#### 1. **Vocabulary Gap Analysis**

The AI analyzes student writing samples to:

- Extract vocabulary patterns from student text
- Compare against grade-level benchmarks and baseline vocabulary
- Identify underused or missing "growth words"
- Determine optimal challenge level for each student

#### 2. **Personalized Recommendation Generation**

For each writing sample, GPT-4o-mini generates vocabulary recommendations by:

**Input Context:**

- Student grade level (6th, 7th, or 8th)
- Current vocabulary level estimate
- Writing sample (cleaned and PII-scrubbed)
- Baseline vocabulary already familiar to the student

**Output Structure:**

- Word: The recommended vocabulary word
- Definition: Age-appropriate definition
- Rationale: Explanation of why the student should learn this word (e.g., "recommended because the student writes frequently about science topics but avoids 'hypothesis' and 'variable'")
- Difficulty Score: Integer 1-10 based on student's current proficiency
- Example Sentence: Age-appropriate sentence using the word correctly

**Prompt Engineering:**

- System prompt defines the AI as an "expert literacy coach"
- Emphasizes age-appropriateness and avoiding profanity
- Requests structured JSON output with specific fields
- Includes baseline vocabulary to avoid duplicates

#### 3. **Processing Pipeline**

1. **Text Extraction**: Extract text from uploaded files (TXT, DOCX, PDF, CSV)
2. **PII Scrubbing**: Remove emails, phone numbers, and names using regex patterns
3. **Word Count Validation**: Ensure minimum word count (200 for initial, 100 for updates)
4. **AI Generation**: Send cleaned text to GPT-4o-mini with student profile context
5. **Response Parsing**: Parse JSON response and validate structure
6. **Content Filtering**: Filter out profanity and sensitive terms from recommendations
7. **Storage**: Store recommendations in database with "pending" status

#### 4. **Error Handling & Retry Logic**

- **Retry Strategy**: 3 attempts with exponential backoff (1.5s base, 30s cap)
- **Permanent vs Retryable Errors**: Distinguishes between API failures (retry) and invalid input (permanent)
- **Fallback Behavior**: If AI generation fails, upload is marked as "failed" with error logging

#### 5. **Cost Optimization**

- **Selective Processing**: Only processes files with sufficient word count
- **Efficient Batching**: Generates 5-10 recommendations per upload (not per word)
- **Model Selection**: Uses GPT-4o-mini (cost-effective) instead of GPT-4
- **Temperature Setting**: 0.4 for consistent, focused output

### AI Configuration

The AI system is configured via environment variables and settings:

- **Model**: `gpt-4o-mini` (configurable via code)
- **Temperature**: `0.4` (balanced creativity and consistency)
- **Max Retries**: `3` attempts
- **Retry Backoff**: Exponential with 1.5s base, 30s cap
- **Response Format**: JSON with structured recommendations array

---

## Setup Instructions

### For Development

1. **Clone the repository** (see Quick Start above)
2. **Set up virtual environment** and install dependencies
3. **Configure `.env` file** with required variables
4. **Use SQLite for development** (set `DATABASE_URL=sqlite:///wordbridge_dev.sqlite`)
5. **Skip AWS setup** (use in-memory queue for development)
6. **Run Flask app** and background worker locally

### For Production

1. **Set up PostgreSQL database** (required for production)
2. **Configure AWS resources**:
   - S3 bucket for file storage
   - SQS queue for background job processing
   - IAM user with appropriate permissions
3. **Set production environment variables**:
   - Strong `SECRET_KEY` (generate with `openssl rand -hex 32`)
   - Production `DATABASE_URL`
   - AWS credentials and bucket name
   - SQS queue URL
4. **Use production WSGI server** (gunicorn recommended)
5. **Run background worker as service** (systemd, supervisor, etc.)

See [AWS Setup Guide](./docs/AWS_SETUP.md) for detailed AWS configuration instructions.

---

## Deployment Instructions

### AWS Deployment

WordBridge is designed to run on AWS infrastructure. Here's how to deploy:

#### 1. **Set Up AWS Resources**

Follow the [AWS Setup Guide](./docs/AWS_SETUP.md) to create:

- S3 bucket for file uploads
- SQS queue for background job processing
- IAM user with S3 and SQS permissions

#### 2. **Configure Production Environment**

Set these environment variables in your production environment:

```bash
# Database (PostgreSQL required for production)
DATABASE_URL=postgresql://user:password@host:5432/wordbridge

# Flask
SECRET_KEY=<strong-random-secret-key>
FLASK_ENV=production

# OpenAI
OPENAI_API_KEY=sk-xxxx

# AWS
AWS_S3_BUCKET_NAME=wordbridge-uploads-production
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_SQS_QUEUE_URL=https://sqs.region.amazonaws.com/account/queue-name
```

#### 3. **Deploy Flask Application**

**Option A: Using Gunicorn (Recommended)**

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 wsgi:app
```

**Option B: Using AWS Elastic Beanstalk**

1. Create `Procfile`:
   ```
   web: gunicorn -w 4 -b 0.0.0.0:5001 wsgi:app
   worker: python -m app.jobs.worker
   ```
2. Deploy via EB CLI or console

**Option C: Using EC2 with systemd**

1. Create systemd service for Flask app
2. Create systemd service for background worker
3. Enable and start services

#### 4. **Run Background Worker**

The background worker must run continuously to process uploads:

```bash
python -m app.jobs.worker
```

**Production Setup:**

- Use systemd, supervisor, or similar process manager
- Configure auto-restart on failure
- Set up log rotation
- Monitor worker health

#### 5. **Set Up Database**

For production, use PostgreSQL:

```bash
# Create database
createdb wordbridge

# Initialize schema (automatic on first run, or manual):
python -c "from models import init_db; init_db()"
```

#### 6. **Configure Reverse Proxy (Optional)**

Use Nginx or Apache as reverse proxy:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### 7. **Set Up SSL/HTTPS**

- Use AWS Certificate Manager (ACM) for SSL certificates
- Configure Application Load Balancer with HTTPS
- Redirect HTTP to HTTPS

#### 8. **Monitoring & Logging**

- Set up CloudWatch logs for Flask app and worker
- Monitor SQS queue depth
- Track OpenAI API usage and costs
- Set up alerts for failed uploads

### Deployment Checklist

- [ ] PostgreSQL database created and accessible
- [ ] AWS S3 bucket created and configured
- [ ] AWS SQS queue created (required for production)
- [ ] IAM user created with S3 and SQS permissions
- [ ] Environment variables set in production environment
- [ ] Flask app running with production WSGI server
- [ ] Background worker running as service
- [ ] SSL/HTTPS configured
- [ ] Monitoring and logging set up
- [ ] Health check endpoint responding (`/health`)

---

## Future Developments

Here are potential enhancements that would fit well within the WordBridge ecosystem:

### 1. **Advanced Analytics & Reporting**

- **Progress Dashboards**: Visual charts showing vocabulary growth over time for individual students and classes
- **Comparative Analytics**: Compare student progress against grade-level benchmarks
- **Usage Reports**: Track which words are most frequently mastered, quiz performance trends, and engagement metrics
- **Export Capabilities**: Enhanced CSV/PDF exports with charts and visualizations

### 2. **Enhanced AI Features**

- **Adaptive Difficulty**: AI automatically adjusts difficulty based on quiz performance and mastery rates
- **Context-Aware Recommendations**: Analyze writing style and topics to recommend domain-specific vocabulary (science, history, literature)
- **Sentence Generation**: AI generates personalized practice sentences using recommended words
- **Writing Feedback**: Provide vocabulary suggestions directly in student writing samples

### 3. **Social & Collaborative Features**

- **Class Leaderboards**: Optional leaderboards for XP, streaks, and words mastered (with privacy controls)
- **Peer Learning**: Students can share example sentences or definitions they've created
- **Educator Collaboration**: Share successful word lists and recommendations across educators
- **Parent Portal**: View-only dashboard for parents to track student progress

### 4. **Enhanced Gamification**

- **Achievement System**: Expand badges beyond word count milestones (perfect quiz scores, long streaks, etc.)
- **Customizable Avatars**: Unlock avatar customization options through achievements
- **Daily Challenges**: Special vocabulary challenges with bonus XP
- **Word Collections**: Organize words into themed collections (e.g., "Science Words", "Descriptive Words")

### 5. **Integration & Import Features**

- **LMS Integration**: Import student writing from Google Classroom, Canvas, or other LMS platforms
- **Bulk Student Import**: CSV import for creating multiple student accounts at once
- **Writing Sample Import**: Automatically fetch writing samples from connected platforms
- **API Access**: RESTful API for third-party integrations

### 6. **Accessibility & Localization**

- **Multi-Language Support**: Support for English language learners with translations and bilingual definitions
- **Text-to-Speech**: Audio pronunciation for vocabulary words
- **Enhanced Accessibility**: Screen reader optimizations, keyboard navigation improvements
- **Mobile App**: Native iOS/Android apps for on-the-go learning

### 7. **Advanced Recommendation Features**

- **Spaced Repetition Algorithm**: Intelligent scheduling of word reviews based on forgetting curves
- **Word Relationships**: Show synonyms, antonyms, and related words
- **Etymology Insights**: Explain word origins and roots to aid memorization
- **Usage Frequency Data**: Show how common words are in academic writing

### 8. **Administrative Features**

- **School/District Management**: Multi-tenant support for school districts
- **Bulk Operations**: Approve/reject recommendations across multiple students
- **Custom Word Lists**: Educators can create and assign custom vocabulary lists
- **Assessment Tools**: Create custom vocabulary assessments aligned with curriculum

### 9. **Performance & Scalability**

- **Caching Layer**: Redis caching for frequently accessed data
- **CDN Integration**: Serve static assets via CDN for faster load times
- **Horizontal Scaling**: Support for multiple worker instances
- **Database Optimization**: Query optimization and indexing improvements

### 10. **Research & Insights**

- **Vocabulary Growth Tracking**: Longitudinal analysis of vocabulary development
- **Learning Pattern Analysis**: Identify optimal learning strategies for different student types
- **Research Mode**: Anonymized data export for educational research
- **Predictive Analytics**: Predict which students need additional support

---

## Documentation

### Core Documentation

- **[Product Requirements Document](./docs/WordBridge_PRD.md)**: Complete product specifications
- **[Design Specification](./docs/WordBridge_Design_Spec.md)**: UI/UX design guidelines
- **[Architecture Documentation](./docs/WordBridge_Architecture.md)**: System architecture and data flow
- **[Task List](./docs/WordBridge_Task_List.md)**: Implementation roadmap
- **[AWS Setup Guide](./docs/AWS_SETUP.md)**: Detailed AWS configuration instructions

### Additional Resources

- **API Endpoints**: See routes in `app/routes.py`
- **Database Schema**: See `models/__init__.py` for table definitions
- **Testing**: Comprehensive test suite in `tests/` directory

---

## License

[Add your license here]

---

## Support

For questions or issues:

- Check the [AWS Setup Guide](./docs/AWS_SETUP.md) for deployment help
- Review [Architecture Documentation](./docs/WordBridge_Architecture.md) for system understanding
- See [Product Requirements Document](./docs/WordBridge_PRD.md) for feature specifications

---

**Last Updated**: November 2025  
**Version**: 1.0  
**Status**: Production Ready

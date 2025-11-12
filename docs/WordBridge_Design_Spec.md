# WordBridge Design Specification

## 1. Overview

WordBridge's interface is designed for simplicity, readability, and ease of use. The focus is on providing educators and students with a clean, distraction-free environment where content, progress, and insights take priority.  
The overall design philosophy is **minimalist, intuitive, and responsive** — ensuring users of all technical skill levels can navigate comfortably.

---

## 2. Design Principles

- **Minimalism:** Only essential features are visible. No clutter or redundant controls.
- **Clarity:** Information is grouped logically and presented in concise, readable sections.
- **Consistency:** Layout and components remain uniform across all pages.
- **Accessibility:** Compliant with WCAG 2.2 AA; high contrast, legible fonts, and keyboard-friendly navigation.
- **Feedback:** Every action (upload, quiz submission, recommendation refresh) provides instant visual confirmation.

---

## 3. Color Palette

| Element   | Color     | Description                              |
| --------- | --------- | ---------------------------------------- |
| Primary   | `#1C3D5A` | Deep blue for headers and accents        |
| Secondary | `#F5F7FA` | Light background tone for clarity        |
| Accent    | `#4DA1FF` | Button highlights and interactive states |
| Success   | `#2ECC71` | Positive confirmation and quiz success   |
| Warning   | `#F39C12` | Alerts or missing uploads                |
| Error     | `#E74C3C` | Validation errors and critical alerts    |
| Text      | `#1E1E1E` | Primary text color (high contrast black) |

The design avoids excessive gradients or shadows — relying on flat, modern color usage for a clean look.

---

## 4. Typography

- **Font Family:** `Inter`, `Roboto`, or system sans-serif equivalent
- **Font Sizes:**
  - Headings: 22–28px
  - Body: 16px
  - Labels & Buttons: 14px
- **Style:** Lightweight with strong hierarchy between headings and content.
- **Alignment:** Left-aligned for readability, center alignment only for dashboard metrics.

---

## 5. Layout Structure

### **Global Layout**

- Persistent top header displaying app name **"WordBridge"**.
- Vertical sidebar (for educators only) containing navigation links: _Dashboard_, _Students_, _Add Student_, _Upload_, _Recommendations_.
- For students, a simple horizontal navigation bar with tabs: _Home_, _My Words_, _Quizzes_, _Profile_.
- All pages share a consistent content container with generous spacing and rounded cards for readability.
- **Logout button** visible in top-right corner for all users.

### **Login Page**

- Clean, centered card with:
  - **Role Selection:** Two large buttons: "Educator" or "Student"
  - **Login Form:** Email/Username field, Password field
  - **Submit Button:** "Log In"
  - **Link to Signup:** "New educator? Sign up here" (only for educators)
- **Validation:** Inline error messages for incorrect credentials or role mismatch

### **Educator Signup Page**

- Centered form with fields:
  - Name (text input)
  - Username (text input, unique validation)
  - Email (email input, unique validation)
  - Password (password input, strength indicator)
  - Confirm Password (validation on blur)
- **Submit Button:** "Create Account"
- **Validation:** Real-time feedback for password match, email format, uniqueness

### **Add Student Page (Educators)**

- Form with fields:
  - Name (text input)
  - Grade (dropdown: 6th, 7th, 8th)
  - Username (text input, unique validation)
  - Email (email input)
  - Password (password input)
- **Submit Button:** "Create Student Account"
- **Success Message:** "Student account created successfully!"
- **Link:** "Add another student" or "Return to dashboard"

### **Educator Dashboard**

- **Top Section:** Summary cards
  - Total Students
  - Pending Recommendations (clickable)
  - Average Class Proficiency
  - Active Streaks (students with current streaks)
- **Main Section:** Table of students
  - Columns: Name, Grade, Vocabulary Level, Pending Words, Last Upload, Actions
  - Actions: "View Profile", "Upload Work", "View Recommendations"
- **Right Sidebar (optional):** Recent activity feed (uploads, approvals)

### **Educator Recommendations Page**

- **Filter Options:** By student, by difficulty, by date
- **Card-Based Layout:** Each recommendation shows:
  - Word (large, bold)
  - Student name
  - Rationale (AI-generated)
  - Difficulty score (visual meter)
  - Example sentence
  - Action buttons: "Approve", "Reject", "Edit Rationale", "Pin"
- **Bulk Actions:** Checkboxes for multi-select, "Approve Selected" and "Reject Selected" buttons
- **Status Indicator:** "X pending recommendations"

### **Educator Upload Page**

- **Student Selection:** Dropdown to select student (required)
- **Multi-File Upload Zone:** Drag-and-drop area
  - Supported formats clearly displayed: .txt, .docx, .pdf, .csv
  - Visual file list with remove option
- **Upload Button:** "Upload and Process"
- **Status Indicator:**
  - "Uploading..." with progress bar
  - "Processing..." with estimated time
  - "Complete!" with success icon
- **Notification:** Toast message on completion or error

### **Student Dashboard**

- **Top Section:**
  - XP progress bar with current level
  - Streak counter with flame icon
  - Badge display (earned badges highlighted)
- **Middle Section:** "Your Vocabulary Words" card
  - List of approved words with:
    - Word + definition
    - Rationale ("Why this word?")
    - Mastery indicator: "Practicing" / "Nearly Mastered" / "Mastered"
    - Visual progress dots (e.g., ●○○ for 1/3 correct)
- **Bottom Section:**
  - "Start Quiz" button (disabled if <5 approved words, with tooltip explaining why)
  - Recent quiz performance summary (last 3 quizzes with scores)

### **Quiz Page (Students)**

- **Progress Indicator:** "Question 2 of 10" at top
- **Question Card:** Clean, centered layout
  - Question text (e.g., "Choose the correct definition of 'hypothesis':")
  - Answer options (multiple-choice radio buttons OR fill-in-the-blank text input)
  - "Submit Answer" button
- **Feedback:**
  - Correct: Green highlight + "Correct! +10 XP"
  - Incorrect: Red highlight + "Not quite. The correct answer is..."
- **Navigation:** "Next Question" button after feedback
- **Completion Modal:**
  - "Quiz Complete!"
  - XP gained (e.g., "+80 XP")
  - Streak status ("5-day streak maintained!")
  - Score (e.g., "8 out of 10 correct")
  - "View Dashboard" button

---

## 6. UI Components

### **Buttons**

- **Primary:** Rounded corners (6px), accent blue background, white text
- **States:**
  - Default: `#4DA1FF`
  - Hover: 90% opacity
  - Active: 80% opacity
  - Disabled: Gray background, cursor not-allowed
  - Loading: Spinner icon inside button, disabled state
- **Secondary:** Outlined style with accent blue border

### **Cards**

- Soft shadows (`rgba(0,0,0,0.1)`)
- Rounded edges (8px)
- White background
- Padding: 20px
- Used for grouping related content

### **Tables/Lists**

- Simple borders (`1px solid #E0E0E0`)
- Alternating row colors for readability (`#F5F7FA` for even rows)
- Hover effect on rows (light blue highlight)

### **Forms**

- **Input Fields:**
  - Border: `1px solid #D0D0D0`
  - Focus: Accent blue border
  - Padding: 10px
  - Border-radius: 4px
- **Labels:** Above input, bold, 14px
- **Placeholder Text:** Gray, italic
- **Validation Feedback:**
  - Inline error messages in red below input
  - Success checkmark icon for valid inputs

### **Modals**

- **Backdrop:** Semi-transparent black (`rgba(0,0,0,0.5)`)
- **Modal Card:** Centered, white background, rounded corners, shadow
- **Close Options:**
  - X button in top-right corner
  - ESC key
  - Clicking backdrop (for non-critical modals)
- **Focus Trap:** Tab navigation cycles within modal

### **Notifications (Toasts)**

- **Position:** Top-right corner
- **Auto-dismiss:** 5 seconds
- **Types:**
  - Success: Green background, checkmark icon
  - Error: Red background, warning icon
  - Info: Blue background, info icon
- **Manual Dismiss:** X button

### **Icons**

- Minimal line icons (e.g., Feather Icons, Heroicons)
- Used for:
  - Navigation (home, profile, logout)
  - Status indicators (checkmark, warning, info)
  - Actions (edit, delete, upload)
- Always accompanied by alt text for accessibility

### **Progress Indicators**

- **XP Bar:** Horizontal bar with fill animation, percentage label
- **Streak Counter:** Number with flame icon, animated on increment
- **Quiz Progress:** "X of Y" text + linear progress bar
- **Loading Spinner:** Circular spinner for async operations

---

## 7. Interactive States

### **Buttons**

- **Default:** Static appearance
- **Hover:** Slight opacity reduction + cursor pointer
- **Active:** Pressed effect (slight scale down)
- **Disabled:** Gray, no hover effect, cursor not-allowed
- **Loading:** Spinner icon, disabled interaction

### **Forms**

- **Validation on Blur:** Check field when user leaves input
- **Inline Errors:** Display immediately below invalid field
- **Success Confirmation:** Green checkmark icon appears when valid
- **Submit Disabled:** Until all required fields are valid

### **Modals**

- **Open Animation:** Fade in + scale up (200ms)
- **Close Animation:** Fade out + scale down (200ms)
- **Backdrop Dismiss:** Click outside to close (non-critical modals only)
- **ESC Key:** Always closes modal
- **Focus Management:** Auto-focus first input on open, return focus on close

### **Notifications**

- **Appear:** Slide in from right (300ms)
- **Auto-dismiss:** Fade out after 5 seconds
- **Hover:** Pause auto-dismiss timer
- **Click:** Dismiss immediately

---

## 8. Navigation Flow

```
[Login] → Role Selection (Educator/Student)
        ↓
    [Educator]                       [Student]
        ↓                                ↓
  [Dashboard]                      [Dashboard]
        ↓                                ↓
[Add Student] → [Upload] → [Recommendations] → [Approve]
                                                    ↓
                                            [Student Dashboard]
                                                    ↓
                                                [Quiz]
                                                    ↓
                                            [Results Modal]
                                                    ↓
                                            [Dashboard Updated]
```

---

## 9. Responsiveness

- Fully responsive design — optimized for desktops and tablets (mobile optional).
- **Breakpoints:**
  - Desktop: ≥1200px
  - Tablet: 768px – 1199px
  - Mobile: <768px (simplified layout)
- **Tablet View:** Sidebar collapses into hamburger menu
- **Mobile View:** Stacks vertically, navigation becomes bottom tabs
- Font and container scaling handled via relative units (em/rem)

---

## 10. Accessibility and Usability

- **Color Contrast:** Minimum 4.5:1 ratio for all text (WCAG 2.2 AA compliant)
- **Keyboard Navigation:** All interactive elements accessible via Tab key
- **Focus Indicators:** Visible outline on focused elements
- **Alt Text:** Provided for all icons and images
- **Screen Reader Support:** ARIA labels for complex components
- **No Time Pressure:** Users control pacing (no auto-advancing)
- **Error Recovery:** Clear instructions for fixing validation errors

---

## 11. Tone and Branding

- The WordBridge brand tone is **educational, approachable, and empowering**.
- Visuals emphasize progress, growth, and clarity.
- Interface copy should be encouraging — using positive reinforcement (e.g., "Great work!", "Keep learning!", "You're on a streak!").
- **Error Messages:** Friendly and constructive (e.g., "Oops! Username already taken. Try another one.")
- **Success Messages:** Celebratory (e.g., "🎉 Quiz complete! You earned 80 XP!")

---

## 12. Summary

WordBridge's design merges simplicity with function — ensuring both educators and students can achieve their goals quickly without navigating complex menus or crowded screens. The interface should feel light, professional, and friendly, with clear hierarchy, visible progress, and instant feedback.

**Design Priorities:**

1. **Clarity:** Users should never be confused about what to do next
2. **Feedback:** Every action provides immediate confirmation
3. **Consistency:** Unified visual language across all pages
4. **Accessibility:** Keyboard-friendly, high contrast, screen reader support
5. **Performance:** Fast load times, smooth animations, responsive interactions

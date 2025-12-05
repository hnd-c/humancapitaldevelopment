# Database Design Blueprint

> **Document Version:** 2.0
> **Last Updated:** December 2024
> **Status:** Ready for Implementation
> **Total Tables:** 52
> **PostgreSQL Extensions Required:** `uuid-ossp`, `vector` (pgvector), `pg_partman`, `pgcrypto`, `pg_trgm`

---

## TABLE OF CONTENTS

1. [Design Principles](#optimized-e-r-design)
2. [Quick Reference: All Tables](#quick-reference-all-tables-52-total)
3. [Core Entities](#core-entities) - Users, Schools, Students, Guardians, Teachers, Admins
4. [Academic Structure](#academic-structure) - Class Levels, Subjects, Paper Types, Papers
5. [Questions & ML Data](#questions--ml-data) - Questions, Images, Mark Schemes, Embeddings, Clusters
6. [Enrollment & Progress](#enrollment--progress) - Enrollments, History, Submissions, State Vectors
7. [Teacher Assignments](#teacher-assignments) - Section Assignments, Assignment Sets
8. [Parent Features](#parent-incentives) - Incentives, Parent Assignments
9. [Admin & System](#admin--system) - System Admins, Student-Teacher Relations
10. [E-R Diagram](#e-r-diagram-relationships) - Complete System Overview
11. [Key Relationships](#key-relationships-summary) - Relationship Summary
12. [Indexes](#indexes-for-performance) - Performance Indexes
13. [ML Integration Notes](#notes-for-ml-integration) - ML System Compatibility
14. [Lookup Tables](#lookup-tables-normalization) - Normalization Lookup Tables
15. [Security Tables](#security-tables) - Sessions, Tokens, API Keys, Audit
16. [Notification System](#notification-system) - Notifications, Preferences
17. [GDPR & Compliance](#gdpr--data-compliance) - Data Requests, Consent
18. [Analytics Tables](#analytics-optimization-tables) - Pre-computed Aggregates
19. [Constraints & Triggers](#check-constraints--validation) - Data Validation
20. [RLS Policies](#row-level-security-rls-policies) - Row-Level Security
21. [Partitioning](#partitioning-strategy) - High-Volume Table Partitioning
22. [Archival Strategy](#data-archival-strategy) - Historical Data Management
23. [Materialized Views](#materialized-views) - Dashboard Performance
24. [Implementation Checklist](#implementation-checklist) - 12-Phase Deployment Guide
25. [Seed Data](#seed-data-examples) - Initial Data Examples
26. [Maintenance Jobs](#maintenance-jobs-cron) - Scheduled Tasks
27. [Next Steps](#next-steps) - Implementation Guide

---

## ORIGINAL CONCEPT NOTES (Historical Reference)

<details>
<summary>Click to expand original concept notes</summary>

```
Question_table: ['class_level(A-Level)', 'subject(Physics)', 'paper_number/type(P1)',
                 'question_number', 'question_text', 'images_paths', 'source_file',
                 'mark scheme', 'openai_embedding', 'umap_embedding', 'soft_cluster']

Student_table: ['id_number','name', 'address', 'phone', 'email', 'DOB', 'School',
                'Department', 'Section', 'Stream', 'Year', 'parent_id']

Parent_table: ['name', 'address', 'phone', 'email', 'education_level', 'occupation', 'parent_id']

Teacher_table: ['name', 'address', 'phone', 'email', 'education_level', 'subject_teacher', 'section_assigned']

School_admin_table: ['name', 'address', 'phone', 'email', 'education_level', 'department']

Student_progress_table: ['student_id', 'subject', 'paper_number', 'question_number',
                         'time_stamp', 'attempt_status', 'time_spent']

Parent_incentivized_table: ['question_id', 'incentive', 'progress', 'incentive_retrived_status']

Teacher_assigned_table: ['question_id', 'student_id', 'assignment_status']
```

**Original System Flow:**
- Separate tables per paper type (P1, P2, P3) and subject (Physics, Chemistry, Biology) for each class level
- Question preprocessing: embeddings (OpenAI) → UMAP dimensionality reduction → Bayesian GMM clustering → soft cluster storage
- Students subscribe to question tables with objectives (coverage, cluster-specific, balanced)
- ML-based question recommendations based on objectives and progress history
- Parents view child progress and can incentivize question completion for rewards
- Teachers view student progress and assign questions based on needs
- System admin connects students to questions, parents, and teachers

</details>

---

## OPTIMIZED E-R DESIGN

### Design Principles Applied:
1. **Normalization (3NF)** - Separate entities for reusable data (Schools, Subjects, Papers)
2. **Explicit Keys** - Primary keys (PK) and Foreign keys (FK) clearly defined
3. **Enrollment Pattern** - Junction tables for student-paper subscriptions
4. **Soft Delete** - `is_active` flags for data retention
5. **Audit Trail** - `created_at`, `updated_at` timestamps
6. **ML-Ready Structure** - Embeddings stored efficiently, soft clusters as arrays
7. **Row-Level Security** - Database-enforced access control
8. **Partitioning** - Time-based partitioning for high-volume tables
9. **Caching** - Materialized views and pre-computed analytics

---

### QUICK REFERENCE: ALL TABLES (52 Total)

| # | Category | Table Name | Description |
|---|----------|------------|-------------|
| 1 | Auth | `users` | Central authentication |
| 2 | Profile | `students` | Student profiles |
| 3 | Profile | `teachers` | Teacher profiles |
| 4 | Profile | `school_admins` | School admin profiles |
| 5 | Profile | `system_admins` | System admin profiles |
| 6 | Profile | `student_guardians` | Parent/guardian links |
| 7 | Org | `schools` | School entities |
| 8 | Lookup | `education_levels` | Education level options |
| 9 | Lookup | `departments` | School departments |
| 10 | Lookup | `sections` | Class sections |
| 11 | Lookup | `streams` | Academic streams |
| 12 | Lookup | `teacher_roles` | Teacher role types |
| 13 | Academic | `class_levels` | A-Level, O-Level, etc. |
| 14 | Academic | `subjects` | Physics, Chemistry, etc. |
| 15 | Academic | `subject_paper_types` | P1, P2, P3 configurations |
| 16 | Academic | `papers` | Individual paper instances |
| 17 | Academic | `questions` | Question content |
| 18 | Academic | `question_images` | Question images (S3) |
| 19 | Academic | `mark_schemes` | Answer/grading criteria |
| 20 | ML | `question_embeddings` | Embeddings & soft clusters |
| 21 | ML | `clusters` | Topic cluster labels |
| 22 | ML | `transition_matrices` | State transition data |
| 23 | Progress | `student_paper_type_enrollments` | Student subscriptions |
| 24 | Progress | `student_question_history` | Attempt records (partitioned) |
| 25 | Progress | `student_submissions` | Answer content (partitioned) |
| 26 | Progress | `student_state_vectors` | ML state cache |
| 27 | Progress | `student_dashboard_analytics` | Dashboard cache |
| 28 | Teacher | `teacher_section_assignments` | Section teaching assignments |
| 29 | Teacher | `teacher_assignment_sets` | Homework/assignment groups |
| 30 | Teacher | `assignment_set_questions` | Questions in assignments |
| 31 | Teacher | `assignment_set_students` | Students in assignments |
| 32 | Teacher | `teacher_class_analytics` | Class performance cache |
| 33 | Parent | `parent_incentives` | Reward incentives |
| 34 | Parent | `incentive_questions` | Incentive question links |
| 35 | Parent | `parent_assignment_sets` | Parent-created assignments |
| 36 | Parent | `parent_assignment_questions` | Parent assignment questions |
| 37 | Parent | `parent_assignment_children` | Children in assignments |
| 38 | Relation | `student_teacher_relations` | Student-teacher links |
| 39 | Security | `user_sessions` | Login sessions |
| 40 | Security | `email_verifications` | Email verification tokens |
| 41 | Security | `password_resets` | Password reset tokens |
| 42 | Security | `api_keys` | API key management |
| 43 | Security | `audit_log` | Change audit trail (partitioned) |
| 44 | Notify | `notifications` | User notifications |
| 45 | Notify | `notification_preferences` | Notification settings |
| 46 | GDPR | `data_deletion_requests` | Deletion requests |
| 47 | GDPR | `data_export_requests` | Data export requests |
| 48 | GDPR | `consent_records` | Consent tracking |
| 49 | Analytics | `daily_student_activity` | Daily aggregates |
| 50 | Analytics | `weekly_leaderboard` | Weekly rankings |
| 51 | Analytics | `cluster_performance_cache` | Topic performance cache |
| 52 | System | `schema_migrations` | Schema version tracking |

---

### CORE ENTITIES

#### 1. Users (Authentication Layer)
```
users
├── user_id (PK, UUID, DEFAULT gen_random_uuid())
├── email (VARCHAR(255), UNIQUE, NOT NULL)
├── password_hash (VARCHAR(255), NOT NULL)
├── display_name (VARCHAR(100), NULL)
├── role (ENUM: student, parent, teacher, school_admin, system_admin, NOT NULL)
├── is_active (BOOLEAN, DEFAULT true, NOT NULL)
├── email_verified (BOOLEAN, DEFAULT false)
├── email_verified_at (TIMESTAMPTZ, NULL)
├── last_login_at (TIMESTAMPTZ, NULL)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
└── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── CHECK: email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
```
*All user types authenticate through this table*

---

#### 2. Schools
```
schools
├── school_id (PK, SERIAL)
├── name (VARCHAR(200), NOT NULL)
├── address (TEXT, NULL)
├── phone (VARCHAR(20), NULL)
├── email (VARCHAR(255), NULL)
├── website (VARCHAR(255), NULL)
│
│   -- SCHOOL DETAILS --
├── school_type (ENUM: public, private, charter, international, NULL)
├── accreditation_body (VARCHAR(100), NULL, e.g., 'Cambridge', 'IB', 'Edexcel')
├── country (VARCHAR(100), NULL)
├── timezone (VARCHAR(50), DEFAULT 'UTC')
│
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── CHECK: email IS NULL OR email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
└── INDEX(name)
```
*Central entity for school management; referenced by students, admins, teachers*

---

#### 3. Students
```
students
├── student_id (PK, FK → users.user_id, UUID)
├── id_number (VARCHAR(50), UNIQUE, external ID like roll number)
├── name (VARCHAR(100), NOT NULL)
├── address (TEXT, NULL)
├── phone (VARCHAR(20), NULL)
├── dob (DATE, NULL)
├── school_id (FK → schools.school_id, NOT NULL)
│
│   -- NORMALIZED REFERENCES (optional FK or denormalized) --
├── department_id (FK → departments.department_id, NULL)
├── section_id (FK → sections.section_id, NULL)
├── stream_id (FK → streams.stream_id, NULL)
│   -- OR keep denormalized for simpler queries: --
├── department (VARCHAR(100), NULL)
├── section (VARCHAR(50), NULL)
├── stream (VARCHAR(50), NULL)
│
├── year (INTEGER, NULL)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── CHECK: year IS NULL OR (year > 0 AND year <= 13)
└── INDEX(school_id)
```
*Choose either FK references (normalized) or VARCHAR fields (denormalized) based on query patterns*

---

#### 4. Student Guardians (Unified: Primary Parent + Secondary Guardians)
```
student_guardians
├── id (PK, SERIAL)
├── student_id (FK → students.student_id, NOT NULL)
├── user_id (FK → users.user_id, NOT NULL)
│
│   -- ROLE & RELATIONSHIP --
├── role (ENUM: primary, secondary, NOT NULL)  ← KEY FIELD: controls permissions
├── relationship (ENUM: father, mother, guardian, grandparent, other, NOT NULL)
│
│   -- GUARDIAN INFO (denormalized for convenience) --
├── name (VARCHAR(100), NOT NULL)
├── phone (VARCHAR(20), NULL)
├── education_level_id (FK → education_levels.level_id, NULL)
│   -- OR: education_level (ENUM: high_school, bachelors, masters, doctorate, other)
├── occupation (VARCHAR(100), NULL)
│
│   -- INVITATION (for secondary only) --
├── invited_by (FK → student_guardians.id, NULL for primary)
├── invite_accepted (BOOLEAN, DEFAULT true for primary)
├── invite_token_hash (VARCHAR(64), NULL)
├── invite_expires_at (TIMESTAMPTZ, NULL)
│
│   -- STATUS --
├── is_active (BOOLEAN, DEFAULT true, NOT NULL)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── UNIQUE(student_id, user_id)
└── INDEX(user_id)
└── INDEX(student_id) WHERE role = 'primary'
```
*Single table for all parent/guardian relationships. Role field determines access.*

**Constraint:** Each student can have only ONE `role='primary'` guardian:
```sql
CREATE UNIQUE INDEX idx_one_primary_per_student
ON student_guardians(student_id)
WHERE role = 'primary';

-- Ensure invite_by is NULL for primary guardians
ALTER TABLE student_guardians ADD CONSTRAINT chk_primary_no_inviter
    CHECK (role = 'secondary' OR invited_by IS NULL);
```

**ALL Parents (Primary + Guardians) See Relative Progress:**

Parents aren't ML experts - they don't need to know "Cluster 5 mastery: 0.73".
They need actionable insights in plain language.

| What Parents See | Example | Why It Helps |
|------------------|---------|--------------|
| Percentile rank | "Top 25% in class" | Easy comparison |
| Practice frequency | "Practiced 40% more than average" | Effort indicator |
| Topic strength | "Strong in 6/10 topics" | Simple overview |
| Weak areas | "Needs practice in: Waves, Electricity" | Specific but simple |
| Streak status | "🔥 12-day streak!" | Motivation visible |
| Trend | "↗️ Improving" / "→ Stable" / "↘️ Needs attention" | Quick health check |
| Incentive progress | "Goal: 60% complete 🎯" | Track rewards |
| Weekly summary | "Practiced 3 days, completed 15 questions" | Engagement overview |

**Primary Parent Additional Capabilities:**
- ✓ Create/manage incentives
- ✓ Set learning objectives
- ✓ Invite secondary guardians
- ✓ See incentive amounts/rewards they set
- ✓ Receive detailed notifications

**Secondary Guardians:**
- ✓ View relative progress (same as primary)
- ✗ Cannot create incentives
- ✗ Cannot modify objectives
- ✗ Cannot see incentive reward details

**Raw Data (Hidden from ALL Parents):**
- Specific question IDs or content
- Exact cluster/embedding data
- ML vectors and scores
- Technical performance metrics

*Raw data is only for the system and teachers who have subject expertise*

---

#### 5. Teachers
```
teachers
├── teacher_id (PK, FK → users.user_id, UUID)
├── name (VARCHAR(100), NOT NULL)
├── address (TEXT, NULL)
├── phone (VARCHAR(20), NULL)
├── education_level_id (FK → education_levels.level_id, NULL)
│   -- OR: education_level (VARCHAR, NULL)
│
│   -- OPTIONAL: School association (if teacher is full-time at one school)
├── primary_school_id (FK → schools.school_id, NULL)
│
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── INDEX(primary_school_id)
```
*Teachers connect to schools via `teacher_section_assignments` for flexibility*

---

#### 6. School Admins
```
school_admins
├── admin_id (PK, FK → users.user_id, UUID)
├── name (VARCHAR(100), NOT NULL)
├── address (TEXT, NULL)
├── phone (VARCHAR(20), NULL)
├── education_level_id (FK → education_levels.level_id, NULL)
│   -- OR: education_level (VARCHAR, NULL)
│
├── school_id (FK → schools.school_id, NOT NULL)
├── department_id (FK → departments.department_id, NULL)
│   -- OR: department (VARCHAR(100), NULL)
│
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── INDEX(school_id)
```
*School admins are bound to a single school*

---

### ACADEMIC STRUCTURE

#### 7. Class Levels
```
class_levels
├── class_level_id (PK, SERIAL)
├── name (VARCHAR(50), NOT NULL, UNIQUE, e.g., 'A-Level', 'O-Level', 'IGCSE', 'IB')
├── description (TEXT, NULL)
├── exam_board (VARCHAR(100), NULL, e.g., 'Cambridge', 'Edexcel', 'IBO')
├── display_order (INTEGER, DEFAULT 0)
│
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── INDEX(name)
```
*Global lookup table for academic levels*

---

#### 8. Subjects
```
subjects
├── subject_id (PK, SERIAL)
├── class_level_id (FK → class_levels.class_level_id, NOT NULL)
├── name (VARCHAR(100), NOT NULL, e.g., 'Physics', 'Chemistry', 'Biology')
├── code (VARCHAR(20), NULL, e.g., '9702' for A-Level Physics)
├── description (TEXT, NULL)
│
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── UNIQUE(class_level_id, name)
└── UNIQUE(class_level_id, code) WHERE code IS NOT NULL
└── INDEX(class_level_id)
```
*Subjects are specific to a class level (A-Level Physics ≠ O-Level Physics)*

---

#### 9. Subject Paper Types (Shared Config per Subject + Paper Type)
```
subject_paper_types
├── paper_type_id (PK, SERIAL)
├── subject_id (FK → subjects.subject_id, NOT NULL)
├── paper_type (VARCHAR(20), NOT NULL, e.g., 'P1', 'P2', 'P3', 'Paper 1')
├── paper_type_name (VARCHAR(100), NULL, e.g., 'Multiple Choice', 'Structured Questions')
│
│   -- CLUSTERING (shared across ALL papers of this type) --
├── n_clusters (INTEGER, NULL, number of topic clusters)
├── clustering_version (VARCHAR(20), NULL, e.g., 'v1.0', 'v2.0', current active version)
│
│   -- MCQ CONFIGURATION (shared across ALL papers of this type) --
├── is_mcq (BOOLEAN, DEFAULT false, NOT NULL)
├── mcq_option_count (INTEGER, NULL, e.g., 4, 5, 6)
├── mcq_option_format (ENUM: alphabetic_upper, alphabetic_lower, numeric_zero, numeric_one, custom, NULL)
├── mcq_custom_labels (TEXT[], NULL, e.g., ['True', 'False'])
├── mcq_multi_select (BOOLEAN, DEFAULT false, NOT NULL)
│
│   -- PAPER TYPE DEFAULTS --
├── default_total_marks (INTEGER, NULL, typical total marks)
├── default_duration_minutes (INTEGER, NULL, typical duration)
│
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
│   -- CONSTRAINTS --
└── UNIQUE(subject_id, paper_type)
└── CHECK: n_clusters IS NULL OR n_clusters > 0
└── CHECK: (is_mcq = false) OR (mcq_option_count >= 2 AND mcq_option_format IS NOT NULL)
└── CHECK: mcq_option_count IS NULL OR mcq_option_count >= 2
└── CHECK: default_total_marks IS NULL OR default_total_marks > 0
└── CHECK: default_duration_minutes IS NULL OR default_duration_minutes > 0
│
└── INDEX(subject_id)
```
*Shared configuration for all papers of the same type within a subject*
*ALL questions across papers of same type share clustering and transition matrix*

**Example Subject Paper Types:**
| class_level | subject | paper_type | n_clusters | is_mcq | mcq_format |
|-------------|---------|------------|------------|--------|------------|
| A-Level | Physics | P1 | 10 | true | alphabetic_upper |
| A-Level | Physics | P2 | 8 | false | NULL |
| A-Level | Biology | P1 | 12 | true | alphabetic_upper |
| IB | Physics | Paper 1 | 9 | true | numeric_one |
| IB | Biology | Paper 1 | 11 | true | numeric_one |

**Why This Structure:**
- A-Level Physics P1 clustering ≠ IB Physics Paper 1 clustering (different syllabi)
- A-Level Physics P1 clustering ≠ A-Level Biology P1 clustering (different topics)
- Cambridge May 2023 P1 + Khan Academy P1 = SAME clustering (same subject+paper_type)

---

#### 10. Papers (Individual Paper Instances)
```
papers
├── paper_id (PK, SERIAL)
├── paper_type_id (FK → subject_paper_types.paper_type_id)
│
│   -- PAPER INSTANCE DETAILS --
├── paper_name (VARCHAR, e.g., 'May/June 2023 Paper 1')
├── exam_year (INTEGER, NULL, e.g., 2023)
├── exam_session (VARCHAR, NULL, e.g., 'May/June', 'Oct/Nov')
├── total_marks (INTEGER, NULL, override default if different)
├── duration_minutes (INTEGER, NULL, override default if different)
├── source_file (VARCHAR, path to original PDF)
│
│   -- PAPER SOURCE & ORIGIN --
├── paper_source_type (ENUM: past_paper, practice, mock, custom)
├── source_organization (VARCHAR, NULL, e.g., 'Cambridge', 'Khan Academy', 'School Name')
├── is_official (BOOLEAN, DEFAULT false, true if from official exam board)
│
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
```
*Each paper is an instance of a paper type (e.g., "Cambridge May 2023" is an instance of "A-Level Physics P1")*
*Clustering and MCQ config inherited from subject_paper_types*
*Source fields allow filtering by origin while sharing clustering*

**Paper Source Types:**
| Source Type | Description | is_official |
|-------------|-------------|-------------|
| `past_paper` | Actual exam paper from official board | true |
| `practice` | Practice questions from textbooks, online resources | false |
| `mock` | Mock/trial exams from schools or tutoring centers | false |
| `custom` | Teacher/tutor created questions | false |

**Example Papers (all sharing A-Level Physics P1 clustering):**
```
subject_paper_types: A-Level Physics P1 (paper_type_id: 1)
├── n_clusters: 10
├── is_mcq: true
├── mcq_option_format: 'alphabetic_upper'
│
└── Papers (all share same clustering):
    ├── paper_id: 101
    │   ├── paper_name: 'May/June 2023'
    │   ├── paper_source_type: 'past_paper'
    │   ├── source_organization: 'Cambridge'
    │   └── is_official: true
    │
    ├── paper_id: 102
    │   ├── paper_name: 'Oct/Nov 2023'
    │   ├── paper_source_type: 'past_paper'
    │   ├── source_organization: 'Cambridge'
    │   └── is_official: true
    │
    ├── paper_id: 103
    │   ├── paper_name: 'Practice Set 1'
    │   ├── paper_source_type: 'practice'
    │   ├── source_organization: 'Khan Academy'
    │   └── is_official: false
    │
    └── paper_id: 104
        ├── paper_name: 'Internal Mock 2024'
        ├── paper_source_type: 'mock'
        ├── source_organization: 'ABC School'
        └── is_official: false
```

**Filter Examples:**
```sql
-- All A-Level Physics P1 papers (any source)
SELECT p.* FROM papers p
JOIN subject_paper_types spt ON p.paper_type_id = spt.paper_type_id
WHERE spt.paper_type = 'P1'
  AND spt.subject_id = (SELECT subject_id FROM subjects WHERE name = 'Physics');

-- Only official past papers for A-Level Physics P1
SELECT p.* FROM papers p
JOIN subject_paper_types spt ON p.paper_type_id = spt.paper_type_id
WHERE spt.paper_type = 'P1'
  AND p.paper_source_type = 'past_paper'
  AND p.is_official = true;

-- All questions from cluster 5, any source
SELECT q.* FROM questions q
JOIN papers p ON q.paper_id = p.paper_id
JOIN question_embeddings e ON q.question_id = e.question_id
WHERE p.paper_type_id = 1  -- A-Level Physics P1
  AND e.soft_cluster[5] > 0.5;

-- Only past paper questions from cluster 5
SELECT q.* FROM questions q
JOIN papers p ON q.paper_id = p.paper_id
JOIN question_embeddings e ON q.question_id = e.question_id
WHERE p.paper_type_id = 1
  AND p.paper_source_type = 'past_paper'
  AND p.is_official = true
  AND e.soft_cluster[5] > 0.5;
```

**Versioning for Updates:**
When questions are added/updated and clusters recalculated:
1. Increment `subject_paper_types.clustering_version` (e.g., 'v1.0' → 'v2.0')
2. New `question_embeddings` records use new version
3. New `transition_matrices` record with new version
4. Old student progress remains valid for old version
5. System can migrate students or keep them on old version until natural transition

---

### QUESTIONS & ML DATA

#### 11. Questions
```
questions
├── question_id (PK, SERIAL)
├── internal_question_id (INTEGER, for ML indexing, 0-based per paper_type)
├── paper_id (FK → papers.paper_id, NOT NULL)
├── question_number (VARCHAR(20), NOT NULL, e.g., '1', '2a', '2b(i)')
├── question_text (TEXT, NOT NULL)
├── marks (INTEGER, NOT NULL)
├── source_file (VARCHAR(500), NULL, path to source PDF/document)
│
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── CHECK: marks > 0
└── UNIQUE(paper_id, question_number)
└── INDEX(paper_id)
```
*Mark scheme moved to separate table for clean separation*
*internal_question_id used for ML system indexing (0-based within paper type)*

---

#### 12. Question Images (S3 bucket abstraction)
```
question_images
├── image_id (PK, SERIAL)
├── question_id (FK → questions.question_id, NOT NULL)
├── s3_key (VARCHAR(500), NOT NULL, e.g., 'questions/physics/p1/2023/q1_fig1.png')
├── image_type (ENUM: question, mark_scheme, diagram, figure, graph, NOT NULL)
├── display_order (INTEGER, DEFAULT 0, NOT NULL)
├── alt_text (VARCHAR(500), NULL, accessibility description)
├── file_size_bytes (INTEGER, NULL)
├── mime_type (VARCHAR(50), NULL, e.g., 'image/png', 'image/jpeg')
│
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── CHECK: display_order >= 0
└── CHECK: file_size_bytes IS NULL OR file_size_bytes > 0
└── INDEX(question_id)
└── INDEX(s3_key)
```
*Images stored in S3, only paths/keys in database*
*One-to-many: single question can have multiple images (1-8+ images per question supported)*
*Use display_order to control sequence when rendering multiple images*

---

#### 12a. Mark Schemes (Separate from Questions)
```
mark_schemes
├── mark_scheme_id (PK, SERIAL)
├── question_id (FK → questions.question_id, UNIQUE, NOT NULL)
│
│   -- MARK SCHEME CONTENT --
├── mark_scheme_text (TEXT, NOT NULL, the actual marking criteria with grading)
│
│   -- MCQ CORRECT ANSWER (NULL for non-MCQ, coherent with submission indices) --
├── mcq_correct_indices (INTEGER[], NULL, e.g., [1] for "B" or [0,2] for multi-select)
│
│   -- METADATA --
├── version (VARCHAR(20), DEFAULT 'v1', e.g., 'v1', 'v2' if mark scheme updated)
├── source_file (VARCHAR(500), NULL, original mark scheme PDF)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── INDEX(question_id)
```
*Separate table for clean separation of question content vs answer/grading criteria*
*Mark schemes often come from different source files than questions*

**Example Mark Schemes:**
```
MCQ (P1 Paper):
├── mark_scheme_text: "B"
├── mcq_correct_indices: [1]
└── Grading: submission[1] == correct[1] → ✓

MCQ Multi-Select:
├── mark_scheme_text: "A, C, D"
├── mcq_correct_indices: [0, 2, 3]
└── Grading: compare arrays

Structured (P2 Paper - 3 marks):
├── mark_scheme_text: "
│   • Use of F = ma [1 mark]
│   • Correct substitution: a = 10/2 [1 mark]
│   • Final answer: a = 5 m/s² with unit [1 mark]
│     - Accept 5 ms⁻²
│     - Deduct 1 mark if no unit
│   "
├── mcq_correct_indices: NULL
└── Grading: Teacher/AI evaluates against criteria

Structured with Alternatives (P2 Paper):
├── mark_scheme_text: "
│   • Correct energy type identified [1 mark]
│     - Accept: kinetic energy / KE / ½mv²
│   • Calculation with working [2 marks]
│     - 1 mark for correct formula
│     - 1 mark for correct answer (400 J)
│     - Allow ECF if formula correct but arithmetic error
│   "
└── mcq_correct_indices: NULL
```

---

#### 13. Question Embeddings (Separate for Performance)
```
question_embeddings
├── id (PK, SERIAL)
├── question_id (FK → questions.question_id, NOT NULL)
├── clustering_version (VARCHAR(20), NOT NULL, e.g., 'v1.0', matches subject_paper_types.clustering_version)
├── openai_embedding (VECTOR(1536), for text-embedding-3-small)
├── umap_embedding (FLOAT[], 2D/3D reduced representation)
├── soft_cluster (FLOAT[], probability distribution across clusters)
├── embedding_model (VARCHAR(50), NOT NULL, e.g., 'text-embedding-3-small')
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
│   -- CONSTRAINTS --
└── UNIQUE(question_id, clustering_version)
└── CHECK: soft_cluster sums to 1.0 (enforced via trigger)
└── CHECK: array_length(soft_cluster, 1) = n_clusters for paper type
│
└── INDEX USING ivfflat(openai_embedding vector_cosine_ops)
└── INDEX(question_id)
```
*Requires pgvector extension for VECTOR type*
*Multiple versions can exist per question - use subject_paper_types.clustering_version to get active one*
*All questions of same paper_type share clustering regardless of source*
*Trigger validates soft_cluster sums to 1.0 ± 0.01 (probability distribution)*

---

#### 14. Clusters (Optional: Label/Describe Topic Clusters, Per Paper Type)
```
clusters
├── cluster_id (PK, SERIAL)
├── paper_type_id (FK → subject_paper_types.paper_type_id, NOT NULL)
├── clustering_version (VARCHAR(20), NOT NULL, e.g., 'v1.0', matches subject_paper_types.clustering_version)
├── cluster_index (INTEGER, NOT NULL, 0-based, matches soft_cluster array index)
├── label (VARCHAR(100), NULL, human-readable topic name, e.g., 'Mechanics', 'Waves')
├── description (TEXT, NULL)
├── representative_keywords (TEXT[], NULL)
├── color_code (VARCHAR(7), NULL, e.g., '#FF5733' for visualization)
│
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── UNIQUE(paper_type_id, clustering_version, cluster_index)
└── CHECK: cluster_index >= 0
└── INDEX(paper_type_id, clustering_version)
```
*Each paper TYPE has its own set of clusters (shared across all papers of that type)*
*Labels are optional - system can work without human-readable names*
*Multiple versions exist when clusters are recalculated - use subject_paper_types.clustering_version to get active*

---

### ENROLLMENT & PROGRESS

#### 15. Student Paper Type Enrollments
```
student_paper_type_enrollments
├── enrollment_id (PK, SERIAL)
├── student_id (FK → students.student_id)
├── paper_type_id (FK → subject_paper_types.paper_type_id)
├── objective (ENUM: coverage, efficiency, success_rate, balanced, custom)
├── target_cluster_id (INTEGER, NULL, specific cluster focus if custom)
├── enrolled_at (TIMESTAMP)
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMP)
└── UNIQUE(student_id, paper_type_id)
```
*This is the "subscription" when student subscribes to a paper TYPE (e.g., A-Level Physics P1)*
*Progress tracked across ALL papers of this type (Cambridge + Khan Academy + mocks)*

---

#### 16. Student Question History
```
student_question_history
├── history_id (PK, BIGSERIAL)
├── enrollment_id (FK → student_paper_type_enrollments.enrollment_id, NOT NULL)
├── question_id (FK → questions.question_id, NOT NULL)
├── attempt_number (INTEGER, DEFAULT 1, NOT NULL)
├── status (ENUM: correct, incorrect, skipped, partial, NOT NULL)
├── is_correct (BOOLEAN, NULL)
├── is_skipped (BOOLEAN, DEFAULT false, NOT NULL)
├── marks_obtained (INTEGER, NULL)
├── time_spent_sec (INTEGER, NULL)
├── confidence_level (INTEGER, NULL, 1-10 scale)
├── device_type (VARCHAR(20), NULL, e.g., 'mobile', 'desktop', 'tablet')
├── session_id (UUID, NULL, group attempts in same session)
├── timestamp (TIMESTAMPTZ, NOT NULL)
│
│   -- ASSIGNMENT CONTEXT (NULL if self-directed practice) --
├── teacher_assignment_set_id (FK → teacher_assignment_sets.set_id, NULL)
├── parent_assignment_set_id (FK → parent_assignment_sets.set_id, NULL)
│
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
│
│   -- CONSTRAINTS --
└── CHECK: attempt_number > 0
└── CHECK: confidence_level IS NULL OR (confidence_level BETWEEN 1 AND 10)
└── CHECK: time_spent_sec IS NULL OR time_spent_sec >= 0
└── CHECK: marks_obtained IS NULL OR marks_obtained >= 0
└── CHECK: NOT (teacher_assignment_set_id IS NOT NULL AND parent_assignment_set_id IS NOT NULL)
│
└── INDEX(enrollment_id, timestamp DESC)
└── INDEX(question_id)
└── INDEX(teacher_assignment_set_id) WHERE teacher_assignment_set_id IS NOT NULL
└── INDEX(parent_assignment_set_id) WHERE parent_assignment_set_id IS NOT NULL
└── INDEX(session_id) WHERE session_id IS NOT NULL
```
*Core table for ML recommendation system - matches vector_encoder.py expectations*
*Assignment context tracks whether attempt was for an assignment or self-directed practice*
*Consider partitioning by timestamp for high-volume deployments (see Partitioning Strategy)*

**Assignment Context Examples:**
```
Self-directed practice:
├── teacher_assignment_set_id: NULL
└── parent_assignment_set_id: NULL

Teacher assignment (Homework #5):
├── teacher_assignment_set_id: 5
└── parent_assignment_set_id: NULL

Parent assignment (Weekend Practice):
├── teacher_assignment_set_id: NULL
└── parent_assignment_set_id: 12
```

---

#### 16a. Student Submissions (MCQ, Text, Image, or Mixed)
```
student_submissions
├── submission_id (PK, BIGSERIAL)
├── history_id (FK → student_question_history.history_id, NOT NULL, UNIQUE)
│
│   -- SUBMISSION CONTENT --
├── submission_type (ENUM: mcq, text, image, mixed, NOT NULL)
├── text_answer (TEXT, NULL, direct text entry or transcribed from image)
│
│   -- MCQ RESPONSE (NULL for non-MCQ, indices only - display derived from paper config) --
├── selected_option_indices (INTEGER[], NULL, e.g., [1] or [0,2,3] for multi-select)
│
│   -- IMAGE HANDLING (S3 abstraction) --
├── s3_key (VARCHAR(500), NULL, e.g., 'submissions/student123/q456_2024-01-15.png')
├── image_type (ENUM: photo, scan, screenshot, NULL if text only)
│
│   -- TRANSCRIPTION (AI/OCR) --
├── is_transcribed (BOOLEAN, DEFAULT false, NOT NULL)
├── transcription_method (ENUM: manual, ocr, gpt4_vision, NULL)
├── transcription_confidence (FLOAT, NULL, 0-1 confidence score)
├── original_text_before_edit (TEXT, NULL, if student corrects transcription)
│
│   -- METADATA --
├── submitted_at (TIMESTAMPTZ, NOT NULL)
├── file_size_bytes (INTEGER, NULL)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
│   -- CONSTRAINTS --
└── CHECK: transcription_confidence IS NULL OR (transcription_confidence BETWEEN 0 AND 1)
└── CHECK: file_size_bytes IS NULL OR file_size_bytes > 0
└── CHECK: (submission_type = 'mcq') = (selected_option_indices IS NOT NULL)
│
└── INDEX(history_id)
└── INDEX USING GIN(selected_option_indices) -- For MCQ analytics queries
```
*Consider partitioning by submitted_at for high-volume deployments*
*Supports MCQ selections, text answers, image uploads (handwritten work), or mixed*
*MCQ stores indices only - display format (A/B/C or 1/2/3) derived from paper's mcq_option_format*
*Images stored in S3, only keys in database*

**Submission Flow Examples:**
```
Scenario 1: MCQ (P1 Paper) - Single Select
├── submission_type: 'mcq'
├── selected_option_indices: [1]        ← Index 1 selected
├── text_answer: NULL
├── s3_key: NULL
└── Display: "B" (from paper.mcq_option_format = 'alphabetic_upper')

Scenario 2: MCQ (Multi-Select)
├── submission_type: 'mcq'
├── selected_option_indices: [0, 2, 3]  ← Multiple indices
├── text_answer: NULL
└── Display: "A, C, D"

Scenario 3: Handwritten Solution (P2/P3 Paper) - Image + Transcription
├── submission_type: 'image'
├── selected_option_indices: NULL
├── text_answer: 'Using F=ma, 10N = 2kg × a, so a = 5 m/s²'  ← AI transcribed
├── s3_key: 'submissions/stu_123/q456_attempt1.jpg'
├── is_transcribed: true
├── transcription_method: 'gpt4_vision'
└── transcription_confidence: 0.92

Scenario 4: Text Answer (Typed)
├── submission_type: 'text'
├── selected_option_indices: NULL
├── text_answer: 'The acceleration is 5 m/s² because...'
└── s3_key: NULL

Scenario 5: Mixed (Diagram + Typed Explanation)
├── submission_type: 'mixed'
├── selected_option_indices: NULL
├── text_answer: 'See diagram. The resultant force is 15N at 30°'
├── s3_key: 'submissions/stu_123/q789_diagram.png'
└── is_transcribed: false  (text was typed, image is supplementary)
```

**MCQ Index → Display Conversion:**
```
Paper config: mcq_option_format = 'alphabetic_upper', mcq_option_count = 4
Submission: selected_option_indices = [2]
Display: "C"  (index 2 → third letter)

Paper config: mcq_option_format = 'numeric_one', mcq_option_count = 5
Submission: selected_option_indices = [3]
Display: "4"  (index 3 → 3+1 = 4)

Paper config: mcq_option_format = 'custom', mcq_custom_labels = ['True', 'False']
Submission: selected_option_indices = [0]
Display: "True"  (index 0 → first label)
```

---

### TEACHER ASSIGNMENTS

#### 17. Teacher Section Assignments
```
teacher_section_assignments
├── assignment_id (PK, SERIAL)
├── teacher_id (FK → teachers.teacher_id)
├── school_id (FK → schools.school_id)
├── subject_id (FK → subjects.subject_id)
├── section (VARCHAR)
├── role (VARCHAR, NULL, e.g., 'lecturer', 'lab_instructor', 'tutor')
├── academic_year (VARCHAR, e.g., '2024-2025')
├── is_active (BOOLEAN)
├── created_at (TIMESTAMP)
└── UNIQUE(teacher_id, school_id, subject_id, section, academic_year)
```
*Multiple teachers can teach same subject/section (e.g., lecturer + lab instructor)*

---

#### 18. Teacher Assignment Sets (Bulk or Individual)
```
teacher_assignment_sets
├── set_id (PK, SERIAL)
├── teacher_id (FK → teachers.teacher_id)
├── paper_id (FK → papers.paper_id)
├── set_name (VARCHAR, e.g., 'Week 3 Homework', 'Mechanics Practice')
│
│   -- TARGET: Section OR Individual Students --
├── target_type (ENUM: section, individual)
├── target_section (VARCHAR, NULL, if target_type='section')
├── target_school_id (FK → schools.school_id, NULL, if section)
│
├── assigned_at (TIMESTAMP)
├── due_date (TIMESTAMP, NULL)
├── notes (TEXT)
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
```

#### 18a. Assignment Set Questions
```
assignment_set_questions
├── id (PK, SERIAL)
├── set_id (FK → teacher_assignment_sets.set_id)
├── question_id (FK → questions.question_id)
├── order_index (INTEGER, display order)
└── UNIQUE(set_id, question_id)
```

#### 18b. Assignment Set Students (for individual targeting)
```
assignment_set_students
├── id (PK, SERIAL)
├── set_id (FK → teacher_assignment_sets.set_id)
├── student_id (FK → students.student_id)
├── status (ENUM: pending, in_progress, completed, overdue)
├── completed_at (TIMESTAMP, NULL)
├── progress_pct (FLOAT, 0-100)
└── UNIQUE(set_id, student_id)
```
*If target_type='section', students are derived from section. If 'individual', use this table.*

**Assignment Examples:**
```
Scenario 1: Same questions to entire section
├── target_type: 'section'
├── target_section: '12A'
├── Questions: Q1, Q2, Q3, Q4, Q5
└── All students in 12A see these questions

Scenario 2: Different questions to specific students
├── target_type: 'individual'
├── Students: John, Sarah, Mike
├── Questions: Q10, Q15, Q20 (remedial)
└── Only these 3 students see these questions
```

---

#### 19. Teacher Class Analytics (Cached Dashboard Data)
```
teacher_class_analytics
├── id (PK, SERIAL)
├── teacher_id (FK → teachers.teacher_id)
├── paper_type_id (FK → subject_paper_types.paper_type_id)
├── section (VARCHAR)
│
│   -- RELATIVE VIEW (Quick Dashboard) --
├── class_avg_percentile (FLOAT, average percentile of class)
├── students_improving (INTEGER, count trending up)
├── students_stable (INTEGER, count stable)
├── students_declining (INTEGER, count needing attention)
├── students_at_risk (INTEGER, count below threshold)
├── class_avg_streak (FLOAT, average streak days)
├── class_engagement_pct (FLOAT, % students active this week)
│
│   -- RAW VIEW (Deep Analysis) --
├── weak_clusters (INTEGER[], cluster indices class struggles with)
├── weak_cluster_labels (TEXT[], human-readable topic names)
├── avg_time_per_question (FLOAT, seconds)
├── common_wrong_questions (INTEGER[], most missed question IDs)
├── total_students (INTEGER)
├── total_attempts_this_week (INTEGER)
│
├── last_computed (TIMESTAMP)
├── created_at (TIMESTAMP)
└── UNIQUE(teacher_id, paper_type_id, section)
```
*Cached analytics for teacher dashboard - recomputed daily*
*Analytics per paper TYPE (all P1 papers combined) since clustering is shared*

**Teacher Dashboard Example:**
```
Section 12A - Physics P1
├── 📊 Class Average: 65th percentile
├── ↗️ Improving: 12 students
├── ↘️ Need attention: 3 students (John, Sarah, Mike)
├── 🔥 Class streak avg: 5.2 days
├── 📚 Weak topics: Waves (Cluster 3), Electricity (Cluster 7)
└── ⚠️ Most missed: Q23, Q41, Q55
```

---

### PARENT INCENTIVES

#### 20. Parent Incentives
```
parent_incentives
├── incentive_id (PK, SERIAL)
├── guardian_id (FK → student_guardians.id, NOT NULL, must be role='primary')
├── student_id (FK → students.student_id, NOT NULL)
├── subject_id (FK → subjects.subject_id, NULL for all subjects)
│
│   -- TARGET DEFINITION --
├── target_type (ENUM: coverage, cluster, questions, streak, time_spent, NOT NULL)
├── target_cluster_index (INTEGER, NULL, if targeting specific cluster)
├── target_value (FLOAT, NOT NULL, e.g., 80% coverage, 10 questions, 5 hours)
├── current_progress (FLOAT, DEFAULT 0, NOT NULL)
│
│   -- REWARD DEFINITION --
├── reward_category (ENUM: money, item, experience, privilege, food, custom, NOT NULL)
├── reward_title (VARCHAR(200), NOT NULL, e.g., 'New Bicycle', 'Pizza Night')
├── reward_description (TEXT, NULL, detailed description if needed)
├── reward_emoji (VARCHAR(10), NULL, e.g., '🚲', '🍕', '🎮', '✈️')
│
│   -- TIMELINE --
├── start_date (DATE, NOT NULL, DEFAULT CURRENT_DATE)
├── end_date (DATE, NULL, no deadline if NULL)
│
│   -- STATUS --
├── status (ENUM: active, completed, expired, claimed, DEFAULT active, NOT NULL)
├── completed_at (TIMESTAMPTZ, NULL, when target was met)
├── claimed_at (TIMESTAMPTZ, NULL, when reward was given)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
│   -- CONSTRAINTS --
└── CHECK: target_value > 0
└── CHECK: current_progress >= 0
└── CHECK: end_date IS NULL OR end_date > start_date
└── CHECK: (target_type = 'cluster') = (target_cluster_index IS NOT NULL)
└── CHECK: completed_at IS NULL OR status IN ('completed', 'claimed')
└── CHECK: claimed_at IS NULL OR status = 'claimed'
│
└── INDEX(student_id, status)
└── INDEX(student_id) WHERE status = 'active'
└── INDEX(guardian_id)
```
*Trigger enforces: guardian_id must reference a row where role='primary'*

**Reward Categories:**
| Category | Examples |
|----------|----------|
| money | $10, $50, allowance increase |
| item | Bicycle, video game, new phone, book |
| experience | Vacation trip, movie night, theme park |
| privilege | Extra screen time, later bedtime, sleepover |
| food | Pizza party, ice cream, chocolate, restaurant |
| custom | Anything else parent defines |

---

#### 20a. Incentive Questions (Optional: Specific Questions for Incentive)
```
incentive_questions
├── id (PK, SERIAL)
├── incentive_id (FK → parent_incentives.incentive_id, NOT NULL)
├── question_id (FK → questions.question_id, NOT NULL)
├── is_completed (BOOLEAN, DEFAULT false, NOT NULL)
├── completed_at (TIMESTAMPTZ, NULL)
├── order_index (INTEGER, DEFAULT 0, display order within incentive)
│
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── UNIQUE(incentive_id, question_id)
└── INDEX(incentive_id)
```
*Links specific questions to incentives for question-based targets*

---

### PARENT ASSIGNMENTS (Practice Sets)

#### 21. Parent Assignment Sets
```
parent_assignment_sets
├── set_id (PK, SERIAL)
├── guardian_id (FK → student_guardians.id, NOT NULL, must be role='primary')
├── paper_id (FK → papers.paper_id, NOT NULL)
├── set_name (VARCHAR(200), NOT NULL, e.g., 'Weekend Practice', 'Before Exam Review')
├── assigned_at (TIMESTAMPTZ, DEFAULT NOW())
├── due_date (TIMESTAMPTZ, NULL)
├── notes (TEXT, NULL, e.g., 'Focus on these before Monday!')
│
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── INDEX(guardian_id)
└── CHECK: due_date IS NULL OR due_date > assigned_at
```
*Only primary guardians can create assignments (enforced by trigger)*

#### 21a. Parent Assignment Questions
```
parent_assignment_questions
├── id (PK, SERIAL)
├── set_id (FK → parent_assignment_sets.set_id, NOT NULL)
├── question_id (FK → questions.question_id, NOT NULL)
├── order_index (INTEGER, DEFAULT 0, display order)
│
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── UNIQUE(set_id, question_id)
└── INDEX(set_id)
```

#### 21b. Parent Assignment Children (Target: One or Multiple Kids)
```
parent_assignment_children
├── id (PK, SERIAL)
├── set_id (FK → parent_assignment_sets.set_id, NOT NULL)
├── student_id (FK → students.student_id, NOT NULL)
├── status (ENUM: pending, in_progress, completed, NOT NULL, DEFAULT 'pending')
├── completed_at (TIMESTAMPTZ, NULL)
├── progress_pct (FLOAT, DEFAULT 0)
│
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── UNIQUE(set_id, student_id)
└── INDEX(set_id)
└── CHECK: progress_pct BETWEEN 0 AND 100
└── CHECK: (status = 'completed') = (completed_at IS NOT NULL)
```
*Parent can assign same set to multiple children (twins, siblings)*

**Parent Assignment Examples:**
```
Scenario 1: Same practice for twins
├── Set: "Weekend Physics Practice"
├── Questions: Q1, Q2, Q3, Q4, Q5
├── Children: Emma, Ethan (twins)
└── Both see the same questions

Scenario 2: Different practice per child
├── Set A: "Emma's Weak Topics"
│   └── Child: Emma only
├── Set B: "Ethan's Review"
│   └── Child: Ethan only
└── Each child sees their own set
```

**Difference: Assignments vs Incentives**
| Feature | Parent Assignments | Parent Incentives |
|---------|-------------------|-------------------|
| Purpose | "Do these questions" | "Complete goal → Get reward" |
| Reward | None | 🚲 Bike, 🍕 Pizza, 💰 Money |
| Target | Specific questions | Coverage/streak/cluster goal |
| Motivation | Practice | Gamification |

---

### ML/RECOMMENDATION SUPPORT

#### 22. Student State Vectors (Cached for Performance, Per Paper Type)
```
student_state_vectors
├── id (PK, SERIAL)
├── student_id (FK → students.student_id)
├── paper_type_id (FK → subject_paper_types.paper_type_id)
├── clustering_version (VARCHAR, which version of clusters this is based on)
├── n_clusters (INTEGER, matches paper type's cluster count)
├── mastery_vector (FLOAT[], per-cluster mastery scores)
├── velocity_vector (FLOAT[], per-cluster learning velocity)
├── exposure_vector (FLOAT[], per-cluster exposure counts)
├── last_state_vector (FLOAT[], latest combined state for recommendations)
├── objective (ENUM: coverage, efficiency, success_rate, balanced)
├── total_attempts (INTEGER)
├── last_updated (TIMESTAMP)
├── created_at (TIMESTAMP)
└── UNIQUE(student_id, paper_type_id, clustering_version)
```
*Cached vectors from vector_encoder.py - per paper TYPE to match transition matrix dimensions*
*Student progress tracked across ALL papers of same type (e.g., all A-Level Physics P1 papers)*
*When clustering is updated, old state vectors remain; new ones created with new version*

---

#### 23. Transition Matrices (Pre-computed, Per Paper Type)
```
transition_matrices
├── id (PK, SERIAL)
├── paper_type_id (FK → subject_paper_types.paper_type_id, NOT NULL)
├── clustering_version (VARCHAR(20), NOT NULL, matches subject_paper_types.clustering_version)
├── n_clusters (INTEGER, NOT NULL, number of clusters for this paper type)
├── matrix_data (FLOAT[][], NOT NULL, n_clusters x n_clusters transition probabilities)
├── alpha (FLOAT, NULL, self-transition weight used in computation)
├── computed_at (TIMESTAMPTZ, DEFAULT NOW())
├── questions_count (INTEGER, NOT NULL, number of questions used to compute)
│
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── UNIQUE(paper_type_id, clustering_version)
└── CHECK: n_clusters > 0
└── CHECK: questions_count > 0
└── CHECK: alpha IS NULL OR (alpha BETWEEN 0 AND 1)
└── INDEX(paper_type_id)
```
*Pre-computed from transition_matrix.py - each paper TYPE has its own transition patterns*
*Shared across all papers of same type (Cambridge P1 + Khan Academy P1 = same matrix)*

**Why Per Paper Type (not individual paper):**
- All P1 questions test same topics → same learning pathways
- P1 (MCQ) has different pathways than P2 (Structured)
- Questions from different sources enrich the same clustering
- Enables cross-source recommendations

**Update Workflow:**
```
When A-Level Physics P1 questions are updated (from any source):
1. Calculate new embeddings → question_embeddings (clustering_version='v2.0')
2. Calculate new clusters → clusters (clustering_version='v2.0')
3. Calculate new transition matrix → transition_matrices (clustering_version='v2.0')
4. Update subject_paper_types → clustering_version = 'v2.0'
5. New students use v2.0 automatically
6. Existing students: recompute state vectors with v2.0 on next activity
```

---

#### 24. Student Dashboard Analytics (Both Views)
```
student_dashboard_analytics
├── id (PK, SERIAL)
├── student_id (FK → students.student_id, NOT NULL)
├── paper_type_id (FK → subject_paper_types.paper_type_id, NOT NULL)
│
│   ══════════════════════════════════════════════════════════
│   RELATIVE VIEW (Quick Dashboard - shown to Students & Parents)
│   ══════════════════════════════════════════════════════════
├── percentile_rank (FLOAT, NULL, 0-100, "Top 25%" = 75.0)
├── practice_vs_average (FLOAT, NULL, 1.4 = "40% more than peers")
├── topics_strong (INTEGER, NULL, count of mastered topics)
├── topics_total (INTEGER, NULL, total topics in paper)
├── topics_weak_labels (TEXT[], NULL, human-readable, e.g., ['Waves', 'Electricity'])
├── trend (ENUM: improving, stable, declining, NULL)
├── trend_description (VARCHAR(200), NULL, e.g., "Getting better each week!")
├── current_streak_days (INTEGER, DEFAULT 0)
├── weekly_practice_days (INTEGER, DEFAULT 0)
├── weekly_questions_completed (INTEGER, DEFAULT 0)
├── weekly_practice_minutes (INTEGER, DEFAULT 0)
├── has_active_incentive (BOOLEAN, DEFAULT false)
├── incentive_progress_pct (FLOAT, NULL, 0-100)
│
│   ══════════════════════════════════════════════════════════
│   RAW VIEW (Study Mode - shown to Students ONLY, not parents)
│   ══════════════════════════════════════════════════════════
├── weak_cluster_indices (INTEGER[], NULL, clusters to focus on)
├── recent_wrong_question_ids (INTEGER[], NULL, last 10 wrong answers)
├── questions_to_review (INTEGER[], NULL, recommended for review)
├── mastery_by_cluster (FLOAT[], NULL, per-cluster mastery scores)
├── total_correct (INTEGER, DEFAULT 0)
├── total_incorrect (INTEGER, DEFAULT 0)
├── total_skipped (INTEGER, DEFAULT 0)
├── avg_time_per_question (FLOAT, NULL, seconds)
├── best_cluster_index (INTEGER, NULL, strongest topic)
├── worst_cluster_index (INTEGER, NULL, weakest topic)
│
│   -- METADATA --
├── peer_comparison_group (VARCHAR(50), DEFAULT 'same_school', e.g., 'same_school', 'same_year')
├── last_computed (TIMESTAMPTZ)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
│
│   -- CONSTRAINTS --
└── UNIQUE(student_id, paper_type_id, peer_comparison_group)
└── CHECK: percentile_rank IS NULL OR (percentile_rank BETWEEN 0 AND 100)
└── CHECK: incentive_progress_pct IS NULL OR (incentive_progress_pct BETWEEN 0 AND 100)
└── CHECK: topics_strong IS NULL OR topics_total IS NULL OR topics_strong <= topics_total
└── CHECK: current_streak_days >= 0
└── CHECK: weekly_practice_days BETWEEN 0 AND 7
└── CHECK: total_correct >= 0 AND total_incorrect >= 0 AND total_skipped >= 0
│
└── INDEX(student_id, paper_type_id)
```
*Cached analytics - Students see both views, Parents see relative only*
*Analytics per paper TYPE since progress is tracked across all papers of same type*

**Student Dashboard (Relative View):**
```
Physics P1 - Top 25% 📊
├── Trend: ↗️ Improving
├── Strong in: 6/10 topics
├── Needs practice: Waves, Electricity
├── This week: 4 days active, 23 questions
├── Streak: 🔥 12 days
└── Goal progress: 60% complete 🎯
```

**Student Study Mode (Raw View):**
```
Physics P1 - Study Plan 📚
├── Your mastery: Mechanics 85%, Waves 42%, Electricity 38%
├── Review these questions: Q23, Q41, Q55, Q67
├── Total: 147 correct, 53 incorrect, 12 skipped
├── Avg time: 45 sec/question
├── Strongest: Cluster 2 (Mechanics)
└── Focus on: Cluster 7 (Electricity) - 38% mastery
```

---

### ADMIN & SYSTEM

#### 25. System Admins
```
system_admins
├── admin_id (PK, FK → users.user_id, UUID)
├── name (VARCHAR(100), NOT NULL)
├── access_level (ENUM: super, standard, NOT NULL, DEFAULT 'standard')
│   -- super: Full system access, can create other admins
│   -- standard: Operational access, limited admin creation
│
├── permissions (JSONB, NULL, fine-grained permission overrides)
│   -- Example: {"can_delete_users": true, "can_export_data": false}
│
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── CHECK: access_level IN ('super', 'standard')
```
*System admins have global access across all schools*

---

#### 26. Student-Teacher Relations (Managed by Admin)
```
student_teacher_relations
├── id (PK, SERIAL)
├── student_id (FK → students.student_id, NOT NULL)
├── teacher_id (FK → teachers.teacher_id, NOT NULL)
├── subject_id (FK → subjects.subject_id, NOT NULL)
│
├── assigned_by (FK → users.user_id, NULL, admin who created)
├── academic_year (VARCHAR(20), NOT NULL, e.g., '2024-2025')
│
├── relationship_type (ENUM: primary, secondary, tutor, NULL, DEFAULT 'primary')
│   -- primary: Main subject teacher
│   -- secondary: Assistant/co-teacher
│   -- tutor: One-on-one tutoring relationship
│
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── updated_at (TIMESTAMPTZ, DEFAULT NOW())
│
└── UNIQUE(student_id, teacher_id, subject_id, academic_year)
└── INDEX(teacher_id, academic_year)
└── INDEX(student_id, is_active)
```
*Many-to-many relationship linking students to their teachers per subject*
*Enables teacher to view student progress for specific subjects*

---

## E-R DIAGRAM RELATIONSHIPS

### COMPLETE SYSTEM OVERVIEW

```
╔═══════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                    AUTHENTICATION & SECURITY LAYER                                  ║
╠═══════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                     ║
║   ┌─────────────────────────────────────────────────────────────────────────────────────────────┐  ║
║   │                                         users                                                │  ║
║   │   (user_id, email, password_hash, role, is_active, email_verified, display_name)            │  ║
║   └─────────────────────────────────────────────┬───────────────────────────────────────────────┘  ║
║                                                 │                                                   ║
║           ┌──────────────┬──────────────┬───────┼───────┬──────────────┬──────────────┐            ║
║           │              │              │       │       │              │              │            ║
║           ▼              ▼              ▼       ▼       ▼              ▼              ▼            ║
║   ┌──────────────┐ ┌───────────┐ ┌──────────┐ ┌───────────────┐ ┌──────────────┐ ┌─────────────┐   ║
║   │user_sessions │ │email_     │ │password_ │ │ api_keys      │ │notifications │ │consent_     │   ║
║   │              │ │verifi-    │ │resets    │ │               │ │              │ │records      │   ║
║   │(session_id,  │ │cations    │ │          │ │(key_id,       │ │(user_id,     │ │             │   ║
║   │refresh_token,│ │           │ │(token,   │ │scopes,        │ │type, title,  │ │(consent_    │   ║
║   │device_info,  │ │(token,    │ │expires,  │ │expires_at)    │ │is_read)      │ │type,        │   ║
║   │expires_at)   │ │verified)  │ │used_at)  │ │               │ │              │ │version)     │   ║
║   └──────────────┘ └───────────┘ └──────────┘ └───────────────┘ └──────────────┘ └─────────────┘   ║
║                                                 │                                                   ║
║           ┌─────────────────────────────────────┼─────────────────────────────────────┐            ║
║           ▼                                     ▼                                     ▼            ║
║   ┌───────────────────┐              ┌──────────────────────┐              ┌──────────────────┐    ║
║   │ notification_     │              │ data_deletion_       │              │ data_export_     │    ║
║   │ preferences       │              │ requests             │              │ requests         │    ║
║   └───────────────────┘              └──────────────────────┘              └──────────────────┘    ║
║                                                                                                     ║
║                                        ┌──────────────────┐                                         ║
║                                        │    audit_log     │ ◄─── Tracks all changes               ║
║                                        │(table, action,   │                                         ║
║                                        │old/new values)   │                                         ║
║                                        └──────────────────┘                                         ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════╝
                                                 │
                     ┌───────────────────────────┼───────────────────────────┐
                     │                           │                           │
                     ▼                           ▼                           ▼
╔════════════════════════════════╗  ╔════════════════════════════════╗  ╔════════════════════════════╗
║         USER PROFILES          ║  ║      GUARDIAN/PARENT FLOW      ║  ║     TEACHER/ADMIN FLOW     ║
╠════════════════════════════════╣  ╠════════════════════════════════╣  ╠════════════════════════════╣
║                                ║  ║                                ║  ║                            ║
║  ┌──────────────────────────┐  ║  ║  ┌──────────────────────────┐  ║  ║  ┌────────────────────┐    ║
║  │        students          │  ║  ║  │    student_guardians     │  ║  ║  │      teachers      │    ║
║  │                          │  ║  ║  │                          │  ║  ║  │                    │    ║
║  │  (student_id → user_id)  │  ║  ║  │  (id, student_id,        │  ║  ║  │  (teacher_id →     │    ║
║  │  (school_id → schools)   │  ║  ║  │   user_id, role:         │  ║  ║  │   user_id)         │    ║
║  │  (department_id)         │  ║  ║  │   primary/secondary,     │  ║  ║  │                    │    ║
║  │  (section_id)            │  ║  ║  │   relationship,          │  ║  ║  └─────────┬──────────┘    ║
║  │  (stream_id)             │  ║  ║  │   education_level_id)    │  ║  ║            │              ║
║  │                          │  ║  ║  │                          │  ║  ║            ▼              ║
║  └────────────┬─────────────┘  ║  ║  └──────────┬───────────────┘  ║  ║  ┌────────────────────┐    ║
║               │                ║  ║             │                  ║  ║  │teacher_section_    │    ║
║               │                ║  ║    ┌────────┴────────┐         ║  ║  │assignments         │    ║
║               │                ║  ║    │                 │         ║  ║  │(section, subject,  │    ║
║               │                ║  ║    ▼                 ▼         ║  ║  │ school, role)      │    ║
║               │                ║  ║  ┌─────────────┐ ┌──────────┐  ║  ║  └─────────┬──────────┘    ║
║               │                ║  ║  │parent_      │ │parent_   │  ║  ║            │              ║
║               │                ║  ║  │incentives   │ │assignment│  ║  ║            ▼              ║
║               │                ║  ║  │(PRIMARY     │ │_sets     │  ║  ║  ┌────────────────────┐    ║
║               │                ║  ║  │ ONLY)       │ │          │  ║  ║  │teacher_assignment_ │    ║
║               │                ║  ║  │             │ │          │  ║  ║  │sets                │    ║
║               │                ║  ║  │reward_      │ └────┬─────┘  ║  ║  │(set_name, due_date)│    ║
║               │                ║  ║  │category,    │      │        ║  ║  └─────────┬──────────┘    ║
║               │                ║  ║  │target_type  │      │        ║  ║            │              ║
║               │                ║  ║  └──────┬──────┘      │        ║  ║     ┌──────┴──────┐       ║
║               │                ║  ║         │             │        ║  ║     │             │       ║
║               │                ║  ║         ▼             ▼        ║  ║     ▼             ▼       ║
║               │                ║  ║  ┌─────────────┐ ┌──────────┐  ║  ║ ┌──────────┐ ┌─────────┐  ║
║               │                ║  ║  │incentive_   │ │parent_   │  ║  ║ │assignment│ │assign-  │  ║
║               │                ║  ║  │questions    │ │assignment│  ║  ║ │_set_     │ │ment_set_│  ║
║               │                ║  ║  │             │ │_questions│  ║  ║ │questions │ │students │  ║
║               │                ║  ║  └─────────────┘ └──────────┘  ║  ║ └──────────┘ └─────────┘  ║
║               │                ║  ║                      │         ║  ║                            ║
║               │                ║  ║                      ▼         ║  ║  ┌────────────────────┐    ║
║               │                ║  ║              ┌────────────┐    ║  ║  │teacher_class_      │    ║
║               │                ║  ║              │parent_     │    ║  ║  │analytics           │    ║
║               │                ║  ║              │assignment_ │    ║  ║  │(cached dashboard)  │    ║
║               │                ║  ║              │children    │    ║  ║  └────────────────────┘    ║
║               │                ║  ║              └────────────┘    ║  ║                            ║
║               │                ║  ║                                ║  ║  ┌────────────────────┐    ║
║               │                ║  ║                                ║  ║  │ school_admins      │    ║
║               │                ║  ║                                ║  ║  │ (admin_id,         │    ║
║               │                ║  ║                                ║  ║  │  school_id)        │    ║
║               │                ║  ║                                ║  ║  └────────────────────┘    ║
║               │                ║  ║                                ║  ║                            ║
║               │                ║  ║                                ║  ║  ┌────────────────────┐    ║
║               │                ║  ║                                ║  ║  │ system_admins      │    ║
║               │                ║  ║                                ║  ║  │ (access_level)     │    ║
║               │                ║  ║                                ║  ║  └────────────────────┘    ║
╚════════════════════════════════╝  ╚════════════════════════════════╝  ╚════════════════════════════╝
               │                                    │                                │
               │                                    │                                │
               └────────────────────────────────────┼────────────────────────────────┘
                                                    │
                                                    ▼
╔═══════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                    STUDENT PROGRESS & LEARNING                                      ║
╠═══════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                     ║
║   ┌───────────────────────────────────────────────────────────────────────────────────────────┐    ║
║   │                         student_paper_type_enrollments                                     │    ║
║   │   (student_id, paper_type_id, objective: coverage/efficiency/balanced, is_active)         │    ║
║   └─────────────────────────────────────────────┬─────────────────────────────────────────────┘    ║
║                                                 │                                                   ║
║                          ┌──────────────────────┼──────────────────────┐                            ║
║                          ▼                      ▼                      ▼                            ║
║   ┌──────────────────────────────┐  ┌──────────────────────────────┐  ┌──────────────────────────┐  ║
║   │   student_question_history   │  │    student_state_vectors     │  │student_dashboard_        │  ║
║   │                              │  │                              │  │analytics                 │  ║
║   │   (enrollment_id,            │  │   (mastery_vector,           │  │                          │  ║
║   │    question_id,              │  │    velocity_vector,          │  │   (percentile_rank,      │  ║
║   │    status: correct/incorrect │  │    exposure_vector,          │  │    trend: improving/     │  ║
║   │           /skipped/partial,  │  │    clustering_version)       │  │          stable/         │  ║
║   │    marks_obtained,           │  │                              │  │          declining,      │  ║
║   │    time_spent_sec,           │  │   [Cached ML State]          │  │    current_streak_days,  │  ║
║   │    confidence_level,         │  │                              │  │    topics_strong/weak)   │  ║
║   │    teacher_assignment_id,    │  │                              │  │                          │  ║
║   │    parent_assignment_id)     │  │                              │  │   [Cached Dashboard]     │  ║
║   │                              │  │                              │  │                          │  ║
║   │   [PARTITIONED BY MONTH]     │  │                              │  │                          │  ║
║   └───────────────┬──────────────┘  └──────────────────────────────┘  └──────────────────────────┘  ║
║                   │                                                                                  ║
║                   ▼                                                                                  ║
║   ┌──────────────────────────────┐                                                                  ║
║   │     student_submissions      │                                                                  ║
║   │                              │                                                                  ║
║   │   (submission_type: mcq/     │                                                                  ║
║   │         text/image/mixed,    │                                                                  ║
║   │    selected_option_indices,  │  ─────────────────────────────────────────────────────────────► ║
║   │    text_answer,              │                  GRADED AGAINST                                  ║
║   │    s3_key [for images],      │                                                                  ║
║   │    transcription_confidence) │                                                                  ║
║   │                              │                                                                  ║
║   │   [PARTITIONED BY MONTH]     │                                                                  ║
║   └──────────────────────────────┘                                                                  ║
║                                                                                                     ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════╝
                                                    │
                                                    │
                                                    ▼
╔═══════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                    ACADEMIC STRUCTURE & CONTENT                                     ║
╠═══════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                     ║
║   ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────────────────────────────┐  ║
║   │  class_levels   │──────►│    subjects     │──────►│        subject_paper_types              │  ║
║   │                 │       │                 │       │                                         │  ║
║   │ (A-Level,       │       │ (Physics,       │       │  (paper_type: P1/P2/P3,                 │  ║
║   │  O-Level,       │       │  Chemistry,     │       │   n_clusters, clustering_version,       │  ║
║   │  IGCSE, IB)     │       │  Biology,       │       │   is_mcq, mcq_option_count/format,      │  ║
║   │                 │       │  code: 9702)    │       │   default_total_marks)                  │  ║
║   └─────────────────┘       └─────────────────┘       └───────────────────┬─────────────────────┘  ║
║                                                                           │                         ║
║                                                       ┌───────────────────┴───────────────────┐    ║
║                                                       ▼                                       ▼    ║
║                                          ┌────────────────────────┐           ┌────────────────────┐║
║                                          │        papers          │           │transition_matrices │║
║                                          │                        │           │                    │║
║                                          │  (paper_name,          │           │  (matrix_data,     │║
║                                          │   exam_year/session,   │           │   n_clusters,      │║
║                                          │   paper_source_type:   │           │   clustering_      │║
║                                          │     past_paper/mock/   │           │   version)         │║
║                                          │     practice/custom,   │           │                    │║
║                                          │   source_organization, │           │  [ML Transitions]  │║
║                                          │   is_official)         │           │                    │║
║                                          └───────────┬────────────┘           └────────────────────┘║
║                                                      │                                              ║
║                                                      ▼                                              ║
║                                          ┌────────────────────────┐                                 ║
║                                          │       questions        │                                 ║
║                                          │                        │                                 ║
║                                          │  (question_number,     │                                 ║
║                                          │   question_text,       │                                 ║
║                                          │   marks)               │                                 ║
║                                          └───────────┬────────────┘                                 ║
║                                                      │                                              ║
║                          ┌───────────────────────────┼───────────────────────────┐                  ║
║                          ▼                           ▼                           ▼                  ║
║           ┌────────────────────────┐    ┌────────────────────────┐    ┌────────────────────────┐    ║
║           │    question_images     │    │     mark_schemes       │    │  question_embeddings   │    ║
║           │                        │    │                        │    │                        │    ║
║           │  (s3_key,              │    │  (mark_scheme_text,    │    │  (openai_embedding     │    ║
║           │   image_type:          │    │   mcq_correct_indices, │    │      VECTOR(1536),     │    ║
║           │     question/diagram/  │    │   version)             │    │   umap_embedding,      │    ║
║           │     mark_scheme,       │    │                        │    │   soft_cluster [FLOAT[]│    ║
║           │   display_order)       │    │  [Grading Criteria]    │    │   embedding_model)     │    ║
║           │                        │    │                        │    │                        │    ║
║           │  [S3 Storage]          │    │                        │    │  [ML Vectors]          │    ║
║           └────────────────────────┘    └────────────────────────┘    └───────────┬────────────┘    ║
║                                                                                   │                 ║
║                                                                                   ▼                 ║
║                                                                      ┌────────────────────────┐    ║
║                                                                      │       clusters         │    ║
║                                                                      │                        │    ║
║                                                                      │  (cluster_index,       │    ║
║                                                                      │   label: 'Mechanics',  │    ║
║                                                                      │   description,         │    ║
║                                                                      │   representative_      │    ║
║                                                                      │   keywords)            │    ║
║                                                                      │                        │    ║
║                                                                      │  [Topic Labels]        │    ║
║                                                                      └────────────────────────┘    ║
║                                                                                                     ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════╝


╔═══════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                    LOOKUP & REFERENCE TABLES                                        ║
╠═══════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                     ║
║   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐            ║
║   │education_levels │   │   departments   │   │    sections     │   │    streams      │            ║
║   │                 │   │                 │   │                 │   │                 │            ║
║   │ high_school     │   │ (school_id,     │   │ (school_id,     │   │ (Science,       │            ║
║   │ bachelors       │   │  name, code)    │   │  name,          │   │  Commerce,      │            ║
║   │ masters         │   │                 │   │  academic_year, │   │  Arts)          │            ║
║   │ doctorate       │   │                 │   │  capacity)      │   │                 │            ║
║   └────────┬────────┘   └────────┬────────┘   └────────┬────────┘   └────────┬────────┘            ║
║            │                     │                     │                     │                      ║
║            └─────────────────────┴─────────────────────┴─────────────────────┘                      ║
║                                            │                                                        ║
║                         Referenced by: students, student_guardians, teachers                        ║
║                                                                                                     ║
║   ┌─────────────────┐   ┌─────────────────┐                                                        ║
║   │  teacher_roles  │   │    schools      │                                                        ║
║   │                 │   │                 │                                                        ║
║   │ lecturer        │   │ (name, address, │                                                        ║
║   │ lab_instructor  │   │  phone, email)  │                                                        ║
║   │ tutor           │   │                 │                                                        ║
║   │ teaching_asst   │   │                 │                                                        ║
║   └─────────────────┘   └─────────────────┘                                                        ║
║                                                                                                     ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════╝


╔═══════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                    ANALYTICS & CACHING LAYER                                        ║
╠═══════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                     ║
║   ┌────────────────────────────┐   ┌────────────────────────────┐   ┌────────────────────────────┐ ║
║   │  daily_student_activity    │   │    weekly_leaderboard      │   │ cluster_performance_cache  │ ║
║   │                            │   │                            │   │                            │ ║
║   │  (student_id, paper_type,  │   │  (paper_type_id, school_id,│   │  (paper_type_id, cluster,  │ ║
║   │   activity_date,           │   │   week_start, rankings     │   │   avg_accuracy,            │ ║
║   │   questions_attempted,     │   │   [JSONB])                 │   │   students_mastered,       │ ║
║   │   questions_correct,       │   │                            │   │   students_struggling)     │ ║
║   │   total_time_sec)          │   │                            │   │                            │ ║
║   │                            │   │  [Weekly Rankings]         │   │  [Topic Analysis]          │ ║
║   │  [Nightly Aggregates]      │   │                            │   │                            │ ║
║   └────────────────────────────┘   └────────────────────────────┘   └────────────────────────────┘ ║
║                                                                                                     ║
║   ════════════════════════════════════════════════════════════════════════════════════════════════  ║
║                                      MATERIALIZED VIEWS                                              ║
║   ════════════════════════════════════════════════════════════════════════════════════════════════  ║
║                                                                                                     ║
║   ┌────────────────────────────┐   ┌────────────────────────────┐   ┌────────────────────────────┐ ║
║   │  mv_student_current_state  │   │mv_teacher_section_overview │   │mv_parent_children_overview │ ║
║   │                            │   │                            │   │                            │ ║
║   │  (student_id, paper_type,  │   │  (teacher_id, section,     │   │  (parent_user_id,          │ ║
║   │   mastery_vector,          │   │   student_count,           │   │   child_name,              │ ║
║   │   percentile_rank,         │   │   avg_percentile,          │   │   percentile_rank,         │ ║
║   │   streak, trend)           │   │   improving_count,         │   │   trend, streak,           │ ║
║   │                            │   │   at_risk_count)           │   │   incentive_progress)      │ ║
║   │  [Student Dashboard]       │   │                            │   │                            │ ║
║   │                            │   │  [Teacher Dashboard]       │   │  [Parent Dashboard]        │ ║
║   └────────────────────────────┘   └────────────────────────────┘   └────────────────────────────┘ ║
║                                                                                                     ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

### RELATIONSHIP SUMMARY DIAGRAM

```
                                   ┌─────────────────────────────────────┐
                                   │              users                  │
                                   │         (auth central)              │
                                   └───────────────┬─────────────────────┘
                                                   │
        ┌──────────────────┬───────────────┬───────┴───────┬───────────────┬──────────────────┐
        │                  │               │               │               │                  │
        ▼                  ▼               ▼               ▼               ▼                  ▼
┌───────────────┐  ┌───────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────┐
│   students    │  │   teachers    │ │school_admins│ │system_admins│ │student_     │ │ Security &   │
│               │  │               │ │             │ │             │ │guardians    │ │ Compliance   │
└───────┬───────┘  └───────┬───────┘ └─────────────┘ └─────────────┘ └──────┬──────┘ │              │
        │                  │                                                │        │ - sessions   │
        │                  │                                                │        │ - audit_log  │
        │                  ▼                                                │        │ - api_keys   │
        │          ┌───────────────────┐                                    │        │ - GDPR       │
        │          │teacher_section_   │                                    │        └──────────────┘
        │          │assignments        │                                    │
        │          └───────┬───────────┘                                    │
        │                  │                                                │
        │                  ▼                                                │
        │          ┌───────────────────┐                ┌───────────────────┤
        │          │teacher_assignment_│                │                   │
        │          │sets               │                ▼                   ▼
        │          └───────────────────┘        ┌───────────────┐   ┌───────────────┐
        │                                       │parent_        │   │parent_        │
        │                                       │incentives     │   │assignment_sets│
        │                                       │(PRIMARY ONLY) │   │(PRIMARY ONLY) │
        │                                       └───────────────┘   └───────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                  ENROLLMENT & LEARNING PATH                                      │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│   students ──► student_paper_type_enrollments ──► student_question_history ──► submissions      │
│                         │                                  │                                     │
│                         │                                  ▼                                     │
│                         │                         student_state_vectors (ML cache)               │
│                         │                                  │                                     │
│                         ▼                                  ▼                                     │
│                  subject_paper_types            student_dashboard_analytics (cached)             │
│                         │                                                                        │
│                         ▼                                                                        │
│                      papers ──► questions ──┬── question_embeddings ──► clusters                 │
│                                             ├── question_images (S3)                             │
│                                             └── mark_schemes                                     │
│                                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘


╔═════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                      KEY: RELATIONSHIP TYPES                                     ║
╠═════════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                                  ║
║   ────►  : Foreign Key (1:N or 1:1)                                                              ║
║   ◄────► : Many-to-Many (via junction table)                                                     ║
║   ═════  : Inheritance (shares user_id as PK)                                                    ║
║                                                                                                  ║
║   ┌──────┐                                                                                       ║
║   │ BOLD │ : Core entity                                                                         ║
║   └──────┘                                                                                       ║
║                                                                                                  ║
║   (dashed) : Optional/nullable FK                                                                ║
║                                                                                                  ║
╚═════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

### TABLE COUNT SUMMARY

| Category | Count | Tables |
|----------|-------|--------|
| **Auth & Profiles** | 6 | `users`, `students`, `teachers`, `school_admins`, `system_admins`, `student_guardians` |
| **Organization** | 6 | `schools`, `education_levels`, `departments`, `sections`, `streams`, `teacher_roles` |
| **Academic Structure** | 7 | `class_levels`, `subjects`, `subject_paper_types`, `papers`, `questions`, `question_images`, `mark_schemes` |
| **ML & Embeddings** | 3 | `question_embeddings`, `clusters`, `transition_matrices` |
| **Student Progress** | 5 | `student_paper_type_enrollments`, `student_question_history`, `student_submissions`, `student_state_vectors`, `student_dashboard_analytics` |
| **Teacher Flow** | 5 | `teacher_section_assignments`, `teacher_assignment_sets`, `assignment_set_questions`, `assignment_set_students`, `teacher_class_analytics` |
| **Parent Flow** | 5 | `parent_incentives`, `incentive_questions`, `parent_assignment_sets`, `parent_assignment_questions`, `parent_assignment_children` |
| **Relations** | 1 | `student_teacher_relations` |
| **Security** | 5 | `user_sessions`, `email_verifications`, `password_resets`, `api_keys`, `audit_log` |
| **Notifications** | 2 | `notifications`, `notification_preferences` |
| **GDPR & Compliance** | 3 | `data_deletion_requests`, `data_export_requests`, `consent_records` |
| **Analytics Cache** | 3 | `daily_student_activity`, `weekly_leaderboard`, `cluster_performance_cache` |
| **System** | 1 | `schema_migrations` |
| **TOTAL** | **52** | *See Quick Reference table above for full details* |

### Access Control Summary

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            STUDENTS                                      │
│                                                                          │
│  ✓ BOTH relative AND raw progress (toggle between views)                │
│  ✓ Dashboard view (relative) - quick motivation & status                │
│  ✓ Study view (raw) - specific questions to review                      │
│  ✓ See their own full attempt history                                   │
│  ✓ Personalized question recommendations                                │
└─────────────────────────────────────────────────────────────────────────┘

**Student View Options:**
| View Mode | Use Case | Data Shown |
|-----------|----------|------------|
| **Dashboard** (Relative) | Quick motivation check | Percentile, streak, trend, incentive progress |
| **Study Mode** (Raw) | Focused practice session | Weak topics, questions to review, mastery % |
| **History** (Raw) | Review past attempts | All questions attempted, time spent, results |
| **Recommendations** (ML) | What to do next | AI-suggested questions based on objective |

┌─────────────────────────────────────────────────────────────────────────┐
│                    ALL PARENTS (Primary + Guardians)                     │
│                                                                          │
│  ✓ Relative progress (percentiles, trends, streaks, weak topics)        │
│  ✓ Plain-language insights ("Strong in 6/10 topics")                    │
│  ✓ Weekly summaries and engagement metrics                              │
│  ✗ NO raw data (cluster IDs, ML scores, specific questions)             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌───────────────────────────────────┐  ┌───────────────────────────────────┐
│        PRIMARY PARENT             │  │     SECONDARY GUARDIANS           │
│                                   │  │                                   │
│  ✓ Create/manage incentives       │  │  ✓ View progress (same as primary)│
│  ✓ Set learning objectives        │  │  ✓ See incentive status           │
│  ✓ Invite secondary guardians     │  │  ✗ Cannot create incentives       │
│  ✓ See own incentive details      │  │  ✗ Cannot see reward amounts      │
│  ✓ Receive all notifications      │  │  ✗ Cannot modify objectives       │
└───────────────────────────────────┘  └───────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           TEACHERS                                       │
│                                                                          │
│  ✓ BOTH relative AND raw progress (toggle between views)                │
│  ✓ Class-level overview (relative) - quick health check                 │
│  ✓ Student-level deep dive (raw) - specific question analysis           │
│  ✓ Cluster/topic performance breakdown                                  │
│  ✓ Assign specific questions to students                                │
│  ✓ Compare students within their sections                               │
└─────────────────────────────────────────────────────────────────────────┘
```

**Teacher View Options:**
| View Mode | Use Case | Data Shown |
|-----------|----------|------------|
| **Dashboard** (Relative) | Quick class overview | Percentiles, trends, at-risk students |
| **Student Detail** (Raw) | Investigate specific student | Question attempts, time spent, clusters |
| **Class Comparison** (Relative) | Compare sections | Average performance, top/bottom students |
| **Topic Analysis** (Raw) | Find common struggles | Which clusters class struggles with |

---

## KEY RELATIONSHIPS SUMMARY

| Relationship | Type | Description |
|--------------|------|-------------|
| Users → Students/Teachers/Admins | 1:1 | Authentication inheritance |
| Users → student_guardians (Parents) | 1:1 | Parents authenticate through users table |
| Users ↔ Students (as guardians) | N:M | Via student_guardians (unified table) |
| Guardians → Students | N:M | One user can be guardian for multiple students |
| Students → Guardians | 1:N | Each student has ONE primary + multiple secondary |
| Students → Schools | N:1 | Student belongs to one school |
| Subjects → Class Levels | N:1 | Subject belongs to one level (A-Level, IB, etc.) |
| Subject Paper Types → Subjects | N:1 | Paper type belongs to one subject |
| Papers → Subject Paper Types | N:1 | Paper instance belongs to one paper type |
| Questions → Papers | N:1 | Question belongs to one paper |
| Questions → Images | 1:N | Question can have multiple images (1-8+) |
| Questions → Mark Schemes | 1:1 | Each question has one mark scheme (separate table) |
| Questions → Embeddings | 1:1 | ML data for each question |
| Students ↔ Paper Types | N:M | Via student_paper_type_enrollments |
| Students → Question History | 1:N | All attempts by student |
| Question History → Submissions | 1:1 | Each attempt has one submission (mcq/text/image/mixed) |
| Teachers ↔ Students | N:M | Via student_teacher_relations |
| Teachers → Class Analytics | 1:N | Teacher can view analytics for multiple paper types |
| Primary Guardian → Incentives | 1:N | ONLY role='primary' can create incentives |
| Teachers → Assignment Sets | 1:N | Teacher creates assignment sets with questions |
| Parents → Assignment Sets | 1:N | Primary parent creates assignment sets for children |
| Assignment Sets → Question History | 1:N | Track which attempts were for assignments |
| Paper Types → Clusters | 1:N | All papers of same type share clustering |
| Paper Types → Transition Matrix | 1:1 | One matrix per paper type (shared across sources) |
| Paper Types → State Vectors | 1:N | Student progress vectors per paper type |

---

## INDEXES FOR PERFORMANCE

```sql
-- ═══════════════════════════════════════════════════════════════════════════
-- CORE QUERY INDEXES
-- ═══════════════════════════════════════════════════════════════════════════

-- Critical for recommendation queries
CREATE INDEX idx_history_enrollment_time ON student_question_history(enrollment_id, timestamp DESC);
CREATE INDEX idx_history_question ON student_question_history(question_id);

-- For assignment-specific queries
CREATE INDEX idx_history_teacher_assignment ON student_question_history(teacher_assignment_set_id) WHERE teacher_assignment_set_id IS NOT NULL;
CREATE INDEX idx_history_parent_assignment ON student_question_history(parent_assignment_set_id) WHERE parent_assignment_set_id IS NOT NULL;

-- For embedding similarity search (requires pgvector)
CREATE INDEX idx_embeddings_vector ON question_embeddings USING ivfflat (openai_embedding vector_cosine_ops);

-- For quick lookups
CREATE INDEX idx_questions_paper ON questions(paper_id);
CREATE INDEX idx_papers_paper_type ON papers(paper_type_id);
CREATE INDEX idx_enrollments_student ON student_paper_type_enrollments(student_id);
CREATE INDEX idx_enrollments_paper_type ON student_paper_type_enrollments(paper_type_id);
CREATE INDEX idx_incentives_student_status ON parent_incentives(student_id, status);

-- For submission lookups
CREATE INDEX idx_submissions_history ON student_submissions(history_id);

-- For MCQ array queries (e.g., "how many students picked option C?")
CREATE INDEX idx_submissions_mcq_options ON student_submissions USING GIN (selected_option_indices);

-- For mark scheme lookups
CREATE INDEX idx_mark_schemes_question ON mark_schemes(question_id);

-- For question images lookups (1-to-many relationship)
CREATE INDEX idx_question_images_question ON question_images(question_id);

-- ═══════════════════════════════════════════════════════════════════════════
-- ADDITIONAL PERFORMANCE INDEXES (NEW)
-- ═══════════════════════════════════════════════════════════════════════════

-- Student lookups by school (for school-based queries)
CREATE INDEX idx_students_school ON students(school_id);

-- Guardian lookups on login
CREATE INDEX idx_guardians_user ON student_guardians(user_id);

-- Primary guardian lookup (very common query)
CREATE INDEX idx_guardians_student_primary ON student_guardians(student_id) WHERE role = 'primary';

-- Paper filtering by year/session
CREATE INDEX idx_papers_year_session ON papers(exam_year, exam_session);

-- Paper filtering by source type
CREATE INDEX idx_papers_source ON papers(paper_source_type, is_official);

-- Active enrollments only (most queries filter by active)
CREATE INDEX idx_enrollments_active ON student_paper_type_enrollments(student_id) WHERE is_active = true;

-- Active teacher assignments
CREATE INDEX idx_teacher_assignments_active ON teacher_assignment_sets(teacher_id) WHERE is_active = true;

-- Active incentives
CREATE INDEX idx_incentives_active ON parent_incentives(student_id) WHERE status = 'active';

-- Session management (security)
CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at) WHERE revoked_at IS NULL;

-- Audit log queries
CREATE INDEX idx_audit_table_time ON audit_log(table_name, changed_at DESC);
CREATE INDEX idx_audit_user ON audit_log(changed_by, changed_at DESC);

-- Notifications (unread first)
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, created_at DESC) WHERE is_read = false;

-- Daily aggregates for analytics
CREATE INDEX idx_daily_activity_student ON daily_student_activity(student_id, activity_date DESC);
```

---

## NOTES FOR ML INTEGRATION

1. **vector_encoder.py compatibility**:
   - `student_question_history` matches expected format with `is_correct`, `is_skipped`, `time_spent_sec`, `confidence_level`, `device_type`
   - `question_embeddings.soft_cluster` is FLOAT[] matching numpy arrays

2. **transition_matrix.py compatibility**:
   - `transition_matrices` stores pre-computed matrices **per paper TYPE** (not per individual paper)
   - Each subject + paper_type combo (A-Level Physics P1) has its own transition patterns
   - ALL questions of same paper_type share clustering regardless of source
   - `clusters` table optional for human-readable cluster labels

3. **Recommendation flow**:
   - Student enrolls in paper TYPE → enrollment created with objective
   - Student attempts questions from ANY paper of that type → history recorded
   - ML system reads history → computes state vector → stores in student_state_vectors
   - Recommendation uses state vector + transition matrix → suggests next questions
   - Can filter recommendations by source (past_paper, practice, etc.)

4. **Student submissions (MCQ, text, image)**:
   - `student_submissions` stores actual answer content (MCQ selections, text, images, or mixed)
   - **MCQ submissions**: store `selected_option_indices` (0-based), display format derived from `subject_paper_types.mcq_option_format`
   - **Text/Image submissions**: Images stored in S3, only keys in database
   - AI transcription (GPT-4 Vision, OCR) converts handwritten work to searchable text
   - `transcription_confidence` helps identify submissions needing manual review
   - Enables future AI-assisted grading for structured questions (P2/P3)

5. **MCQ configuration (paper TYPE level)**:
   - MCQ format configured once per paper TYPE in `subject_paper_types`, not per individual paper
   - `subject_paper_types.is_mcq` determines if paper type uses MCQ submissions
   - `subject_paper_types.mcq_option_format` defines display format (A-D, 1-4, custom labels)
   - `subject_paper_types.mcq_option_count` defines how many options (4, 5, 6, etc.)
   - `subject_paper_types.mcq_multi_select` allows multiple correct answers
   - Query MCQ analytics: `WHERE selected_option_indices @> ARRAY[index]`

6. **Mark schemes (separate table)**:
   - `mark_schemes` table stores answer/grading criteria separately from questions
   - **MCQ grading**: `mcq_correct_indices` compared with `submission.selected_option_indices`
   - **Structured grading**: `mark_scheme_text` contains criteria for teacher/AI evaluation
   - Mark schemes can be versioned if exam board updates criteria
   - Questions and mark schemes can be imported from different source files

7. **Paper source filtering**:
   - `paper_source_type`: past_paper, practice, mock, custom
   - `source_organization`: Cambridge, IB, Edexcel, Khan Academy, School Name, etc.
   - `is_official`: true for official exam board papers
   - Students/teachers/parents can filter by source for targeted practice
   - Analytics can compare performance across official vs practice materials
   - **Clustering shared across sources** - can recommend Khan Academy question after Cambridge question

8. **subject_paper_types structure**:
   - Shared config per subject + paper_type (e.g., A-Level Physics P1)
   - Clustering at this level: ALL questions of same paper_type share clusters
   - Different class levels have different clustering (A-Level ≠ IB)
   - Different subjects have different clustering (Physics P1 ≠ Biology P1)
   - Individual papers reference paper_type_id for shared config

9. **Assignment tracking**:
   - `student_question_history` links attempts to assignments via optional FKs
   - `teacher_assignment_set_id` - links to teacher assignment (NULL if self-directed)
   - `parent_assignment_set_id` - links to parent assignment (NULL if self-directed)
   - Enables: "Show attempts for Assignment #5", "Compare assigned vs self-directed performance"
   - Teachers/parents can review assignment history and detailed progress

---

## LOOKUP TABLES (Normalization)

*These lookup tables ensure data consistency and enable easier maintenance*

#### L1. Education Levels
```
education_levels
├── level_id (PK, SERIAL)
├── name (VARCHAR, NOT NULL, UNIQUE)
├── display_order (INTEGER)
└── created_at (TIMESTAMP)
```
**Values:** `high_school`, `associate`, `bachelors`, `masters`, `doctorate`, `professional`, `other`

*Referenced by: student_guardians.education_level, teachers.education_level, school_admins.education_level*

---

#### L2. Departments (Per School)
```
departments
├── department_id (PK, SERIAL)
├── school_id (FK → schools.school_id)
├── name (VARCHAR, NOT NULL)
├── code (VARCHAR, NULL, e.g., 'SCI', 'ARTS')
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMP)
└── UNIQUE(school_id, name)
```

---

#### L3. Sections (Per School, Per Academic Year)
```
sections
├── section_id (PK, SERIAL)
├── school_id (FK → schools.school_id)
├── department_id (FK → departments.department_id, NULL)
├── name (VARCHAR, NOT NULL, e.g., '12A', '11B')
├── academic_year (VARCHAR, e.g., '2024-2025')
├── capacity (INTEGER, NULL)
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMP)
└── UNIQUE(school_id, name, academic_year)
```

---

#### L4. Streams (Academic Tracks)
```
streams
├── stream_id (PK, SERIAL)
├── school_id (FK → schools.school_id, NULL for global)
├── name (VARCHAR, NOT NULL, e.g., 'Science', 'Commerce', 'Arts')
├── description (TEXT)
├── created_at (TIMESTAMP)
└── UNIQUE(school_id, name)
```

---

#### L5. Teacher Roles
```
teacher_roles
├── role_id (PK, SERIAL)
├── name (VARCHAR, NOT NULL, UNIQUE)
├── description (TEXT)
├── created_at (TIMESTAMP)
```
**Values:** `lecturer`, `lab_instructor`, `tutor`, `teaching_assistant`, `head_of_department`

---

## SECURITY TABLES

*Critical tables for authentication, authorization, and audit compliance*

#### S1. User Sessions
```
user_sessions
├── session_id (PK, UUID, DEFAULT gen_random_uuid())
├── user_id (FK → users.user_id, NOT NULL)
├── refresh_token_hash (VARCHAR(64))
├── device_info (JSONB, e.g., {"browser": "Chrome", "os": "macOS", "device": "desktop"})
├── ip_address (INET)
├── user_agent (TEXT)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── expires_at (TIMESTAMPTZ, NOT NULL)
├── revoked_at (TIMESTAMPTZ, NULL)
├── last_activity (TIMESTAMPTZ, DEFAULT NOW())
└── INDEX(user_id)
└── INDEX(expires_at) WHERE revoked_at IS NULL
```
*Manages active login sessions; supports multi-device login*

**Session Management:**
```sql
-- Revoke all sessions for a user (logout everywhere)
UPDATE user_sessions SET revoked_at = NOW() WHERE user_id = $1;

-- Check if session is valid
SELECT * FROM user_sessions
WHERE session_id = $1
  AND revoked_at IS NULL
  AND expires_at > NOW();

-- Clean expired sessions (run daily)
DELETE FROM user_sessions WHERE expires_at < NOW() - INTERVAL '30 days';
```

---

#### S2. Email Verifications
```
email_verifications
├── id (PK, SERIAL)
├── user_id (FK → users.user_id)
├── email (VARCHAR, NOT NULL)
├── token_hash (VARCHAR(64), NOT NULL)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── expires_at (TIMESTAMPTZ, NOT NULL)
├── verified_at (TIMESTAMPTZ, NULL)
└── INDEX(user_id)
└── INDEX(token_hash)
```

---

#### S3. Password Resets
```
password_resets
├── id (PK, SERIAL)
├── user_id (FK → users.user_id)
├── token_hash (VARCHAR(64), NOT NULL)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── expires_at (TIMESTAMPTZ, NOT NULL)
├── used_at (TIMESTAMPTZ, NULL)
├── ip_address (INET)
└── INDEX(user_id)
└── INDEX(token_hash)
```

---

#### S4. API Keys (For System Integrations)
```
api_keys
├── key_id (PK, UUID, DEFAULT gen_random_uuid())
├── user_id (FK → users.user_id, NULL for system keys)
├── key_hash (VARCHAR(64), NOT NULL)
├── name (VARCHAR(100), NOT NULL, e.g., 'ML Service Key')
├── scopes (TEXT[], e.g., ['read:questions', 'write:embeddings'])
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── expires_at (TIMESTAMPTZ, NULL)
├── last_used_at (TIMESTAMPTZ)
├── is_active (BOOLEAN, DEFAULT true)
└── INDEX(key_hash) WHERE is_active = true
```

---

#### S5. Audit Log
```
audit_log
├── log_id (PK, BIGSERIAL)
├── table_name (VARCHAR(100), NOT NULL)
├── record_id (VARCHAR(100), NOT NULL)
├── action (VARCHAR(10), NOT NULL)  -- INSERT, UPDATE, DELETE
├── changed_by (UUID, FK → users.user_id, NULL for system)
├── changed_at (TIMESTAMPTZ, DEFAULT NOW())
├── old_values (JSONB, NULL for INSERT)
├── new_values (JSONB, NULL for DELETE)
├── ip_address (INET)
├── user_agent (TEXT)
└── INDEX(table_name, changed_at DESC)
└── INDEX(changed_by, changed_at DESC)
```
*Tracks WHO changed WHAT and WHEN for compliance and debugging*

**Audit Trigger Function:**
```sql
CREATE OR REPLACE FUNCTION audit_trigger_func()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_log (
        table_name, record_id, action,
        changed_by, old_values, new_values
    )
    VALUES (
        TG_TABLE_NAME,
        COALESCE(NEW.id::text, OLD.id::text,
                 NEW.user_id::text, OLD.user_id::text,
                 NEW.student_id::text, OLD.student_id::text),
        TG_OP,
        current_setting('app.current_user_id', true)::uuid,
        CASE WHEN TG_OP != 'INSERT' THEN row_to_json(OLD) END,
        CASE WHEN TG_OP != 'DELETE' THEN row_to_json(NEW) END
    );
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Apply to sensitive tables
CREATE TRIGGER audit_users
AFTER INSERT OR UPDATE OR DELETE ON users
FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

CREATE TRIGGER audit_parent_incentives
AFTER INSERT OR UPDATE OR DELETE ON parent_incentives
FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

CREATE TRIGGER audit_student_guardians
AFTER INSERT OR UPDATE OR DELETE ON student_guardians
FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

CREATE TRIGGER audit_password_changes
AFTER UPDATE ON users
FOR EACH ROW
WHEN (OLD.password_hash IS DISTINCT FROM NEW.password_hash)
EXECUTE FUNCTION audit_trigger_func();
```

---

## NOTIFICATION SYSTEM

#### N1. Notifications
```
notifications
├── notification_id (PK, UUID, DEFAULT gen_random_uuid())
├── user_id (FK → users.user_id, NOT NULL)
├── type (VARCHAR(50), NOT NULL)
├── title (VARCHAR(200), NOT NULL)
├── body (TEXT)
├── data (JSONB, additional context)
├── priority (ENUM: low, normal, high, urgent, DEFAULT normal)
├── is_read (BOOLEAN, DEFAULT false)
├── read_at (TIMESTAMPTZ, NULL)
├── created_at (TIMESTAMPTZ, DEFAULT NOW())
├── expires_at (TIMESTAMPTZ, NULL)
└── INDEX(user_id, created_at DESC) WHERE is_read = false
```

**Notification Types:**
| Type | Recipients | Trigger |
|------|------------|---------|
| `assignment_new` | Student | Teacher/parent creates assignment |
| `assignment_due` | Student | 24h before due date |
| `assignment_overdue` | Student, Teacher | Past due date |
| `incentive_progress` | Student, Parent | 25%, 50%, 75% milestones |
| `incentive_complete` | Student, Parent | Target achieved |
| `streak_milestone` | Student | 7, 14, 30, 60, 90 days |
| `streak_risk` | Student | Streak about to break (20h warning) |
| `weekly_summary` | Parent | Every Sunday |
| `child_declining` | Parent | Trend turns negative |
| `student_at_risk` | Teacher | Student falls below threshold |

---

#### N2. Notification Preferences
```
notification_preferences
├── id (PK, SERIAL)
├── user_id (FK → users.user_id, NOT NULL, UNIQUE)
├── email_enabled (BOOLEAN, DEFAULT true)
├── push_enabled (BOOLEAN, DEFAULT true)
├── sms_enabled (BOOLEAN, DEFAULT false)
├── quiet_hours_start (TIME, NULL, e.g., '22:00')
├── quiet_hours_end (TIME, NULL, e.g., '07:00')
├── weekly_digest (BOOLEAN, DEFAULT true)
├── disabled_types (TEXT[], types to suppress)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
```

---

## GDPR & DATA COMPLIANCE

#### G1. Data Deletion Requests
```
data_deletion_requests
├── request_id (PK, UUID, DEFAULT gen_random_uuid())
├── user_id (FK → users.user_id)
├── requested_at (TIMESTAMPTZ, DEFAULT NOW())
├── reason (TEXT)
├── status (ENUM: pending, processing, completed, rejected, DEFAULT pending)
├── processed_at (TIMESTAMPTZ, NULL)
├── processed_by (FK → users.user_id, NULL)
├── rejection_reason (TEXT, NULL)
├── completed_at (TIMESTAMPTZ, NULL)
└── INDEX(status) WHERE status = 'pending'
```

---

#### G2. Data Export Requests
```
data_export_requests
├── export_id (PK, UUID, DEFAULT gen_random_uuid())
├── user_id (FK → users.user_id)
├── requested_at (TIMESTAMPTZ, DEFAULT NOW())
├── status (ENUM: pending, processing, ready, expired, DEFAULT pending)
├── export_format (ENUM: json, csv, pdf, DEFAULT json)
├── s3_key (VARCHAR(500), NULL, path when ready)
├── download_url (VARCHAR(500), NULL, signed URL)
├── expires_at (TIMESTAMPTZ, NULL)
├── completed_at (TIMESTAMPTZ, NULL)
├── downloaded_at (TIMESTAMPTZ, NULL)
└── INDEX(user_id)
```

---

#### G3. Consent Records
```
consent_records
├── id (PK, SERIAL)
├── user_id (FK → users.user_id)
├── consent_type (ENUM: terms_of_service, privacy_policy, marketing, analytics)
├── version (VARCHAR, e.g., 'v1.2')
├── consented_at (TIMESTAMPTZ, DEFAULT NOW())
├── ip_address (INET)
├── revoked_at (TIMESTAMPTZ, NULL)
└── UNIQUE(user_id, consent_type, version)
```

---

## ANALYTICS OPTIMIZATION TABLES

*Pre-computed aggregates for dashboard performance*

#### A1. Daily Student Activity
```
daily_student_activity
├── id (PK, SERIAL)
├── student_id (FK → students.student_id)
├── paper_type_id (FK → subject_paper_types.paper_type_id)
├── activity_date (DATE, NOT NULL)
├── questions_attempted (INTEGER, DEFAULT 0)
├── questions_correct (INTEGER, DEFAULT 0)
├── questions_incorrect (INTEGER, DEFAULT 0)
├── questions_skipped (INTEGER, DEFAULT 0)
├── total_time_sec (INTEGER, DEFAULT 0)
├── clusters_practiced (INTEGER[], DEFAULT '{}')
├── sessions_count (INTEGER, DEFAULT 0)
├── created_at (TIMESTAMP)
├── updated_at (TIMESTAMP)
└── UNIQUE(student_id, paper_type_id, activity_date)
```
*Aggregated nightly from student_question_history*

---

#### A2. Weekly Leaderboard Cache
```
weekly_leaderboard
├── id (PK, SERIAL)
├── paper_type_id (FK → subject_paper_types.paper_type_id)
├── school_id (FK → schools.school_id, NULL for global)
├── section (VARCHAR, NULL for school-wide)
├── week_start (DATE, NOT NULL)
├── rankings (JSONB)
│   -- e.g., [{"student_id": "...", "rank": 1, "score": 95, "streak": 12, "improvement": 5}]
├── total_participants (INTEGER)
├── computed_at (TIMESTAMPTZ)
└── UNIQUE(paper_type_id, school_id, section, week_start)
```

---

#### A3. Cluster Performance Cache
```
cluster_performance_cache
├── id (PK, SERIAL)
├── paper_type_id (FK → subject_paper_types.paper_type_id)
├── clustering_version (VARCHAR)
├── school_id (FK → schools.school_id, NULL for global)
├── section (VARCHAR, NULL)
├── cluster_index (INTEGER)
├── avg_accuracy (FLOAT)
├── total_attempts (INTEGER)
├── students_mastered (INTEGER, >80% accuracy)
├── students_struggling (INTEGER, <40% accuracy)
├── common_mistakes (JSONB, question patterns)
├── computed_at (TIMESTAMPTZ)
└── UNIQUE(paper_type_id, clustering_version, school_id, section, cluster_index)
```

---

## CHECK CONSTRAINTS & VALIDATION

*All CHECK constraints and triggers for data integrity*

```sql
-- ═══════════════════════════════════════════════════════════════════════════
-- TABLE-LEVEL CHECK CONSTRAINTS
-- ═══════════════════════════════════════════════════════════════════════════

-- Users: Email format validation
ALTER TABLE users ADD CONSTRAINT chk_users_email_format
    CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$');

-- Users: Email must be verified for active accounts (optional, enforced at app level)
ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT false;
ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMPTZ;

-- Users: Display name for convenience
ALTER TABLE users ADD COLUMN display_name VARCHAR(100);

-- Students: Year must be positive
ALTER TABLE students ADD CONSTRAINT chk_students_year_positive
    CHECK (year > 0 AND year <= 13);

-- Student Question History: Confidence level range
ALTER TABLE student_question_history ADD CONSTRAINT chk_history_confidence_range
    CHECK (confidence_level IS NULL OR (confidence_level BETWEEN 1 AND 10));

-- Student Question History: Attempt number positive
ALTER TABLE student_question_history ADD CONSTRAINT chk_history_attempt_positive
    CHECK (attempt_number > 0);

-- Student Question History: Time spent non-negative
ALTER TABLE student_question_history ADD CONSTRAINT chk_history_time_positive
    CHECK (time_spent_sec IS NULL OR time_spent_sec >= 0);

-- Student Question History: Assignment mutual exclusivity
ALTER TABLE student_question_history ADD CONSTRAINT chk_history_assignment_exclusive
    CHECK (NOT (teacher_assignment_set_id IS NOT NULL AND parent_assignment_set_id IS NOT NULL));

-- Student Submissions: Transcription confidence range
ALTER TABLE student_submissions ADD CONSTRAINT chk_submission_confidence_range
    CHECK (transcription_confidence IS NULL OR (transcription_confidence BETWEEN 0 AND 1));

-- Parent Incentives: Progress cannot exceed target
ALTER TABLE parent_incentives ADD CONSTRAINT chk_incentive_progress_valid
    CHECK (current_progress >= 0);

-- Parent Incentives: End date after start date
ALTER TABLE parent_incentives ADD CONSTRAINT chk_incentive_dates_valid
    CHECK (end_date IS NULL OR end_date > start_date);

-- Parent Incentives: Target value must be positive
ALTER TABLE parent_incentives ADD CONSTRAINT chk_incentive_target_positive
    CHECK (target_value > 0);

-- Subject Paper Types: Clusters must be positive
ALTER TABLE subject_paper_types ADD CONSTRAINT chk_paper_types_clusters_positive
    CHECK (n_clusters IS NULL OR n_clusters > 0);

-- Subject Paper Types: MCQ config coherence
ALTER TABLE subject_paper_types ADD CONSTRAINT chk_paper_types_mcq_config
    CHECK (
        (is_mcq = false) OR
        (is_mcq = true AND mcq_option_count >= 2 AND mcq_option_format IS NOT NULL)
    );

-- Student Dashboard Analytics: Percentile range
ALTER TABLE student_dashboard_analytics ADD CONSTRAINT chk_analytics_percentile_range
    CHECK (percentile_rank IS NULL OR (percentile_rank BETWEEN 0 AND 100));

-- Student Dashboard Analytics: Topics consistency
ALTER TABLE student_dashboard_analytics ADD CONSTRAINT chk_analytics_topics_valid
    CHECK (topics_strong IS NULL OR topics_total IS NULL OR topics_strong <= topics_total);

-- Assignment Set Students: Progress percentage range
ALTER TABLE assignment_set_students ADD CONSTRAINT chk_assignment_progress_range
    CHECK (progress_pct BETWEEN 0 AND 100);

-- Parent Assignment Children: Progress percentage range
ALTER TABLE parent_assignment_children ADD CONSTRAINT chk_parent_assignment_progress_range
    CHECK (progress_pct BETWEEN 0 AND 100);

-- Teacher Class Analytics: Percentile range
ALTER TABLE teacher_class_analytics ADD CONSTRAINT chk_class_analytics_percentile_range
    CHECK (class_avg_percentile IS NULL OR (class_avg_percentile BETWEEN 0 AND 100));

-- Teacher Class Analytics: Engagement percentage range
ALTER TABLE teacher_class_analytics ADD CONSTRAINT chk_class_engagement_range
    CHECK (class_engagement_pct IS NULL OR (class_engagement_pct BETWEEN 0 AND 100));

-- ═══════════════════════════════════════════════════════════════════════════
-- CROSS-TABLE VALIDATION TRIGGERS
-- ═══════════════════════════════════════════════════════════════════════════

-- Trigger: Only primary guardians can create incentives
CREATE OR REPLACE FUNCTION check_primary_guardian_for_incentive()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM student_guardians
        WHERE id = NEW.guardian_id AND role = 'primary' AND is_active = true
    ) THEN
        RAISE EXCEPTION 'Only primary guardians can create incentives';
    END IF;

    -- Also verify guardian is linked to this student
    IF NOT EXISTS (
        SELECT 1 FROM student_guardians
        WHERE id = NEW.guardian_id AND student_id = NEW.student_id
    ) THEN
        RAISE EXCEPTION 'Guardian is not linked to this student';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_incentive_primary_only
BEFORE INSERT OR UPDATE ON parent_incentives
FOR EACH ROW EXECUTE FUNCTION check_primary_guardian_for_incentive();

-- Trigger: Only primary guardians can create assignments
CREATE OR REPLACE FUNCTION check_primary_guardian_for_assignment()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM student_guardians
        WHERE id = NEW.guardian_id AND role = 'primary' AND is_active = true
    ) THEN
        RAISE EXCEPTION 'Only primary guardians can create assignments';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_parent_assignment_primary_only
BEFORE INSERT OR UPDATE ON parent_assignment_sets
FOR EACH ROW EXECUTE FUNCTION check_primary_guardian_for_assignment();

-- Trigger: Validate marks_obtained against question marks
CREATE OR REPLACE FUNCTION validate_marks_obtained()
RETURNS TRIGGER AS $$
DECLARE
    max_marks INTEGER;
BEGIN
    IF NEW.marks_obtained IS NOT NULL THEN
        SELECT q.marks INTO max_marks
        FROM questions q WHERE q.question_id = NEW.question_id;

        IF max_marks IS NOT NULL AND NEW.marks_obtained > max_marks THEN
            RAISE EXCEPTION 'marks_obtained (%) exceeds question max marks (%)',
                NEW.marks_obtained, max_marks;
        END IF;

        IF NEW.marks_obtained < 0 THEN
            RAISE EXCEPTION 'marks_obtained cannot be negative';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_marks
BEFORE INSERT OR UPDATE ON student_question_history
FOR EACH ROW EXECUTE FUNCTION validate_marks_obtained();

-- Trigger: Validate MCQ submission matches paper type
CREATE OR REPLACE FUNCTION validate_mcq_submission()
RETURNS TRIGGER AS $$
DECLARE
    paper_is_mcq BOOLEAN;
    option_count INTEGER;
BEGIN
    -- Get paper type config via history → enrollment → paper_type
    SELECT spt.is_mcq, spt.mcq_option_count
    INTO paper_is_mcq, option_count
    FROM student_question_history sqh
    JOIN student_paper_type_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
    JOIN subject_paper_types spt ON spe.paper_type_id = spt.paper_type_id
    WHERE sqh.history_id = NEW.history_id;

    -- MCQ paper requires MCQ submission
    IF paper_is_mcq AND NEW.submission_type != 'mcq' THEN
        RAISE EXCEPTION 'MCQ paper requires MCQ submission type';
    END IF;

    -- Non-MCQ paper cannot have MCQ options
    IF NOT paper_is_mcq AND NEW.selected_option_indices IS NOT NULL THEN
        RAISE EXCEPTION 'Non-MCQ paper cannot have MCQ options';
    END IF;

    -- Validate option indices are within range
    IF NEW.selected_option_indices IS NOT NULL AND option_count IS NOT NULL THEN
        IF EXISTS (
            SELECT 1 FROM unnest(NEW.selected_option_indices) AS idx
            WHERE idx < 0 OR idx >= option_count
        ) THEN
            RAISE EXCEPTION 'MCQ option index out of range (0-%)', option_count - 1;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_mcq_submission
BEFORE INSERT OR UPDATE ON student_submissions
FOR EACH ROW EXECUTE FUNCTION validate_mcq_submission();

-- Trigger: Validate target_cluster_index for incentives
CREATE OR REPLACE FUNCTION validate_incentive_cluster()
RETURNS TRIGGER AS $$
DECLARE
    max_clusters INTEGER;
BEGIN
    IF NEW.target_cluster_index IS NOT NULL AND NEW.subject_id IS NOT NULL THEN
        -- Get max clusters from subject's paper types
        SELECT MAX(spt.n_clusters) INTO max_clusters
        FROM subject_paper_types spt
        WHERE spt.subject_id = NEW.subject_id;

        IF max_clusters IS NOT NULL AND NEW.target_cluster_index >= max_clusters THEN
            RAISE EXCEPTION 'Invalid cluster index % (max: %)',
                NEW.target_cluster_index, max_clusters - 1;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_incentive_cluster
BEFORE INSERT OR UPDATE ON parent_incentives
FOR EACH ROW
WHEN (NEW.target_cluster_index IS NOT NULL)
EXECUTE FUNCTION validate_incentive_cluster();

-- Trigger: Validate soft_cluster sums to 1.0 (probability distribution)
CREATE OR REPLACE FUNCTION validate_soft_cluster_sum()
RETURNS TRIGGER AS $$
DECLARE
    cluster_sum FLOAT;
BEGIN
    IF NEW.soft_cluster IS NOT NULL THEN
        SELECT SUM(val) INTO cluster_sum
        FROM unnest(NEW.soft_cluster) AS val;

        -- Allow small floating point tolerance
        IF ABS(cluster_sum - 1.0) > 0.01 THEN
            RAISE EXCEPTION 'soft_cluster must sum to 1.0 (got: %)', cluster_sum;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_soft_cluster
BEFORE INSERT OR UPDATE ON question_embeddings
FOR EACH ROW EXECUTE FUNCTION validate_soft_cluster_sum();

-- Trigger: Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables with updated_at (comprehensive list)
-- Core entities
CREATE TRIGGER trg_update_timestamp_users BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_students BEFORE UPDATE ON students FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_teachers BEFORE UPDATE ON teachers FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_schools BEFORE UPDATE ON schools FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_school_admins BEFORE UPDATE ON school_admins FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_system_admins BEFORE UPDATE ON system_admins FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_guardians BEFORE UPDATE ON student_guardians FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Academic structure
CREATE TRIGGER trg_update_timestamp_class_levels BEFORE UPDATE ON class_levels FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_subjects BEFORE UPDATE ON subjects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_paper_types BEFORE UPDATE ON subject_paper_types FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_papers BEFORE UPDATE ON papers FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_questions BEFORE UPDATE ON questions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_images BEFORE UPDATE ON question_images FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_mark_schemes BEFORE UPDATE ON mark_schemes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_embeddings BEFORE UPDATE ON question_embeddings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_clusters BEFORE UPDATE ON clusters FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Progress & submissions
CREATE TRIGGER trg_update_timestamp_enrollments BEFORE UPDATE ON student_paper_type_enrollments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_submissions BEFORE UPDATE ON student_submissions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_state_vectors BEFORE UPDATE ON student_state_vectors FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_dashboard BEFORE UPDATE ON student_dashboard_analytics FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Assignments & incentives
CREATE TRIGGER trg_update_timestamp_incentives BEFORE UPDATE ON parent_incentives FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_teacher_assign BEFORE UPDATE ON teacher_assignment_sets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_update_timestamp_parent_assign BEFORE UPDATE ON parent_assignment_sets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Relations
CREATE TRIGGER trg_update_timestamp_teacher_relations BEFORE UPDATE ON student_teacher_relations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## ROW-LEVEL SECURITY (RLS) POLICIES

*Database-enforced access control for multi-tenant isolation*

```sql
-- Enable RLS on sensitive tables
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_question_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE parent_incentives ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_guardians ENABLE ROW LEVEL SECURITY;
ALTER TABLE teacher_assignment_sets ENABLE ROW LEVEL SECURITY;

-- ═══════════════════════════════════════════════════════════════════════════
-- STUDENT POLICIES
-- ═══════════════════════════════════════════════════════════════════════════

-- Students can only see their own data
CREATE POLICY student_own_data ON students
    FOR ALL
    USING (student_id = current_setting('app.current_user_id', true)::uuid);

-- Students can only see their own history
CREATE POLICY student_own_history ON student_question_history
    FOR ALL
    USING (
        enrollment_id IN (
            SELECT enrollment_id FROM student_paper_type_enrollments
            WHERE student_id = current_setting('app.current_user_id', true)::uuid
        )
    );

-- Students can only see their own submissions
CREATE POLICY student_own_submissions ON student_submissions
    FOR ALL
    USING (
        history_id IN (
            SELECT sqh.history_id FROM student_question_history sqh
            JOIN student_paper_type_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
            WHERE spe.student_id = current_setting('app.current_user_id', true)::uuid
        )
    );

-- ═══════════════════════════════════════════════════════════════════════════
-- GUARDIAN/PARENT POLICIES
-- ═══════════════════════════════════════════════════════════════════════════

-- Guardians can see their linked students
CREATE POLICY guardian_view_students ON students
    FOR SELECT
    USING (
        student_id IN (
            SELECT student_id FROM student_guardians
            WHERE user_id = current_setting('app.current_user_id', true)::uuid
              AND is_active = true
        )
    );

-- Guardians can see their students' history (read-only)
CREATE POLICY guardian_view_history ON student_question_history
    FOR SELECT
    USING (
        enrollment_id IN (
            SELECT spe.enrollment_id
            FROM student_paper_type_enrollments spe
            JOIN student_guardians sg ON spe.student_id = sg.student_id
            WHERE sg.user_id = current_setting('app.current_user_id', true)::uuid
              AND sg.is_active = true
        )
    );

-- Primary guardians can manage incentives for their students
CREATE POLICY guardian_manage_incentives ON parent_incentives
    FOR ALL
    USING (
        guardian_id IN (
            SELECT id FROM student_guardians
            WHERE user_id = current_setting('app.current_user_id', true)::uuid
              AND role = 'primary'
              AND is_active = true
        )
    );

-- ═══════════════════════════════════════════════════════════════════════════
-- TEACHER POLICIES
-- ═══════════════════════════════════════════════════════════════════════════

-- Teachers can see students in their sections
CREATE POLICY teacher_view_students ON students
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM teacher_section_assignments tsa
            WHERE tsa.teacher_id = current_setting('app.current_user_id', true)::uuid
              AND tsa.section = students.section
              AND tsa.school_id = students.school_id
              AND tsa.is_active = true
        )
    );

-- Teachers can manage their own assignments
CREATE POLICY teacher_manage_assignments ON teacher_assignment_sets
    FOR ALL
    USING (teacher_id = current_setting('app.current_user_id', true)::uuid);

-- ═══════════════════════════════════════════════════════════════════════════
-- ADMIN BYPASS
-- ═══════════════════════════════════════════════════════════════════════════

-- System admins bypass all RLS
CREATE POLICY admin_bypass_students ON students
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM users u
            JOIN system_admins sa ON u.user_id = sa.admin_id
            WHERE u.user_id = current_setting('app.current_user_id', true)::uuid
        )
    );

-- School admins can see students in their school
CREATE POLICY school_admin_view_students ON students
    FOR SELECT
    USING (
        school_id IN (
            SELECT school_id FROM school_admins
            WHERE admin_id = current_setting('app.current_user_id', true)::uuid
        )
    );

-- ═══════════════════════════════════════════════════════════════════════════
-- APPLICATION CONTEXT SETUP
-- ═══════════════════════════════════════════════════════════════════════════

-- Set user context at start of each request (in application layer)
-- Example: SELECT set_config('app.current_user_id', 'uuid-here', true);
-- Example: SELECT set_config('app.current_user_role', 'student', true);
```

---

## PARTITIONING STRATEGY

*For high-volume tables that grow unbounded*

```sql
-- ═══════════════════════════════════════════════════════════════════════════
-- PARTITION: student_question_history BY MONTH
-- ═══════════════════════════════════════════════════════════════════════════

-- Convert to partitioned table (for new installations)
CREATE TABLE student_question_history_partitioned (
    history_id BIGSERIAL,
    enrollment_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    attempt_number INTEGER DEFAULT 1,
    status VARCHAR(20) NOT NULL,
    is_correct BOOLEAN,
    is_skipped BOOLEAN DEFAULT false,
    marks_obtained INTEGER,
    time_spent_sec INTEGER,
    confidence_level INTEGER,
    device_type VARCHAR(20),
    session_id UUID,
    timestamp TIMESTAMPTZ NOT NULL,
    teacher_assignment_set_id INTEGER,
    parent_assignment_set_id INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (history_id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Create monthly partitions
CREATE TABLE sqh_2024_01 PARTITION OF student_question_history_partitioned
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE sqh_2024_02 PARTITION OF student_question_history_partitioned
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
CREATE TABLE sqh_2024_03 PARTITION OF student_question_history_partitioned
    FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');
-- Continue for each month...

-- Default partition for data outside defined ranges
CREATE TABLE sqh_default PARTITION OF student_question_history_partitioned DEFAULT;

-- ═══════════════════════════════════════════════════════════════════════════
-- PARTITION: student_submissions BY MONTH
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE student_submissions_partitioned (
    submission_id BIGSERIAL,
    history_id BIGINT NOT NULL,
    submission_type VARCHAR(10) NOT NULL,
    text_answer TEXT,
    selected_option_indices INTEGER[],
    s3_key VARCHAR(500),
    image_type VARCHAR(20),
    is_transcribed BOOLEAN DEFAULT false,
    transcription_method VARCHAR(20),
    transcription_confidence FLOAT,
    original_text_before_edit TEXT,
    submitted_at TIMESTAMPTZ NOT NULL,
    file_size_bytes INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    PRIMARY KEY (submission_id, submitted_at)
) PARTITION BY RANGE (submitted_at);

-- ═══════════════════════════════════════════════════════════════════════════
-- PARTITION: audit_log BY MONTH
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE audit_log_partitioned (
    log_id BIGSERIAL,
    table_name VARCHAR(100) NOT NULL,
    record_id VARCHAR(100) NOT NULL,
    action VARCHAR(10) NOT NULL,
    changed_by UUID,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    PRIMARY KEY (log_id, changed_at)
) PARTITION BY RANGE (changed_at);

-- ═══════════════════════════════════════════════════════════════════════════
-- AUTO-CREATE PARTITIONS (using pg_partman extension)
-- ═══════════════════════════════════════════════════════════════════════════

-- Install pg_partman
CREATE EXTENSION IF NOT EXISTS pg_partman;

-- Configure automatic partition creation
SELECT partman.create_parent(
    p_parent_table := 'public.student_question_history_partitioned',
    p_control := 'timestamp',
    p_type := 'range',
    p_interval := '1 month',
    p_premake := 3  -- Create 3 months ahead
);

-- Schedule partition maintenance (add to cron)
-- SELECT partman.run_maintenance();
```

---

## DATA ARCHIVAL STRATEGY

```sql
-- ═══════════════════════════════════════════════════════════════════════════
-- ARCHIVE TABLES (for data older than 2 years)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE student_question_history_archive (
    LIKE student_question_history INCLUDING ALL
);

CREATE TABLE student_submissions_archive (
    LIKE student_submissions INCLUDING ALL
);

CREATE TABLE audit_log_archive (
    LIKE audit_log INCLUDING ALL
);

-- ═══════════════════════════════════════════════════════════════════════════
-- ARCHIVAL PROCEDURE (run monthly)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE PROCEDURE archive_old_data(cutoff_interval INTERVAL DEFAULT '2 years')
LANGUAGE plpgsql
AS $$
DECLARE
    cutoff_date TIMESTAMPTZ := NOW() - cutoff_interval;
    archived_count INTEGER;
BEGIN
    -- Archive student_question_history
    WITH archived AS (
        DELETE FROM student_question_history
        WHERE timestamp < cutoff_date
        RETURNING *
    )
    INSERT INTO student_question_history_archive
    SELECT * FROM archived;
    GET DIAGNOSTICS archived_count = ROW_COUNT;
    RAISE NOTICE 'Archived % rows from student_question_history', archived_count;

    -- Archive student_submissions
    WITH archived AS (
        DELETE FROM student_submissions
        WHERE submitted_at < cutoff_date
        RETURNING *
    )
    INSERT INTO student_submissions_archive
    SELECT * FROM archived;
    GET DIAGNOSTICS archived_count = ROW_COUNT;
    RAISE NOTICE 'Archived % rows from student_submissions', archived_count;

    -- Archive audit_log
    WITH archived AS (
        DELETE FROM audit_log
        WHERE changed_at < cutoff_date
        RETURNING *
    )
    INSERT INTO audit_log_archive
    SELECT * FROM archived;
    GET DIAGNOSTICS archived_count = ROW_COUNT;
    RAISE NOTICE 'Archived % rows from audit_log', archived_count;

    COMMIT;
END;
$$;

-- Schedule: CALL archive_old_data('2 years');
```

---

## MATERIALIZED VIEWS

*Pre-computed views for complex dashboard queries*

```sql
-- ═══════════════════════════════════════════════════════════════════════════
-- MV: Student Current State (for dashboard)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE MATERIALIZED VIEW mv_student_current_state AS
SELECT
    s.student_id,
    s.name AS student_name,
    s.school_id,
    spe.paper_type_id,
    spe.enrollment_id,
    spe.objective,
    spt.paper_type,
    spt.n_clusters,
    subj.name AS subject_name,
    cl.name AS class_level_name,
    ssv.mastery_vector,
    ssv.total_attempts,
    ssv.last_updated AS state_updated,
    sda.percentile_rank,
    sda.current_streak_days,
    sda.trend,
    sda.topics_strong,
    sda.topics_total,
    sda.weekly_questions_completed,
    sda.last_computed AS analytics_updated
FROM students s
JOIN student_paper_type_enrollments spe ON s.student_id = spe.student_id
JOIN subject_paper_types spt ON spe.paper_type_id = spt.paper_type_id
JOIN subjects subj ON spt.subject_id = subj.subject_id
JOIN class_levels cl ON subj.class_level_id = cl.class_level_id
LEFT JOIN student_state_vectors ssv ON s.student_id = ssv.student_id
    AND spe.paper_type_id = ssv.paper_type_id
    AND ssv.clustering_version = spt.clustering_version
LEFT JOIN student_dashboard_analytics sda ON s.student_id = sda.student_id
    AND spe.paper_type_id = sda.paper_type_id
WHERE spe.is_active = true;

CREATE UNIQUE INDEX ON mv_student_current_state(student_id, paper_type_id);
CREATE INDEX ON mv_student_current_state(school_id, paper_type_id);

-- Refresh strategy (run hourly or on-demand)
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_student_current_state;

-- ═══════════════════════════════════════════════════════════════════════════
-- MV: Teacher Section Overview (for teacher dashboard)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE MATERIALIZED VIEW mv_teacher_section_overview AS
SELECT
    tsa.teacher_id,
    tsa.school_id,
    tsa.subject_id,
    tsa.section,
    tsa.academic_year,
    subj.name AS subject_name,
    spt.paper_type_id,
    spt.paper_type,
    COUNT(DISTINCT s.student_id) AS student_count,
    AVG(sda.percentile_rank) AS avg_percentile,
    AVG(sda.current_streak_days) AS avg_streak,
    SUM(CASE WHEN sda.trend = 'improving' THEN 1 ELSE 0 END) AS improving_count,
    SUM(CASE WHEN sda.trend = 'declining' THEN 1 ELSE 0 END) AS declining_count,
    SUM(CASE WHEN sda.percentile_rank < 25 THEN 1 ELSE 0 END) AS at_risk_count,
    MAX(sda.last_computed) AS last_updated
FROM teacher_section_assignments tsa
JOIN subjects subj ON tsa.subject_id = subj.subject_id
JOIN subject_paper_types spt ON subj.subject_id = spt.subject_id
JOIN students s ON s.section = tsa.section AND s.school_id = tsa.school_id
JOIN student_paper_type_enrollments spe ON s.student_id = spe.student_id
    AND spe.paper_type_id = spt.paper_type_id
LEFT JOIN student_dashboard_analytics sda ON s.student_id = sda.student_id
    AND sda.paper_type_id = spt.paper_type_id
WHERE tsa.is_active = true AND spe.is_active = true
GROUP BY tsa.teacher_id, tsa.school_id, tsa.subject_id, tsa.section,
         tsa.academic_year, subj.name, spt.paper_type_id, spt.paper_type;

CREATE UNIQUE INDEX ON mv_teacher_section_overview(teacher_id, paper_type_id, section);

-- ═══════════════════════════════════════════════════════════════════════════
-- MV: Parent Children Overview (for parent dashboard)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE MATERIALIZED VIEW mv_parent_children_overview AS
SELECT
    sg.user_id AS parent_user_id,
    sg.role AS guardian_role,
    s.student_id,
    s.name AS child_name,
    spe.paper_type_id,
    spt.paper_type,
    subj.name AS subject_name,
    sda.percentile_rank,
    sda.trend,
    sda.topics_strong,
    sda.topics_total,
    sda.current_streak_days,
    sda.weekly_questions_completed,
    sda.has_active_incentive,
    sda.incentive_progress_pct,
    sda.last_computed
FROM student_guardians sg
JOIN students s ON sg.student_id = s.student_id
JOIN student_paper_type_enrollments spe ON s.student_id = spe.student_id
JOIN subject_paper_types spt ON spe.paper_type_id = spt.paper_type_id
JOIN subjects subj ON spt.subject_id = subj.subject_id
LEFT JOIN student_dashboard_analytics sda ON s.student_id = sda.student_id
    AND spe.paper_type_id = sda.paper_type_id
WHERE sg.is_active = true AND spe.is_active = true;

CREATE INDEX ON mv_parent_children_overview(parent_user_id);
```

---

## REQUIRED POSTGRESQL EXTENSIONS

```sql
-- ═══════════════════════════════════════════════════════════════════════════
-- REQUIRED EXTENSIONS (run before table creation)
-- ═══════════════════════════════════════════════════════════════════════════

-- UUID support (for user_id, session_id, etc.)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- OR use: CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Vector similarity search (for embeddings)
CREATE EXTENSION IF NOT EXISTS "vector";

-- Partition management (for automated partition creation)
CREATE EXTENSION IF NOT EXISTS "pg_partman";

-- Cryptographic functions (for password hashing, tokens)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Full-text search optimization (optional)
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ═══════════════════════════════════════════════════════════════════════════
-- CUSTOM ENUM TYPES
-- ═══════════════════════════════════════════════════════════════════════════

-- User roles
CREATE TYPE user_role AS ENUM ('student', 'parent', 'teacher', 'school_admin', 'system_admin');

-- Guardian roles
CREATE TYPE guardian_role AS ENUM ('primary', 'secondary');

-- Guardian relationships
CREATE TYPE guardian_relationship AS ENUM ('father', 'mother', 'guardian', 'grandparent', 'other');

-- Learning objectives
CREATE TYPE learning_objective AS ENUM ('coverage', 'efficiency', 'success_rate', 'balanced', 'custom');

-- Question attempt status
CREATE TYPE attempt_status AS ENUM ('correct', 'incorrect', 'skipped', 'partial');

-- Trend direction
CREATE TYPE trend_direction AS ENUM ('improving', 'stable', 'declining');

-- Submission types
CREATE TYPE submission_type AS ENUM ('mcq', 'text', 'image', 'mixed');

-- Question image types
CREATE TYPE question_image_type AS ENUM ('question', 'mark_scheme', 'diagram', 'figure', 'graph');

-- Submission image types
CREATE TYPE submission_image_type AS ENUM ('photo', 'scan', 'screenshot');

-- Transcription methods
CREATE TYPE transcription_method AS ENUM ('manual', 'ocr', 'gpt4_vision');

-- School types
CREATE TYPE school_type AS ENUM ('public', 'private', 'charter', 'international');

-- Teacher relationship types
CREATE TYPE teacher_relationship_type AS ENUM ('primary', 'secondary', 'tutor');

-- MCQ option formats
CREATE TYPE mcq_format AS ENUM ('alphabetic_upper', 'alphabetic_lower', 'numeric_zero', 'numeric_one', 'custom');

-- Paper source types
CREATE TYPE paper_source AS ENUM ('past_paper', 'practice', 'mock', 'custom');

-- Assignment target types
CREATE TYPE assignment_target AS ENUM ('section', 'individual');

-- Assignment status
CREATE TYPE assignment_status AS ENUM ('pending', 'in_progress', 'completed', 'overdue');

-- Incentive target types
CREATE TYPE incentive_target AS ENUM ('coverage', 'cluster', 'questions', 'streak', 'time_spent');

-- Reward categories
CREATE TYPE reward_category AS ENUM ('money', 'item', 'experience', 'privilege', 'food', 'custom');

-- Incentive status
CREATE TYPE incentive_status AS ENUM ('active', 'completed', 'expired', 'claimed');

-- Admin access levels
CREATE TYPE admin_level AS ENUM ('super', 'standard');

-- Notification priority
CREATE TYPE notification_priority AS ENUM ('low', 'normal', 'high', 'urgent');

-- Consent types
CREATE TYPE consent_type AS ENUM ('terms_of_service', 'privacy_policy', 'marketing', 'analytics');

-- Data request status
CREATE TYPE request_status AS ENUM ('pending', 'processing', 'completed', 'rejected', 'ready', 'expired');

-- Export formats
CREATE TYPE export_format AS ENUM ('json', 'csv', 'pdf');
```

---

## IMPLEMENTATION CHECKLIST

*Reference this when converting blueprint to executable SQL*

### Phase 1: Core Infrastructure
- [ ] Create extensions (uuid-ossp, vector, pgcrypto, pg_partman, pg_trgm)
- [ ] Create all ENUM types
- [ ] Create lookup tables (education_levels, departments, sections, streams, teacher_roles)
- [ ] Create users table with email verification fields
- [ ] Create schools table

### Phase 2: User Entities
- [ ] Create students table with normalized FK references
- [ ] Create student_guardians table with unique primary constraint
- [ ] Create teachers table
- [ ] Create school_admins table
- [ ] Create system_admins table

### Phase 3: Academic Structure
- [ ] Create class_levels table
- [ ] Create subjects table
- [ ] Create subject_paper_types table with MCQ config
- [ ] Create papers table with source tracking
- [ ] Create questions table
- [ ] Create question_images table
- [ ] Create mark_schemes table
- [ ] Create question_embeddings table
- [ ] Create clusters table

### Phase 4: Enrollment & Progress
- [ ] Create student_paper_type_enrollments table
- [ ] Create student_question_history table (or partitioned version)
- [ ] Create student_submissions table (or partitioned version)
- [ ] Create student_state_vectors table
- [ ] Create student_dashboard_analytics table

### Phase 5: Assignments & Incentives
- [ ] Create teacher_section_assignments table
- [ ] Create teacher_assignment_sets table
- [ ] Create assignment_set_questions table
- [ ] Create assignment_set_students table
- [ ] Create teacher_class_analytics table
- [ ] Create parent_incentives table
- [ ] Create incentive_questions table
- [ ] Create parent_assignment_sets table
- [ ] Create parent_assignment_questions table
- [ ] Create parent_assignment_children table

### Phase 6: ML/Analytics Support
- [ ] Create transition_matrices table
- [ ] Create daily_student_activity table
- [ ] Create weekly_leaderboard table
- [ ] Create cluster_performance_cache table

### Phase 7: Security & Compliance
- [ ] Create user_sessions table
- [ ] Create email_verifications table
- [ ] Create password_resets table
- [ ] Create api_keys table
- [ ] Create audit_log table (or partitioned version)
- [ ] Create notifications table
- [ ] Create notification_preferences table
- [ ] Create data_deletion_requests table
- [ ] Create data_export_requests table
- [ ] Create consent_records table

### Phase 8: Constraints & Triggers
- [ ] Add all CHECK constraints
- [ ] Create audit trigger function
- [ ] Apply audit triggers to sensitive tables
- [ ] Create updated_at trigger function
- [ ] Apply updated_at triggers to all tables
- [ ] Create validation triggers (primary guardian, marks, MCQ, clusters, soft_cluster sum)

### Phase 9: Indexes
- [ ] Create all core query indexes
- [ ] Create additional performance indexes
- [ ] Create partial indexes for common filters
- [ ] Create GIN indexes for array columns

### Phase 10: RLS & Views
- [ ] Enable RLS on sensitive tables
- [ ] Create student policies
- [ ] Create guardian/parent policies
- [ ] Create teacher policies
- [ ] Create admin bypass policies
- [ ] Create materialized views
- [ ] Set up refresh schedules

### Phase 11: Partitioning & Archival
- [ ] Set up pg_partman
- [ ] Create partitions for high-volume tables
- [ ] Create archive tables
- [ ] Create archival procedure
- [ ] Schedule maintenance jobs

### Phase 12: Initial Data
- [ ] Seed education_levels
- [ ] Seed teacher_roles
- [ ] Seed default streams (Science, Commerce, Arts)
- [ ] Create system admin user
- [ ] Create test school and users (dev only)

---

## SEED DATA EXAMPLES

```sql
-- ═══════════════════════════════════════════════════════════════════════════
-- EDUCATION LEVELS
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO education_levels (name, display_order) VALUES
('high_school', 1),
('associate', 2),
('bachelors', 3),
('masters', 4),
('doctorate', 5),
('professional', 6),
('other', 7);

-- ═══════════════════════════════════════════════════════════════════════════
-- TEACHER ROLES
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO teacher_roles (name, description) VALUES
('lecturer', 'Primary classroom instructor'),
('lab_instructor', 'Laboratory session instructor'),
('tutor', 'One-on-one or small group tutor'),
('teaching_assistant', 'Assists primary instructor'),
('head_of_department', 'Department head with administrative duties');

-- ═══════════════════════════════════════════════════════════════════════════
-- DEFAULT STREAMS (Global)
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO streams (school_id, name, description) VALUES
(NULL, 'Science', 'Science stream including Physics, Chemistry, Biology'),
(NULL, 'Commerce', 'Commerce stream including Accounting, Economics, Business Studies'),
(NULL, 'Arts', 'Arts/Humanities stream including History, Geography, Languages');

-- ═══════════════════════════════════════════════════════════════════════════
-- EXAMPLE CLASS LEVELS
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO class_levels (name, description) VALUES
('A-Level', 'Cambridge Advanced Level'),
('AS-Level', 'Cambridge Advanced Subsidiary Level'),
('O-Level', 'Cambridge Ordinary Level'),
('IGCSE', 'International General Certificate of Secondary Education'),
('IB', 'International Baccalaureate');

-- ═══════════════════════════════════════════════════════════════════════════
-- EXAMPLE SUBJECTS (A-Level)
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO subjects (class_level_id, name, code, description) VALUES
((SELECT class_level_id FROM class_levels WHERE name = 'A-Level'), 'Physics', '9702', 'Cambridge A-Level Physics'),
((SELECT class_level_id FROM class_levels WHERE name = 'A-Level'), 'Chemistry', '9701', 'Cambridge A-Level Chemistry'),
((SELECT class_level_id FROM class_levels WHERE name = 'A-Level'), 'Biology', '9700', 'Cambridge A-Level Biology'),
((SELECT class_level_id FROM class_levels WHERE name = 'A-Level'), 'Mathematics', '9709', 'Cambridge A-Level Mathematics');

-- ═══════════════════════════════════════════════════════════════════════════
-- EXAMPLE PAPER TYPES (A-Level Physics)
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO subject_paper_types (
    subject_id, paper_type, paper_type_name,
    is_mcq, mcq_option_count, mcq_option_format,
    default_total_marks, default_duration_minutes
) VALUES
(
    (SELECT subject_id FROM subjects WHERE code = '9702'),
    'P1', 'Multiple Choice',
    true, 4, 'alphabetic_upper',
    40, 60
),
(
    (SELECT subject_id FROM subjects WHERE code = '9702'),
    'P2', 'Structured Questions',
    false, NULL, NULL,
    60, 75
),
(
    (SELECT subject_id FROM subjects WHERE code = '9702'),
    'P3', 'Advanced Practical Skills',
    false, NULL, NULL,
    40, 120
);
```

---

## MAINTENANCE JOBS (CRON)

```bash
# ═══════════════════════════════════════════════════════════════════════════
# DAILY JOBS (run at 2 AM)
# ═══════════════════════════════════════════════════════════════════════════

# Refresh materialized views
0 2 * * * psql -d hcd_db -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_student_current_state;"
0 2 * * * psql -d hcd_db -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_teacher_section_overview;"
0 2 * * * psql -d hcd_db -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_parent_children_overview;"

# Aggregate daily activity
0 3 * * * psql -d hcd_db -c "CALL aggregate_daily_activity();"

# Compute student analytics
0 4 * * * psql -d hcd_db -c "CALL compute_student_analytics();"

# Compute teacher class analytics
0 5 * * * psql -d hcd_db -c "CALL compute_teacher_analytics();"

# Clean expired sessions
0 1 * * * psql -d hcd_db -c "DELETE FROM user_sessions WHERE expires_at < NOW() - INTERVAL '30 days';"

# ═══════════════════════════════════════════════════════════════════════════
# WEEKLY JOBS (run Sunday 3 AM)
# ═══════════════════════════════════════════════════════════════════════════

# Compute weekly leaderboards
0 3 * * 0 psql -d hcd_db -c "CALL compute_weekly_leaderboard();"

# Send weekly parent summaries (via application)
0 8 * * 0 curl -X POST https://api.example.com/notifications/weekly-summary

# ═══════════════════════════════════════════════════════════════════════════
# MONTHLY JOBS (run 1st of month 4 AM)
# ═══════════════════════════════════════════════════════════════════════════

# Partition maintenance
0 4 1 * * psql -d hcd_db -c "SELECT partman.run_maintenance();"

# Archive old data (2+ years)
0 5 1 * * psql -d hcd_db -c "CALL archive_old_data('2 years');"

# Vacuum analyze large tables
0 6 1 * * psql -d hcd_db -c "VACUUM ANALYZE student_question_history;"
0 6 1 * * psql -d hcd_db -c "VACUUM ANALYZE student_submissions;"
```

---

## MIGRATION VERSION TRACKING

*For tracking schema versions during development and deployment*

```sql
CREATE TABLE schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    description TEXT,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    applied_by VARCHAR(100)
);

-- Example entries
INSERT INTO schema_migrations (version, description, applied_by) VALUES
('001', 'Initial schema creation', 'system'),
('002', 'Add security tables', 'system'),
('003', 'Add partitioning', 'system'),
('004', 'Add notification system', 'system');
```

---

## NEXT STEPS

1. **Convert to Executable SQL**: Use this blueprint to generate migration files
2. **Set Up Development Database**: Create local PostgreSQL with all extensions
3. **Implement Application Layer**:
   - User context setting (`SET app.current_user_id`)
   - Session management
   - API endpoints with proper RLS enforcement
4. **Populate Question Data**: Import P1 questions with embeddings
5. **Build Analytics Pipeline**: Implement compute procedures for cached analytics
6. **Deploy with Proper Permissions**: Set up read replicas, connection pooling



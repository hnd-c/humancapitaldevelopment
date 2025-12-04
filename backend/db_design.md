Question_table: ['class_level(A-Level)', 'subject(Physics)', 'paper_number/type(P1)', 'question_number', 'question_text', 'images_paths', 'source_file', 'mark scheme', 'openai_embedding', 'umap_embedding', 'soft_cluster']

Student_table: ['id_number','name', 'address', 'phone', 'email', 'DOB', 'School', 'Department', 'Section', 'Stream', 'Year', 'parent_id']

Parent_table: ['name', 'address', 'phone', 'email', 'education_level', 'occupation','parent_id']

Teacher_table: ['name', 'address', 'phone', 'email', 'education_level', 'subject_teacher', 'section_assigned']

School_admin_table: ['name', 'address', 'phone', 'email', 'education_level', 'department']

Student_progress_table: ['student_id', 'subject', 'paper_number', 'question_number', 'time_stamp', 'attempt_status', 'time_spent']

Parent_incentivized_table: ['question_id', 'incentive', 'progress', 'incentive_retrived_status']

Teacher_assigned_table: ['question_id', 'student_id', 'assignment_status']


How would the system work (in terms of the data storage andflow)?

There will be different tables each for specific paper type (p1, p2, p3, etc.) and each for specific subject (Physics, Chemistry, Biology, etc.) for specific class level (A-Level, etc.). The quesuestions in the table will go through preprocessing, for example, the question texts will be converted to embeddings using open ai model, then the embedding space will be reduced using umap, then baysian gausian mixture model will be used to cluster the questions into different clusters, and the sofcluster for each question will be stored in the database.

Then in the system, the student can create an account and subscribe to the table of questions they want. They can start attempting the questions with different objectives, for example, to increase coverage of across the question space, or to increase coverage across specific one cluster, or something in between. The system will then recommend the questions to the student based on their objective and their progress history. The progress history will be sotred in the student_progress_table for each paper_type.

On the parents side, they can kind of see how their kids progress, and they can incentive their kids to do a set of questions to earn a given reward. Parents can incentive their kids to improver coverage across all the question or just for a specific cluster/topic.

Similary, on the teacher side, they can see how their students progress, and they can assign different questions to different students based on their progress and their needs.

System adimin will help connect students to question tables, and students to parents and teachers.

---

## OPTIMIZED E-R DESIGN

### Design Principles Applied:
1. **Normalization (3NF)** - Separate entities for reusable data (Schools, Subjects, Papers)
2. **Explicit Keys** - Primary keys (PK) and Foreign keys (FK) clearly defined
3. **Enrollment Pattern** - Junction tables for student-paper subscriptions
4. **Soft Delete** - `is_active` flags for data retention
5. **Audit Trail** - `created_at`, `updated_at` timestamps
6. **ML-Ready Structure** - Embeddings stored efficiently, soft clusters as arrays

---

### CORE ENTITIES

#### 1. Users (Authentication Layer)
```
users
├── user_id (PK, UUID)
├── email (UNIQUE, NOT NULL)
├── password_hash (NOT NULL)
├── role (ENUM: student, parent, teacher, school_admin, system_admin)
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
```
*All user types authenticate through this table*

---

#### 2. Schools
```
schools
├── school_id (PK, SERIAL)
├── name (NOT NULL)
├── address
├── phone
├── email
├── is_active (BOOLEAN)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
```

---

#### 3. Students
```
students
├── student_id (PK, FK → users.user_id)
├── id_number (UNIQUE, external ID like roll number)
├── name (NOT NULL)
├── address
├── phone
├── dob (DATE)
├── school_id (FK → schools.school_id)
├── department
├── section
├── stream
├── year (INTEGER)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
```

---

#### 4. Student Guardians (Unified: Primary Parent + Secondary Guardians)
```
student_guardians
├── id (PK, SERIAL)
├── student_id (FK → students.student_id)
├── user_id (FK → users.user_id)
│
│   -- ROLE & RELATIONSHIP --
├── role (ENUM: primary, secondary)  ← KEY FIELD: controls permissions
├── relationship (ENUM: father, mother, guardian, grandparent, other)
│
│   -- GUARDIAN INFO (denormalized for convenience) --
├── name (NOT NULL)
├── phone
├── education_level
├── occupation
│
│   -- INVITATION (for secondary only) --
├── invited_by (FK → student_guardians.id, NULL for primary)
├── invite_accepted (BOOLEAN, DEFAULT true for primary)
│
│   -- STATUS --
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMP)
├── updated_at (TIMESTAMP)
│
└── UNIQUE(student_id, user_id)
└── CHECK: Only ONE primary per student
```
*Single table for all parent/guardian relationships. Role field determines access.*

**Constraint:** Each student can have only ONE `role='primary'` guardian:
```sql
CREATE UNIQUE INDEX idx_one_primary_per_student
ON student_guardians(student_id)
WHERE role = 'primary';
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
├── teacher_id (PK, FK → users.user_id)
├── name (NOT NULL)
├── address
├── phone
├── education_level
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
```

---

#### 6. School Admins
```
school_admins
├── admin_id (PK, FK → users.user_id)
├── name (NOT NULL)
├── address
├── phone
├── education_level
├── school_id (FK → schools.school_id)
├── department
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
```

---

### ACADEMIC STRUCTURE

#### 8. Class Levels
```
class_levels
├── class_level_id (PK, SERIAL)
├── name (NOT NULL, e.g., 'A-Level', 'O-Level', 'IGCSE')
├── description
└── created_at (TIMESTAMP)
```

---

#### 9. Subjects
```
subjects
├── subject_id (PK, SERIAL)
├── class_level_id (FK → class_levels.class_level_id)
├── name (NOT NULL, e.g., 'Physics', 'Chemistry')
├── code (e.g., '9702' for A-Level Physics)
├── description
├── created_at (TIMESTAMP)
└── UNIQUE(class_level_id, name)
```

---

#### 10. Papers
```
papers
├── paper_id (PK, SERIAL)
├── subject_id (FK → subjects.subject_id)
├── paper_type (VARCHAR, e.g., 'P1', 'P2', 'P3')
├── paper_name (e.g., 'Multiple Choice', 'Structured Questions')
├── exam_year (INTEGER)
├── exam_session (VARCHAR, e.g., 'May/June', 'Oct/Nov')
├── total_marks (INTEGER)
├── duration_minutes (INTEGER)
├── n_clusters (INTEGER, number of topic clusters for this paper)
├── clustering_version (VARCHAR, e.g., 'v1.0', 'v2.0', current active version)
├── source_file (VARCHAR, path to original PDF)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
```
*Each paper has its own clustering - P1 MCQ clusters differ from P2 structured question clusters*

**Versioning for Updates:**
When questions are added/updated and clusters recalculated:
1. Increment `clustering_version` (e.g., 'v1.0' → 'v2.0')
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
├── internal_question_id (SERIAL, for ML indexing, 0-based internally)
├── paper_id (FK → papers.paper_id)
├── question_number (VARCHAR, e.g., '1', '2a', '2b(i)')
├── question_text (TEXT, NOT NULL)
├── mark_scheme (TEXT)
├── marks (INTEGER)
├── source_file (VARCHAR)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
```

---

#### 12. Question Images (S3 bucket abstraction)
```
question_images
├── image_id (PK, SERIAL)
├── question_id (FK → questions.question_id)
├── s3_key (VARCHAR, NOT NULL, e.g., 'questions/physics/p1/2023/q1_fig1.png')
├── image_type (ENUM: question, mark_scheme, diagram)
├── display_order (INTEGER, DEFAULT 0)
├── alt_text (VARCHAR)
├── created_at (TIMESTAMP)
└── INDEX(question_id)
```
*Images stored in S3, only paths/keys in database*

---

#### 13. Question Embeddings (Separate for Performance)
```
question_embeddings
├── id (PK, SERIAL)
├── question_id (FK → questions.question_id)
├── clustering_version (VARCHAR, e.g., 'v1.0', matches paper.clustering_version)
├── openai_embedding (VECTOR(1536), for text-embedding-3-small)
├── umap_embedding (FLOAT[], 2D/3D reduced representation)
├── soft_cluster (FLOAT[], probability distribution across clusters)
├── embedding_model (VARCHAR, e.g., 'text-embedding-3-small')
├── created_at (TIMESTAMP)
├── updated_at (TIMESTAMP)
└── UNIQUE(question_id, clustering_version)
```
*Consider using pgvector extension for VECTOR type*
*Multiple versions can exist per question - use paper.clustering_version to get active one*

---

#### 14. Clusters (Optional: Label/Describe Topic Clusters, Per Paper)
```
clusters
├── cluster_id (PK, SERIAL)
├── paper_id (FK → papers.paper_id)
├── clustering_version (VARCHAR, e.g., 'v1.0', matches paper.clustering_version)
├── cluster_index (INTEGER, 0-based, matches soft_cluster array index)
├── label (VARCHAR, human-readable topic name, e.g., 'Mechanics', 'Waves')
├── description (TEXT)
├── representative_keywords (TEXT[])
├── created_at (TIMESTAMP)
└── UNIQUE(paper_id, clustering_version, cluster_index)
```
*Each paper has its own set of clusters derived from its questions*
*Multiple versions exist when clusters are recalculated - use paper.clustering_version to get active*

---

### ENROLLMENT & PROGRESS

#### 15. Student Paper Enrollments
```
student_paper_enrollments
├── enrollment_id (PK, SERIAL)
├── student_id (FK → students.student_id)
├── paper_id (FK → papers.paper_id)
├── objective (ENUM: coverage, efficiency, success_rate, balanced, custom)
├── target_cluster_id (INTEGER, NULL, specific cluster focus if custom)
├── enrolled_at (TIMESTAMP)
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMP)
└── UNIQUE(student_id, paper_id)
```
*This is the "subscription" when student subscribes to a paper*

---

#### 16. Student Question History
```
student_question_history
├── history_id (PK, SERIAL)
├── enrollment_id (FK → student_paper_enrollments.enrollment_id)
├── question_id (FK → questions.question_id)
├── attempt_number (INTEGER, DEFAULT 1)
├── status (ENUM: correct, incorrect, skipped, partial)
├── is_correct (BOOLEAN)
├── is_skipped (BOOLEAN, DEFAULT false)
├── marks_obtained (INTEGER, NULL)
├── time_spent_sec (INTEGER)
├── confidence_level (INTEGER, 1-10 scale)
├── device_type (VARCHAR, e.g., 'mobile', 'desktop', 'tablet')
├── session_id (UUID, group attempts in same session)
├── timestamp (TIMESTAMP, NOT NULL)
├── created_at (TIMESTAMP)
└── INDEX(enrollment_id, timestamp)
└── INDEX(question_id)
```
*Core table for ML recommendation system - matches vector_encoder.py expectations*

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
├── paper_id (FK → papers.paper_id)
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
└── UNIQUE(teacher_id, paper_id, section)
```
*Cached analytics for teacher dashboard - recomputed daily*

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

#### 19. Parent Incentives
```
parent_incentives
├── incentive_id (PK, SERIAL)
├── guardian_id (FK → student_guardians.id, must be role='primary')
├── student_id (FK → students.student_id)
├── subject_id (FK → subjects.subject_id, NULL for all subjects)
│
│   -- TARGET DEFINITION --
├── target_type (ENUM: coverage, cluster, questions, streak, time_spent)
├── target_cluster_index (INTEGER, NULL, if targeting specific cluster)
├── target_value (FLOAT, e.g., 80% coverage, 10 questions, 5 hours)
├── current_progress (FLOAT, DEFAULT 0)
│
│   -- REWARD DEFINITION --
├── reward_category (ENUM: money, item, experience, privilege, food, custom)
├── reward_title (VARCHAR, NOT NULL, e.g., 'New Bicycle', 'Pizza Night')
├── reward_description (TEXT, NULL, detailed description if needed)
├── reward_emoji (VARCHAR(10), NULL, e.g., '🚲', '🍕', '🎮', '✈️')
│
│   -- TIMELINE --
├── start_date (DATE)
├── end_date (DATE, NULL, no deadline if NULL)
│
│   -- STATUS --
├── status (ENUM: active, completed, expired, claimed)
├── completed_at (TIMESTAMP, NULL, when target was met)
├── claimed_at (TIMESTAMP, NULL, when reward was given)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
└── INDEX(student_id, status)
```

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

#### 20. Incentive Questions (Optional: Specific Questions for Incentive)
```
incentive_questions
├── id (PK, SERIAL)
├── incentive_id (FK → parent_incentives.incentive_id)
├── question_id (FK → questions.question_id)
├── is_completed (BOOLEAN, DEFAULT false)
├── completed_at (TIMESTAMP, NULL)
└── UNIQUE(incentive_id, question_id)
```

---

### PARENT ASSIGNMENTS (Practice Sets)

#### 21. Parent Assignment Sets
```
parent_assignment_sets
├── set_id (PK, SERIAL)
├── guardian_id (FK → student_guardians.id, must be role='primary')
├── paper_id (FK → papers.paper_id)
├── set_name (VARCHAR, e.g., 'Weekend Practice', 'Before Exam Review')
├── assigned_at (TIMESTAMP)
├── due_date (TIMESTAMP, NULL)
├── notes (TEXT, e.g., 'Focus on these before Monday!')
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
```

#### 21a. Parent Assignment Questions
```
parent_assignment_questions
├── id (PK, SERIAL)
├── set_id (FK → parent_assignment_sets.set_id)
├── question_id (FK → questions.question_id)
├── order_index (INTEGER, display order)
└── UNIQUE(set_id, question_id)
```

#### 21b. Parent Assignment Children (Target: One or Multiple Kids)
```
parent_assignment_children
├── id (PK, SERIAL)
├── set_id (FK → parent_assignment_sets.set_id)
├── student_id (FK → students.student_id)
├── status (ENUM: pending, in_progress, completed)
├── completed_at (TIMESTAMP, NULL)
├── progress_pct (FLOAT, 0-100)
└── UNIQUE(set_id, student_id)
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

#### 22. Student State Vectors (Cached for Performance, Per Paper)
```
student_state_vectors
├── id (PK, SERIAL)
├── student_id (FK → students.student_id)
├── paper_id (FK → papers.paper_id)
├── clustering_version (VARCHAR, which version of clusters this is based on)
├── n_clusters (INTEGER, matches paper's cluster count)
├── mastery_vector (FLOAT[], per-cluster mastery scores)
├── velocity_vector (FLOAT[], per-cluster learning velocity)
├── exposure_vector (FLOAT[], per-cluster exposure counts)
├── last_state_vector (FLOAT[], latest combined state for recommendations)
├── objective (ENUM: coverage, efficiency, success_rate, balanced)
├── total_attempts (INTEGER)
├── last_updated (TIMESTAMP)
├── created_at (TIMESTAMP)
└── UNIQUE(student_id, paper_id, clustering_version)
```
*Cached vectors from vector_encoder.py - per paper to match transition matrix dimensions*
*When clustering is updated, old state vectors remain; new ones created with new version*

---

#### 23. Transition Matrices (Pre-computed, Per Paper)
```
transition_matrices
├── id (PK, SERIAL)
├── paper_id (FK → papers.paper_id)
├── clustering_version (VARCHAR, matches paper.clustering_version)
├── n_clusters (INTEGER, number of clusters for this paper)
├── matrix_data (FLOAT[][], n_clusters x n_clusters)
├── alpha (FLOAT, self-transition weight used)
├── computed_at (TIMESTAMP)
├── questions_count (INTEGER, number of questions used to compute)
├── is_active (BOOLEAN, DEFAULT true)
├── created_at (TIMESTAMP)
└── UNIQUE(paper_id, clustering_version)
```
*Pre-computed from transition_matrix.py - each paper has its own transition patterns*

**Why Per Paper:**
- P1 (MCQ) has different learning pathways than P2 (Structured)
- Clusters are derived from questions within a specific paper
- More accurate recommendations for each paper type

**Update Workflow:**
```
When Physics P1 questions are updated:
1. Calculate new embeddings → question_embeddings (clustering_version='v2.0')
2. Calculate new clusters → clusters (clustering_version='v2.0')
3. Calculate new transition matrix → transition_matrices (clustering_version='v2.0')
4. Update paper → papers.clustering_version = 'v2.0'
5. New students use v2.0 automatically
6. Existing students: recompute state vectors with v2.0 on next activity
```

---

#### 23. Student Dashboard Analytics (Both Views)
```
student_dashboard_analytics
├── id (PK, SERIAL)
├── student_id (FK → students.student_id)
├── paper_id (FK → papers.paper_id)
│
│   ══════════════════════════════════════════════════════════
│   RELATIVE VIEW (Quick Dashboard - shown to Students & Parents)
│   ══════════════════════════════════════════════════════════
├── percentile_rank (FLOAT, 0-100, "Top 25%" = 75.0)
├── practice_vs_average (FLOAT, 1.4 = "40% more than peers")
├── topics_strong (INTEGER, count of mastered topics)
├── topics_total (INTEGER, total topics in paper)
├── topics_weak_labels (TEXT[], human-readable, e.g., ['Waves', 'Electricity'])
├── trend (ENUM: improving, stable, declining)
├── trend_description (VARCHAR, e.g., "Getting better each week!")
├── current_streak_days (INTEGER)
├── weekly_practice_days (INTEGER)
├── weekly_questions_completed (INTEGER)
├── weekly_practice_minutes (INTEGER)
├── has_active_incentive (BOOLEAN)
├── incentive_progress_pct (FLOAT, 0-100)
│
│   ══════════════════════════════════════════════════════════
│   RAW VIEW (Study Mode - shown to Students ONLY, not parents)
│   ══════════════════════════════════════════════════════════
├── weak_cluster_indices (INTEGER[], clusters to focus on)
├── recent_wrong_question_ids (INTEGER[], last 10 wrong answers)
├── questions_to_review (INTEGER[], recommended for review)
├── mastery_by_cluster (FLOAT[], per-cluster mastery scores)
├── total_correct (INTEGER)
├── total_incorrect (INTEGER)
├── total_skipped (INTEGER)
├── avg_time_per_question (FLOAT, seconds)
├── best_cluster_index (INTEGER, strongest topic)
├── worst_cluster_index (INTEGER, weakest topic)
│
│   -- METADATA --
├── peer_comparison_group (VARCHAR, e.g., 'same_school', 'same_year')
├── last_computed (TIMESTAMP)
├── created_at (TIMESTAMP)
└── UNIQUE(student_id, paper_id, peer_comparison_group)
```
*Cached analytics - Students see both views, Parents see relative only*

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

#### 24. System Admins
```
system_admins
├── admin_id (PK, FK → users.user_id)
├── name (NOT NULL)
├── access_level (ENUM: super, standard)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
```

---

#### 25. Student-Teacher Relations (Managed by Admin)
```
student_teacher_relations
├── id (PK, SERIAL)
├── student_id (FK → students.student_id)
├── teacher_id (FK → teachers.teacher_id)
├── subject_id (FK → subjects.subject_id)
├── assigned_by (FK → users.user_id, admin who created)
├── academic_year (VARCHAR)
├── is_active (BOOLEAN)
├── created_at (TIMESTAMP)
└── UNIQUE(student_id, teacher_id, subject_id, academic_year)
```

---

## E-R DIAGRAM RELATIONSHIPS

```
                              ┌─────────────────┐
                              │     Users       │
                              │    (auth)       │
                              └───────┬─────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
          ▼                           ▼                           ▼
   ┌──────────────┐            ┌─────────────┐            ┌──────────────┐
   │   students   │            │  teachers   │            │ school_admins│
   │              │            │             │            │              │
   └──────┬───────┘            └──────┬──────┘            └──────────────┘
          │                           │
          │                           │ N:M (via student_teacher_relations)
          │                           │
          │◄──────────────────────────┴─────────────────────────┐
          │                                                     │
          │                                          ┌─────────────────────────┐
          │◄─────────────────────────────────────────│ student_teacher_relations│
          │                                          └─────────────────────────┘
          │
          │◄─────────────────────────────────────┐
          │                                      │
          │                     ┌────────────────────────────────┐
          │                     │      student_guardians         │
          │                     │   (UNIFIED: primary + secondary)│
          │                     │                                │
          │                     │  role=primary → can incentivize │
          │                     │  role=secondary → view only    │
          │                     └────────────────┬───────────────┘
          │                                      │
          │                                      ▼
          │                              ┌──────────────────┐
          │                              │ parent_incentives│
          │                              │ (primary only)   │
          │                              └──────────────────┘
          │
          ├──────────────────────────────┐
          │                              │
          ▼                              ▼
   ┌─────────────┐            ┌───────────────────┐
   │   schools   │            │ student_paper_    │
   │             │            │   enrollments     │
   └─────────────┘            └─────────┬─────────┘
                                        │
                                        ▼
                          ┌─────────────────────────┐
                          │ student_question_history │◄───── ML Recommendations
                          └───────────┬─────────────┘
                                      │
                      ┌───────────────┼───────────────┐
                      ▼               ▼               ▼
              ┌───────────┐   ┌───────────────┐  ┌──────────────────┐
              │ questions │   │    papers     │  │ student_state_   │
              │           │   │               │  │    vectors       │
              └─────┬─────┘   └───────┬───────┘  └──────────────────┘
                    │                 │
                    ▼                 ▼
            ┌───────────────┐  ┌───────────┐   ┌──────────────┐
            │   question_   │  │ subjects  │──►│ class_levels │
            │  embeddings   │  │           │   │              │
            └───────────────┘  └───────────┘   └──────────────┘
                    │
                    ▼
            ┌───────────────┐
            │   clusters    │
     │  (optional)   │
     └───────────────┘
```

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
| Users → Students/Teachers | 1:1 | Authentication inheritance |
| Users ↔ Students (as guardians) | N:M | Via student_guardians (unified table) |
| Guardians → Students | N:M | One user can be guardian for multiple students |
| Students → Guardians | 1:N | Each student has ONE primary + multiple secondary |
| Students → Schools | N:1 | Student belongs to one school |
| Students ↔ Papers | N:M | Via student_paper_enrollments |
| Students → Question History | 1:N | All attempts by student |
| Questions → Papers | N:1 | Question belongs to one paper |
| Papers → Subjects | N:1 | Paper belongs to one subject |
| Subjects → Class Levels | N:1 | Subject belongs to one level |
| Questions → Embeddings | 1:1 | ML data for each question |
| Teachers ↔ Students | N:M | Via student_teacher_relations |
| Primary Guardian → Incentives | 1:N | ONLY role='primary' can create incentives |
| Teachers → Assignments | 1:N | Teacher assigns questions to students |

---

## INDEXES FOR PERFORMANCE

```sql
-- Critical for recommendation queries
CREATE INDEX idx_history_enrollment_time ON student_question_history(enrollment_id, timestamp DESC);
CREATE INDEX idx_history_question ON student_question_history(question_id);

-- For embedding similarity search (requires pgvector)
CREATE INDEX idx_embeddings_vector ON question_embeddings USING ivfflat (openai_embedding vector_cosine_ops);

-- For quick lookups
CREATE INDEX idx_questions_paper ON questions(paper_id);
CREATE INDEX idx_enrollments_student ON student_paper_enrollments(student_id);
CREATE INDEX idx_incentives_student_status ON parent_incentives(student_id, status);
```

---

## NOTES FOR ML INTEGRATION

1. **vector_encoder.py compatibility**:
   - `student_question_history` matches expected format with `is_correct`, `is_skipped`, `time_spent_sec`, `confidence_level`, `device_type`
   - `question_embeddings.soft_cluster` is FLOAT[] matching numpy arrays

2. **transition_matrix.py compatibility**:
   - `transition_matrices` stores pre-computed matrices **per paper** (not per subject)
   - Each paper type (P1, P2, P3) has its own transition patterns
   - `clusters` table optional for human-readable cluster labels

3. **Recommendation flow**:
   - Student enrolls → enrollment created with objective
   - Student attempts → history recorded
   - ML system reads history → computes state vector → stores in student_state_vectors
   - Recommendation uses state vector + transition matrix → suggests next questions







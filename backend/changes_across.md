# 🔄 Cross-System Changes Report: Multi-Tenant Database Expansion

## Executive Summary

This document analyzes the current Human Capital Development System and provides a detailed roadmap of changes needed across all components to implement the multi-tenant, multi-curriculum expansion outlined in `expand_database.md`.

**Current State**: Single-school (St. Xavier's College), single-subject (Physics P1), single-paper system  
**Target State**: Multi-tenant, multi-curriculum, multi-subject, all paper types, multi-user system

---

## 📊 Impact Analysis by Component

### Overall System Impact Metrics
- **Database Schema**: 🔴 **Major Changes** (15 new tables, 8 enhanced tables)
- **Python Scripts**: 🟡 **Moderate Changes** (3 scripts to rewrite, 5 new scripts)
- **API Endpoints**: 🟡 **Moderate Changes** (15 new endpoints, 8 modified endpoints)
- **Services Layer**: 🟡 **Moderate Changes** (3 new services, 5 enhanced services)
- **Configuration**: 🟢 **Minor Changes** (2 new config files, 1 enhanced)
- **ML/Vector Operations**: 🟢 **Minimal Changes** (embeddings remain compatible)

---

## 🗄️ DATABASE LAYER CHANGES

### 1. Schema Migration Files

#### **Current State**
```
database/migrations/01_initial_schema.sql (Single-tenant schema)
├── 10 tables: institutions, departments, academic_years, sections, subjects, papers, 
│              students, student_paper_enrollments, questions, student_question_history
├── Single institution per database
├── No user management
├── Only Physics subject
└── Only P1 paper support
```

#### **Required Changes**

##### **NEW FILE: `database/migrations/01_initial_schema.sql`** 🔴 REPLACE
Keep vector support but update for multi-tenancy:
```sql
-- Keep existing tables but add school_id to:
-- institutions, departments, academic_years, sections, students

-- Preserve vector operations (these remain unchanged):
-- - questions.openai_embedding vector(3072)
-- - questions.umap_embedding vector(50)
-- - questions.soft_cluster vector(20)
-- - questions.umap_2d_embedding vector(2)
```

**Action Required**: Rewrite to include school_id columns while preserving vector indexes.

##### **NEW FILE: `database/migrations/02_multi_tenant_schema.sql`** 🆕 CREATE
Add multi-tenant foundation:
```sql
-- NEW TABLES:
CREATE TABLE schools (...)              -- Top-level school entities
CREATE TABLE curricula (...)            -- Cambridge, IB, CBSE, etc.
CREATE TABLE school_curricula (...)     -- School-curriculum associations
CREATE TABLE school_settings (...)      -- Per-school configuration
```

**Action Required**: Create new file with 4 tables + indexes.

##### **NEW FILE: `database/migrations/03_user_management_schema.sql`** 🆕 CREATE
Add comprehensive user system:
```sql
-- NEW TABLES:
CREATE TABLE users (...)                         -- All user types
CREATE TABLE roles (...)                         -- Role definitions
CREATE TABLE user_roles (...)                    -- User-role assignments
CREATE TABLE teachers (...)                      -- Teacher profiles
CREATE TABLE teacher_subjects (...)              -- Teacher assignments
CREATE TABLE teacher_sections (...)              -- Section assignments
CREATE TABLE school_admins (...)                 -- Admin profiles
CREATE TABLE parent_student_relationships (...)  -- Parent-child links
CREATE TABLE user_activity_logs (...)            -- Audit trail
CREATE TABLE user_sessions (...)                 -- Session management
```

**Action Required**: Create new file with 10 tables + indexes + RLS policies.

##### **NEW FILE: `database/migrations/04_subject_enhancement.sql`** 🆕 CREATE
Enhance for all paper types and written answers:
```sql
-- NEW TABLES:
CREATE TABLE paper_components (...)        -- P1, P2, P3, P4, P5 definitions
CREATE TABLE question_parts (...)          -- Sub-parts for structured questions
CREATE TABLE mark_schemes (...)            -- Marking criteria
CREATE TABLE curriculum_exam_rules (...)   -- Exam-specific rules
CREATE TABLE question_metrics (...)        -- Performance tracking

-- ENHANCE questions table:
ALTER TABLE questions
    ADD COLUMN response_type VARCHAR(20),        -- 'mcq' or 'written'
    ADD COLUMN total_marks INTEGER,              -- Question marks
    ADD COLUMN difficulty_level VARCHAR(20),     -- easy/medium/hard
    ADD COLUMN language_code VARCHAR(10),        -- en, ne, hi, etc.
    ADD COLUMN transcription_status VARCHAR(50); -- For screenshots

-- ENHANCE student_question_history:
ALTER TABLE student_question_history
    ADD COLUMN student_response TEXT,            -- Full answer text
    ADD COLUMN response_images JSONB,            -- Scanned answer sheets
    ADD COLUMN llm_evaluation JSONB,             -- LLM grading
    ADD COLUMN llm_score DECIMAL(5,2),
    ADD COLUMN teacher_score DECIMAL(5,2),       -- Override
    ADD COLUMN final_score DECIMAL(5,2);         -- Actual awarded
```

**Action Required**: Create new file with 5 new tables + enhancements.

##### **NEW FILE: `database/migrations/05_indexes_and_constraints.sql`** 🆕 CREATE
Add RLS and performance optimizations:
```sql
-- Enable Row Level Security
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_question_history ENABLE ROW LEVEL SECURITY;

-- Create isolation policies
CREATE POLICY school_isolation_students ON students
    USING (school_id = current_setting('app.current_school_id')::INTEGER);

-- Partitioning for scale
CREATE TABLE student_question_history_2024 PARTITION OF ...;

-- Additional performance indexes
CREATE INDEX idx_students_school_user ON students(school_id, user_id);
```

**Action Required**: Create new file with RLS policies + partitioning + indexes.

---

### 2. Impact on Existing Data

#### **Critical Consideration: Data Migration Path**

**Current Data Structure**:
- 24,000+ students (currently all from "St. Xavier's College")
- 3,200+ questions (all Physics P1)
- 500,000+ student attempts

**Migration Strategy**:
```sql
-- STEP 1: Create default school
INSERT INTO schools (school_id, school_code, school_name, school_type)
VALUES (1, 'SXC', 'St. Xavier''s College', 'college');

-- STEP 2: Migrate existing data
UPDATE institutions SET school_id = 1;
UPDATE departments SET school_id = 1;
UPDATE students SET school_id = 1;

-- STEP 3: Create default curriculum
INSERT INTO curricula (curriculum_id, curriculum_code, curriculum_name)
VALUES (1, 'CAMBRIDGE_ALEVEL', 'Cambridge International A Level');

-- STEP 4: Link subjects to curriculum
UPDATE subjects SET curriculum_id = 1;

-- STEP 5: Create default users for existing students
INSERT INTO users (school_id, email, username, full_name, user_type)
SELECT 
    1 as school_id,
    CONCAT('student', student_id, '@stxaviers.edu') as email,
    CONCAT('SXC_STU_', LPAD(student_id::text, 5, '0')) as username,
    CONCAT('Student ', base_student_number) as full_name,
    'student' as user_type
FROM students;
```

**Action Required**: Write backward-compatible migration script in `scripts/migrate_existing_data.py`.

---

## 📜 PYTHON SCRIPTS LAYER CHANGES

### 1. `scripts/reset_database.py` 🔴 MAJOR REWRITE

#### **Current Implementation**
- Connects to single database
- Applies single migration file
- No backup mechanism
- No multi-environment support

#### **Required Changes**

```python
# CURRENT (simplified):
def reset_database():
    conn = psycopg2.connect(**db_params)
    with open("01_initial_schema.sql") as f:
        conn.execute(f.read())

# REQUIRED:
class DatabaseReset:
    def __init__(self, config_path='config/database.yaml'):
        self.config = self.load_config(config_path)
        self.migration_dir = Path('migrations')
    
    def create_backup(self):
        """Backup before destructive operations"""
        subprocess.run(['pg_dump', '-f', f'backup_{timestamp}.sql'])
    
    def reset_database(self, skip_backup=False):
        """Apply all migrations in order"""
        migration_files = [
            "01_initial_schema.sql",
            "02_multi_tenant_schema.sql",
            "03_user_management_schema.sql",
            "04_subject_enhancement.sql",
            "05_indexes_and_constraints.sql"
        ]
        
        for migration_file in migration_files:
            self.apply_migration(migration_file)
        
        self.setup_rls()  # Configure Row Level Security
        self.create_defaults()  # System roles, default curricula
    
    def setup_rls(self, cursor):
        """Configure Row Level Security for multi-tenancy"""
        cursor.execute("""
            ALTER TABLE students ENABLE ROW LEVEL SECURITY;
            CREATE POLICY school_isolation ON students
                USING (school_id = current_setting('app.current_school_id')::INTEGER);
        """)
```

**Action Required**: 
1. Rewrite as class-based with proper error handling
2. Add backup functionality
3. Add migration file ordering
4. Add RLS setup
5. Add default data creation (roles, curricula)
6. Add validation checks post-migration

**Estimated Effort**: 4-6 hours

---

### 2. `scripts/migrate_data.py` 🔴 MAJOR REWRITE

#### **Current Implementation**
- Hardcodes "St. Xavier's College"
- Creates only Physics subject
- No curriculum support
- No user generation
- Output: 10 normalized parquet files

#### **Required Changes**

```python
# CURRENT (simplified):
def create_normalized_schema(source_file):
    df = pd.read_csv(source_file)
    
    # Hardcoded single institution
    institutions = df[['institution_key', 'institution_name']].drop_duplicates()
    
    # Only Physics
    subjects = [{'subject_name': 'Physics', 'cambridge_code': 9702}]
    
    # Save to parquet
    institutions.to_parquet('normalized_institutions.parquet')

# REQUIRED:
class MultiSchoolDataMigrator:
    def __init__(self, schools_config_file='config/schools_config.yaml'):
        self.schools_config = self.load_schools_config(schools_config_file)
        self.curriculum_mapping = self.load_curriculum_mapping()
    
    def migrate_all_schools(self):
        """Migrate multiple schools from config"""
        # Migrate foundation
        schools_df = self.migrate_schools()
        curricula_df = self.migrate_curricula()
        school_curricula_df = self.migrate_school_curricula()
        
        # Migrate each school
        for school in self.schools_config:
            self.migrate_school_data(school)
    
    def migrate_schools(self) -> pd.DataFrame:
        """Create schools from config"""
        schools = []
        for school_config in self.schools_config['schools']:
            school = {
                'school_id': school_config['id'],
                'school_code': school_config['code'],
                'school_name': school_config['name'],
                'school_type': school_config['type'],
                'country_code': school_config['country'],
                'timezone': school_config['timezone'],
                'subscription_tier': school_config['tier']
            }
            schools.append(school)
        return pd.DataFrame(schools)
    
    def migrate_users(self, school_id, source_file):
        """Create users for students, teachers, parents, admins"""
        users = []
        
        # Students
        for student in students_df.iterrows():
            users.append({
                'school_id': school_id,
                'email': f"student{id}@{school_domain}",
                'user_type': 'student',
                ...
            })
        
        # Teachers (generated based on sections)
        for section in sections:
            users.append({
                'school_id': school_id,
                'email': f"teacher_{section}@{school_domain}",
                'user_type': 'teacher',
                ...
            })
        
        # Parents (50% of students)
        # Admins (per school)
        
        return pd.DataFrame(users)
    
    def migrate_subjects(self, school):
        """Create subjects for school's curricula"""
        subjects = []
        for curriculum_code in school.curricula:
            curriculum_subjects = self.curriculum_mapping[curriculum_code]['subjects']
            for subject in curriculum_subjects:
                subjects.append({
                    'curriculum_id': curriculum_id,
                    'subject_code': subject['code'],
                    'subject_name': subject['name'],
                    ...
                })
        return pd.DataFrame(subjects)
```

**New Configuration Required**:

Create `config/schools_config.yaml`:
```yaml
schools:
  - id: 1
    code: SXC
    name: St. Xavier's College
    type: college
    country: IN
    timezone: Asia/Kolkata
    tier: premium
    domain: stxaviers.edu
    curricula:
      - CAMBRIDGE_ALEVEL
      - CBSE
    settings:
      academic_year_start: 6
      grading_system: percentage
  
  - id: 2
    code: CIS
    name: Cambridge International School
    type: high_school
    country: GB
    timezone: Europe/London
    tier: enterprise
    domain: cambridge-intl.edu.uk
    curricula:
      - CAMBRIDGE_IGCSE
      - CAMBRIDGE_ALEVEL
      - IB_DIPLOMA
```

Create `config/subjects_mapping.yaml`:
```yaml
CAMBRIDGE_ALEVEL:
  id: 1
  name: Cambridge International A Level
  board: Cambridge Assessment International Education
  subjects:
    physics:
      code: "9702"
      name: Physics
      components:
        P1: {type: multiple_choice, duration: 45, marks: 40}
        P2: {type: structured, duration: 75, marks: 60}
        P3: {type: practical, duration: 120, marks: 40}
        P4: {type: structured, duration: 105, marks: 100}
        P5: {type: planning, duration: 75, marks: 30}
    chemistry:
      code: "9701"
      name: Chemistry
      components:
        P1: {type: multiple_choice, duration: 45, marks: 40}
        # ... similar structure
```

**Action Required**:
1. Complete rewrite as class-based architecture
2. Create YAML config loaders
3. Implement multi-school processing
4. Add user generation logic
5. Add teacher-subject-section assignment logic
6. Add parent-student relationship generation
7. Update output to include 15+ new parquet files

**Estimated Effort**: 12-16 hours

---

### 3. `scripts/load_to_postgres.py` 🟡 MODERATE CHANGES

#### **Current Implementation**
- Loads 10 parquet files sequentially
- No school context setting
- No RLS awareness
- No vector data cleaning

#### **Required Changes**

```python
# CURRENT (simplified):
def load_to_postgres():
    tables = ['institutions', 'departments', ...]
    for table in tables:
        df = pd.read_parquet(f'normalized_{table}.parquet')
        df.to_sql(table, conn, if_exists='append')

# REQUIRED:
class MultiTenantPostgreSQLLoader:
    def __init__(self):
        self.load_order = [
            # Foundation
            'schools',
            'curricula',
            'school_curricula',
            
            # Users and roles
            'users',
            'roles',
            'user_roles',
            
            # Institutional hierarchy (with school_id)
            'institutions',
            'departments',
            ...
            
            # Questions (SHARED across schools - no school_id!)
            'questions',
            
            # People
            'students',
            'teachers',
            ...
        ]
    
    def set_school_context(self, school_id: int):
        """Set RLS context for school-specific operations"""
        with psycopg2.connect(**self.db_params) as conn:
            cursor = conn.cursor()
            cursor.execute("SET app.current_school_id = %s", (school_id,))
    
    def load_with_school_isolation(self, school_id: int, table_name: str):
        """Load data with proper school context"""
        self.set_school_context(school_id)
        
        # Add school_id ONLY to school-specific tables
        # Questions are SHARED - do NOT add school_id!
        if table_name in ['students', 'teachers', 'admins']:
            df['school_id'] = school_id
        
        return self.load_table_from_parquet(table_name, df)
    
    def create_default_roles(self, school_id: int):
        """Create standard roles for each school"""
        default_roles = [
            {
                'school_id': school_id,
                'role_name': 'student',
                'permissions': {'can_practice': True, 'can_view_progress': True}
            },
            {
                'school_id': school_id,
                'role_name': 'teacher',
                'permissions': {'can_grade': True, 'can_view_analytics': True}
            },
            ...
        ]
        for role in default_roles:
            self.create_role(role)
```

**Action Required**:
1. Add school context management
2. Add role creation logic
3. Update load order for dependencies
4. Add validation for each table load
5. Add progress reporting
6. Handle vector data properly (already working, preserve)

**Estimated Effort**: 6-8 hours

---

### 4. **NEW SCRIPT: `scripts/migrate_existing_data.py`** 🆕 CREATE

For backward compatibility with current production data:

```python
#!/usr/bin/env python3
"""
Migrate existing single-tenant data to multi-tenant schema
Preserves all current data while adding multi-tenant capabilities
"""

class ExistingDataMigrator:
    def migrate_to_multitenant(self):
        """One-time migration script"""
        
        # 1. Create default school
        self.create_default_school()
        
        # 2. Update existing tables with school_id
        self.add_school_ids_to_existing_data()
        
        # 3. Create users for existing students
        self.create_users_from_students()
        
        # 4. Create default curriculum
        self.create_default_curriculum()
        
        # 5. Validate migration
        self.validate_migration()
```

**Action Required**: Create new migration script for production deployment.

**Estimated Effort**: 4-6 hours

---

## 🔌 API LAYER CHANGES

### 1. `api/routes.py` 🟡 MODERATE CHANGES

#### **Required Additions**

##### **A. Multi-Tenant Authentication Middleware**

```python
# NEW: Add to middleware stack
from api.middleware import SchoolContextMiddleware

app.add_middleware(SchoolContextMiddleware)

# Implementation in middleware.py:
class SchoolContextMiddleware:
    async def __call__(self, request: Request, call_next):
        # Extract school from JWT or header
        school_id = request.headers.get('X-School-ID')
        if not school_id:
            school_id = extract_from_jwt(request.headers.get('Authorization'))
        
        # Set database context
        request.state.school_id = school_id
        request.state.db.execute("SET app.current_school_id = %s", (school_id,))
        
        response = await call_next(request)
        return response
```

##### **B. New School Management Endpoints**

```python
@app.get("/api/v2/schools")
async def list_schools(user: User = Depends(require_super_admin)):
    """List all schools (super admin only)"""
    return school_service.get_all_schools()

@app.get("/api/v2/schools/{school_id}")
async def get_school_details(school_id: int, user: User = Depends(require_admin)):
    """Get school details"""
    return school_service.get_school(school_id)

@app.put("/api/v2/schools/{school_id}/settings")
async def update_school_settings(
    school_id: int, 
    settings: SchoolSettings,
    user: User = Depends(require_admin)
):
    """Update school configuration"""
    return school_service.update_settings(school_id, settings)
```

##### **C. New User Management Endpoints**

```python
@app.post("/api/v2/users")
async def create_user(
    user_data: UserCreate,
    school_context: SchoolContext = Depends(get_school_context)
):
    """Create new user (student/teacher/parent/admin)"""
    return user_service.create_user(user_data, school_context.school_id)

@app.get("/api/v2/users")
async def list_users(
    user_type: Optional[str] = None,
    school_context: SchoolContext = Depends(get_school_context)
):
    """List users (filtered by school context)"""
    return user_service.get_users(school_context.school_id, user_type)

@app.post("/api/v2/users/{user_id}/roles")
async def assign_roles(
    user_id: int,
    roles: List[str],
    admin: User = Depends(require_admin)
):
    """Assign roles to user"""
    return user_service.assign_roles(user_id, roles)
```

##### **D. New Curriculum Endpoints**

```python
@app.get("/api/v2/curricula")
async def list_curricula():
    """List available curricula"""
    return curriculum_service.get_all_curricula()

@app.get("/api/v2/curricula/{curriculum_id}/subjects")
async def get_curriculum_subjects(curriculum_id: int):
    """Get subjects for a curriculum"""
    return curriculum_service.get_subjects(curriculum_id)

@app.get("/api/v2/subjects/{subject_id}/components")
async def get_paper_components(subject_id: int):
    """Get paper components (P1, P2, P3, etc.)"""
    return subject_service.get_components(subject_id)
```

##### **E. Enhanced Question Endpoints**

```python
@app.post("/api/v2/questions/transcribe")
async def transcribe_question(
    image: UploadFile,
    metadata: QuestionMetadata
):
    """Transcribe question from screenshot using LLM"""
    return question_service.transcribe_question(image, metadata)

@app.post("/api/v2/questions/{question_id}/evaluate")
async def evaluate_written_answer(
    question_id: str,
    student_answer: str,
    student_id: str
):
    """Evaluate written answer using LLM"""
    return answer_service.evaluate_answer(question_id, student_answer, student_id)
```

##### **F. Modified Existing Endpoints**

Update all existing endpoints to respect school context:

```python
# BEFORE:
@app.get("/student/{student_id}/performance")
async def get_student_performance(student_id: str):
    return student_service.get_performance(student_id)

# AFTER:
@app.get("/student/{student_id}/performance")
async def get_student_performance(
    student_id: str,
    school_context: SchoolContext = Depends(get_school_context)
):
    # RLS automatically filters by school_id
    # No code changes needed if RLS is properly configured
    return student_service.get_performance(student_id)
```

**Action Required**:
1. Add 15+ new endpoints
2. Add school context middleware
3. Add authentication dependencies
4. Update all existing endpoints to include school context
5. Add proper error handling for cross-school access attempts

**Estimated Effort**: 10-12 hours

---

### 2. `api/schemas.py` 🟡 MODERATE CHANGES

Add new Pydantic models:

```python
# NEW MODELS:

class SchoolCreate(BaseModel):
    school_code: str
    school_name: str
    school_type: str
    country_code: str
    timezone: str
    subscription_tier: str

class SchoolResponse(SchoolCreate):
    school_id: int
    is_active: bool
    created_at: datetime

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    user_type: str  # 'student', 'teacher', 'parent', 'admin'
    school_id: int

class UserResponse(UserCreate):
    user_id: int
    is_active: bool
    email_verified: bool
    last_login: Optional[datetime]

class CurriculumResponse(BaseModel):
    curriculum_id: int
    curriculum_code: str
    curriculum_name: str
    curriculum_board: str
    country_code: str

class PaperComponentResponse(BaseModel):
    component_id: int
    component_code: str  # P1, P2, P3, etc.
    component_name: str
    component_type: str  # multiple_choice, structured, practical
    duration_minutes: int
    total_marks: int
    weightage_percent: float

class QuestionTranscriptionRequest(BaseModel):
    curriculum: str
    subject: str
    paper_type: str
    language: str = "en"
    needs_llm: bool = True

class WrittenAnswerEvaluationRequest(BaseModel):
    question_id: str
    student_answer: str
    mark_scheme_id: int

class WrittenAnswerEvaluationResponse(BaseModel):
    is_correct: bool
    marks_awarded: float
    max_marks: float
    llm_feedback: str
    llm_confidence: float
    breakdown: Dict[str, Any]
```

**Action Required**:
1. Add 15+ new Pydantic models
2. Update existing models with school_id fields where appropriate
3. Add validation for school-curriculum relationships
4. Add enum definitions for user types, paper types, etc.

**Estimated Effort**: 4-6 hours

---

## 🛠️ SERVICES LAYER CHANGES

### 1. `services/student_service.py` 🟡 MODERATE CHANGES

#### **Current Implementation**
- No school awareness
- Simple performance analysis
- No user integration

#### **Required Changes**

```python
# CURRENT:
class StudentService:
    def get_student_by_id(self, student_id: str):
        query = "SELECT * FROM students WHERE student_id = %s"
        return self.db.execute(query, (student_id,))

# REQUIRED:
class StudentService:
    def get_student_by_id(self, student_id: str, school_context: SchoolContext):
        # RLS automatically filters by school
        query = """
            SELECT s.*, u.email, u.full_name, u.user_type
            FROM students s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.student_id = %s
        """
        # RLS ensures only school's students are visible
        return self.db.execute(query, (student_id,))
    
    def get_student_with_curriculum(self, student_id: str):
        """Get student with their curriculum information"""
        query = """
            SELECT s.*, c.curriculum_name, c.curriculum_code
            FROM students s
            LEFT JOIN curricula c ON s.curriculum_id = c.curriculum_id
            WHERE s.student_id = %s
        """
        return self.db.execute(query, (student_id,))
```

**Action Required**:
1. Add user integration to all student queries
2. Add curriculum context
3. Update performance analysis to respect school boundaries
4. Add parent access methods

**Estimated Effort**: 4-6 hours

---

### 2. **NEW SERVICE: `services/user_service.py`** 🆕 CREATE

```python
class UserService:
    def __init__(self, db_manager):
        self.db = db_manager
    
    def create_user(self, user_data: UserCreate, school_id: int) -> User:
        """Create new user with proper role assignment"""
        # Hash password
        password_hash = hash_password(user_data.password)
        
        # Create user
        user = self.db.execute("""
            INSERT INTO users (school_id, email, username, full_name, user_type, password_hash)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (school_id, user_data.email, user_data.username, 
              user_data.full_name, user_data.user_type, password_hash))
        
        # Assign default role
        self.assign_default_role(user.user_id, user.user_type, school_id)
        
        return user
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user and return user object"""
        user = self.get_user_by_email(email)
        if user and verify_password(password, user.password_hash):
            # Update last_login
            self.update_last_login(user.user_id)
            return user
        return None
    
    def assign_roles(self, user_id: int, role_names: List[str]):
        """Assign multiple roles to user"""
        for role_name in role_names:
            role = self.get_role_by_name(role_name)
            if role:
                self.db.execute("""
                    INSERT INTO user_roles (user_id, role_id, assigned_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT DO NOTHING
                """, (user_id, role.role_id))
    
    def get_user_permissions(self, user_id: int) -> Dict[str, Any]:
        """Get aggregated permissions from all user roles"""
        roles = self.db.execute("""
            SELECT r.permissions
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.role_id
            WHERE ur.user_id = %s AND ur.is_active = true
        """, (user_id,))
        
        # Merge permissions
        combined_permissions = {}
        for role in roles:
            combined_permissions.update(role.permissions)
        
        return combined_permissions
```

**Action Required**: Create complete user management service.

**Estimated Effort**: 8-10 hours

---

### 3. **NEW SERVICE: `services/school_service.py`** 🆕 CREATE

```python
class SchoolService:
    def create_school(self, school_data: SchoolCreate) -> School:
        """Create new school with default setup"""
        # Create school
        school = self.db.execute("""
            INSERT INTO schools (school_code, school_name, school_type, ...)
            VALUES (%s, %s, %s, ...)
            RETURNING *
        """, (...))
        
        # Create default roles for school
        self.create_default_roles(school.school_id)
        
        # Create default admin user
        self.create_admin_user(school.school_id)
        
        return school
    
    def get_school_statistics(self, school_id: int) -> Dict[str, Any]:
        """Get comprehensive school statistics"""
        return {
            'total_students': self.count_students(school_id),
            'total_teachers': self.count_teachers(school_id),
            'total_subjects': self.count_subjects(school_id),
            'total_attempts': self.count_question_attempts(school_id),
            'avg_performance': self.calculate_avg_performance(school_id)
        }
```

**Action Required**: Create school management service.

**Estimated Effort**: 6-8 hours

---

### 4. **NEW SERVICE: `services/curriculum_service.py`** 🆕 CREATE

```python
class CurriculumService:
    def get_curriculum_subjects(self, curriculum_id: int) -> List[Subject]:
        """Get all subjects for a curriculum"""
        return self.db.execute("""
            SELECT * FROM subjects
            WHERE curriculum_id = %s AND is_active = true
        """, (curriculum_id,))
    
    def get_paper_components(self, subject_id: int) -> List[PaperComponent]:
        """Get all paper components for a subject (P1, P2, etc.)"""
        return self.db.execute("""
            SELECT * FROM paper_components
            WHERE subject_id = %s AND is_active = true
            ORDER BY component_code
        """, (subject_id,))
    
    def get_exam_rules(self, curriculum_id: int, exam_type: str) -> Dict[str, Any]:
        """Get exam-specific rules (negative marking, time limits, etc.)"""
        rules = self.db.execute("""
            SELECT exam_rules FROM curriculum_exam_rules
            WHERE curriculum_id = %s AND exam_type = %s
        """, (curriculum_id, exam_type))
        
        return rules.exam_rules if rules else {}
```

**Action Required**: Create curriculum management service.

**Estimated Effort**: 4-6 hours

---

### 5. `services/question_service.py` 🟡 MODERATE CHANGES

#### **Required Enhancements**

```python
# ADD: Screenshot transcription support
class QuestionService:
    def transcribe_question_from_image(
        self, 
        image_path: str, 
        metadata: QuestionMetadata
    ) -> Question:
        """Transcribe question using LLM (GPT-4 Vision)"""
        # 1. Upload to CDN
        image_url = self.upload_to_cdn(image_path)
        
        # 2. Call LLM for transcription
        transcription = self.llm_client.transcribe_image(
            image_url, 
            language=metadata.language,
            curriculum=metadata.curriculum
        )
        
        # 3. Generate embeddings
        embeddings = self.vector_encoder.encode_text(transcription)
        
        # 4. Save to database
        question = self.create_question({
            'combined_text': transcription,
            'images': [image_url],
            'openai_embedding': embeddings['openai'],
            'response_type': metadata.response_type,
            'language_code': metadata.language,
            'transcription_status': 'completed'
        })
        
        return question
    
    def get_questions_by_component(self, component_id: int) -> List[Question]:
        """Get questions for a specific paper component (P1, P2, etc.)"""
        return self.db.execute("""
            SELECT q.* FROM questions q
            JOIN papers p ON q.paper_id = p.paper_id
            WHERE p.component_id = %s
        """, (component_id,))
```

**Action Required**:
1. Add LLM transcription support
2. Add component-based filtering
3. Add multi-language support
4. Add response_type handling (mcq vs written)

**Estimated Effort**: 6-8 hours

---

### 6. **NEW SERVICE: `services/answer_evaluation_service.py`** 🆕 CREATE

```python
class AnswerEvaluationService:
    def __init__(self, db_manager, llm_client):
        self.db = db_manager
        self.llm = llm_client
    
    async def evaluate_written_answer(
        self,
        question_id: str,
        student_answer: str,
        student_id: str
    ) -> EvaluationResult:
        """Evaluate written answer using LLM"""
        
        # 1. Get question and mark scheme
        question = self.db.get_question_by_id(question_id)
        mark_scheme = self.db.get_mark_scheme(question_id)
        
        # 2. Build evaluation prompt
        prompt = self._build_evaluation_prompt(
            question.combined_text,
            student_answer,
            mark_scheme.marking_criteria,
            mark_scheme.total_marks
        )
        
        # 3. Call LLM for evaluation
        evaluation = await self.llm.evaluate(prompt)
        
        # 4. Save evaluation result
        result = self.db.execute("""
            INSERT INTO student_question_history (
                enrollment_id, internal_question_id, student_response,
                llm_evaluation, llm_score, llm_confidence, llm_feedback,
                grading_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'auto_graded')
            RETURNING *
        """, (
            enrollment_id, question.internal_question_id, student_answer,
            evaluation['breakdown'], evaluation['score'], 
            evaluation['confidence'], evaluation['feedback']
        ))
        
        return EvaluationResult(
            marks_awarded=evaluation['score'],
            max_marks=mark_scheme.total_marks,
            feedback=evaluation['feedback'],
            confidence=evaluation['confidence'],
            breakdown=evaluation['breakdown']
        )
    
    def _build_evaluation_prompt(self, question, answer, criteria, marks):
        """Build curriculum-aware evaluation prompt"""
        return f"""
        Question: {question}
        Total Marks: {marks}
        
        Student's Answer:
        {answer}
        
        Marking Criteria:
        {json.dumps(criteria, indent=2)}
        
        Provide:
        1. Suggested score out of {marks}
        2. Point-by-point evaluation
        3. Specific feedback
        4. Confidence level (0-1)
        """
```

**Action Required**: Create LLM-based answer evaluation service.

**Estimated Effort**: 10-12 hours

---

## 📁 CONFIGURATION LAYER CHANGES

### 1. `config/config.py` 🟢 MINOR CHANGES

#### **Required Additions**

```python
# ADD: Multi-school configuration
@dataclass
class MultiTenantConfig:
    enable_school_isolation: bool = True
    allow_cross_school_access: bool = False  # For super admins only
    default_school_id: Optional[int] = None
    
# ADD to SystemConfig:
@dataclass
class SystemConfig:
    # ... existing config ...
    multi_tenant: MultiTenantConfig
    
    # ADD: LLM Configuration
    llm_provider: str = "openai"  # openai, anthropic, etc.
    llm_model: str = "gpt-4-vision-preview"
    llm_api_key: str = ""
    
    # ADD: CDN Configuration
    cdn_provider: str = "cloudflare"  # cloudflare, s3, local
    cdn_base_url: str = ""
    cdn_api_key: str = ""
```

**Action Required**:
1. Add multi-tenant settings
2. Add LLM configuration
3. Add CDN configuration
4. Update environment profiles

**Estimated Effort**: 2-3 hours

---

### 2. **NEW FILE: `config/schools_config.yaml`** 🆕 CREATE

See detailed content in migration script section above.

**Action Required**: Create schools configuration file.

**Estimated Effort**: 1-2 hours

---

### 3. **NEW FILE: `config/subjects_mapping.yaml`** 🆕 CREATE

See detailed content in migration script section above.

**Action Required**: Create curriculum-subject mapping file.

**Estimated Effort**: 2-3 hours

---

## 🤖 ML/VECTOR LAYER CHANGES

### `ml/vector_encoder.py`, `ml/vector_operations_manager.py` 🟢 MINIMAL CHANGES

#### **Good News**: Vector operations remain largely unchanged!

The vector embeddings and similarity search are **school-agnostic** by design:
- Questions are shared across schools
- Embeddings remain the same
- Vector indexes unchanged
- Similarity functions work as-is

#### **Only Required Changes**:

```python
# In recommendation generation:
def recommend_questions_for_student(self, student_id: str):
    # OLD: No school awareness
    similar_questions = self.vector_ops.find_similar(embedding)
    
    # NEW: Filter by student's curriculum (not school!)
    student_curriculum = self.get_student_curriculum(student_id)
    similar_questions = self.vector_ops.find_similar(
        embedding,
        filters={'curriculum_id': student_curriculum.curriculum_id}
    )
```

**Action Required**:
1. Add curriculum-based filtering
2. Preserve all existing vector operations
3. No changes to embedding dimensions or indexes

**Estimated Effort**: 2-3 hours

---

## 🔐 AUTHENTICATION & AUTHORIZATION (NEW LAYER)

### **NEW MODULE: `auth/`** 🆕 CREATE

Create new authentication module:

```
auth/
├── __init__.py
├── jwt_handler.py       # JWT token generation/validation
├── password_handler.py  # Password hashing/verification
├── permissions.py       # Permission checking
└── dependencies.py      # FastAPI dependencies
```

#### **`auth/jwt_handler.py`**

```python
from jose import JWTError, jwt
from datetime import datetime, timedelta

class JWTHandler:
    def create_access_token(self, user: User, school_id: int) -> str:
        """Create JWT with user and school context"""
        payload = {
            'user_id': user.user_id,
            'email': user.email,
            'user_type': user.user_type,
            'school_id': school_id,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return token
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT and extract payload"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
```

#### **`auth/dependencies.py`**

```python
from fastapi import Depends, HTTPException, Header

async def get_current_user(
    authorization: str = Header(None)
) -> User:
    """Get current user from JWT token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    payload = jwt_handler.verify_token(token)
    
    user = user_service.get_user_by_id(payload['user_id'])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require admin role"""
    if user.user_type not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

async def require_teacher(user: User = Depends(get_current_user)) -> User:
    """Require teacher role"""
    if user.user_type not in ['teacher', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Teacher access required")
    return user

async def get_school_context(
    user: User = Depends(get_current_user),
    x_school_id: Optional[int] = Header(None)
) -> SchoolContext:
    """Get school context from header or user"""
    school_id = x_school_id or user.school_id
    
    # Verify user has access to this school
    if not user_service.has_school_access(user.user_id, school_id):
        raise HTTPException(status_code=403, detail="No access to this school")
    
    return SchoolContext(school_id=school_id, user=user)
```

**Action Required**: Create complete authentication module.

**Estimated Effort**: 8-10 hours

---

## 📊 TESTING CHANGES

### **NEW: Multi-Tenant Test Suite** 🆕 CREATE

Create `tests/test_multi_tenant.py`:

```python
import pytest

class TestSchoolIsolation:
    def test_student_cannot_see_other_school_data(self):
        """Test RLS prevents cross-school data access"""
        # Create two schools
        school1 = create_test_school("School A")
        school2 = create_test_school("School B")
        
        # Set context to school1
        set_school_context(school1.school_id)
        students_school1 = get_students()
        
        # Switch to school2
        set_school_context(school2.school_id)
        students_school2 = get_students()
        
        # Verify no overlap
        assert len(set(students_school1) & set(students_school2)) == 0
    
    def test_questions_are_shared(self):
        """Test that questions are visible across schools"""
        school1_physics = get_questions(school_id=1, subject="physics")
        school2_physics = get_questions(school_id=2, subject="physics")
        
        # Same questions should be returned
        assert school1_physics == school2_physics
    
    def test_teacher_can_only_grade_own_school(self):
        """Test teachers can't grade other school's students"""
        teacher = create_teacher(school_id=1)
        student = create_student(school_id=2)
        
        with pytest.raises(PermissionError):
            teacher.grade_student(student.student_id)

class TestUserManagement:
    def test_create_all_user_types(self):
        """Test creating students, teachers, parents, admins"""
        school = create_test_school()
        
        student = create_user(school_id=school.id, user_type='student')
        teacher = create_user(school_id=school.id, user_type='teacher')
        parent = create_user(school_id=school.id, user_type='parent')
        admin = create_user(school_id=school.id, user_type='admin')
        
        assert all([student, teacher, parent, admin])
    
    def test_parent_student_relationship(self):
        """Test parent can view their children's progress"""
        parent = create_user(user_type='parent')
        student1 = create_user(user_type='student')
        student2 = create_user(user_type='student')
        
        link_parent_student(parent.id, student1.id)
        link_parent_student(parent.id, student2.id)
        
        children = get_parent_children(parent.id)
        assert len(children) == 2
        
        progress = get_student_progress(student1.id, viewer=parent)
        assert progress is not None

class TestCurriculumSupport:
    def test_multiple_curricula_per_school(self):
        """Test school can have multiple curricula"""
        school = create_test_school()
        
        add_curriculum_to_school(school.id, 'CAMBRIDGE_ALEVEL')
        add_curriculum_to_school(school.id, 'IB_DIPLOMA')
        
        curricula = get_school_curricula(school.id)
        assert len(curricula) == 2
    
    def test_paper_components(self):
        """Test P1-P5 component support"""
        physics = get_subject('physics')
        components = get_paper_components(physics.id)
        
        assert 'P1' in [c.component_code for c in components]
        assert 'P2' in [c.component_code for c in components]
        # ... etc.
```

**Action Required**: Create comprehensive test suite for multi-tenant features.

**Estimated Effort**: 12-15 hours

---

## 📈 DEPLOYMENT & MIGRATION STRATEGY

### Phase-Based Rollout

#### **Phase 1: Database Schema (Week 1)**
1. **Monday-Tuesday**: Create all 5 migration files
2. **Wednesday**: Test migrations on staging
3. **Thursday**: Create backup and migration scripts
4. **Friday**: Execute on development environment

**Deliverables**:
- 5 SQL migration files
- Backup script
- Validation scripts

#### **Phase 2: Data Migration Scripts (Week 2)**
1. **Monday-Tuesday**: Rewrite `reset_database.py`
2. **Wednesday-Thursday**: Rewrite `migrate_data.py`
3. **Friday**: Update `load_to_postgres.py` + create config files

**Deliverables**:
- Updated Python scripts
- `schools_config.yaml`
- `subjects_mapping.yaml`

#### **Phase 3: Services & API (Week 3)**
1. **Monday**: Create user/school/curriculum services
2. **Tuesday**: Update student service
3. **Wednesday-Thursday**: Update API routes + add new endpoints
4. **Friday**: Add authentication module

**Deliverables**:
- 3 new services
- 5 updated services
- 15+ new API endpoints
- Auth module

#### **Phase 4: Testing & Validation (Week 4)**
1. **Monday**: Write test suite
2. **Tuesday-Wednesday**: Integration testing
3. **Thursday**: Performance testing
4. **Friday**: Documentation

**Deliverables**:
- Complete test suite
- Performance benchmarks
- Migration documentation

---

## 🔢 SUMMARY STATISTICS

### Development Effort Breakdown

| Component | Status | Estimated Hours |
|-----------|--------|-----------------|
| **Database Migrations** | 🔴 Major | 20-24h |
| **Python Scripts** | 🔴 Major | 26-34h |
| **API Layer** | 🟡 Moderate | 18-24h |
| **Services Layer** | 🟡 Moderate | 44-56h |
| **Configuration** | 🟢 Minor | 5-8h |
| **ML/Vector Ops** | 🟢 Minimal | 2-3h |
| **Authentication** | 🆕 New | 8-10h |
| **Testing** | 🆕 New | 12-15h |
| **Documentation** | 🆕 New | 6-8h |
| **Total** | | **141-182 hours** |

**Team Estimate**: 
- 1 developer full-time: 4-5 weeks
- 2 developers: 2-3 weeks
- 3 developers: 1.5-2 weeks

---

## ⚠️ CRITICAL CONSIDERATIONS

### 1. **Data Migration Risk Assessment**

**HIGH RISK**: Migrating 500,000+ student attempt records
- **Mitigation**: Create comprehensive backup before migration
- **Rollback Plan**: Keep old schema available for 2 weeks
- **Testing**: Test on copy of production data first

### 2. **Performance Impact**

**CONCERN**: RLS policies may add query overhead
- **Mitigation**: Extensive performance testing
- **Benchmark Target**: <10% performance degradation
- **Fallback**: Can disable RLS for performance-critical queries

### 3. **Backward Compatibility**

**REQUIREMENT**: Existing API clients must continue to work
- **Solution**: Keep all existing endpoints functional
- **Strategy**: Add `/api/v2/` endpoints for new features
- **Timeline**: Deprecate v1 after 6 months

### 4. **LLM Costs**

**CONCERN**: LLM transcription and evaluation costs
- **Mitigation**: Cache transcriptions aggressively
- **Budget**: Estimate $0.01-0.05 per question transcription
- **Alternative**: Batch processing during off-hours

---

## 🎯 PRIORITIZED IMPLEMENTATION ORDER

### Must-Have for MVP (Week 1-2)
1. ✅ Database migrations (all 5 files)
2. ✅ Multi-tenant data migration scripts
3. ✅ Basic school/user/curriculum services
4. ✅ RLS configuration
5. ✅ API authentication

### Should-Have for Beta (Week 3)
6. ✅ Complete API endpoints
7. ✅ Teacher/parent functionality
8. ✅ Paper component support (P2-P5)
9. ✅ Basic LLM transcription

### Nice-to-Have for v1.0 (Week 4)
10. ✅ LLM answer evaluation
11. ✅ Multi-language support
12. ✅ Advanced analytics per school
13. ✅ Comprehensive testing

---

## 📝 CHECKLIST FOR IMPLEMENTATION

### Database
- [ ] Create 5 migration SQL files
- [ ] Test migrations on empty database
- [ ] Test migrations on copy of production
- [ ] Create rollback scripts
- [ ] Document schema changes

### Python Scripts
- [ ] Rewrite `reset_database.py`
- [ ] Rewrite `migrate_data.py`
- [ ] Update `load_to_postgres.py`
- [ ] Create `migrate_existing_data.py`
- [ ] Create `schools_config.yaml`
- [ ] Create `subjects_mapping.yaml`

### Services
- [ ] Create `user_service.py`
- [ ] Create `school_service.py`
- [ ] Create `curriculum_service.py`
- [ ] Create `answer_evaluation_service.py`
- [ ] Update `student_service.py`
- [ ] Update `question_service.py`

### API
- [ ] Add school management endpoints (3)
- [ ] Add user management endpoints (5)
- [ ] Add curriculum endpoints (3)
- [ ] Add question enhancement endpoints (2)
- [ ] Update existing endpoints for school context (10+)
- [ ] Add authentication middleware

### Authentication
- [ ] Create `auth/` module
- [ ] Implement JWT handling
- [ ] Implement password hashing
- [ ] Create permission system
- [ ] Add API dependencies

### Testing
- [ ] School isolation tests
- [ ] User management tests
- [ ] Curriculum tests
- [ ] RLS tests
- [ ] Integration tests
- [ ] Performance tests

### Documentation
- [ ] API documentation update
- [ ] Migration guide
- [ ] Configuration guide
- [ ] Deployment guide

---

## 🚀 GETTING STARTED

### Day 1 Action Plan

1. **Morning**: Create database migrations
   ```bash
   cd database/migrations
   # Create files 01-05 based on expand_database.md
   ```

2. **Afternoon**: Test migrations
   ```bash
   cd scripts
   python reset_database.py --test
   ```

3. **Evening**: Begin `migrate_data.py` rewrite
   ```bash
   # Create MultiSchoolDataMigrator class
   # Implement migrate_schools() method
   ```

### Day 2 Action Plan

1. Continue `migrate_data.py`
2. Create configuration YAML files
3. Test multi-school data generation

**Continue with systematic implementation following the 4-week roadmap...**

---

## 📞 SUPPORT & QUESTIONS

For questions about this implementation plan:
1. Review `expand_database.md` for detailed specifications
2. Check existing code comments for context
3. Test each component in isolation before integration
4. Document any deviations from this plan

**End of Report**

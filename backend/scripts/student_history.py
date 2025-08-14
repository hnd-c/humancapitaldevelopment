import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# Load question index from the combined questions parquet file
print("🔍 Loading questions data...")
questions_df = pd.read_parquet("../combined_questions.parquet")

# Reset index and keep only the required columns for question identification
questions_df = questions_df.reset_index(drop=True)[["paper_number", "question_number"]]

# Create question_id from paper_number and question_number
questions_df["question_id"] = questions_df["paper_number"].astype(str) + "_" + questions_df["question_number"].astype(str)

print(f"✅ Loaded {len(questions_df)} questions from {questions_df['paper_number'].nunique()} papers")

# Device types for realistic distribution
device_types = ["desktop", "mobile", "tablet"]
device_weights = [0.6, 0.3, 0.1]  # Desktop most common, then mobile, then tablet

# Institutional hierarchy configuration
# Structure: Institution -> Department -> Year -> Section -> Subject -> Paper Component
INSTITUTIONS = {
    "st_xaviers": {
        "name": "St. Xavier's College",
        "code": "SXC",
        "departments": {
            "a_level": {
                "name": "A-Level",
                "code": "AL",
                "years": {
                    "year_1": {
                        "name": "Year 1",
                        "code": "Y1",
                        "sections": {
                            "section_b": {
                                "name": "Section B",
                                "code": "B",
                                "academic_year": "2024-2025",
                                "subjects": {
                                    "physics": {
                                        "name": "Physics",
                                        "code": "PHY",
                                        "subject_code": "9702",  # Cambridge Physics code
                                        "paper_components": {
                                            "p1": {
                                                "name": "Paper 1 - Multiple Choice",
                                                "code": "P1",
                                                "description": "Multiple Choice Questions",
                                                "duration_minutes": 45,
                                                "max_marks": 40,
                                                "has_data": True  # We have data for P1
                                            },
                                            "p2": {
                                                "name": "Paper 2 - AS Level Structured Questions",
                                                "code": "P2",
                                                "description": "Structured Questions",
                                                "duration_minutes": 75,
                                                "max_marks": 60,
                                                "has_data": False  # No data yet
                                            },
                                            "p3": {
                                                "name": "Paper 3 - Advanced Practical Skills",
                                                "code": "P3",
                                                "description": "Practical Skills",
                                                "duration_minutes": 120,
                                                "max_marks": 40,
                                                "has_data": False  # No data yet
                                            },
                                            "p4": {
                                                "name": "Paper 4 - A Level Structured Questions",
                                                "code": "P4",
                                                "description": "Advanced Structured Questions",
                                                "duration_minutes": 105,
                                                "max_marks": 100,
                                                "has_data": False  # No data yet
                                            },
                                            "p5": {
                                                "name": "Paper 5 - Planning, Analysis and Evaluation",
                                                "code": "P5",
                                                "description": "Planning, Analysis and Evaluation",
                                                "duration_minutes": 75,
                                                "max_marks": 30,
                                                "has_data": False  # No data yet
                                            }
                                        },
                                        "students": 30
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

def generate_realistic_timestamp(days_back_max=30):
    """Generate a random timestamp within the last N days"""
    days_back = random.uniform(0, days_back_max)
    return datetime.now() - timedelta(days=days_back)

def generate_confidence_level():
    """Generate raw confidence level as student would self-report (independent of correctness)"""
    # Students can be overconfident or underconfident regardless of correctness
    return random.choices([1, 2, 3, 4, 5], weights=[0.1, 0.2, 0.4, 0.2, 0.1])[0]

def generate_student_ability():
    """Generate student ability level that affects their performance patterns"""
    # Low, Medium-Low, Medium, Medium-High, High
    return random.choices(
        ["low", "medium_low", "medium", "medium_high", "high"],
        weights=[0.15, 0.2, 0.3, 0.2, 0.15]
    )[0]

def get_status_probabilities(ability_level: str) -> List[float]:
    """Get status probabilities based on student ability"""
    ability_probs = {
        "low": [0.2, 0.7, 0.1],        # [correct, wrong, skipped]
        "medium_low": [0.3, 0.6, 0.1],
        "medium": [0.4, 0.5, 0.1],
        "medium_high": [0.55, 0.4, 0.05],
        "high": [0.7, 0.25, 0.05]
    }
    return ability_probs[ability_level]

def maybe_generate_history(question_id: str, student_ability: str, prob_attempted=0.05) -> List[Dict]:
    """Generate history for a question with enhanced attributes"""
    if random.random() > prob_attempted:
        return None

    num_attempts = random.randint(1, 3)
    base_timestamp = generate_realistic_timestamp()
    device_type = random.choices(device_types, weights=device_weights)[0]

    status_probs = get_status_probabilities(student_ability)

    history_records = []
    for i in range(num_attempts):
        status = random.choices(
            ["correct", "wrong", "skipped"],
            weights=status_probs
        )[0]

        # Generate time spent based on status and ability
        if status == "skipped":
            time_spent = round(random.uniform(5, 30), 2)
        elif status == "correct":
            # Higher ability students might solve faster when correct
            base_time = 120 if student_ability in ["high", "medium_high"] else 150
            time_spent = round(random.uniform(20, base_time), 2)
        else:  # wrong
            # Lower ability students might spend more time on wrong answers
            base_time = 180 if student_ability in ["low", "medium_low"] else 150
            time_spent = round(random.uniform(15, base_time + 60), 2)

        # Add some time between attempts (seconds to minutes)
        attempt_timestamp = base_timestamp + timedelta(seconds=random.uniform(0, 3600 * i))

        record = {
            "question_id": question_id,
            "attempt_number": i + 1,
            "status": status,
            "time_spent_sec": time_spent,
            "timestamp": attempt_timestamp,
            "confidence_level": generate_confidence_level(),
            "device_type": device_type  # Same device for all attempts of a question
        }
        history_records.append(record)

    return history_records

def generate_student_id(institution_code: str, dept_code: str, year_code: str, section_code: str, subject_code: str, paper_code: str, student_number: int) -> str:
    """Generate a structured student ID with paper component for paper-level tracking"""
    return f"{institution_code}_{dept_code}_{year_code}_{section_code}_{subject_code}_{paper_code}_STU_{student_number:03d}"

def generate_students_for_paper_component(institution_key: str, dept_key: str, year_key: str, section_key: str, subject_key: str, paper_key: str, subject_config: Dict, paper_config: Dict) -> List[Dict]:
    """Generate student records for a specific paper component within a subject"""
    institution_config = INSTITUTIONS[institution_key]
    dept_config = institution_config["departments"][dept_key]
    year_config = dept_config["years"][year_key]
    section_config = year_config["sections"][section_key]

    students = []
    for i in range(1, subject_config["students"] + 1):
        # Generate paper-specific student ID
        student_id = generate_student_id(
            institution_config["code"],
            dept_config["code"],
            year_config["code"],
            section_config["code"],
            subject_config["code"],
            paper_config["code"],
            i
        )

        # Create student record with all hierarchy information including paper component
        student_record = {
            "student_id": student_id,
            "base_student_number": i,  # The actual student number (same across papers)
            "institution_key": institution_key,
            "institution_name": institution_config["name"],
            "institution_code": institution_config["code"],
            "department_key": dept_key,
            "department_name": dept_config["name"],
            "department_code": dept_config["code"],
            "year_key": year_key,
            "year_name": year_config["name"],
            "year_code": year_config["code"],
            "section_key": section_key,
            "section_name": section_config["name"],
            "section_code": section_config["code"],
            "academic_year": section_config["academic_year"],
            "subject_key": subject_key,
            "subject_name": subject_config["name"],
            "subject_code": subject_config["code"],
            "cambridge_subject_code": subject_config["subject_code"],
            "paper_key": paper_key,
            "paper_name": paper_config["name"],
            "paper_code": paper_config["code"],
            "paper_description": paper_config["description"],
            "paper_duration_minutes": paper_config["duration_minutes"],
            "paper_max_marks": paper_config["max_marks"],
            "ability_level": generate_student_ability(),  # Each student has consistent ability across papers
            "has_data": paper_config["has_data"]
        }

        students.append(student_record)

    return students

def generate_all_student_histories():
    """Generate history data for all students across the full institutional hierarchy with paper-level tracking"""

    print("\n🏫 Generating student data for institutional hierarchy with paper-level tracking...")

    # Store student ability by base student number to maintain consistency across papers
    student_abilities = {}

    # Generate all students (now per paper component)
    all_students = []
    for inst_key, inst_config in INSTITUTIONS.items():
        for dept_key, dept_config in inst_config["departments"].items():
            for year_key, year_config in dept_config["years"].items():
                for section_key, section_config in year_config["sections"].items():
                    for subject_key, subject_config in section_config["subjects"].items():

                        # Generate students for each paper component
                        for paper_key, paper_config in subject_config["paper_components"].items():
                            if paper_config["has_data"]:  # Only generate for papers with data

                                # Ensure consistent ability levels across papers for same student
                                for i in range(1, subject_config["students"] + 1):
                                    if i not in student_abilities:
                                        student_abilities[i] = generate_student_ability()

                                students = generate_students_for_paper_component(
                                    inst_key, dept_key, year_key, section_key, subject_key,
                                    paper_key, subject_config, paper_config
                                )

                                # Apply consistent abilities
                                for student in students:
                                    student["ability_level"] = student_abilities[student["base_student_number"]]

                                all_students.extend(students)

                                print(f"   • {inst_config['name']} → {dept_config['name']} → {year_config['name']} → {section_config['name']} → {subject_config['name']} → {paper_config['name']}: {len(students)} student records")

    print(f"✅ Total student-paper records generated: {len(all_students)}")
    print(f"📊 Unique students: {len(student_abilities)} (tracked across {len(all_students) // len(student_abilities)} papers each)")

    # Generate history records for each student-paper combination
    all_records = []

    for i, student in enumerate(all_students):
        print(f"\r📚 Generating history for student-paper {i+1}/{len(all_students)}: {student['student_id']}", end="")

        student_records = []

        # More realistic practice pattern: students focus on subset of exam sessions
        target_paper = student["paper_key"]

        # Each student practices from a realistic subset of exam sessions (not all)
        available_sessions = questions_df['paper_number'].unique()

        # Students practice from 3-8 recent exam sessions (more realistic)
        num_sessions_to_practice = random.randint(3, 8)
        student_practice_sessions = random.sample(list(available_sessions),
                                                min(num_sessions_to_practice, len(available_sessions)))

        if i < 5:  # Show first 5 students' practice patterns
            print(f"\n   📋 {student['student_id']}: practicing from {len(student_practice_sessions)} sessions")
            print(f"      Sessions: {student_practice_sessions[:3]}{'...' if len(student_practice_sessions) > 3 else ''}")

        for _, row in questions_df.iterrows():
            question_id = row["question_id"]
            paper_number = row["paper_number"]

            # Skip if this session is not in student's practice set
            if paper_number not in student_practice_sessions:
                continue

            # Check if this question belongs to the target paper component
            # Extract paper component from paper_number (e.g., "9702_s04_qp_1" -> P1)
            paper_parts = paper_number.split('_')
            if len(paper_parts) >= 4:
                qp_part = paper_parts[3]  # e.g., "1", "11", "12", "13"

                # Map question paper numbers to our paper components
                # For Physics 9702: qp_1 = P1, qp_11/12/13 = P1 variants, etc.
                if qp_part in ["1"] or qp_part.startswith("1"):
                    question_paper_component = "p1"
                else:
                    # For now, we only have P1 data, so skip others
                    continue

                # Only generate history if this question matches the student's paper
                if question_paper_component == target_paper:
                    history = maybe_generate_history(question_id, student["ability_level"])

                    if history:  # If student attempted this question
                        for record in history:
                            # Add student and institutional context
                            record.update({
                                "student_id": student["student_id"],
                                "base_student_number": student["base_student_number"],
                                "paper_number": row["paper_number"],
                                "question_number": row["question_number"],
                                "institution_key": student["institution_key"],
                                "institution_name": student["institution_name"],
                                "institution_code": student["institution_code"],
                                "department_key": student["department_key"],
                                "department_name": student["department_name"],
                                "department_code": student["department_code"],
                                "year_key": student["year_key"],
                                "year_name": student["year_name"],
                                "year_code": student["year_code"],
                                "section_key": student["section_key"],
                                "section_name": student["section_name"],
                                "section_code": student["section_code"],
                                "academic_year": student["academic_year"],
                                "subject_key": student["subject_key"],
                                "subject_name": student["subject_name"],
                                "subject_code": student["subject_code"],
                                "cambridge_subject_code": student["cambridge_subject_code"],
                                "paper_key": student["paper_key"],
                                "paper_name": student["paper_name"],
                                "paper_code": student["paper_code"],
                                "paper_description": student["paper_description"],
                                "paper_duration_minutes": student["paper_duration_minutes"],
                                "paper_max_marks": student["paper_max_marks"],
                                "student_ability_level": student["ability_level"]
                            })
                            student_records.append(record)

        all_records.extend(student_records)

    print(f"\n✅ Generated {len(all_records)} total history records")
    return all_records, all_students

# Generate all history data
all_records, all_students = generate_all_student_histories()

if all_records:
    # Create DataFrame from all records
    history_df = pd.DataFrame(all_records)

    # Reorder columns to match database schema with paper-level tracking
    column_order = [
        "student_id", "base_student_number", "institution_key", "institution_name", "institution_code",
        "department_key", "department_name", "department_code",
        "year_key", "year_name", "year_code",
        "section_key", "section_name", "section_code",
        "academic_year", "subject_key", "subject_name", "subject_code", "cambridge_subject_code",
        "paper_key", "paper_name", "paper_code", "paper_description", "paper_duration_minutes", "paper_max_marks",
        "student_ability_level",
        "question_id", "paper_number", "question_number",
        "attempt_number", "status", "time_spent_sec", "timestamp",
        "confidence_level", "device_type"
    ]
    history_df = history_df[column_order]

    # Sort by institution, department, year, section, subject, paper, base student number, then timestamp
    history_df = history_df.sort_values([
        "institution_code", "department_code", "year_code", "section_code",
        "subject_code", "paper_code", "base_student_number", "timestamp"
    ]).reset_index(drop=True)

    # Add sequential ID (simulating database SERIAL PRIMARY KEY)
    history_df.insert(0, "id", range(1, len(history_df) + 1))

    # Save to files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parquet_filename = f"student_history_enhanced_{timestamp}.parquet"
    csv_filename = f"student_history_enhanced_{timestamp}.csv"

    history_df.to_parquet(parquet_filename, index=False)
    history_df.to_csv(csv_filename, index=False)

    # Show preview and statistics
    print("\n" + "="*70)
    print("📊 ENHANCED STUDENT HISTORY WITH INSTITUTIONAL HIERARCHY")
    print("="*70)

    print(f"\n📋 Dataset Overview:")
    print(f"   • Total records: {len(history_df):,}")
    print(f"   • Total students: {history_df['student_id'].nunique():,}")
    print(f"   • Total institutions: {history_df['institution_name'].nunique()}")
    print(f"   • Total departments: {history_df['department_name'].nunique()}")
    print(f"   • Total years: {history_df['year_name'].nunique()}")
    print(f"   • Total sections: {history_df['section_name'].nunique()}")
    print(f"   • Total subjects: {history_df['subject_name'].nunique()}")
    print(f"   • Total paper components: {history_df['paper_name'].nunique()}")
    print(f"   • Questions attempted: {history_df['question_id'].nunique():,}")
    print(f"   • Total questions available: {len(questions_df):,}")
    print(f"   • Overall attempt rate: {history_df['question_id'].nunique() / len(questions_df):.1%}")

    print(f"\n🏫 Full Institutional Hierarchy Breakdown:")
    hierarchy_breakdown = history_df.groupby([
        'institution_name', 'department_name', 'year_name', 'section_name',
        'subject_name', 'paper_name'
    ]).agg({
        'student_id': 'nunique',
        'base_student_number': 'nunique',
        'id': 'count'
    }).rename(columns={'student_id': 'paper_student_records', 'base_student_number': 'unique_students', 'id': 'records'})

    for (inst, dept, year, section, subject, paper), data in hierarchy_breakdown.iterrows():
        print(f"   • {inst} → {dept} → {year} → {section} → {subject} → {paper}: {data['unique_students']} students, {data['records']:,} records")

    print(f"\n📄 Paper-Level Student Tracking Analysis:")
    paper_breakdown = history_df.groupby(['paper_name', 'paper_code']).agg({
        'student_id': 'nunique',
        'base_student_number': 'nunique',
        'question_id': 'nunique',
        'id': 'count'
    }).rename(columns={'student_id': 'paper_student_records', 'base_student_number': 'unique_students', 'question_id': 'questions', 'id': 'records'})

    for (paper_name, paper_code), data in paper_breakdown.iterrows():
        print(f"   • {paper_name} ({paper_code}): {data['unique_students']} students, {data['questions']} questions, {data['records']:,} records")

    print(f"\n👤 Paper-Level Student ID Examples:")
    sample_students = history_df[['student_id', 'base_student_number', 'paper_name']].drop_duplicates().head(5)
    for _, row in sample_students.iterrows():
        print(f"   • Student #{row['base_student_number']:03d} for {row['paper_name']}: {row['student_id']}")

    print(f"\n🔗 Cross-Paper Student Tracking:")
    cross_paper = history_df.groupby('base_student_number').agg({
        'paper_name': 'nunique',
        'student_id': 'nunique',
        'id': 'count'
    }).rename(columns={'paper_name': 'papers_enrolled', 'student_id': 'paper_student_ids', 'id': 'total_records'})

    print(f"   • Students enrolled in {cross_paper['papers_enrolled'].iloc[0]} paper(s) each")
    print(f"   • Each student has {cross_paper['paper_student_ids'].iloc[0]} unique paper-level ID(s)")
    print(f"   • Average records per student: {cross_paper['total_records'].mean():.0f}")

    print(f"\n📈 Performance Distribution:")
    status_dist = history_df['status'].value_counts(normalize=True)
    for status, pct in status_dist.items():
        print(f"   • {status.title()}: {pct:.1%}")

    print(f"\n🎯 Student Ability Distribution:")
    ability_dist = history_df['student_ability_level'].value_counts(normalize=True)
    for ability, pct in ability_dist.items():
        print(f"   • {ability.replace('_', ' ').title()}: {pct:.1%}")

    print(f"\n📱 Device Type Distribution:")
    device_dist = history_df['device_type'].value_counts(normalize=True)
    for device, pct in device_dist.items():
        print(f"   • {device.title()}: {pct:.1%}")

    print(f"\n⏱️  Average Time Spent by Status:")
    time_stats = history_df.groupby('status')['time_spent_sec'].agg(['mean', 'std']).round(2)
    for status, stats in time_stats.iterrows():
        print(f"   • {status.title()}: {stats['mean']:.1f}s (±{stats['std']:.1f}s)")

    print(f"\n📊 Confidence Level Distribution:")
    conf_dist = history_df['confidence_level'].value_counts().sort_index()
    for level, count in conf_dist.items():
        pct = count / len(history_df) * 100
        print(f"   • Level {level}: {count:,} records ({pct:.1f}%)")

    # Sample record showcase
    print(f"\n🔍 Sample Record (Student: {history_df.iloc[0]['student_id']}):")
    print("-" * 70)
    sample_record = history_df.iloc[0].to_dict()
    for key, value in sample_record.items():
        if key == 'timestamp':
            print(f"   {key}: {value.isoformat()}")
        else:
            print(f"   {key}: {value}")

    print(f"\n💾 Files Generated:")
    print(f"   • {parquet_filename}")
    print(f"   • {csv_filename}")

    # Create student registry file for reference
    students_df = pd.DataFrame(all_students)
    students_filename = f"student_registry_{timestamp}.csv"
    students_df.to_csv(students_filename, index=False)
    print(f"   • {students_filename} (student registry)")

    print(f"\n✅ Enhanced student history generation completed!")
    print(f"🎓 Ready for institutional analysis and cohort comparisons")



    print(f"\n🎉 SYNTHETIC DATA GENERATION COMPLETED!")
    print("=" * 60)
    print(f"📊 Generated Data:")
    print(f"   • Student learning records: {len(history_df):,}")
    print(f"   • Individual students tracked: {history_df['student_id'].nunique()}")
    print(f"   • Questions with attempts: {history_df['question_id'].nunique():,}")
    print(f"   • Institutional hierarchy: Complete structure")
    print(f"   • Paper-level tracking: Ready for P2, P3, P4, P5 expansion")

    print(f"\n📁 Files Generated:")
    print(f"   • {parquet_filename}")
    print(f"   • {csv_filename}")
    print(f"   • {students_filename}")

    print(f"\n🚀 Next Steps:")
    print(f"   1. 📋 Migrate to database: python migrate_data.py {csv_filename}")
    print(f"   2. 🧠 Test ML pipeline: python ../ml/vector_encoder.py")
    print(f"   3. 🌐 Start API server: python ../main.py --mode api")
    print(f"   4. 🧪 Run system demo: python ../main.py --mode demo")

    print(f"\n💡 Tips:")
    print(f"   • Use the CSV file for database migration")
    print(f"   • Use the Parquet file for ML/analytics work")
    print(f"   • Student registry shows the institutional structure")

else:
    print("❌ No history records were generated!")
    print("💡 Check the questions data and institutional configuration")

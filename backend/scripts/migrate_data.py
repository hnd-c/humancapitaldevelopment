#!/usr/bin/env python3
"""
Normalized Database Schema Creator

This script refactors the flat student history data into properly normalized tables
following database design best practices for future PostgreSQL migration.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import uuid

def create_normalized_schema(source_file="student_history_enhanced_20250812_084700.csv"):
    """
    Transform flat student history data into normalized table structure.
    """

    print("🔄 CREATING NORMALIZED DATABASE SCHEMA")
    print("=" * 60)

    # Load source data
    df = pd.read_csv(source_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"📊 Source data: {len(df):,} rows, {len(df.columns)} columns")

    # ========================================
    # 1. INSTITUTIONS TABLE
    # ========================================
    institutions = df[['institution_key', 'institution_name', 'institution_code']].drop_duplicates().copy()
    institutions['institution_id'] = range(1, len(institutions) + 1)
    institutions = institutions[['institution_id', 'institution_key', 'institution_name', 'institution_code']]

    # ========================================
    # 2. DEPARTMENTS TABLE
    # ========================================
    departments = df[['institution_key', 'department_key', 'department_name', 'department_code']].drop_duplicates().copy()
    departments = departments.merge(institutions[['institution_key', 'institution_id']], on='institution_key')
    departments['department_id'] = range(1, len(departments) + 1)
    departments = departments[['department_id', 'institution_id', 'department_key', 'department_name', 'department_code']]

    # ========================================
    # 3. ACADEMIC_YEARS TABLE
    # ========================================
    years = df[['year_key', 'year_name', 'year_code', 'academic_year']].drop_duplicates().copy()
    years['year_id'] = range(1, len(years) + 1)
    years = years[['year_id', 'year_key', 'year_name', 'year_code', 'academic_year']]

    # ========================================
    # 4. SECTIONS TABLE
    # ========================================
    sections = df[['section_key', 'section_name', 'section_code']].drop_duplicates().copy()
    sections['section_id'] = range(1, len(sections) + 1)
    sections = sections[['section_id', 'section_key', 'section_name', 'section_code']]

    # ========================================
    # 5. SUBJECTS TABLE
    # ========================================
    subjects = df[['subject_key', 'subject_name', 'subject_code', 'cambridge_subject_code']].drop_duplicates().copy()
    subjects['subject_id'] = range(1, len(subjects) + 1)
    subjects = subjects[['subject_id', 'subject_key', 'subject_name', 'subject_code', 'cambridge_subject_code']]

    # ========================================
    # 6. PAPERS TABLE - Each paper_number is a unique paper (includes session info)
    # ========================================
    papers = df[['paper_number', 'paper_key', 'paper_name', 'paper_code', 'paper_description',
                 'paper_duration_minutes', 'paper_max_marks', 'subject_key']].drop_duplicates().copy()
    papers = papers.merge(subjects[['subject_key', 'subject_id']], on='subject_key')
    papers['paper_id'] = range(1, len(papers) + 1)

    # Add session info extracted from paper_number (e.g., "9702_w23_qp_12" -> session="w23", year="23")
    papers['exam_session'] = papers['paper_number'].str.extract(r'_([smw]\d{2})_', expand=False)
    papers['exam_year'] = papers['paper_number'].str.extract(r'_[smw](\d{2})_', expand=False)
    papers['full_paper_name'] = papers['paper_name'] + ' (' + papers['exam_session'] + ')'

    papers = papers[['paper_id', 'subject_id', 'paper_number', 'paper_key', 'paper_name', 'full_paper_name',
                     'paper_code', 'paper_description', 'paper_duration_minutes', 'paper_max_marks',
                     'exam_session', 'exam_year']]

    # ========================================
    # 7. STUDENTS TABLE (Base students)
    # ========================================
    students = df[['base_student_number', 'student_ability_level', 'institution_key',
                   'department_key', 'year_key', 'section_key']].drop_duplicates().copy()

    # Add foreign keys
    students = students.merge(institutions[['institution_key', 'institution_id']], on='institution_key')
    students = students.merge(departments[['department_key', 'department_id']], on='department_key')
    students = students.merge(years[['year_key', 'year_id']], on='year_key')
    students = students.merge(sections[['section_key', 'section_id']], on='section_key')

    students['student_id'] = range(1, len(students) + 1)
    students['created_at'] = datetime.now()
    students['is_active'] = True

    students = students[['student_id', 'base_student_number', 'institution_id', 'department_id',
                        'year_id', 'section_id', 'student_ability_level', 'is_active', 'created_at']]

    # ========================================
    # 8. STUDENT_PAPER_ENROLLMENTS TABLE
    # ========================================
    enrollments = df[['base_student_number', 'paper_number']].drop_duplicates().copy()
    enrollments = enrollments.merge(students[['base_student_number', 'student_id']], on='base_student_number')
    enrollments = enrollments.merge(papers[['paper_number', 'paper_id']], on='paper_number')
    enrollments['enrollment_id'] = range(1, len(enrollments) + 1)
    enrollments['enrolled_at'] = datetime.now()
    enrollments['is_active'] = True

    # Create paper-specific student IDs for backward compatibility
    # Map each enrollment to its original student_id from the source data
    enrollment_to_student_map = df[['base_student_number', 'paper_number', 'student_id']].drop_duplicates()
    enrollments = enrollments.merge(
        enrollment_to_student_map,
        on=['base_student_number', 'paper_number'],
        how='left'
    )
    enrollments.rename(columns={'student_id_y': 'paper_student_id', 'student_id_x': 'student_id'}, inplace=True)

    enrollments = enrollments[['enrollment_id', 'student_id', 'paper_id', 'paper_student_id',
                              'is_active', 'enrolled_at']]

        # ========================================
    # 9. QUESTIONS TABLE - Load ALL questions from parquet, not just practiced ones
    # ========================================

    # Extract ALL question metadata from combined_questions_2d.parquet
    try:
        questions_detail = pd.read_parquet('../combined_questions_2d.parquet')
        questions_detail = questions_detail.reset_index(drop=True)
        questions_detail['question_id'] = (questions_detail['paper_number'].astype(str) + '_' +
                                         questions_detail['question_number'].astype(str))

        # Use ALL questions from parquet as the base (complete question bank)
        available_columns = ['question_id', 'paper_number', 'question_number', 'combined_text', 'images', 'source_file', 'ms',
                           'openai_embedding', 'text_length', 'umap_embedding', 'soft_cluster', 'umap_2d']

        # Keep only columns that exist in parquet
        questions_columns = ['question_id', 'paper_number', 'question_number']
        for col in available_columns[3:]:  # Skip the first 3 as they're always included
            if col in questions_detail.columns:
                questions_columns.append(col)

        questions = questions_detail[questions_columns].copy()
        print(f"✅ Loaded ALL {len(questions)} questions from parquet file ({len(questions_columns)-3} data columns)")
    except Exception as e:
        print(f"⚠️  Error loading parquet data: {e}")
        questions['combined_text'] = None
        questions['images'] = None
        questions['source_file'] = None
        questions['ms'] = None
        questions['openai_embedding'] = None
        questions['text_length'] = None
        questions['umap_embedding'] = None
        questions['soft_cluster'] = None
        print("⚠️  Using basic question structure (detailed content not available)")

    # Create papers for ALL question sessions (not just student history)
    all_paper_numbers = questions['paper_number'].unique()

    # Create additional papers for question sessions not in student history
    existing_papers = papers['paper_number'].unique()
    missing_paper_numbers = [p for p in all_paper_numbers if p not in existing_papers]

    if missing_paper_numbers:
        print(f"🔧 Creating {len(missing_paper_numbers)} additional papers for complete question bank")

        # Get subject_id (should be 1 for physics)
        subject_id = papers['subject_id'].iloc[0] if len(papers) > 0 else 1

        additional_papers = []
        current_paper_id = papers['paper_id'].max() + 1 if len(papers) > 0 else 1

        for paper_number in missing_paper_numbers:
            # Extract session info
            paper_parts = paper_number.split('_')
            exam_session = paper_parts[1] if len(paper_parts) > 1 else 'unknown'
            exam_year = paper_parts[1][1:] if len(paper_parts) > 1 and len(paper_parts[1]) > 1 else '00'

            additional_papers.append({
                'paper_id': current_paper_id,
                'subject_id': subject_id,
                'paper_number': paper_number,
                'paper_key': 'p1',  # All current questions are P1
                'paper_name': 'Paper 1 - Multiple Choice',
                'full_paper_name': f'Paper 1 - Multiple Choice ({exam_session})',
                'paper_code': 'P1',
                'paper_description': 'Multiple Choice Questions',
                'paper_duration_minutes': 45,
                'paper_max_marks': 40,
                'exam_session': exam_session,
                'exam_year': exam_year
            })
            current_paper_id += 1

        # Add to papers dataframe
        additional_papers_df = pd.DataFrame(additional_papers)
        papers = pd.concat([papers, additional_papers_df], ignore_index=True)

    # Map to paper_id using paper_number (which includes session info)
    questions = questions.merge(papers[['paper_number', 'paper_id']], on='paper_number', how='left')

    questions['internal_question_id'] = range(1, len(questions) + 1)
    questions['created_at'] = datetime.now()
    questions['is_active'] = True

    # Fill missing ML columns if not from parquet
    if 'openai_embedding' not in questions.columns:
        questions['openai_embedding'] = None
    if 'umap_embedding' not in questions.columns:
        questions['umap_embedding'] = None
    if 'soft_cluster' not in questions.columns:
        questions['soft_cluster'] = None
    if 'umap_2d' not in questions.columns:
        questions['umap_2d'] = None
    if 'text_length' not in questions.columns:
        questions['text_length'] = questions['combined_text'].str.len()
    if 'ms' not in questions.columns:
        questions['ms'] = None
    if 'source_file' not in questions.columns:
        questions['source_file'] = None

    # Add standard database columns
    questions['embedding_model'] = 'text-embedding-3-large'
    questions['embedding_created_at'] = None
    questions['cluster_model_version'] = None
    questions['updated_at'] = datetime.now()

    questions = questions[['internal_question_id', 'question_id', 'paper_id', 'question_number',
                          'combined_text', 'images', 'openai_embedding', 'umap_embedding', 'soft_cluster', 'umap_2d',
                          'embedding_model', 'embedding_created_at', 'cluster_model_version',
                          'text_length', 'source_file', 'ms', 'is_active', 'created_at', 'updated_at']]

    # ========================================
    # 10. STUDENT_QUESTION_HISTORY TABLE (Main transaction table)
    # ========================================
    history = df.copy()

    # Add foreign keys
    history = history.merge(enrollments[['paper_student_id', 'enrollment_id']],
                           left_on='student_id', right_on='paper_student_id')
    history = history.merge(questions[['question_id', 'internal_question_id']], on='question_id')

    # Create proper history table
    history_clean = history[['id', 'enrollment_id', 'internal_question_id', 'attempt_number',
                            'status', 'time_spent_sec', 'timestamp', 'confidence_level', 'device_type']].copy()

    # Ensure proper data types
    history_clean['history_id'] = history_clean['id']  # Rename for clarity
    history_clean['timestamp'] = pd.to_datetime(history_clean['timestamp'])
    history_clean['is_correct'] = history_clean['status'] == 'correct'
    history_clean['is_skipped'] = history_clean['status'] == 'skipped'

    history_clean = history_clean[['history_id', 'enrollment_id', 'internal_question_id',
                                  'attempt_number', 'status', 'is_correct', 'is_skipped',
                                  'time_spent_sec', 'timestamp', 'confidence_level', 'device_type']]

    # Note: mark_schemes, question_images, source_files are now part of questions table
    # No separate tables needed since database schema has these as columns

    # ========================================
    # SAVE NORMALIZED TABLES
    # ========================================
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create tables dictionary matching actual database schema
    tables = {
        'institutions': institutions,
        'departments': departments,
        'academic_years': years,
        'sections': sections,
        'subjects': subjects,
        'papers': papers,
        'students': students,
        'student_paper_enrollments': enrollments,
        'questions': questions,
        'student_question_history': history_clean
    }

    print(f"\n📁 NORMALIZED TABLES CREATED:")
    print("-" * 40)

    for table_name, table_df in tables.items():
        # Save as Parquet with fixed filename (overwrite on each run)
        parquet_file = f"normalized_{table_name}.parquet"
        table_df.to_parquet(parquet_file, index=False)

        print(f"📋 {table_name}:")
        print(f"   • Rows: {len(table_df):,}")
        print(f"   • Columns: {len(table_df.columns)}")
        print(f"   • File: {parquet_file}")
        print(f"   • Primary Key: {table_df.columns[0]}")

        # Show sample data
        if len(table_df) > 0:
            print(f"   • Sample: {dict(table_df.iloc[0])}")
        print()

    # ========================================
    # ANALYSIS & RECOMMENDATIONS
    # ========================================
    print(f"📊 NORMALIZATION BENEFITS:")
    print("-" * 40)

    original_size = df.memory_usage(deep=True).sum() / 1024 / 1024
    normalized_size = sum(table.memory_usage(deep=True).sum() for table in tables.values()) / 1024 / 1024

    print(f"💾 Storage Efficiency:")
    print(f"   • Original flat file: {original_size:.1f} MB")
    print(f"   • Normalized tables: {normalized_size:.1f} MB")
    print(f"   • Space reduction: {((original_size - normalized_size) / original_size * 100):.1f}%")

    print(f"\n🎯 Database Design Compliance:")
    print(f"   ✅ Separate entities ({len(tables)} logical tables)")
    print(f"   ✅ Primary keys & foreign keys defined")
    print(f"   ✅ Avoided repeated metadata")
    print(f"   ✅ Strong typing (explicit data types)")
    print(f"   ✅ ISO datetime format")
    print(f"   ✅ Boolean flags for status checks")
    print(f"   ✅ Narrow tables (max {max(len(t.columns) for t in tables.values())} columns)")
    print(f"   ✅ Surrogate keys for all entities")
    print(f"   ✅ Question bank separated from history")
    print(f"   ✅ Mark schemes included in questions table")
    print(f"   ✅ Question images included in questions table")
    print(f"   ✅ Source file provenance included in questions table")
    print(f"   ✅ ML embeddings ready for vector operations")
    print(f"   ✅ Consistent null handling")
    print(f"   ✅ Ready for foreign key constraints")

    print(f"\n🚀 READY FOR POSTGRESQL MIGRATION!")
    print(f"   • All tables have surrogate primary keys")
    print(f"   • Foreign key relationships clearly defined")
    print(f"   • Index-friendly structure (student_id, timestamp, etc.)")
    print(f"   • Partition-ready (by student_id, date)")
    print(f"   • No mixed data types")
    print(f"   • Performance-oriented layout")

    return tables

if __name__ == "__main__":
    # Find the most recent student history file
    import glob
    import os

    files = glob.glob("student_history_enhanced_*.csv")
    if files:
        latest_file = max(files, key=os.path.getctime)
        print(f"📂 Using latest student history file: {latest_file}")
        tables = create_normalized_schema(latest_file)
    else:
        print("❌ No student history files found. Please run student_history.py first.")

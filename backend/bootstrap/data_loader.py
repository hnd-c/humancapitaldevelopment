#!/usr/bin/env python3
"""
Data Loader - Load and process data files for the system

This module handles:
- Loading parquet files
- Processing student history data
- Data validation and preprocessing
"""

import pandas as pd
import numpy as np
import glob
import os
from typing import Dict, Any, Optional, Tuple
from datetime import datetime


class DataLoader:
    """Handles loading and processing of various data sources"""

    def __init__(self, base_path: str = "."):
        self.base_path = base_path

    def load_questions_data(self, file_path: str = "combined_questions.parquet") -> Tuple[pd.DataFrame, np.ndarray]:
        """Load question data and extract soft clusters"""
        try:
            full_path = os.path.join(self.base_path, file_path)
            questions_df = pd.read_parquet(full_path)
            soft_clusters = np.stack(questions_df['soft_cluster'].values)

            print(f"✅ Loaded {len(questions_df)} questions with {soft_clusters.shape[1]} clusters")
            return questions_df, soft_clusters

        except FileNotFoundError:
            print(f"❌ {file_path} not found!")
            raise
        except Exception as e:
            print(f"❌ Error loading question data: {e}")
            raise

    def load_student_history(self, file_pattern: str = "student_history_enhanced_*.csv") -> Optional[pd.DataFrame]:
        """Load the latest student history file"""
        try:
            files = glob.glob(os.path.join(self.base_path, file_pattern))
            if not files:
                print(f"❌ No files found matching pattern: {file_pattern}")
                return None

            latest_file = max(files, key=os.path.getctime)
            print(f"📂 Using latest student history file: {latest_file}")

            df = pd.read_csv(latest_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])

            print(f"✅ Loaded {len(df)} student history records")
            return df

        except Exception as e:
            print(f"❌ Error loading student history: {e}")
            return None

    def create_question_mapping(self, questions_df: pd.DataFrame) -> Dict[str, int]:
        """Create mapping from question_id strings to integer indices"""
        questions_indexed = questions_df.reset_index(drop=True)
        questions_indexed["question_id"] = (
            questions_indexed["paper_number"].astype(str) + "_" +
            questions_indexed["question_number"].astype(str)
        )

        question_mapping = {}
        for idx, row in questions_indexed.iterrows():
            question_mapping[row["question_id"]] = idx

        return question_mapping

    def validate_data_integrity(self, questions_df: pd.DataFrame, student_history_df: Optional[pd.DataFrame] = None) -> bool:
        """Validate data integrity and consistency"""
        try:
            # Validate questions data
            required_columns = ['soft_cluster', 'paper_number', 'question_number']
            missing_columns = [col for col in required_columns if col not in questions_df.columns]
            if missing_columns:
                print(f"❌ Missing required columns in questions data: {missing_columns}")
                return False

            # Check for null clusters
            null_clusters = questions_df['soft_cluster'].isnull().sum()
            if null_clusters > 0:
                print(f"⚠️  Found {null_clusters} questions with null clusters")

            # Validate student history if provided
            if student_history_df is not None:
                history_required = ['student_id', 'question_id', 'timestamp', 'is_correct']
                missing_history_cols = [col for col in history_required if col not in student_history_df.columns]
                if missing_history_cols:
                    print(f"❌ Missing required columns in student history: {missing_history_cols}")
                    return False

            print("✅ Data integrity validation passed")
            return True

        except Exception as e:
            print(f"❌ Data validation failed: {e}")
            return False

    def preprocess_data(self, questions_df: pd.DataFrame) -> pd.DataFrame:
        """Preprocess questions data for ML pipeline"""
        try:
            processed_df = questions_df.copy()

            # Ensure soft_cluster is properly formatted
            if 'soft_cluster' in processed_df.columns:
                # Convert to numpy arrays if they're not already
                processed_df['soft_cluster'] = processed_df['soft_cluster'].apply(
                    lambda x: np.array(x) if not isinstance(x, np.ndarray) else x
                )

            print("✅ Data preprocessing completed")
            return processed_df

        except Exception as e:
            print(f"❌ Data preprocessing failed: {e}")
            raise

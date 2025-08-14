import numpy as np
import pandas as pd
from datetime import datetime
import glob
import os

class RichVectorEncoder:
    def __init__(self, soft_clusters, question_mapping=None, db_manager=None):
        self.soft_clusters = soft_clusters
        self.question_mapping = question_mapping  # Maps question_id strings to integer indices
        self.n_clusters = soft_clusters.shape[1]  # Derive cluster count from data
        self.db_manager = db_manager  # Database manager for direct database access

    def encode_student_context(self, current_question, student_attempts, objective,
                              population_stats=None):
        """
        Create rich vector encoding full student context
        """
        # Convert current_question to index if it's a string
        current_question_idx = self._get_question_index(current_question)
        if current_question_idx is None:
            # Fallback to uniform distribution if question not found
            return np.ones(self.n_clusters) / self.n_clusters

        # Base: Current question's cluster distribution
        base_state = self.soft_clusters[current_question_idx]

        # Student mastery in each cluster
        mastery_encoding = self._encode_mastery(student_attempts)

        # Learning velocity in each cluster
        velocity_encoding = self._encode_learning_velocity(student_attempts)

        # Objective-specific boosts
        objective_encoding = self._encode_objective(objective, student_attempts)

        # Population-informed adjustments (optional)
        if population_stats:
            population_encoding = self._encode_population_context(student_attempts, population_stats)
        else:
            population_encoding = np.zeros(self.n_clusters)

        # Combine using learned weights or heuristics
        enhanced_vector = self._combine_encodings(
            base_state, mastery_encoding, velocity_encoding,
            objective_encoding, population_encoding
        )

        return enhanced_vector

    def _get_question_index(self, question_id):
        """Convert question_id (string or int) to integer index for cluster lookup"""
        if isinstance(question_id, int):
            return question_id if question_id < len(self.soft_clusters) else None
        elif isinstance(question_id, str) and self.question_mapping:
            return self.question_mapping.get(question_id)
        return None

    def _encode_mastery(self, student_attempts):
        """
        Encode mastery per cluster using **all historical attempts**.

        - For each cluster, sum weighted correct attempts.
        - Divide by total weighted attempts (correct + incorrect).
        - Use cluster membership as soft weighting.
        """
        mastery = np.zeros(self.n_clusters)
        attempt_counts = np.zeros(self.n_clusters)

        for attempt in student_attempts:
            question_id = attempt.get('question_id')
            question_idx = self._get_question_index(question_id)

            if question_idx is not None:
                for cluster_idx in range(self.n_clusters):
                    membership = self.soft_clusters[question_idx][cluster_idx]
                    if membership > 0.1:  # Threshold to consider cluster membership
                        attempt_counts[cluster_idx] += membership
                        if attempt['status'] == 'correct':
                            mastery[cluster_idx] += membership

        # Compute mastery as correct / total attempts per cluster
        nonzero_mask = attempt_counts > 0
        mastery[nonzero_mask] = mastery[nonzero_mask] / attempt_counts[nonzero_mask]

        # Clusters with no attempts remain zero mastery
        return mastery

    def _encode_learning_velocity(self, student_attempts):
        """
        Encode learning velocity per cluster using improvement over time.

        Compares early vs recent performance within each cluster.
        Now includes per-cluster data sufficiency checks.
        """
        velocity = np.zeros(self.n_clusters)
        early_correct = np.zeros(self.n_clusters)
        early_total = np.zeros(self.n_clusters)
        recent_correct = np.zeros(self.n_clusters)
        recent_total = np.zeros(self.n_clusters)

        # Sort attempts by timestamp to split into early/recent
        sorted_attempts = sorted(student_attempts, key=lambda x: x.get('timestamp', datetime.min))

        if len(sorted_attempts) < 6:  # Need sufficient data for velocity
            return velocity

        mid_point = len(sorted_attempts) // 2
        early_attempts = sorted_attempts[:mid_point]
        recent_attempts = sorted_attempts[mid_point:]

        # Process early attempts
        for attempt in early_attempts:
            question_id = attempt.get('question_id')
            question_idx = self._get_question_index(question_id)
            if question_idx is not None:
                for cluster_idx in range(self.n_clusters):
                    membership = self.soft_clusters[question_idx][cluster_idx]
                    if membership > 0.1:
                        early_total[cluster_idx] += membership
                        if attempt['status'] == 'correct':
                            early_correct[cluster_idx] += membership

        # Process recent attempts
        for attempt in recent_attempts:
            question_id = attempt.get('question_id')
            question_idx = self._get_question_index(question_id)
            if question_idx is not None:
                for cluster_idx in range(self.n_clusters):
                    membership = self.soft_clusters[question_idx][cluster_idx]
                    if membership > 0.1:
                        recent_total[cluster_idx] += membership
                        if attempt['status'] == 'correct':
                            recent_correct[cluster_idx] += membership

        # Compute improvement: recent_rate - early_rate with per-cluster sufficiency checks
        min_cluster_attempts = 1.0  # Minimum weighted attempts per period per cluster
        for cluster_idx in range(self.n_clusters):
            # Only compute velocity if BOTH periods have sufficient data for this cluster
            if (early_total[cluster_idx] >= min_cluster_attempts and
                recent_total[cluster_idx] >= min_cluster_attempts):

                early_rate = early_correct[cluster_idx] / early_total[cluster_idx]
                recent_rate = recent_correct[cluster_idx] / recent_total[cluster_idx]
                improvement = recent_rate - early_rate
                velocity[cluster_idx] = max(0.0, improvement)  # Only positive improvement
            # else: velocity remains 0 for clusters with insufficient data

        return velocity

    def _encode_objective(self, objective, student_attempts):
        """Encode learning objective as cluster weights"""
        if objective == 'coverage':
            # Boost unexplored clusters
            exposure = self._compute_cluster_exposure(student_attempts)
            max_exposure = np.max(exposure) if np.max(exposure) > 0 else 1
            return (max_exposure - exposure) / max_exposure

        elif objective == 'efficiency':
            # Boost clusters where student learns quickly
            velocity = self._encode_learning_velocity(student_attempts)
            return velocity

        elif objective == 'success_rate':
            # Boost clusters where student likely to succeed
            mastery = self._encode_mastery(student_attempts)
            return mastery

        else:  # balanced
            return np.ones(self.n_clusters) / self.n_clusters

    def _combine_encodings(self, base_state, mastery, velocity, objective, population):
        """
        Intelligently combine different encodings
        """
        # Adaptive weighting based on student profile
        student_confidence = np.mean(mastery)

        if student_confidence > 0.8:  # Advanced student
            # Trust their mastery pattern more
            weights = [0.2, 0.4, 0.2, 0.2, 0.0]
        elif student_confidence < 0.3:  # Struggling student
            # Follow objectives and population patterns more
            weights = [0.4, 0.1, 0.1, 0.3, 0.1]
        else:  # Average student
            weights = [0.3, 0.25, 0.2, 0.2, 0.05]

        combined = (weights[0] * base_state +
                   weights[1] * mastery +
                   weights[2] * velocity +
                   weights[3] * objective +
                   weights[4] * population)

        # Ensure valid probability distribution
        combined = np.maximum(combined, 0.01)  # Minimum probability
        combined /= combined.sum()

        return combined

    def _compute_cluster_exposure(self, student_attempts):
        """Compute how much exposure student has had to each cluster"""
        exposure = np.zeros(self.n_clusters)

        for attempt in student_attempts:
            question_id = attempt.get('question_id')
            question_idx = self._get_question_index(question_id)

            if question_idx is not None:
                # Add cluster memberships weighted by time spent or attempts
                for cluster_idx in range(self.n_clusters):
                    membership = self.soft_clusters[question_idx][cluster_idx]
                    exposure[cluster_idx] += membership

        return exposure

    def _encode_population_context(self, student_attempts, population_stats):
        """Encode how student compares to population in each cluster"""
        population_encoding = np.zeros(self.n_clusters)
        student_correct = np.zeros(self.n_clusters)
        student_total = np.zeros(self.n_clusters)

        # Compute student success rates per cluster efficiently
        for attempt in student_attempts:
            question_id = attempt.get('question_id')
            question_idx = self._get_question_index(question_id)
            if question_idx is not None:
                for cluster_idx in range(self.n_clusters):
                    membership = self.soft_clusters[question_idx][cluster_idx]
                    if membership > 0.1:
                        student_total[cluster_idx] += membership
                        if attempt['status'] == 'correct':
                            student_correct[cluster_idx] += membership

        # Compare to population rates
        for cluster_idx in range(self.n_clusters):
            if student_total[cluster_idx] > 0:
                student_rate = student_correct[cluster_idx] / student_total[cluster_idx]
                population_rate = population_stats.get(f'cluster_{cluster_idx}_avg_success', 0.5)

                # Encode relative performance
                if population_rate > 0:
                    relative_performance = student_rate / population_rate
                    population_encoding[cluster_idx] = min(2.0, relative_performance)  # Cap at 2x

        return population_encoding / 2.0  # Normalize to [0, 1]


def find_latest_normalized_files():
    """Find the most recent normalized table files"""
    files = {}

    # Find latest files for each table type
    table_types = [
        'student_question_history', 'questions', 'students',
        'student_paper_enrollments', 'papers', 'subjects'
    ]

    for table_type in table_types:
        pattern = f"normalized_{table_type}_*.parquet"
        matching_files = glob.glob(pattern)
        if matching_files:
            latest_file = max(matching_files, key=os.path.getctime)
            files[table_type] = latest_file
        else:
            print(f"⚠️  No files found for {table_type}")

    return files


def load_student_history_from_database(student_id, db_manager):
    """Load student history directly from database"""
    try:
        print(f"📖 Loading student history for student_id={student_id} from database...")

        # Use the existing optimized method from database manager
        history_data = db_manager.get_student_history_optimized(student_id)

        if not history_data:
            print(f"⚠️ No history found for student_id={student_id}")
            return []

        # Convert to the format expected by vector encoder
        student_attempts = []
        for record in history_data:
            student_attempts.append({
                'id': record.get('history_id'),
                'enrollment_id': record.get('enrollment_id'),
                'question_id': record.get('question_id'),
                'internal_question_id': record.get('internal_question_id'),
                'status': 'correct' if record.get('is_correct') else 'incorrect',
                'is_correct': record.get('is_correct', False),
                'is_skipped': record.get('is_skipped', False),
                'time_spent_sec': record.get('time_spent_sec', 0),
                'timestamp': record.get('timestamp'),
                'confidence_level': record.get('confidence_level', 5),
                'device_type': record.get('device_type', 'unknown')
            })

        print(f"✅ Loaded {len(student_attempts)} attempts from database")
        if student_attempts:
            correct_count = sum(1 for a in student_attempts if a['is_correct'])
            print(f"   - Correct: {correct_count}")
            print(f"   - Incorrect: {len(student_attempts) - correct_count}")

        return student_attempts

    except Exception as e:
        print(f"❌ Error loading student history from database: {e}")
        return []


def load_student_history_normalized(student_id=1, db_manager=None):
    """Load student history from database or normalized tables"""

    # If database manager is provided, use database
    if db_manager is not None:
        return load_student_history_from_database(student_id, db_manager)

    # Fallback to parquet files (original behavior)
    try:
        print(f"📖 Loading student history for student_id={student_id} from normalized tables...")

        # Find latest normalized files
        files = find_latest_normalized_files()

        if 'student_question_history' not in files:
            print("❌ Student question history table not found")
            return []

        # Load student question history
        history_df = pd.read_parquet(files['student_question_history'])
        print(f"✅ Loaded {len(history_df)} total history records")

        # Load enrollments to get student mapping
        if 'student_paper_enrollments' in files:
            enrollments_df = pd.read_parquet(files['student_paper_enrollments'])

            # Get enrollments for this student
            student_enrollments = enrollments_df[enrollments_df['student_id'] == student_id]
            enrollment_ids = student_enrollments['enrollment_id'].tolist()

            if not enrollment_ids:
                print(f"⚠️  No enrollments found for student_id={student_id}")
                return []

            # Filter history for this student's enrollments
            student_history = history_df[history_df['enrollment_id'].isin(enrollment_ids)]
            print(f"📚 Found {len(student_history)} records for student {student_id}")
        else:
            print("⚠️  Using enrollment_id=1 as fallback")
            student_history = history_df[history_df['enrollment_id'] == student_id]

        # Load questions for question_id mapping
        if 'questions' in files:
            questions_df = pd.read_parquet(files['questions'])
            # Create question mapping
            question_map = dict(zip(questions_df['internal_question_id'], questions_df['question_id']))
        else:
            question_map = {}

        # Convert to list of dictionaries
        student_attempts = []
        for _, row in student_history.iterrows():
            # Map internal question ID to external question ID
            question_id = question_map.get(row['internal_question_id'], f"q_{row['internal_question_id']}")

            student_attempts.append({
                'id': row['history_id'],
                'enrollment_id': row['enrollment_id'],
                'question_id': question_id,
                'internal_question_id': row['internal_question_id'],
                'attempt_number': row['attempt_number'],
                'status': row['status'],
                'is_correct': row['is_correct'],
                'is_skipped': row['is_skipped'],
                'time_spent_sec': row['time_spent_sec'],
                'timestamp': pd.to_datetime(row['timestamp']),
                'confidence_level': row['confidence_level'],
                'device_type': row['device_type']
            })

        print(f"✅ Parsed {len(student_attempts)} student attempts")
        if student_attempts:
            print(f"   - Correct: {sum(1 for a in student_attempts if a['is_correct'])}")
            print(f"   - Wrong: {sum(1 for a in student_attempts if not a['is_correct'] and not a['is_skipped'])}")
            print(f"   - Skipped: {sum(1 for a in student_attempts if a['is_skipped'])}")

        return student_attempts

    except Exception as e:
        print(f"❌ Error loading normalized student history: {e}")
        return []


def create_question_mapping_from_normalized():
    """Create question mapping from normalized questions table"""
    try:
        files = find_latest_normalized_files()
        if 'questions' not in files:
            print("❌ Questions table not found")
            return {}

        # Load questions table
        questions_df = pd.read_parquet(files['questions'])
        print(f"📋 Loaded {len(questions_df)} questions from normalized table")

        # Create mapping from external question_id to internal index
        question_mapping = {}
        for _, row in questions_df.iterrows():
            # Use internal_question_id as the index for cluster lookup
            question_mapping[row['question_id']] = row['internal_question_id'] - 1  # 0-based indexing

        print(f"📋 Created mapping for {len(question_mapping)} questions")
        return question_mapping

    except Exception as e:
        print(f"❌ Error creating question mapping: {e}")
        return {}


def create_enriched_vector_example():
    """Example using normalized tables (RECOMMENDED)"""
    print("🚀 ENRICHED VECTOR ANALYSIS - Using Normalized Tables")
    print("=" * 60)

    # 1. Load the soft clusters from combined_questions.parquet
    print("📊 Loading question clusters...")
    try:
        df_questions = pd.read_parquet("combined_questions.parquet")
        soft_clusters = np.stack(df_questions['soft_cluster'].values)
        print(f"✅ Loaded {len(soft_clusters)} questions with {soft_clusters.shape[1]} clusters")
    except Exception as e:
        print(f"❌ Error loading clusters: {e}")
        return None, []

    # 2. Create question mapping from normalized tables
    print("\n🗂️ Creating question mapping from normalized tables...")
    question_mapping = create_question_mapping_from_normalized()

    if not question_mapping:
        print("❌ Cannot proceed without question mapping")
        return None, []

    # 3. Initialize the encoder
    encoder = RichVectorEncoder(soft_clusters, question_mapping)

    # 4. Load student history from normalized tables
    print("\n👤 Loading student history from normalized tables...")
    student_attempts = load_student_history_normalized(student_id=1)  # Load first student

    if not student_attempts:
        print("⚠️  No student history found")
        return None, []

    # 5. Create enriched vectors for different scenarios
    print("\n🧮 Creating enriched vectors...")

    # Use a real question from the student's history
    sample_question = student_attempts[0]['question_id']
    print(f"📝 Using sample question: {sample_question}")

    # Different learning objectives
    objectives = ['coverage', 'efficiency', 'success_rate', 'balanced']

    for objective in objectives:
        try:
            enriched_vector = encoder.encode_student_context(
                current_question=sample_question,
                student_attempts=student_attempts,
                objective=objective
            )

            print(f"\n📈 {objective.upper()} objective:")
            print(f"   Top 5 clusters: {np.argsort(enriched_vector)[-5:]}")
            print(f"   Probabilities: {np.sort(enriched_vector)[-5:].round(3)}")

        except Exception as e:
            print(f"❌ Error with {objective}: {e}")

    return encoder, student_attempts


def analyze_student_performance_normalized():
    """Analyze student performance using normalized tables"""
    print("\n🧪 STUDENT PERFORMANCE ANALYSIS - Normalized Tables")
    print("=" * 60)

    # Load student attempts from normalized tables
    student_attempts = load_student_history_normalized(student_id=1)
    if not student_attempts:
        return

    # Load clusters and mapping
    try:
        df_questions = pd.read_parquet("combined_questions.parquet")
        soft_clusters = np.stack(df_questions['soft_cluster'].values)
        question_mapping = create_question_mapping_from_normalized()
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return

    print(f"\n📊 Performance Analysis for Student 1:")
    cluster_stats = {}

    for attempt in student_attempts:
        question_id = attempt['question_id']
        question_idx = question_mapping.get(question_id)

        if question_idx is not None and question_idx < len(soft_clusters):
            # Find primary cluster (highest membership)
            primary_cluster = np.argmax(soft_clusters[question_idx])

            if primary_cluster not in cluster_stats:
                cluster_stats[primary_cluster] = {
                    'total': 0, 'correct': 0, 'total_time': 0,
                    'confidence_sum': 0, 'devices': set()
                }

            stats = cluster_stats[primary_cluster]
            stats['total'] += 1
            stats['total_time'] += attempt['time_spent_sec']
            stats['confidence_sum'] += attempt['confidence_level']
            stats['devices'].add(attempt['device_type'])

            if attempt['is_correct']:
                stats['correct'] += 1

    # Show cluster performance
    print(f"\nTop 10 clusters by activity:")
    sorted_clusters = sorted(cluster_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:10]

    for cluster_id, stats in sorted_clusters:
        if stats['total'] > 0:
            success_rate = stats['correct'] / stats['total']
            avg_time = stats['total_time'] / stats['total']
            avg_confidence = stats['confidence_sum'] / stats['total']

            print(f"   Cluster {cluster_id}: {success_rate:.1%} success, "
                  f"{avg_time:.0f}s avg, {avg_confidence:.1f} confidence "
                  f"({stats['total']} attempts)")

    return cluster_stats


if __name__ == "__main__":
    # Run the normalized table analysis (RECOMMENDED)
    print("🚀 Running enriched vector analysis with NORMALIZED TABLES...")
    encoder, student_attempts = create_enriched_vector_example()

    if encoder and student_attempts:
        analyze_student_performance_normalized()
    else:
        print("❌ Cannot proceed without valid student history")

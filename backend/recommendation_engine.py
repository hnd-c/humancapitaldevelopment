"""
Complete Recommendation Engine
Integrates enriched vectors + transition matrix to recommend specific questions
"""

import numpy as np
import pandas as pd
from enriched_vector import RichVectorEncoder, load_student_history_normalized, create_question_mapping_from_normalized
from transition_matrix import _build_cooccurrence_transitions, recommend_next_clusters


class QuestionRecommendationEngine:
    def __init__(self):
        """Initialize the complete recommendation system"""
        print("🚀 Initializing Recommendation Engine...")

        # Load question data and clusters from combined_questions.parquet
        try:
            self.questions_df = pd.read_parquet("combined_questions.parquet")
            self.soft_clusters = np.stack(self.questions_df['soft_cluster'].values)
            print(f"✅ Loaded {len(self.questions_df)} questions with {self.soft_clusters.shape[1]} clusters")

            # Create question mapping for string IDs
            self.question_mapping = self._create_question_mapping()

        except FileNotFoundError:
            print("❌ combined_questions.parquet not found!")
            print("💡 Make sure the clustering data is available")
            raise
        except Exception as e:
            print(f"❌ Error loading question data: {e}")
            raise

        # Initialize components
        self.encoder = RichVectorEncoder(self.soft_clusters, self.question_mapping)
        self.transition_matrix = _build_cooccurrence_transitions(alpha=0.1, normalize=True)

        if self.transition_matrix is not None:
            print("✅ Initialized encoder and transition matrix")
        else:
            print("❌ Failed to initialize transition matrix")
            raise ValueError("Cannot proceed without transition matrix")

    def _create_question_mapping(self):
        """Create mapping from question_id strings to integer indices"""
        # Reset index to ensure sequential mapping
        questions_indexed = self.questions_df.reset_index(drop=True)

        # Create question_id from paper_number and question_number
        questions_indexed["question_id"] = (
            questions_indexed["paper_number"].astype(str) + "_" +
            questions_indexed["question_number"].astype(str)
        )

        # Create mapping from question_id string to integer index
        question_mapping = {}
        for idx, row in questions_indexed.iterrows():
            question_mapping[row["question_id"]] = idx

        print(f"📋 Created mapping for {len(question_mapping)} questions")
        return question_mapping

    def recommend_questions(self, student_id, objective='balanced', top_k=5):
        """
        Complete recommendation pipeline

        Args:
            student_id: Student identifier (can be string like "SXC_AL_Y1_B_PHY_P1_STU_001" or int)
            objective: Learning objective ('coverage', 'efficiency', 'success_rate', 'balanced')
            top_k: Number of questions to recommend

        Returns:
            List of recommended question IDs with scores
        """
        print(f"\n🎯 Generating recommendations for {student_id} with {objective} objective...")

        # 1. Load student history from normalized tables
        try:
            if isinstance(student_id, str):
                # Extract base student number from full student ID
                if "_STU_" in student_id:
                    base_number = int(student_id.split("_STU_")[-1])
                else:
                    base_number = int(student_id)
            else:
                base_number = student_id

            student_attempts = load_student_history_normalized(base_number)
        except Exception as e:
            print(f"⚠️  Error loading student history: {e}")
            student_attempts = []

        if not student_attempts:
            print("⚠️  No student history found, using default recommendations")
            return self._default_recommendations(top_k)

        # 2. Find current question (last attempted)
        current_question = student_attempts[-1]['question_id']
        print(f"📍 Current question: {current_question}")

        # 3. Create enriched state vector
        current_state = self.encoder.encode_student_context(
            current_question=current_question,
            student_attempts=student_attempts,
            objective=objective
        )
        print(f"🧠 Current state vector (top 3 clusters): {np.argsort(current_state)[-3:]}")

        # 4. Apply transition matrix to get next cluster priorities
        next_cluster_priorities = recommend_next_clusters(current_state, self.transition_matrix)
        print(f"➡️  Next priorities (top 3 clusters): {np.argsort(next_cluster_priorities)[-3:]}")

        # 5. Select questions based on cluster priorities
        recommendations = self._select_questions_by_clusters(
            next_cluster_priorities,
            student_attempts,
            top_k
        )

        return recommendations

    def _select_questions_by_clusters(self, cluster_priorities, student_attempts, top_k):
        """Select specific questions based on cluster priorities with better diversity"""

        # Get attempted question IDs
        attempted_questions = {attempt['question_id'] for attempt in student_attempts}

        # Score all unattempted questions by cluster
        questions_by_cluster = {}

        for q_idx in range(len(self.questions_df)):
            question_row = self.questions_df.iloc[q_idx]
            question_id = f"{question_row['paper_number']}_{question_row['question_number']}"

            if question_id not in attempted_questions:
                question_clusters = self.soft_clusters[q_idx]
                primary_cluster = np.argmax(question_clusters)

                # Score = weighted sum of cluster priorities
                score = np.sum(question_clusters * cluster_priorities)

                if primary_cluster not in questions_by_cluster:
                    questions_by_cluster[primary_cluster] = []

                questions_by_cluster[primary_cluster].append({
                    'question_id': question_id,
                    'question_index': q_idx,
                    'score': score,
                    'primary_cluster': primary_cluster,
                    'cluster_strength': np.max(question_clusters),
                    'paper_number': question_row['paper_number'],
                    'question_number': question_row['question_number']
                })

        # Get diverse recommendations across top clusters
        recommendations = []
        top_clusters = np.argsort(cluster_priorities)[-10:][::-1]  # Top 10 clusters

        # Try to get questions from different clusters for diversity
        for cluster_id in top_clusters:
            if cluster_id in questions_by_cluster and len(recommendations) < top_k:
                # Sort questions in this cluster by score
                cluster_questions = sorted(questions_by_cluster[cluster_id],
                                         key=lambda x: x['score'], reverse=True)

                # Add best question from this cluster
                if cluster_questions:
                    recommendations.append(cluster_questions[0])

        # If still need more questions, fill with highest scoring overall
        if len(recommendations) < top_k:
            all_questions = []
            for cluster_questions in questions_by_cluster.values():
                all_questions.extend(cluster_questions)

            all_questions.sort(key=lambda x: x['score'], reverse=True)

            # Add questions not already included
            included_ids = {r['question_id'] for r in recommendations}
            for question in all_questions:
                if question['question_id'] not in included_ids and len(recommendations) < top_k:
                    recommendations.append(question)

        print(f"\n📋 Top {min(top_k, len(recommendations))} Recommendations:")
        for i, rec in enumerate(recommendations[:top_k], 1):
            print(f"   {i}. Question {rec['question_id']}: "
                  f"Score={rec['score']:.3f}, "
                  f"Cluster={rec['primary_cluster']}, "
                  f"Paper={rec['paper_number']}")

        return recommendations[:top_k]

    def _default_recommendations(self, top_k):
        """Fallback recommendations when no student history"""
        print("📋 Using default recommendations...")

        # Recommend questions from different clusters for diversity
        cluster_questions = {}
        for q_idx in range(min(1000, len(self.questions_df))):  # Limit for performance
            primary_cluster = np.argmax(self.soft_clusters[q_idx])
            if primary_cluster not in cluster_questions:
                cluster_questions[primary_cluster] = []

            question_row = self.questions_df.iloc[q_idx]
            question_id = f"{question_row['paper_number']}_{question_row['question_number']}"
            cluster_questions[primary_cluster].append({
                'question_id': question_id,
                'question_index': q_idx,
                'paper_number': question_row['paper_number'],
                'question_number': question_row['question_number']
            })

        # Sample one question from each of the first top_k clusters
        recommendations = []
        for cluster_id in sorted(cluster_questions.keys())[:top_k]:
            if cluster_questions[cluster_id]:
                question_data = np.random.choice(cluster_questions[cluster_id])
                recommendations.append({
                    'question_id': question_data['question_id'],
                    'question_index': question_data['question_index'],
                    'score': 1.0,
                    'primary_cluster': cluster_id,
                    'cluster_strength': 1.0,
                    'paper_number': question_data['paper_number'],
                    'question_number': question_data['question_number']
                })

        return recommendations

    def analyze_recommendations(self, student_id, objectives=['coverage', 'efficiency', 'success_rate', 'balanced']):
        """Compare recommendations across different objectives"""
        print(f"\n🔬 Analyzing recommendations for {student_id} across objectives...")

        all_recommendations = {}
        for objective in objectives:
            try:
                recs = self.recommend_questions(student_id, objective, top_k=3)
                all_recommendations[objective] = [r['question_id'] for r in recs]
                print(f"\n{objective.upper()}: Questions {all_recommendations[objective]}")
            except Exception as e:
                print(f"❌ Error with {objective} objective: {e}")
                all_recommendations[objective] = []

        # Find overlap
        all_questions = set()
        for questions in all_recommendations.values():
            all_questions.update(questions)

        print(f"\n📊 Analysis:")
        print(f"   Total unique questions: {len(all_questions)}")

        # Find questions that appear in multiple objectives
        question_counts = {}
        for questions in all_recommendations.values():
            for q in questions:
                question_counts[q] = question_counts.get(q, 0) + 1

        popular_questions = [q for q, count in question_counts.items() if count > 1]
        if popular_questions:
            print(f"   Questions appearing in multiple objectives: {popular_questions}")
        else:
            print(f"   No questions appear in multiple objectives (high diversity)")

        return all_recommendations

    def get_question_details(self, question_id):
        """Get detailed information about a specific question"""
        try:
            question_idx = self.question_mapping.get(question_id)
            if question_idx is None:
                return None

            question_row = self.questions_df.iloc[question_idx]
            cluster_membership = self.soft_clusters[question_idx]

            # Fix array comparison bug
            def safe_has_data(value):
                """Safely check if data exists, handling arrays/lists"""
                try:
                    # Handle arrays/lists first before pd.isna check
                    if isinstance(value, (list, np.ndarray)):
                        return len(value) > 0
                    elif isinstance(value, str):
                        return len(value.strip()) > 0
                    elif pd.isna(value):
                        return False
                    else:
                        return value is not None
                except:
                    # Fallback for any edge cases
                    return value is not None and value != ""

            return {
                'question_id': question_id,
                'paper_number': question_row['paper_number'],
                'question_number': question_row['question_number'],
                'primary_cluster': np.argmax(cluster_membership),
                'cluster_distribution': cluster_membership,
                'top_3_clusters': np.argsort(cluster_membership)[-3:][::-1],
                'has_text': safe_has_data(question_row.get('combined_text')),
                'has_images': safe_has_data(question_row.get('images'))
            }
        except Exception as e:
            print(f"❌ Error getting question details: {e}")
            return None

    def explain_recommendation(self, student_id, question_id, objective='balanced'):
        """Explain why a specific question was recommended"""
        print(f"\n🔍 Explaining recommendation: {question_id} for {student_id}")

        # Get question details
        question_details = self.get_question_details(question_id)
        if not question_details:
            print(f"❌ Question {question_id} not found")
            return

        print(f"📝 Question Details:")
        print(f"   Paper: {question_details['paper_number']}")
        print(f"   Primary Cluster: {question_details['primary_cluster']}")
        print(f"   Top 3 Clusters: {question_details['top_3_clusters']}")

        # Load student history and create state
        try:
            if isinstance(student_id, str) and "_STU_" in student_id:
                base_number = int(student_id.split("_STU_")[-1])
            else:
                base_number = int(student_id)

            student_attempts = load_student_history_normalized(base_number)

            if student_attempts:
                current_question = student_attempts[-1]['question_id']
                current_state = self.encoder.encode_student_context(
                    current_question=current_question,
                    student_attempts=student_attempts,
                    objective=objective
                )

                print(f"\n🧠 Student State Analysis:")
                print(f"   Last attempted: {current_question}")
                print(f"   Strong clusters: {np.argsort(current_state)[-3:]}")
                print(f"   Objective: {objective}")

                # Show why this question matches
                question_cluster_strength = question_details['cluster_distribution']
                alignment_score = np.sum(current_state * question_cluster_strength)
                print(f"   Alignment score: {alignment_score:.3f}")

        except Exception as e:
            print(f"⚠️  Could not load student analysis: {e}")


def main():
    """Example usage of the complete recommendation system"""
    print("🚀 COMPLETE RECOMMENDATION ENGINE DEMO")
    print("=" * 60)

    try:
        # Initialize the engine
        engine = QuestionRecommendationEngine()

        # Test with student (use base student number or full ID)
        test_students = [1, "SXC_AL_Y1_B_PHY_P1_STU_001"]

        for student_id in test_students:
            print(f"\n{'='*60}")
            print(f"🎓 Testing with student: {student_id}")

            try:
                # Get recommendations for different objectives
                recommendations = engine.analyze_recommendations(student_id)

                # Deep dive into one objective
                print(f"\n🔍 Detailed recommendation for BALANCED objective:")
                detailed_recs = engine.recommend_questions(student_id, 'balanced', top_k=5)

                # Explain first recommendation
                if detailed_recs:
                    first_rec = detailed_recs[0]
                    engine.explain_recommendation(student_id, first_rec['question_id'], 'balanced')

            except Exception as e:
                print(f"❌ Error testing student {student_id}: {e}")
                continue

        print(f"\n✅ RECOMMENDATION ENGINE DEMO COMPLETED!")
        print("=" * 60)
        print(f"🎯 Integration Ready:")
        print(f"   ✅ Enriched vector encoding")
        print(f"   ✅ Transition matrix pathways")
        print(f"   ✅ Multi-objective optimization")
        print(f"   ✅ Question scoring & ranking")
        print(f"   ✅ Explanation & transparency")

        return engine

    except Exception as e:
        print(f"❌ Failed to initialize recommendation engine: {e}")
        print(f"💡 Check that required files exist:")
        print(f"   • combined_questions.parquet")
        print(f"   • normalized_*_*.parquet files")
        return None


if __name__ == "__main__":
    engine = main()

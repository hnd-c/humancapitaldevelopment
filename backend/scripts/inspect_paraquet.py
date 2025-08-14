import pandas as pd
import numpy as np
from collections import defaultdict

def inspect_combined_questions():
    """
    Inspect combined_questions.parquet to identify missing questions and papers.
    Each paper should have 40 questions.
    """

    print("🔍 INSPECTING COMBINED_QUESTIONS.PARQUET")
    print("=" * 50)

    try:
        # Load the parquet file
        df = pd.read_parquet('../combined_questions.parquet')

        # Reset index to make paper_number and question_number regular columns
        df = df.reset_index()

        print(f"📊 Total records loaded: {len(df)}")
        print(f"📋 Columns: {list(df.columns)}")
        print(f"📋 Index was: {df.index.names if hasattr(df.index, 'names') else 'RangeIndex'}")
        print()

        # Display sample data
        print("📝 Sample data (first 5 rows):")
        print(df.head())
        print()

        # Analyze soft cluster column if it exists
        if 'soft_cluster' in df.columns:
            print("🎯 SOFT CLUSTER ANALYSIS:")
            print("-" * 40)

            # Check if soft_cluster contains probability arrays
            soft_cluster_sample = df['soft_cluster'].dropna()
            if len(soft_cluster_sample) > 0:
                first_soft_cluster = soft_cluster_sample.iloc[0]

                # Handle both list and numpy array formats
                if (isinstance(first_soft_cluster, (list, np.ndarray)) and len(first_soft_cluster) > 1):
                    # This is the new format with probability arrays
                    print(f"✅ Soft cluster format: Probability arrays")
                    print(f"📊 Records with soft clusters: {len(soft_cluster_sample)}")
                    print(f"🎯 Number of clusters: {len(first_soft_cluster)}")

                    # Calculate hard cluster assignments (max probability)
                    hard_clusters = []
                    confidences = []

                    for prob_array in soft_cluster_sample:
                        if isinstance(prob_array, (list, np.ndarray)) and len(prob_array) > 0:
                            # Convert to numpy array if it's a list
                            if isinstance(prob_array, list):
                                prob_array = np.array(prob_array)
                            max_idx = np.argmax(prob_array)
                            max_prob = np.max(prob_array)
                            hard_clusters.append(max_idx)
                            confidences.append(max_prob)

                    # Hard cluster distribution
                    print(f"\n📈 Hard cluster distribution (max probability):")
                    hard_cluster_counts = pd.Series(hard_clusters).value_counts().sort_index()
                    for cluster_id, count in hard_cluster_counts.items():
                        percentage = (count / len(hard_clusters)) * 100
                        print(f"   Cluster {cluster_id}: {count} questions ({percentage:.1f}%)")

                    # Confidence statistics
                    print(f"\n📊 Clustering confidence statistics:")
                    conf_stats = pd.Series(confidences).describe()
                    print(f"   Mean confidence: {conf_stats['mean']:.3f}")
                    print(f"   Median confidence: {conf_stats['50%']:.3f}")
                    print(f"   Min confidence: {conf_stats['min']:.3f}")
                    print(f"   Max confidence: {conf_stats['max']:.3f}")

                    # Show sample probabilities
                    print(f"\n🔍 Sample probability distributions (first 3 rows):")
                    for i, prob_array in enumerate(soft_cluster_sample.head(3)):
                        if isinstance(prob_array, list):
                            prob_array = np.array(prob_array)
                        max_cluster = np.argmax(prob_array)
                        max_prob = np.max(prob_array)
                        first_5_probs = [f'{p:.3f}' for p in prob_array[:5]]
                        print(f"   Row {i+1}: Cluster {max_cluster} ({max_prob:.3f}), Full: {first_5_probs}{'...' if len(prob_array) > 5 else ''}")

                else:
                    # Old format or other format
                    print(f"⚠️  Soft cluster format: {type(first_soft_cluster)}")
                    print(f"📊 Sample value: {str(first_soft_cluster)[:100]}...")
                    try:
                        print(f"📈 Total records: {len(soft_cluster_sample)}")
                        # Skip value_counts for non-hashable types
                    except Exception as e:
                        print(f"⚠️  Cannot analyze distribution: {e}")
            else:
                print("❌ No soft cluster data found")
            print()

        # Analyze UMAP embeddings if they exist
        if 'umap_embedding' in df.columns:
            print("🗺️  UMAP EMBEDDING ANALYSIS:")
            print("-" * 40)

            umap_sample = df['umap_embedding'].dropna()
            if len(umap_sample) > 0:
                first_umap = umap_sample.iloc[0]
                if isinstance(first_umap, (list, np.ndarray)):
                    print(f"✅ UMAP embeddings found: {len(umap_sample)} records")
                    print(f"🎯 UMAP dimensions: {len(first_umap)}")

                    # Convert to numpy for analysis
                    umap_array = np.array([emb for emb in umap_sample if isinstance(emb, (list, np.ndarray))])

                    if len(umap_array) > 0:
                        print(f"📊 UMAP statistics:")
                        print(f"   Mean: {np.mean(umap_array, axis=0)[:3]} ... (first 3 dims)")
                        print(f"   Std:  {np.std(umap_array, axis=0)[:3]} ... (first 3 dims)")
                        print(f"   Range: [{np.min(umap_array):.3f}, {np.max(umap_array):.3f}]")
                else:
                    print(f"⚠️  UMAP format: {type(first_umap)}")
            else:
                print("❌ No UMAP embedding data found")
            print()

        # Analyze OpenAI embeddings if they exist
        if 'openai_embedding' in df.columns:
            print("🤖 OPENAI EMBEDDING ANALYSIS:")
            print("-" * 40)

            openai_sample = df['openai_embedding'].dropna()
            if len(openai_sample) > 0:
                first_openai = openai_sample.iloc[0]
                if isinstance(first_openai, (list, np.ndarray)):
                    print(f"✅ OpenAI embeddings found: {len(openai_sample)} records")
                    print(f"🎯 Embedding dimensions: {len(first_openai)}")
                    print(f"📊 Sample values: {first_openai[:5]} ... (first 5 dims)")
                else:
                    print(f"⚠️  OpenAI format: {type(first_openai)}")
            else:
                print("❌ No OpenAI embedding data found")
            print()

        # Group by paper_number to count questions per paper
        question_counts = df.groupby('paper_number')['question_number'].agg(['count', 'min', 'max', 'nunique']).reset_index()
        question_counts.columns = ['paper_number', 'total_questions', 'min_question', 'max_question', 'unique_questions']

        print(f"📈 QUESTION COUNT ANALYSIS")
        print("-" * 40)
        print(f"Total papers found: {len(question_counts)}")
        print()

        # Expected questions per paper
        EXPECTED_QUESTIONS = 40

        # Find papers with missing questions
        incomplete_papers = question_counts[question_counts['total_questions'] != EXPECTED_QUESTIONS]
        complete_papers = question_counts[question_counts['total_questions'] == EXPECTED_QUESTIONS]

        print(f"✅ Complete papers (40 questions): {len(complete_papers)}")
        print(f"❌ Incomplete papers: {len(incomplete_papers)}")
        print()

        if len(incomplete_papers) > 0:
            print("🚨 PAPERS WITH MISSING QUESTIONS:")
            print("-" * 40)
            for _, row in incomplete_papers.iterrows():
                paper = row['paper_number']
                count = row['total_questions']
                min_q = row['min_question']
                max_q = row['max_question']
                unique = row['unique_questions']
                missing = EXPECTED_QUESTIONS - count

                print(f"📄 {paper}:")
                print(f"   • Questions found: {count}/{EXPECTED_QUESTIONS} (missing {missing})")
                print(f"   • Range: {min_q} to {max_q}")
                print(f"   • Unique questions: {unique}")

                # Find which specific questions are missing
                paper_questions = set(df[df['paper_number'] == paper]['question_number'])
                expected_questions = set(range(1, EXPECTED_QUESTIONS + 1))
                missing_questions = expected_questions - paper_questions

                if missing_questions:
                    missing_list = sorted(list(missing_questions))
                    if len(missing_list) <= 10:
                        print(f"   • Missing questions: {missing_list}")
                    else:
                        print(f"   • Missing questions: {missing_list[:10]}... (and {len(missing_list)-10} more)")

                print()

        # Analyze by year/session
        print("📅 ANALYSIS BY YEAR/SESSION:")
        print("-" * 40)

        # Extract year and session from paper_number
        def extract_year_session(paper_number):
            parts = paper_number.split('_')
            if len(parts) >= 3:
                year_session = parts[1]  # e.g., 'm17', 's17', 'w17'
                return year_session
            return 'unknown'

        question_counts['year_session'] = question_counts['paper_number'].apply(extract_year_session)

        # Group by year/session
        year_session_summary = question_counts.groupby('year_session').agg({
            'paper_number': 'count',
            'total_questions': ['min', 'max', 'mean']
        }).round(2)

        year_session_summary.columns = ['papers_count', 'min_questions', 'max_questions', 'avg_questions']
        year_session_summary = year_session_summary.reset_index()

        print(year_session_summary.to_string(index=False))
        print()

        # Find year/sessions with problems
        problematic_sessions = []
        for _, row in year_session_summary.iterrows():
            session = row['year_session']
            min_q = row['min_questions']
            max_q = row['max_questions']
            avg_q = row['avg_questions']

            if min_q < EXPECTED_QUESTIONS or max_q < EXPECTED_QUESTIONS or avg_q < EXPECTED_QUESTIONS:
                problematic_sessions.append(session)

        if problematic_sessions:
            print("⚠️  PROBLEMATIC YEAR/SESSIONS:")
            print("-" * 40)
            for session in problematic_sessions:
                session_papers = question_counts[question_counts['year_session'] == session]
                incomplete_in_session = session_papers[session_papers['total_questions'] != EXPECTED_QUESTIONS]

                print(f"📅 {session}:")
                print(f"   • Total papers: {len(session_papers)}")
                print(f"   • Incomplete papers: {len(incomplete_in_session)}")
                if len(incomplete_in_session) > 0:
                    incomplete_list = incomplete_in_session['paper_number'].tolist()
                    if len(incomplete_list) <= 5:
                        print(f"   • Incomplete: {incomplete_list}")
                    else:
                        print(f"   • Incomplete: {incomplete_list[:5]}... (and {len(incomplete_list)-5} more)")
                print()

        # Summary statistics
        print("📊 OVERALL STATISTICS:")
        print("-" * 40)
        print(f"Total papers: {len(question_counts)}")
        print(f"Complete papers: {len(complete_papers)} ({len(complete_papers)/len(question_counts)*100:.1f}%)")
        print(f"Incomplete papers: {len(incomplete_papers)} ({len(incomplete_papers)/len(question_counts)*100:.1f}%)")
        print(f"Total questions found: {df['question_number'].count()}")
        print(f"Expected total questions: {len(question_counts) * EXPECTED_QUESTIONS}")
        print(f"Missing questions: {len(question_counts) * EXPECTED_QUESTIONS - df['question_number'].count()}")

        # Question number distribution
        print("\n📈 QUESTION NUMBER DISTRIBUTION:")
        print("-" * 40)
        question_dist = df['question_number'].value_counts().sort_index()
        print("Question number: Count")
        for q_num in range(1, min(21, question_dist.index.max() + 1)):  # Show first 20
            count = question_dist.get(q_num, 0)
            expected_count = len(question_counts)
            print(f"Q{q_num:2d}: {count:3d}/{expected_count:3d} papers ({count/expected_count*100:5.1f}%)")

        if question_dist.index.max() > 20:
            print("...")
            for q_num in range(max(21, question_dist.index.max() - 4), question_dist.index.max() + 1):
                count = question_dist.get(q_num, 0)
                expected_count = len(question_counts)
                print(f"Q{q_num:2d}: {count:3d}/{expected_count:3d} papers ({count/expected_count*100:5.1f}%)")

    except FileNotFoundError:
        print("❌ File 'combined_questions.parquet' not found!")
        print("Make sure the file exists in the current directory.")
    except Exception as e:
        print(f"❌ Error reading parquet file: {e}")

if __name__ == "__main__":
    inspect_combined_questions()

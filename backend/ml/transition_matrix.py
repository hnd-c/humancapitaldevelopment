import numpy as np
import pandas as pd

def _normalize_transition_matrix(T):
    """Normalize each row to sum to 1 (valid probability distribution)"""
    T_normalized = T.copy()
    for i in range(T.shape[0]):
        row_sum = T_normalized[i].sum()
        if row_sum > 0:
            T_normalized[i] /= row_sum
        else:
            # If no transitions from cluster i, uniform distribution
            T_normalized[i] = np.ones(T.shape[1]) / T.shape[1]

    return T_normalized


def _build_cooccurrence_transitions(alpha=0.1, normalize=True):
    """
    Build transitions based on how often clusters co-occur in the same questions
    Logic: If a question involves both cluster i and j, there should be transitions i→j and j→i
    """
    try:
        # Load from combined_questions.parquet (based on enriched_vector.py pattern)
        df = pd.read_parquet("../combined_questions.parquet")
        soft_clusters = np.stack(df['soft_cluster'].values)  # Convert to numpy array
        n_clusters = soft_clusters.shape[1]
        n_questions = soft_clusters.shape[0]
        print(f"✅ Loaded {n_questions} questions with {n_clusters} clusters")
    except FileNotFoundError:
        print("❌ combined_questions.parquet not found!")
        print("💡 Make sure the clustering data is available")
        return None
    except Exception as e:
        print(f"❌ Error loading clustering data: {e}")
        return None

    T = np.zeros((n_clusters, n_clusters))

    # For each question, create transitions between its clusters
    for q in range(n_questions):
        question_memberships = soft_clusters[q]  # n_clusters-dimensional vector

        # Create transitions weighted by membership strength
        for i in range(n_clusters):
            for j in range(n_clusters):
                if i != j:  # No self-transitions initially
                    # Transition strength = geometric mean of memberships
                    transition_strength = np.sqrt(question_memberships[i] * question_memberships[j])
                    T[i, j] += transition_strength

    # Add small self-transition probabilities (students might stay in same concept)
    for i in range(n_clusters):
        T[i, i] = alpha * np.sum(T[i, :])  # Self-transition = alpha * total outgoing

    if normalize:
        T = _normalize_transition_matrix(T)

    return T


def recommend_next_clusters(current_state_vector, transition_matrix):
    """
    Use current student state to recommend next cluster priorities

    Args:
        current_state_vector: n_clusters-D probability distribution (from enriched_vector.py)
        transition_matrix: n_clusters x n_clusters transition probabilities

    Returns:
        next_state_vector: n_clusters-D probability distribution for next recommendations
    """
    # Matrix multiplication: current_state @ transition_matrix
    next_state = current_state_vector @ transition_matrix

    # Ensure it's still a valid probability distribution
    next_state = np.maximum(next_state, 0.001)  # Minimum probability
    next_state /= next_state.sum()  # Normalize

    return next_state


def analyze_transition_patterns(transition_matrix, top_k=5):
    """
    Analyze the most common learning pathways in the transition matrix

    Args:
        transition_matrix: n_clusters x n_clusters transition matrix
        top_k: Number of top transitions to show per cluster

    Returns:
        dict: Analysis results with top transitions per cluster
    """
    n_clusters = transition_matrix.shape[0]
    analysis = {}

    print(f"\n📊 TRANSITION MATRIX ANALYSIS:")
    print("=" * 50)

    for i in range(n_clusters):
        # Get top transitions from cluster i
        row = transition_matrix[i]
        top_indices = np.argsort(row)[-top_k:][::-1]  # Top k indices, descending
        top_probs = row[top_indices]

        analysis[i] = {
            'top_transitions': list(zip(top_indices, top_probs)),
            'entropy': -np.sum(row * np.log(row + 1e-10)),  # Diversity measure
            'self_transition': row[i]
        }

        print(f"\n🎯 Cluster {i}:")
        print(f"   Self-transition: {row[i]:.3f}")
        print(f"   Entropy (diversity): {analysis[i]['entropy']:.3f}")
        print(f"   Top {top_k} transitions:")
        for j, (target_cluster, prob) in enumerate(analysis[i]['top_transitions']):
            arrow = "→" if target_cluster != i else "↻"
            print(f"     {i} {arrow} {target_cluster}: {prob:.3f}")

    return analysis


def save_transition_matrix(transition_matrix, filename=None):
    """Save transition matrix for later use"""
    if filename is None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transition_matrix_{timestamp}.npz"

    np.savez_compressed(filename, transition_matrix=transition_matrix)
    print(f"💾 Saved transition matrix to: {filename}")
    return filename


def load_transition_matrix(filename):
    """Load saved transition matrix"""
    try:
        data = np.load(filename)
        transition_matrix = data['transition_matrix']
        print(f"📖 Loaded transition matrix from: {filename}")
        print(f"   Shape: {transition_matrix.shape}")
        return transition_matrix
    except FileNotFoundError:
        print(f"❌ File not found: {filename}")
        return None
    except Exception as e:
        print(f"❌ Error loading transition matrix: {e}")
        return None


def demonstrate_recommendations():
    """Demonstrate how to use transition matrix for recommendations"""
    print(f"\n🚀 DEMONSTRATION: Learning Path Recommendations")
    print("=" * 60)

    # Build transition matrix
    T = _build_cooccurrence_transitions(alpha=0.1, normalize=True)
    if T is None:
        return

    # Create example student state (focused on cluster 2)
    n_clusters = T.shape[0]
    current_state = np.zeros(n_clusters)
    current_state[2] = 0.7  # Strong in cluster 2
    current_state[5] = 0.2  # Some knowledge in cluster 5
    current_state[8] = 0.1  # Little knowledge in cluster 8

    print(f"\n👤 Current Student State:")
    top_current = np.argsort(current_state)[-5:][::-1]
    for i in top_current:
        if current_state[i] > 0.01:
            print(f"   Cluster {i}: {current_state[i]:.3f}")

    # Get recommendations
    next_state = recommend_next_clusters(current_state, T)

    print(f"\n🎯 Recommended Next Focus Areas:")
    top_next = np.argsort(next_state)[-5:][::-1]
    for i in top_next:
        change = next_state[i] - current_state[i]
        arrow = "↗️" if change > 0.01 else "→" if abs(change) < 0.01 else "↘️"
        print(f"   Cluster {i}: {next_state[i]:.3f} {arrow} (Δ{change:+.3f})")

    return T, current_state, next_state


def main():
    """Main function to build and analyze transition matrix"""
    print(f"🔄 BUILDING CO-OCCURRENCE TRANSITION MATRIX")
    print("=" * 60)

    # Build transition matrix
    T = _build_cooccurrence_transitions(alpha=0.1, normalize=True)

    if T is None:
        print("❌ Cannot proceed without clustering data")
        return

    print(f"\n📊 Transition Matrix Built Successfully!")
    print(f"   Shape: {T.shape}")
    print(f"   Row sums (should be ~1.0): {T.sum(axis=1)[:5].round(3)}")
    print(f"   Sparsity: {(T == 0).sum() / T.size:.1%} zeros")

    # Analyze patterns
    analysis = analyze_transition_patterns(T, top_k=3)

    # Save matrix
    filename = save_transition_matrix(T)

    # Demonstrate usage
    demonstrate_recommendations()

    print(f"\n✅ TRANSITION MATRIX SYSTEM READY!")
    print("=" * 60)
    print(f"🎯 Use Cases:")
    print(f"   • Learning path recommendations")
    print(f"   • Adaptive question sequencing")
    print(f"   • Knowledge prerequisite modeling")
    print(f"   • Curriculum optimization")

    return T


if __name__ == "__main__":
    main()

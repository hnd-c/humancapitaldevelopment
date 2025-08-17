#!/usr/bin/env python3
"""
2D UMAP Embedding Generator for Combined Questions
Converts OpenAI embeddings to 2D UMAP embeddings and adds them to the parquet file
"""

import pandas as pd
import numpy as np
import umap
import pickle
import time
from pathlib import Path
import ast
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_parquet_file(file_path):
    """Load the combined_questions.parquet file"""
    try:
        logger.info(f"📂 Loading parquet file: {file_path}")
        df = pd.read_parquet(file_path)
        logger.info(f"✅ Successfully loaded {len(df)} records")
        logger.info(f"📋 Columns: {list(df.columns)}")
        return df
    except Exception as e:
        logger.error(f"❌ Error loading parquet file: {e}")
        raise

def parse_openai_embeddings(df):
    """Parse OpenAI embeddings from string format to numpy arrays"""
    logger.info("🔄 Parsing OpenAI embeddings...")

    embeddings = []
    valid_indices = []

    for idx, row in df.iterrows():
        try:
            embedding = row['openai_embedding']

            # Handle different formats
            if isinstance(embedding, str):
                # Try to parse as literal
                try:
                    embedding_array = np.array(ast.literal_eval(embedding))
                except:
                    # If that fails, try eval (less safe but sometimes necessary)
                    embedding_array = np.array(eval(embedding))
            elif isinstance(embedding, (list, np.ndarray)):
                embedding_array = np.array(embedding)
            else:
                logger.warning(f"⚠️ Skipping row {idx}: Invalid embedding format")
                continue

            # Validate embedding dimensions
            if len(embedding_array.shape) == 1 and len(embedding_array) > 0:
                embeddings.append(embedding_array)
                valid_indices.append(idx)
            else:
                logger.warning(f"⚠️ Skipping row {idx}: Invalid embedding shape {embedding_array.shape}")

        except Exception as e:
            logger.warning(f"⚠️ Error parsing embedding at row {idx}: {e}")
            continue

    if not embeddings:
        raise ValueError("❌ No valid embeddings found!")

    embeddings_matrix = np.vstack(embeddings)
    logger.info(f"✅ Parsed {len(embeddings)} valid embeddings with shape {embeddings_matrix.shape}")

    return embeddings_matrix, valid_indices

def generate_2d_umap(embeddings_matrix, n_neighbors=15, min_dist=0.1, metric='cosine', random_state=42):
    """Generate 2D UMAP embeddings from OpenAI embeddings"""
    logger.info("🎯 Generating 2D UMAP embeddings...")
    logger.info(f"📊 Input shape: {embeddings_matrix.shape}")
    logger.info(f"⚙️ Parameters: n_neighbors={n_neighbors}, min_dist={min_dist}, metric={metric}")

    start_time = time.time()

    # Initialize UMAP
    umap_reducer = umap.UMAP(
        n_components=2,
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        metric=metric,
        random_state=random_state,
        verbose=True
    )

    # Fit and transform
    umap_2d = umap_reducer.fit_transform(embeddings_matrix)

    elapsed_time = time.time() - start_time
    logger.info(f"✅ UMAP completed in {elapsed_time:.2f} seconds")
    logger.info(f"📊 Output shape: {umap_2d.shape}")
    logger.info(f"📈 X range: [{umap_2d[:, 0].min():.3f}, {umap_2d[:, 0].max():.3f}]")
    logger.info(f"📈 Y range: [{umap_2d[:, 1].min():.3f}, {umap_2d[:, 1].max():.3f}]")

    return umap_2d, umap_reducer

def add_2d_umap_to_dataframe(df, umap_2d, valid_indices):
    """Add 2D UMAP embeddings to the dataframe"""
    logger.info("🔄 Adding 2D UMAP embeddings to dataframe...")

    # Initialize the 2D UMAP column with None/NaN
    df['umap_2d'] = None

    # Add 2D UMAP embeddings for valid indices
    for i, idx in enumerate(valid_indices):
        # Store as list for parquet compatibility
        df.at[idx, 'umap_2d'] = umap_2d[i].tolist()

    # Count successful additions
    successful_additions = df['umap_2d'].notna().sum()
    logger.info(f"✅ Added 2D UMAP embeddings to {successful_additions} rows")

    return df

def save_updated_parquet(df, output_path):
    """Save the updated dataframe to parquet"""
    logger.info(f"💾 Saving updated parquet file to: {output_path}")

    try:
        df.to_parquet(output_path, index=False)
        logger.info("✅ Successfully saved updated parquet file")
    except Exception as e:
        logger.error(f"❌ Error saving parquet file: {e}")
        raise


def main():
    """Main function to process the parquet file and add 2D UMAP embeddings"""

    print("🚀 STARTING 2D UMAP EMBEDDING GENERATION")
    print("=" * 50)

    # File paths
    input_file = Path("../combined_questions.parquet")  # Go up one directory to backend root
    output_file = Path("../combined_questions_2d.parquet")  # Save in backend root


    try:
        # Step 1: Load the parquet file
        df = load_parquet_file(input_file)

        # Step 2: Parse OpenAI embeddings
        embeddings_matrix, valid_indices = parse_openai_embeddings(df)

        # Step 3: Generate 2D UMAP embeddings
        umap_2d, umap_reducer = generate_2d_umap(embeddings_matrix)

        # Step 4: Add 2D UMAP embeddings to dataframe
        df_updated = add_2d_umap_to_dataframe(df, umap_2d, valid_indices)

        # Step 5: Save updated parquet file
        save_updated_parquet(df_updated, output_file)


        # Final statistics
        print("\n📊 FINAL STATISTICS")
        print("=" * 50)
        print(f"📂 Input file: {input_file}")
        print(f"📂 Output file: {output_file}")
        print(f"📊 Total records: {len(df_updated)}")
        print(f"✅ Records with 2D UMAP: {df_updated['umap_2d'].notna().sum()}")
        print(f"❌ Records without 2D UMAP: {df_updated['umap_2d'].isna().sum()}")
        print(f"📋 Updated columns: {list(df_updated.columns)}")

        print("\n✅ 2D UMAP EMBEDDING GENERATION COMPLETED SUCCESSFULLY!")

    except Exception as e:
        logger.error(f"❌ Process failed: {e}")
        print(f"\n❌ PROCESS FAILED: {e}")
        raise

if __name__ == "__main__":
    main()
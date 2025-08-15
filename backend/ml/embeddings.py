# Consolidated embeddings file - Functions moved to ml/vector_operations_manager.py
# This file is a placeholder to prevent import errors during consolidation
# All embedding operations are now handled by VectorOperationsManager

from .vector_operations_manager import VectorOperationsManager

# Legacy compatibility class
class EmbeddingManager:
    def __init__(self, db_manager):
        print("⚠️  EmbeddingManager is deprecated. Use VectorOperationsManager instead.")
        self._manager = VectorOperationsManager(db_manager)
        
    def __getattr__(self, name):
        return getattr(self._manager, name)

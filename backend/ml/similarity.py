# Consolidated similarity file - Functions moved to ml/vector_operations_manager.py  
# This file is a placeholder to prevent import errors during consolidation
# All similarity operations are now handled by VectorOperationsManager

from .vector_operations_manager import VectorOperationsManager

# Legacy compatibility class
class SimilarityCalculator:
    def __init__(self, db_manager):
        print("⚠️  SimilarityCalculator is deprecated. Use VectorOperationsManager instead.")
        self._manager = VectorOperationsManager(db_manager)
        
    def __getattr__(self, name):
        return getattr(self._manager, name)

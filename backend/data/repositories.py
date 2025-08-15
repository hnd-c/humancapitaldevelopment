# Consolidated repository file - Vector operations moved to ml/vector_operations_manager.py
# This file is a placeholder to prevent import errors during consolidation
# All vector operations are now handled by VectorOperationsManager

from ml.vector_operations_manager import VectorOperationsManager

# Legacy compatibility class
class VectorOperations:
    def __init__(self, db_manager):
        print("⚠️  VectorOperations is deprecated. Use VectorOperationsManager instead.")
        self._manager = VectorOperationsManager(db_manager)
        
    def __getattr__(self, name):
        return getattr(self._manager, name)

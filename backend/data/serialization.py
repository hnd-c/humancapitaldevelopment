#!/usr/bin/env python3
"""
Serialization Utilities - Efficient cache serialization and deserialization

This module provides:
- Optimized serialization for dataclasses and common Python objects
- Automatic handling of numpy arrays, datetime objects, and custom types
- Compression support for large objects
- Type-safe deserialization with validation
"""

import json
import pickle
import gzip
import lzma
from dataclasses import dataclass, fields, is_dataclass, asdict
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Union, Type, TypeVar
from enum import Enum
import numpy as np
import logging

T = TypeVar('T')

class SerializationMethod(Enum):
    """Available serialization methods"""
    JSON = "json"
    PICKLE = "pickle"
    JSON_COMPRESSED = "json_gz"
    PICKLE_COMPRESSED = "pickle_lzma"

class CacheSerializer:
    """Optimized cache serialization with automatic type handling"""

    def __init__(self, default_method: SerializationMethod = SerializationMethod.JSON_COMPRESSED):
        self.default_method = default_method
        self.logger = logging.getLogger(__name__)

    def serialize(self, obj: Any, method: Optional[SerializationMethod] = None,
                 compress_threshold: int = 1024) -> bytes:
        """
        Serialize object with automatic optimization

        Args:
            obj: Object to serialize
            method: Serialization method (defaults to instance default)
            compress_threshold: Size threshold for automatic compression (bytes)

        Returns:
            Serialized bytes
        """
        if method is None:
            method = self.default_method

        try:
            # Pre-process object for serialization
            processed_obj = self._preprocess_object(obj)

            # Choose serialization method
            if method == SerializationMethod.JSON:
                serialized = json.dumps(processed_obj, default=self._json_serializer).encode('utf-8')
            elif method == SerializationMethod.PICKLE:
                serialized = pickle.dumps(processed_obj)
            elif method == SerializationMethod.JSON_COMPRESSED:
                json_data = json.dumps(processed_obj, default=self._json_serializer).encode('utf-8')
                serialized = gzip.compress(json_data)
            elif method == SerializationMethod.PICKLE_COMPRESSED:
                pickle_data = pickle.dumps(processed_obj)
                serialized = lzma.compress(pickle_data)
            else:
                raise ValueError(f"Unknown serialization method: {method}")

            # Auto-compress if size exceeds threshold and not already compressed
            if (len(serialized) > compress_threshold and
                method not in [SerializationMethod.JSON_COMPRESSED, SerializationMethod.PICKLE_COMPRESSED]):
                self.logger.debug(f"Auto-compressing large object ({len(serialized)} bytes)")
                if method == SerializationMethod.JSON:
                    return gzip.compress(serialized)
                elif method == SerializationMethod.PICKLE:
                    return lzma.compress(serialized)

            return serialized

        except Exception as e:
            self.logger.error(f"Serialization failed: {e}")
            raise

    def deserialize(self, data: Union[bytes, str], target_type: Optional[Type[T]] = None,
                   method: Optional[SerializationMethod] = None) -> T:
        """
        Deserialize data with automatic type detection and validation

        Args:
            data: Serialized data (bytes or string)
            target_type: Expected type for validation
            method: Deserialization method (auto-detected if None)

        Returns:
            Deserialized object
        """
        try:
            # Handle string input (Redis sometimes returns strings)
            if isinstance(data, str):
                # Try to parse as JSON first (old format)
                try:
                    obj = json.loads(data)
                    return self._postprocess_object(obj, target_type)
                except json.JSONDecodeError:
                    # Convert to bytes for further processing
                    data = data.encode('utf-8')

            # Now we have bytes - auto-detect compression and format
            is_gzip = len(data) >= 2 and data[:2] == b'\x1f\x8b'
            is_lzma = len(data) >= 6 and data[:6] == b'\xfd7zXZ\x00'

            if method is None:
                # Auto-detect method
                if is_gzip:
                    method = SerializationMethod.JSON_COMPRESSED
                elif is_lzma:
                    method = SerializationMethod.PICKLE_COMPRESSED
                else:
                    # Try to detect based on content
                    try:
                        test_str = data.decode('utf-8')
                        # If it starts with { or [ it's likely JSON
                        if test_str.strip().startswith(('{', '[')):
                            method = SerializationMethod.JSON
                        else:
                            method = SerializationMethod.PICKLE
                    except UnicodeDecodeError:
                        method = SerializationMethod.PICKLE

            # Decompress if needed
            if method == SerializationMethod.JSON_COMPRESSED:
                data = gzip.decompress(data)
                method = SerializationMethod.JSON
            elif method == SerializationMethod.PICKLE_COMPRESSED:
                data = lzma.decompress(data)
                method = SerializationMethod.PICKLE

            # Deserialize
            if method == SerializationMethod.JSON:
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                obj = json.loads(data)
            elif method == SerializationMethod.PICKLE:
                obj = pickle.loads(data)
            else:
                raise ValueError(f"Unknown deserialization method: {method}")

            # Post-process and validate
            result = self._postprocess_object(obj, target_type)

            return result

        except Exception as e:
            self.logger.error(f"Deserialization failed: {e}")
            raise

    def _preprocess_object(self, obj: Any) -> Any:
        """Convert object to serialization-friendly format"""
        if obj is None:
            return None

        if isinstance(obj, (str, int, float, bool)):
            return obj

        if isinstance(obj, (list, tuple)):
            return [self._preprocess_object(item) for item in obj]

        if isinstance(obj, dict):
            return {key: self._preprocess_object(value) for key, value in obj.items()}

        if is_dataclass(obj):
            # Convert dataclass to dict with type information
            result = asdict(obj)
            result['__dataclass_type__'] = f"{obj.__class__.__module__}.{obj.__class__.__name__}"
            return result

        if isinstance(obj, np.ndarray):
            return {
                '__numpy_array__': True,
                'data': obj.tolist(),
                'dtype': str(obj.dtype),
                'shape': obj.shape
            }

        if isinstance(obj, (datetime, date)):
            return {
                '__datetime__': True,
                'isoformat': obj.isoformat(),
                'type': obj.__class__.__name__
            }

        # Fallback for other objects
        if hasattr(obj, '__dict__'):
            result = obj.__dict__.copy()
            result['__object_type__'] = f"{obj.__class__.__module__}.{obj.__class__.__name__}"
            return result

        return str(obj)  # Final fallback

    def _postprocess_object(self, obj: Any, target_type: Optional[Type] = None) -> Any:
        """Convert deserialized object back to original types"""
        if obj is None:
            return None

        if isinstance(obj, (str, int, float, bool)):
            return obj

        if isinstance(obj, list):
            return [self._postprocess_object(item) for item in obj]

        if isinstance(obj, dict):
            # Handle special type markers
            if '__numpy_array__' in obj:
                array_data = np.array(obj['data'], dtype=obj['dtype'])
                return array_data.reshape(obj['shape'])

            if '__datetime__' in obj:
                if obj['type'] == 'datetime':
                    return datetime.fromisoformat(obj['isoformat'])
                elif obj['type'] == 'date':
                    return date.fromisoformat(obj['isoformat'])

            if '__dataclass_type__' in obj:
                # Reconstruct dataclass
                type_path = obj.pop('__dataclass_type__')
                if target_type and is_dataclass(target_type):
                    # Use provided target type
                    field_dict = {field.name: self._postprocess_object(obj.get(field.name))
                                 for field in fields(target_type)}
                    return target_type(**field_dict)
                else:
                    # Try to import and reconstruct the type
                    try:
                        module_name, class_name = type_path.rsplit('.', 1)
                        module = __import__(module_name, fromlist=[class_name])
                        cls = getattr(module, class_name)
                        field_dict = {key: self._postprocess_object(value)
                                     for key, value in obj.items()}
                        return cls(**field_dict)
                    except (ImportError, AttributeError):
                        # Return as dict if reconstruction fails
                        return {key: self._postprocess_object(value)
                               for key, value in obj.items()}

            if '__object_type__' in obj:
                # Generic object reconstruction
                obj.pop('__object_type__')  # Remove marker
                return {key: self._postprocess_object(value)
                       for key, value in obj.items()}

            # Regular dict
            return {key: self._postprocess_object(value) for key, value in obj.items()}

        return obj

    def _json_serializer(self, obj: Any) -> Any:
        """Custom JSON serializer for non-standard types"""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

class OptimizedCacheKey:
    """Optimized cache key generation with consistent hashing"""

    @staticmethod
    def create(key_type: str, *identifiers, params: Optional[Dict[str, Any]] = None) -> str:
        """Create a deterministic cache key"""
        base_key = f"{key_type}:{':'.join(str(id) for id in identifiers)}"

        if params:
            # Create deterministic hash of parameters
            import hashlib
            serializer = CacheSerializer()
            param_bytes = serializer.serialize(params, SerializationMethod.JSON)
            param_hash = hashlib.md5(param_bytes).hexdigest()[:8]
            base_key += f":{param_hash}"

        return base_key

# Global instance for convenience
default_serializer = CacheSerializer()

# Convenience functions
def serialize_for_cache(obj: Any, compress_large: bool = True) -> bytes:
    """Serialize object for caching with automatic optimization"""
    method = SerializationMethod.JSON_COMPRESSED if compress_large else SerializationMethod.JSON
    return default_serializer.serialize(obj, method)

def deserialize_from_cache(data: Union[bytes, str], target_type: Optional[Type[T]] = None) -> T:
    """Deserialize object from cache with type validation"""
    return default_serializer.deserialize(data, target_type)

def create_cache_key(key_type: str, *identifiers, **params) -> str:
    """Create optimized cache key"""
    return OptimizedCacheKey.create(key_type, *identifiers, params=params if params else None)

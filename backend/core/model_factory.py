"""
Model Factory

Runtime Pydantic model generation from JSON Schema.
Generates validation models dynamically without code deployment.
"""
import json
import hashlib
import logging
from typing import Dict, Any, Type, Optional
from pydantic import BaseModel, create_model, Field

logger = logging.getLogger(__name__)


class ModelFactory:
    """Generate Pydantic models at runtime from JSON Schema.
    """

    # JSON Schema type to Python type mapping
    TYPE_MAP = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }

    def __init__(self, cache=None):
        self.cache = cache # Upstream cache manager

    def create_pydantic_model(
        self,
        tenant_id: str,
        entity_type: str,
        json_schema: Dict[str, Any],
        **kwargs
    ) -> Type[BaseModel]:
        """
        Generate Pydantic model from JSON Schema.
        """
        # Caching skipped for now in simplified upstream version
        return self._create_model_from_schema(entity_type, json_schema)

    def _create_model_from_schema(
        self,
        entity_type: str,
        schema: Dict[str, Any]
    ) -> Type[BaseModel]:
        """
        Convert JSON Schema to Pydantic model fields.
        """
        fields = {}
        required_fields = set(schema.get("required", []))
        properties = schema.get("properties", {})

        for field_name, field_def in properties.items():
            field_type = self._map_json_type_to_python(field_def)
            default = ... if field_name in required_fields else None
            description = field_def.get("description", "")
            fields[field_name] = (field_type, Field(default=default, description=description))

        # Create dynamic model
        model = create_model(
            entity_type,
            __base__=BaseModel,
            **fields
        )

        return model

    def _map_json_type_to_python(self, field_def: Dict) -> Type:
        """Map JSON Schema type to Python type."""
        field_type = field_def.get("type")

        if isinstance(field_type, list):
            types = [self.TYPE_MAP.get(t, str) for t in field_type if t != "null"]
            primary_type = types[0] if types else str
            if "null" in field_type:
                return Optional[primary_type]
            return primary_type

        if field_type:
            return self.TYPE_MAP.get(field_type, str)

        return str

    def invalidate_cache(self, tenant_id: str, entity_type: str) -> int:
        """Invalidate all cached models for an entity type."""
        return 0


# Global factory instance
_model_factory: Optional[ModelFactory] = None

def get_model_factory() -> ModelFactory:
    global _model_factory
    if _model_factory is None:
        from core.cache import cache
        _model_factory = ModelFactory(cache=cache)
    return _model_factory

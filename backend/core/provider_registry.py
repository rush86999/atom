from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from core.models import ProviderRegistry, ModelCatalog
from core.database import get_db_session
import logging

logger = logging.getLogger(__name__)


class ProviderRegistryService:
    """Service for managing provider registry and model catalog CRUD operations"""

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session

    def create_provider(self, provider_data: Dict[str, Any]) -> ProviderRegistry:
        """Create a new provider

        Args:
            provider_data: Dictionary with provider fields

        Returns:
            Created ProviderRegistry instance
        """
        if self.db is None:
            with get_db_session() as db:
                return self._create_provider_in_session(db, provider_data)
        else:
            return self._create_provider_in_session(self.db, provider_data)

    def _create_provider_in_session(self, db: Session, provider_data: Dict[str, Any]) -> ProviderRegistry:
        """Internal method to create provider in given session"""
        provider = ProviderRegistry(**provider_data)
        db.add(provider)
        db.commit()
        db.refresh(provider)
        logger.info(f"Created provider: {provider.provider_id}")
        return provider

    def get_provider(self, provider_id: str) -> Optional[ProviderRegistry]:
        """Get single provider by ID

        Args:
            provider_id: Provider identifier

        Returns:
            ProviderRegistry instance or None
        """
        if self.db is None:
            with get_db_session() as db:
                return db.query(ProviderRegistry).filter(
                    ProviderRegistry.provider_id == provider_id
                ).first()
        else:
            return self.db.query(ProviderRegistry).filter(
                ProviderRegistry.provider_id == provider_id
            ).first()

    def list_providers(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """List providers with model counts

        Args:
            active_only: Only return active providers

        Returns:
            List of dicts with provider_id, name, model_count, quality_score, etc.
        """
        if self.db is None:
            with get_db_session() as db:
                return self._list_providers_in_session(db, active_only)
        else:
            return self._list_providers_in_session(self.db, active_only)

    def _list_providers_in_session(self, db: Session, active_only: bool) -> List[Dict[str, Any]]:
        """Internal method to list providers in given session"""
        query = db.query(
            ProviderRegistry.provider_id,
            ProviderRegistry.name,
            ProviderRegistry.description,
            ProviderRegistry.litellm_provider,
            ProviderRegistry.quality_score,
            ProviderRegistry.is_active,
            ProviderRegistry.supports_vision,
            ProviderRegistry.supports_tools,
            ProviderRegistry.supports_cache,
            func.count(ModelCatalog.model_id).label('model_count')
        ).outerjoin(
            ModelCatalog,
            ProviderRegistry.provider_id == ModelCatalog.provider_id
        ).group_by(
            ProviderRegistry.provider_id
        )

        if active_only:
            query = query.filter(ProviderRegistry.is_active == True)

        results = query.all()
        providers = [
            {
                'provider_id': r.provider_id,
                'name': r.name,
                'description': r.description,
                'litellm_provider': r.litellm_provider,
                'quality_score': r.quality_score,
                'is_active': r.is_active,
                'supports_vision': r.supports_vision,
                'supports_tools': r.supports_tools,
                'supports_cache': r.supports_cache,
                'model_count': r.model_count or 0
            }
            for r in results
        ]
        logger.debug(f"Listed {len(providers)} providers (active_only={active_only})")
        return providers

    def update_provider(self, provider_id: str, updates: Dict[str, Any]) -> Optional[ProviderRegistry]:
        """Update provider fields

        Args:
            provider_id: Provider identifier
            updates: Dictionary of fields to update

        Returns:
            Updated ProviderRegistry instance or None
        """
        if self.db is None:
            with get_db_session() as db:
                return self._update_provider_in_session(db, provider_id, updates)
        else:
            return self._update_provider_in_session(self.db, provider_id, updates)

    def _update_provider_in_session(self, db: Session, provider_id: str, updates: Dict[str, Any]) -> Optional[ProviderRegistry]:
        """Internal method to update provider in given session"""
        provider = db.query(ProviderRegistry).filter(
            ProviderRegistry.provider_id == provider_id
        ).first()

        if not provider:
            logger.warning(f"Provider not found for update: {provider_id}")
            return None

        for key, value in updates.items():
            if hasattr(provider, key):
                setattr(provider, key, value)

        db.commit()
        db.refresh(provider)
        logger.info(f"Updated provider: {provider_id}")
        return provider

    def delete_provider(self, provider_id: str) -> bool:
        """Soft delete provider (set is_active=False)

        Args:
            provider_id: Provider identifier

        Returns:
            True if deleted, False if not found
        """
        if self.db is None:
            with get_db_session() as db:
                return self._delete_provider_in_session(db, provider_id)
        else:
            return self._delete_provider_in_session(self.db, provider_id)

    def _delete_provider_in_session(self, db: Session, provider_id: str) -> bool:
        """Internal method to soft delete provider in given session"""
        provider = db.query(ProviderRegistry).filter(
            ProviderRegistry.provider_id == provider_id
        ).first()

        if not provider:
            logger.warning(f"Provider not found for deletion: {provider_id}")
            return False

        provider.is_active = False
        db.commit()
        logger.info(f"Soft deleted provider: {provider_id}")
        return True

    def create_model(self, model_data: Dict[str, Any]) -> ModelCatalog:
        """Create a new model

        Args:
            model_data: Dictionary with model fields

        Returns:
            Created ModelCatalog instance
        """
        if self.db is None:
            with get_db_session() as db:
                return self._create_model_in_session(db, model_data)
        else:
            return self._create_model_in_session(self.db, model_data)

    def _create_model_in_session(self, db: Session, model_data: Dict[str, Any]) -> ModelCatalog:
        """Internal method to create model in given session"""
        model = ModelCatalog(**model_data)
        db.add(model)
        db.commit()
        db.refresh(model)
        logger.info(f"Created model: {model.model_id}")
        return model

    def get_models_by_provider(self, provider_id: str) -> List[ModelCatalog]:
        """Get all models for a provider

        Args:
            provider_id: Provider identifier

        Returns:
            List of ModelCatalog instances
        """
        if self.db is None:
            with get_db_session() as db:
                return db.query(ModelCatalog).filter(
                    ModelCatalog.provider_id == provider_id
                ).all()
        else:
            return self.db.query(ModelCatalog).filter(
                ModelCatalog.provider_id == provider_id
            ).all()

    def search_models(self, filters: Dict[str, Any]) -> List[ModelCatalog]:
        """Search models by capability, cost, quality

        Args:
            filters: Dictionary with search criteria (supports_vision, min_quality, max_cost)

        Returns:
            List of ModelCatalog instances matching filters
        """
        if self.db is None:
            with get_db_session() as db:
                return self._search_models_in_session(db, filters)
        else:
            return self._search_models_in_session(self.db, filters)

    def _search_models_in_session(self, db: Session, filters: Dict[str, Any]) -> List[ModelCatalog]:
        """Internal method to search models in given session"""
        query = db.query(ModelCatalog).join(ProviderRegistry)

        # Filter by provider capabilities
        if filters.get('supports_vision'):
            query = query.filter(ProviderRegistry.supports_vision == True)
        if filters.get('supports_tools'):
            query = query.filter(ProviderRegistry.supports_tools == True)
        if filters.get('supports_cache'):
            query = query.filter(ProviderRegistry.supports_cache == True)

        # Filter by provider quality score
        if filters.get('min_quality'):
            query = query.filter(ProviderRegistry.quality_score >= filters['min_quality'])

        # Filter by cost
        if filters.get('max_cost'):
            max_cost = filters['max_cost']
            query = query.filter(
                (ModelCatalog.input_cost_per_token <= max_cost) |
                (ModelCatalog.input_cost_per_token.is_(None))
            )

        results = query.all()
        logger.debug(f"Found {len(results)} models matching filters: {filters}")
        return results

    def get_provider_stats(self, provider_id: str) -> Dict[str, Any]:
        """Get provider statistics

        Args:
            provider_id: Provider identifier

        Returns:
            Dictionary with model_count, avg_cost, capabilities
        """
        if self.db is None:
            with get_db_session() as db:
                return self._get_provider_stats_in_session(db, provider_id)
        else:
            return self._get_provider_stats_in_session(self.db, provider_id)

    def _get_provider_stats_in_session(self, db: Session, provider_id: str) -> Dict[str, Any]:
        """Internal method to get provider stats in given session"""
        provider = db.query(ProviderRegistry).filter(
            ProviderRegistry.provider_id == provider_id
        ).first()

        if not provider:
            return {}

        model_count = db.query(func.count(ModelCatalog.model_id)).filter(
            ModelCatalog.provider_id == provider_id
        ).scalar()

        avg_input_cost = db.query(func.avg(ModelCatalog.input_cost_per_token)).filter(
            ModelCatalog.provider_id == provider_id
        ).scalar()

        avg_output_cost = db.query(func.avg(ModelCatalog.output_cost_per_token)).filter(
            ModelCatalog.provider_id == provider_id
        ).scalar()

        return {
            'provider_id': provider.provider_id,
            'name': provider.name,
            'model_count': model_count or 0,
            'avg_input_cost_per_token': float(avg_input_cost) if avg_input_cost else None,
            'avg_output_cost_per_token': float(avg_output_cost) if avg_output_cost else None,
            'supports_vision': provider.supports_vision,
            'supports_tools': provider.supports_tools,
            'supports_cache': provider.supports_cache,
            'quality_score': provider.quality_score
        }

    def upsert_provider(self, provider_dict: Dict[str, Any]) -> ProviderRegistry:
        """Merge provider, update if exists

        Args:
            provider_dict: Dictionary with provider fields

        Returns:
            ProviderRegistry instance (created or updated)
        """
        if self.db is None:
            with get_db_session() as db:
                return self._upsert_provider_in_session(db, provider_dict)
        else:
            return self._upsert_provider_in_session(self.db, provider_dict)

    def _upsert_provider_in_session(self, db: Session, provider_dict: Dict[str, Any]) -> ProviderRegistry:
        """Internal method to upsert provider in given session"""
        provider_id = provider_dict.get('provider_id')
        if not provider_id:
            raise ValueError("provider_id is required for upsert")

        provider = db.query(ProviderRegistry).filter(
            ProviderRegistry.provider_id == provider_id
        ).first()

        if provider:
            # Update existing
            for key, value in provider_dict.items():
                if hasattr(provider, key):
                    setattr(provider, key, value)
            logger.debug(f"Upserted existing provider: {provider_id}")
        else:
            # Create new
            provider = ProviderRegistry(**provider_dict)
            db.add(provider)
            logger.debug(f"Upserted new provider: {provider_id}")

        db.commit()
        db.refresh(provider)
        return provider

    def upsert_model(self, model_dict: Dict[str, Any]) -> ModelCatalog:
        """Merge model, update if exists

        Args:
            model_dict: Dictionary with model fields

        Returns:
            ModelCatalog instance (created or updated)
        """
        if self.db is None:
            with get_db_session() as db:
                return self._upsert_model_in_session(db, model_dict)
        else:
            return self._upsert_model_in_session(self.db, model_dict)

    def _upsert_model_in_session(self, db: Session, model_dict: Dict[str, Any]) -> ModelCatalog:
        """Internal method to upsert model in given session"""
        model_id = model_dict.get('model_id')
        if not model_id:
            raise ValueError("model_id is required for upsert")

        model = db.query(ModelCatalog).filter(
            ModelCatalog.model_id == model_id
        ).first()

        if model:
            # Update existing
            for key, value in model_dict.items():
                if hasattr(model, key):
                    setattr(model, key, value)
            logger.debug(f"Upserted existing model: {model_id}")
        else:
            # Create new
            model = ModelCatalog(**model_dict)
            db.add(model)
            logger.debug(f"Upserted new model: {model_id}")

        db.commit()
        db.refresh(model)
        return model


# Singleton instance
_registry_instance: Optional[ProviderRegistryService] = None


def get_provider_registry(db_session: Optional[Session] = None) -> ProviderRegistryService:
    """Get singleton ProviderRegistryService instance

    Args:
        db_session: Optional database session (for testing)

    Returns:
        ProviderRegistryService instance
    """
    global _registry_instance
    if _registry_instance is None or db_session is not None:
        _registry_instance = ProviderRegistryService(db_session)
    return _registry_instance

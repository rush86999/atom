"""
LUX Model Marketplace Integration
Distribute and manage LUX models and automation templates
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import hashlib
import requests

logger = logging.getLogger(__name__)

class ModelType(Enum):
    """Types of models available in marketplace"""
    COMPUTER_USE = "computer_use"
    VISION = "vision"
    AUTOMATION = "automation"
    CUSTOM = "custom"

class ModelCategory(Enum):
    """Categories for marketplace models"""
    PRODUCTIVITY = "productivity"
    DEVELOPMENT = "development"
    DESIGN = "design"
    GAMING = "gaming"
    ACCESSIBILITY = "accessibility"
    TESTING = "testing"
    GENERAL = "general"

@dataclass
class MarketplaceModel:
    """Represents a model in the marketplace"""
    id: str
    name: str
    description: str
    author: str
    version: str
    model_type: ModelType
    category: ModelCategory
    price: float
    rating: float
    downloads: int
    tags: List[str]
    capabilities: List[str]
    requirements: Dict[str, Any]
    created_at: str
    updated_at: str
    file_size: int
    checksum: str
    demo_video_url: Optional[str] = None
    documentation_url: Optional[str] = None

@dataclass
class AutomationTemplate:
    """Represents an automation template"""
    id: str
    name: str
    description: str
    author: str
    category: str
    commands: List[str]
    parameters: Dict[str, Any]
    tags: List[str]
    rating: float
    downloads: int
    created_at: str
    compatibility: List[str]  # Compatible model types

class LuxMarketplace:
    """LUX Model Marketplace Manager"""

    def __init__(self, api_base_url: str = "https://api.atom-lux-marketplace.com"):
        self.api_base_url = api_base_url
        self.local_models_path = os.path.expanduser("~/.atom/lux/models")
        self.templates_path = os.path.expanduser("~/.atom/lux/templates")

        # Ensure directories exist
        os.makedirs(self.local_models_path, exist_ok=True)
        os.makedirs(self.templates_path, exist_ok=True)

        # Initialize local marketplace data
        self._initialize_local_marketplace()

    def _initialize_local_marketplace(self):
        """Initialize local marketplace with built-in models"""
        built_in_models = {
            "lux-base": MarketplaceModel(
                id="lux-base",
                name="LUX Base Computer Use Model",
                description="Base computer use model for general desktop automation",
                author="ATOM Team",
                version="1.0.0",
                model_type=ModelType.COMPUTER_USE,
                category=ModelCategory.GENERAL,
                price=0.0,
                rating=4.8,
                downloads=0,
                tags=["computer", "automation", "base", "free"],
                capabilities=["screen_analysis", "click", "type", "keyboard", "screenshot"],
                requirements={"min_ram": "4GB", "os": ["macOS", "Windows", "Linux"]},
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                file_size=1024 * 1024,  # 1MB
                checksum="base_model_checksum"
            ),
            "lux-pro": MarketplaceModel(
                id="lux-pro",
                name="LUX Pro Automation Model",
                description="Advanced automation model with OCR and element detection",
                author="ATOM Team",
                version="2.0.0",
                model_type=ModelType.AUTOMATION,
                category=ModelCategory.PRODUCTIVITY,
                price=29.99,
                rating=4.9,
                downloads=0,
                tags=["automation", "ocr", "pro", "advanced"],
                capabilities=["screen_analysis", "ocr", "element_detection", "automation_chains"],
                requirements={"min_ram": "8GB", "gpu": "recommended", "os": ["macOS", "Windows", "Linux"]},
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                file_size=5 * 1024 * 1024,  # 5MB
                checksum="pro_model_checksum"
            ),
            "lux-dev": MarketplaceModel(
                id="lux-dev",
                name="LUX Developer Assistant",
                description="Specialized model for software development automation",
                author="ATOM Team",
                version="1.5.0",
                model_type=ModelType.CUSTOM,
                category=ModelCategory.DEVELOPMENT,
                price=49.99,
                rating=4.7,
                downloads=0,
                tags=["development", "coding", "ide", "pro"],
                capabilities=["code_understanding", "ide_automation", "debugging_assist"],
                requirements={"min_ram": "16GB", "ide": ["VSCode", "JetBrains", "Xcode"], "os": ["macOS", "Windows", "Linux"]},
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                file_size=8 * 1024 * 1024,  # 8MB
                checksum="dev_model_checksum"
            )
        }

        # Save built-in models to local cache
        for model_id, model in built_in_models.items():
            model_path = os.path.join(self.local_models_path, f"{model_id}.json")
            if not os.path.exists(model_path):
                # Convert model to dict and handle enum serialization
                model_dict = asdict(model)
                model_dict['model_type'] = model.model_type.value
                model_dict['category'] = model.category.value
                with open(model_path, 'w') as f:
                    json.dump(model_dict, f, indent=2)

    def get_available_models(self, category: Optional[ModelCategory] = None,
                           model_type: Optional[ModelType] = None,
                           price_range: Optional[tuple] = None) -> List[MarketplaceModel]:
        """Get available models from marketplace"""
        models = []

        # Load models from local cache
        for filename in os.listdir(self.local_models_path):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(self.local_models_path, filename), 'r') as f:
                        model_data = json.load(f)

                        # Convert string values back to enums
                        if 'model_type' in model_data and isinstance(model_data['model_type'], str):
                            model_data['model_type'] = ModelType(model_data['model_type'])
                        if 'category' in model_data and isinstance(model_data['category'], str):
                            model_data['category'] = ModelCategory(model_data['category'])

                        model = MarketplaceModel(**model_data)

                        # Apply filters
                        if category and model.category != category:
                            continue
                        if model_type and model.model_type != model_type:
                            continue
                        if price_range and not (price_range[0] <= model.price <= price_range[1]):
                            continue

                        models.append(model)
                except Exception as e:
                    logger.error(f"Failed to load model {filename}: {e}")

        return models

    def get_model_details(self, model_id: str) -> Optional[MarketplaceModel]:
        """Get detailed information about a specific model"""
        model_path = os.path.join(self.local_models_path, f"{model_id}.json")
        if os.path.exists(model_path):
            try:
                with open(model_path, 'r') as f:
                    model_data = json.load(f)

                # Convert string values back to enums
                if 'model_type' in model_data and isinstance(model_data['model_type'], str):
                    model_data['model_type'] = ModelType(model_data['model_type'])
                if 'category' in model_data and isinstance(model_data['category'], str):
                    model_data['category'] = ModelCategory(model_data['category'])

                return MarketplaceModel(**model_data)
            except Exception as e:
                logger.error(f"Failed to load model details {model_id}: {e}")
        return None

    def download_model(self, model_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Download a model from marketplace"""
        try:
            # For built-in models, simulate download
            if model_id in ["lux-base", "lux-pro", "lux-dev"]:
                # Simulate download process
                model = self.get_model_details(model_id)
                if not model:
                    return {"success": False, "error": "Model not found"}

                # Create model package
                model_package_path = os.path.join(self.local_models_path, f"{model_id}.pkg")

                # In a real implementation, this would download actual model files
                # For now, create a placeholder package
                with open(model_package_path, 'w') as f:
                    f.write(f"LUX Model Package: {model_id}\n")
                    f.write(f"Version: {model.version}\n")
                    f.write(f"Checksum: {model.checksum}\n")
                    f.write("Model binary would be here in production\n")

                return {
                    "success": True,
                    "model_id": model_id,
                    "path": model_package_path,
                    "size": model.file_size,
                    "message": "Model downloaded successfully"
                }

            # For external models, would make API call to marketplace
            # This is a placeholder for real marketplace integration
            return {"success": False, "error": "External marketplace not implemented yet"}

        except Exception as e:
            logger.error(f"Model download failed: {e}")
            return {"success": False, "error": str(e)}

    def get_automation_templates(self, category: Optional[str] = None) -> List[AutomationTemplate]:
        """Get available automation templates"""
        templates = []

        # Built-in templates
        built_in_templates = [
            AutomationTemplate(
                id="open-slack",
                name="Open Slack",
                description="Opens Slack application and waits for it to load",
                author="ATOM Team",
                category="communication",
                commands=["open Slack app", "wait 3 seconds"],
                parameters={"app_name": "Slack"},
                tags=["slack", "communication", "app"],
                rating=4.5,
                downloads=0,
                created_at=datetime.now().isoformat(),
                compatibility=["computer_use", "automation"]
            ),
            AutomationTemplate(
                id="check-gmail",
                name="Check Gmail",
                description="Opens browser and navigates to Gmail",
                author="ATOM Team",
                category="productivity",
                commands=[
                    "open Chrome",
                    "type gmail.com",
                    "press Enter",
                    "wait 2 seconds"
                ],
                parameters={"browser": "Chrome", "url": "gmail.com"},
                tags=["gmail", "email", "browser", "productivity"],
                rating=4.3,
                downloads=0,
                created_at=datetime.now().isoformat(),
                compatibility=["computer_use", "automation"]
            ),
            AutomationTemplate(
                id="take-notes",
                name="Take Notes",
                description="Opens notes app and creates new note",
                author="ATOM Team",
                category="productivity",
                commands=[
                    "open Notes app",
                    "wait 1 second",
                    "type 'Meeting Notes'",
                    "press Enter",
                    "type 'Date:' and press Enter"
                ],
                parameters={"app": "Notes", "note_title": "Meeting Notes"},
                tags=["notes", "productivity", "text"],
                rating=4.4,
                downloads=0,
                created_at=datetime.now().isoformat(),
                compatibility=["computer_use", "automation"]
            )
        ]

        if category:
            built_in_templates = [t for t in built_in_templates if t.category == category]

        return built_in_templates

    def rate_model(self, model_id: str, rating: float, review: Optional[str] = None) -> Dict[str, Any]:
        """Rate a model"""
        try:
            model = self.get_model_details(model_id)
            if not model:
                return {"success": False, "error": "Model not found"}

            # Update rating (in real implementation, would save to server)
            # For now, just return success
            return {
                "success": True,
                "model_id": model_id,
                "new_rating": rating,
                "message": "Rating submitted successfully"
            }

        except Exception as e:
            logger.error(f"Rating submission failed: {e}")
            return {"success": False, "error": str(e)}

    def search_models(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[MarketplaceModel]:
        """Search models in marketplace"""
        models = self.get_available_models()

        # Filter by search query
        if query:
            query_lower = query.lower()
            models = [
                model for model in models
                if (query_lower in model.name.lower() or
                    query_lower in model.description.lower() or
                    any(query_lower in tag.lower() for tag in model.tags))
            ]

        # Apply additional filters
        if filters:
            if "category" in filters:
                models = [m for m in models if m.category == filters["category"]]
            if "model_type" in filters:
                models = [m for m in models if m.model_type == filters["model_type"]]
            if "max_price" in filters:
                models = [m for m in models if m.price <= filters["max_price"]]

        return models

    def get_featured_models(self) -> List[MarketplaceModel]:
        """Get featured models for homepage"""
        models = self.get_available_models()

        # Featured models logic (high rating, recent, etc.)
        featured = [
            model for model in models
            if model.rating >= 4.5 or model.downloads > 100
        ]

        return featured[:6]  # Limit to 6 featured models

    def upload_model(self, model_data: Dict[str, Any], package_file: str,
                    api_key: str) -> Dict[str, Any]:
        """Upload a new model to marketplace (for creators)"""
        try:
            # In real implementation, this would upload to marketplace API
            # For now, just validate and return success
            required_fields = ["name", "description", "version", "model_type"]
            for field in required_fields:
                if field not in model_data:
                    return {"success": False, "error": f"Missing required field: {field}"}

            model_id = hashlib.md5(f"{model_data['name']}_{model_data['version']}_{api_key}".encode()).hexdigest()

            return {
                "success": True,
                "model_id": model_id,
                "message": "Model uploaded successfully",
                "status": "pending_review"
            }

        except Exception as e:
            logger.error(f"Model upload failed: {e}")
            return {"success": False, "error": str(e)}

# Global marketplace instance
marketplace = LuxMarketplace()
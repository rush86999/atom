"""
Comprehensive ATOM Integration Architecture
Unified system for all document and communication integrations with LanceDB memory pipeline
"""

# Core Integration Classes
from .core import (
    AtomIntegrationRegistry,
    AtomIntegrationManager,
    AtomIntegrationFactory,
    AtomIntegrationOrchestrator,
)

# Document Storage Integrations
from .document_storage import (
    DocumentStorageIntegration,
    GoogleDriveIntegration,
    OneDriveIntegration,
    DropboxIntegration,
    BoxIntegration,
)

# Communication Integrations
from .communication import (
    CommunicationIntegration,
    SlackIntegration,
    GmailIntegration,
    OutlookIntegration,
    TeamsIntegration,
)

# Productivity Integrations
from .productivity import (
    ProductivityIntegration,
    NotionIntegration,
    AsanaIntegration,
    JiraIntegration,
    LinearIntegration,
)

# Development Integrations
from .development import (
    DevelopmentIntegration,
    GitHubIntegration,
    GitLabIntegration,
    NextjsIntegration,
)

# LanceDB Memory Pipeline
from .memory_pipeline import (
    LanceDBMemoryPipeline,
    DocumentProcessor,
    EmbeddingGenerator,
    VectorStorage,
    IncrementalSync,
)

# API Endpoints
from .api import (
    create_comprehensive_api_blueprint,
    register_all_integrations,
    initialize_integration_endpoints,
)

# Export all components
__all__ = [
    # Core
    'AtomIntegrationRegistry',
    'AtomIntegrationManager',
    'AtomIntegrationFactory',
    'AtomIntegrationOrchestrator',
    
    # Document Storage
    'DocumentStorageIntegration',
    'GoogleDriveIntegration',
    'OneDriveIntegration',
    'DropboxIntegration',
    'BoxIntegration',
    
    # Communication
    'CommunicationIntegration',
    'SlackIntegration',
    'GmailIntegration',
    'OutlookIntegration',
    'TeamsIntegration',
    
    # Productivity
    'ProductivityIntegration',
    'NotionIntegration',
    'AsanaIntegration',
    'JiraIntegration',
    'LinearIntegration',
    
    # Development
    'DevelopmentIntegration',
    'GitHubIntegration',
    'GitLabIntegration',
    'NextjsIntegration',
    
    # Memory Pipeline
    'LanceDBMemoryPipeline',
    'DocumentProcessor',
    'EmbeddingGenerator',
    'VectorStorage',
    'IncrementalSync',
    
    # API
    'create_comprehensive_api_blueprint',
    'register_all_integrations',
    'initialize_integration_endpoints',
]

# Version
__version__ = "2.0.0"
__author__ = "ATOM Team"
__description__ = "Comprehensive ATOM Integration System"
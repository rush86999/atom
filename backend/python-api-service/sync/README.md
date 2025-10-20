# LanceDB Sync System

A comprehensive document ingestion pipeline with incremental updates and dual storage (local + S3) for the ATOM application.

## Overview

The LanceDB Sync System provides:

- **Incremental Document Processing**: Only processes changed documents since last sync
- **Dual Storage Architecture**: 
  - Local LanceDB for fast desktop app access
  - S3 backup for remote sync and multi-device access
- **Source Monitoring**: Automatic change detection from multiple sources
- **Real-time Sync**: Continuous monitoring with configurable intervals
- **Health Monitoring**: Built-in health checks and status reporting

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Source Types  │    │  Change Detector │    │  Sync Service   │
│                 │    │                  │    │                 │
│ • Local Files   │───▶│ • File Watching  │───▶│ • Local LanceDB │
│ • Notion        │    │ • API Polling    │    │ • S3 Backup     │
│ • Dropbox       │    │ • Checksum       │    │ • Incremental   │
│ • Google Drive  │    │ • State Tracking │    │   Processing    │
│ • S3            │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                               │                        │
                               ▼                        ▼
                     ┌──────────────────┐    ┌─────────────────┐
                     │  Orchestration   │    │   API Service   │
                     │     Service      │    │                 │
                     │                  │    │ • REST API      │
                     │ • Lifecycle Mgmt │    │ • Status        │
                     │ • Health Checks  │    │ • Management    │
                     │ • Error Handling │    │ • Monitoring    │
                     └──────────────────┘    └─────────────────┘
```

## Components

### 1. Incremental Sync Service (`incremental_sync_service.py`)
- **Purpose**: Manages document processing with change detection
- **Features**:
  - Checksum-based change detection
  - Local LanceDB storage
  - S3 backup and sync
  - Failed sync cleanup
- **Key Classes**:
  - `IncrementalSyncService`: Main sync orchestration
  - `SyncConfig`: Configuration management
  - `ChangeRecord`: Change tracking

### 2. Source Change Detector (`source_change_detector.py`)
- **Purpose**: Monitors document sources for changes
- **Supported Sources**:
  - Local Filesystem
  - Notion (API-based)
  - Dropbox (placeholder)
  - Google Drive (placeholder)
  - S3 (placeholder)
- **Key Classes**:
  - `SourceChangeDetector`: Main monitoring service
  - `SourceConfig`: Source configuration
  - `SourceChange`: Detected change representation

### 3. Orchestration Service (`orchestration_service.py`)
- **Purpose**: Coordinates all components and manages lifecycle
- **Features**:
  - Component initialization
  - Health monitoring
  - Graceful shutdown
  - Error handling
- **Key Classes**:
  - `OrchestrationService`: Main orchestration
  - `OrchestrationConfig`: System configuration

### 4. API Service (`api_service.py`)
- **Purpose**: REST API for system management
- **Endpoints**:
  - `/api/v1/sources` - Source management
  - `/api/v1/status` - System status
  - `/api/v1/sync/*` - Sync operations
  - `/health` - Health checks

### 5. Configuration (`__init__.py`)
- **Purpose**: Centralized configuration management
- **Features**:
  - Environment variable support
  - Validation
  - Default values
- **Key Classes**:
  - `LanceDBSyncConfig`: Main configuration class

### 6. Startup Script (`startup.py`)
- **Purpose**: System initialization and management
- **Features**:
  - Graceful startup/shutdown
  - Signal handling
  - Default source configuration

## Installation

### Prerequisites
```bash
pip install lancedb pyarrow boto3 fastapi uvicorn aiohttp aiofiles
```

### Environment Variables
```bash
# Local Storage
LANCEDB_URI=data/lancedb
LANCEDB_TABLE_NAME=processed_documents
LANCEDB_CHUNKS_TABLE_NAME=document_chunks

# S3 Configuration (optional)
S3_BUCKET=your-bucket-name
S3_PREFIX=lancedb-backup
AWS_REGION=us-east-1

# Sync Behavior
SYNC_INTERVAL=300
MAX_CONCURRENT_PROCESSING=5
CHUNK_SIZE_MB=50
MAX_RETRIES=3

# Source Monitoring
ENABLE_SOURCE_MONITORING=true
SYNC_STATE_DIR=data/sync_state
HEALTH_CHECK_INTERVAL=60
DEFAULT_POLL_INTERVAL=300
CHECKSUM_ENABLED=true
```

## Usage

### Standalone Service
```python
from sync.startup import create_sync_system

# Create and start the system
startup = create_sync_system()
await startup.initialize()
await startup.start()

# Get system status
status = await startup.get_status()
print(status)
```

### Integrated with Existing Application
```python
from sync.orchestration_service import create_orchestration_service

# Create orchestration service
service = create_orchestration_service(
    local_db_path="data/lancedb",
    s3_bucket="my-backup-bucket",
    enable_source_monitoring=True
)

# Start the service
await service.start()

# Add a document source
from sync.source_change_detector import SourceConfig, SourceType

local_source = SourceConfig(
    source_type=SourceType.LOCAL_FILESYSTEM,
    source_id="documents",
    config={
        "watch_paths": ["/path/to/documents"],
        "file_patterns": ["*.pdf", "*.docx", "*.txt"]
    },
    poll_interval=300
)

await service.add_source(local_source)
```

### API Service
```python
from sync.api_service import create_api_service

# Create and run API service
api_service = create_api_service()
app = api_service.get_app()

# Run with uvicorn
# uvicorn sync.api_service:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Health & Status
- `GET /health` - System health check
- `GET /api/v1/status` - Comprehensive system status

### Source Management
- `POST /api/v1/sources` - Add a document source
- `GET /api/v1/sources` - List monitored sources
- `DELETE /api/v1/sources/{type}/{id}` - Remove a source
- `POST /api/v1/sources/{type}/{id}/scan` - Force source scan

### Sync Operations
- `GET /api/v1/sync/status` - Get sync status
- `POST /api/v1/sync/cleanup` - Clean up failed syncs
- `POST /api/v1/sync/manual` - Manual document sync

### Pipeline Control
- `POST /api/v1/pipeline/start` - Start ingestion pipeline
- `POST /api/v1/pipeline/stop` - Stop ingestion pipeline

## Configuration Examples

### Local Filesystem Source
```python
source_config = SourceConfig(
    source_type=SourceType.LOCAL_FILESYSTEM,
    source_id="my_documents",
    config={
        "watch_paths": ["~/Documents", "~/Downloads"],
        "file_patterns": ["*.pdf", "*.docx", "*.txt", "*.md"]
    },
    poll_interval=300,  # 5 minutes
    enabled=True
)
```

### Notion Source
```python
source_config = SourceConfig(
    source_type=SourceType.NOTION,
    source_id="my_notion",
    config={
        "api_key": "your-notion-api-key",
        "database_ids": ["database-id-1", "database-id-2"],
        "page_ids": ["page-id-1"]
    },
    poll_interval=600,  # 10 minutes
    enabled=True
)
```

## Error Handling

The system includes comprehensive error handling:

- **Retry Logic**: Configurable retries for failed operations
- **Graceful Degradation**: Continues operation when components fail
- **Health Monitoring**: Automatic detection of component failures
- **Cleanup Operations**: Tools to recover from failed states

## Monitoring

### Health Checks
The system performs regular health checks on:
- Local LanceDB connectivity
- S3 connectivity (if configured)
- Source monitoring status
- Sync queue status

### Logging
Comprehensive logging with configurable levels:
```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Performance Considerations

### Local Storage
- LanceDB provides fast vector search for desktop applications
- Optimized for read-heavy workloads
- Efficient memory usage with memory-mapped files

### S3 Sync
- Asynchronous background sync to avoid blocking operations
- Configurable chunk sizes for large documents
- Incremental updates to minimize bandwidth usage

### Change Detection
- Checksum-based detection for accurate change identification
- Configurable poll intervals to balance performance and freshness
- Efficient state tracking to avoid redundant processing

## Security

- **Source Credentials**: Securely stored in configuration
- **S3 Access**: Uses AWS IAM roles or credentials
- **API Security**: CORS configuration for web access
- **Data Privacy**: Local processing keeps sensitive data on-premises

## Troubleshooting

### Common Issues

1. **S3 Sync Failing**
   - Check AWS credentials and permissions
   - Verify S3 bucket exists and is accessible
   - Check network connectivity

2. **Source Monitoring Not Working**
   - Verify source configuration
   - Check API keys and permissions
   - Review poll interval settings

3. **High Memory Usage**
   - Adjust `max_concurrent_processing`
   - Reduce `chunk_size_mb`
   - Monitor document sizes

### Debug Mode
Enable debug logging for detailed troubleshooting:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Development

### Adding New Source Types
1. Extend `SourceType` enum
2. Implement detection method in `SourceChangeDetector`
3. Add configuration schema
4. Update API models

### Testing
```bash
# Run unit tests
pytest tests/

# Test API endpoints
curl http://localhost:8000/health

# Test sync operations
curl http://localhost:8000/api/v1/status
```

## Contributing

1. Follow existing code style and patterns
2. Add comprehensive tests for new features
3. Update documentation for API changes
4. Ensure backward compatibility

## License

This project is part of the ATOM application. See main project LICENSE for details.
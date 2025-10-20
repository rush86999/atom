# LanceDB Sync System Deployment Guide with Backend Location Support

This deployment guide covers the LanceDB sync system with enhanced backend location detection and frontend-specific storage configurations.

## Key Assumptions
- **Backend folder might be in cloud or local environment** - System automatically detects backend location
- **Desktop app will always be local for LanceDB sync** - Desktop maintains local-first storage
- **Backend will have cloud default settings for web app** - Web app defaults to cloud-native configuration

## Overview

This guide covers the deployment of the LanceDB Sync System, which provides incremental document ingestion with dual storage (local LanceDB + S3 backup) for the ATOM application.

## Prerequisites

### System Requirements
- **Python**: 3.8+
- **Storage**: Minimum 1GB free space for local LanceDB
- **Memory**: 2GB RAM minimum, 4GB+ recommended
- **Network**: Internet access for S3 sync (optional)

### Python Dependencies
```bash
pip install lancedb pyarrow boto3 fastapi uvicorn aiohttp aiofiles
```

## Environment Configuration

### Required Environment Variables
```bash
# Local Storage
LANCEDB_URI=data/lancedb
LANCEDB_TABLE_NAME=processed_documents
LANCEDB_CHUNKS_TABLE_NAME=document_chunks

# S3 Storage Configuration
S3_STORAGE_ENABLED=false
S3_BUCKET=your-primary-bucket-name
S3_PREFIX=lancedb-primary
S3_REGION=us-east-1
S3_ENDPOINT=  # Optional: for custom S3-compatible endpoints

# S3 Backup Configuration
S3_BACKUP_ENABLED=false
S3_BACKUP_BUCKET=your-backup-bucket-name
S3_BACKUP_PREFIX=lancedb-backup

# Storage Behavior
USE_S3_AS_PRIMARY=false
LOCAL_CACHE_ENABLED=true
SYNC_ON_STARTUP=true

# AWS Credentials (if not using IAM roles)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

### Optional Environment Variables
```bash
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

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Integration Settings
ENABLE_LEGACY_FALLBACK=true
MIGRATE_EXISTING_DATA=false
SYNC_ENABLED_BY_DEFAULT=true
```

## Deployment Options

### Option 1: Standalone Service

#### 1.1 Using Startup Script
```python
# deploy_standalone.py
import asyncio
from sync.startup import create_sync_system

async def main():
    startup = create_sync_system()
    await startup.initialize()
    await startup.start()
    await startup.add_default_sources()
    
    # Keep service running
    await startup.wait_until_stopped()

if __name__ == "__main__":
    asyncio.run(main())
```

Run with:
```bash
python deploy_standalone.py
```

#### 1.2 Using Systemd Service
Create `/etc/systemd/system/lancedb-sync.service`:
```ini
[Unit]
Description=LanceDB Sync System
After=network.target

[Service]
Type=simple
User=atom
WorkingDirectory=/opt/atom/backend/python-api-service
Environment=LANCEDB_URI=/opt/atom/data/lancedb
Environment=S3_STORAGE_ENABLED=true
Environment=S3_BUCKET=atom-primary-bucket
Environment=S3_BACKUP_ENABLED=true
Environment=S3_BACKUP_BUCKET=atom-backup-bucket
Environment=S3_REGION=us-east-1
ExecStart=/opt/atom/venv/bin/python sync/startup.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable lancedb-sync
sudo systemctl start lancedb-sync
```

### Option 2: API Service Deployment

#### 2.1 Using Uvicorn Directly
```bash
cd atom/backend/python-api-service
uvicorn sync.api_service:app --host 0.0.0.0 --port 8000 --workers 4
```

#### 2.2 Using Gunicorn with Uvicorn Workers
```bash
pip install gunicorn
gunicorn sync.api_service:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

#### 2.3 Docker Deployment
Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Create data directories
RUN mkdir -p data/lancedb data/sync_state

EXPOSE 8000

CMD ["uvicorn", "sync.api_service:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t lancedb-sync .
docker run -d \
  -p 8000:8000 \
  -v ./data:/app/data \
  -e S3_STORAGE_ENABLED=true \
  -e S3_BUCKET=your-primary-bucket \
  -e S3_BACKUP_ENABLED=true \
  -e S3_BACKUP_BUCKET=your-backup-bucket \
  -e S3_REGION=us-east-1 \
  lancedb-sync
```

### Option 3: Integration with Existing ATOM Application

#### 3.1 Direct Integration
```python
# In your main application
from sync.startup import create_sync_system

class AtomApplication:
    def __init__(self):
        self.sync_system = None
        
    async def startup(self):
        # Initialize sync system
        self.sync_system = create_sync_system()
        await self.sync_system.initialize()
        await self.sync_system.start()
        
    async def shutdown(self):
        if self.sync_system:
            await self.sync_system.stop()
```

#### 3.2 Background Task Integration
```python
import asyncio
from sync.orchestration_service import create_orchestration_service

async def start_sync_background():
    service = create_orchestration_service()
    await service.start()
    return service

# In your FastAPI application
@app.on_event("startup")
async def startup_event():
    app.state.sync_service = await start_sync_background()

@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, 'sync_service'):
        await app.state.sync_service.stop()
```

## Source Configuration

### Local Filesystem Source
```python
from sync.source_change_detector import SourceConfig, SourceType

local_source = SourceConfig(
    source_type=SourceType.LOCAL_FILESYSTEM,
    source_id="user_documents",
    config={
        "watch_paths": [
            "~/Documents",
            "~/Downloads",
            "/path/to/shared/documents"
        ],
        "file_patterns": ["*.pdf", "*.docx", "*.txt", "*.md"]
    },
    poll_interval=300,  # 5 minutes
    enabled=True
)
```

### Notion Source
```python
notion_source = SourceConfig(
    source_type=SourceType.NOTION,
    source_id="notion_pages",
    config={
        "api_key": "your-notion-integration-token",
        "database_ids": ["database-id-1", "database-id-2"],
        "page_ids": ["page-id-1", "page-id-2"]
    },
    poll_interval=600,  # 10 minutes
    enabled=True
)
```

### S3 Storage Configuration

## Storage Modes by Frontend and Backend Location

The system automatically configures storage modes based on frontend type and backend location:

### Web App Configurations
- **Web App + Cloud Backend**: S3 primary storage with local cache
- **Web App + Local Backend**: Local primary storage with S3 sync (development mode)

### Desktop App Configurations  
- **Desktop App + Cloud Backend**: Local primary storage with S3 backup
- **Desktop App + Local Backend**: Local primary storage with S3 backup

### Backend Location Detection
The system automatically detects backend location using environment indicators:
- AWS Lambda, Google Cloud Functions, Azure Functions
- Kubernetes, Docker containers
- Cloud-specific environment variables
- Explicit `BACKEND_LOCATION` setting

The system supports multiple storage configurations:

1. **Local Only** (Default)
   - Fastest for desktop applications
   - No cloud dependencies
   - Limited scalability

2. **S3 Primary + Local Cache**
   - S3 as primary storage backend
   - Local cache for performance
   - Best for cloud-native applications

3. **Local Primary + S3 Backup**
   - Local storage for fast access
   - S3 for backup and disaster recovery
   - Good balance of performance and durability

4. **S3 Only**
   - Pure cloud storage
   - No local cache
   - Maximum scalability

#### Bucket Setup
```bash
# Create primary S3 bucket (if using S3 storage)
aws s3 mb s3://atom-lancedb-primary --region us-east-1

# Create backup S3 bucket (if using S3 backup)
aws s3 mb s3://atom-lancedb-backup --region us-east-1

# Set lifecycle policy for backup (optional)
aws s3api put-bucket-lifecycle-configuration \
    --bucket atom-lancedb-backup \
    --lifecycle-configuration file://lifecycle.json
```

Example `lifecycle.json`:
```json
{
  "Rules": [
    {
      "ID": "ArchiveOldBackups",
      "Status": "Enabled",
      "Prefix": "lancedb-primary/",
      "Transition": {
        "Days": 30,
        "StorageClass": "GLACIER"
      }
    }
  ]
}
```

### IAM Policy
Create IAM policy for S3 access:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:DeleteObject"
      ],
      "Resource": [
          "arn:aws:s3:::atom-lancedb-primary",
          "arn:aws:s3:::atom-lancedb-primary/*",
          "arn:aws:s3:::atom-lancedb-backup",
          "arn:aws:s3:::atom-lancedb-backup/*"
      ]
    }
  ]
}
```

## Monitoring and Health Checks

### Health Endpoints
```bash
# Basic health check
curl http://localhost:8000/health

# Detailed system status
curl http://localhost:8000/api/v1/status

# Sync status for specific user
curl "http://localhost:8000/api/v1/sync/status?user_id=user123"
```

### Logging Configuration
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sync_system.log'),
        logging.StreamHandler()
    ]
)
```

### Performance Monitoring
Key metrics to monitor:
- `pending_syncs`: Number of documents waiting for sync
- `failed_syncs`: Number of failed sync operations
- `storage_service_available`: Storage service connectivity
- `s3_primary_enabled`: S3 primary storage status
- `s3_backup_enabled`: S3 backup sync status
- `local_cache_enabled`: Local cache availability
- `sources_monitored`: Number of active source monitors

## Backup and Recovery

### Data Backup Strategy
1. **Local LanceDB**: Regular file system backups of `data/lancedb` directory
2. **S3 Backups**: Automatic incremental backups to S3
3. **Sync State**: Backup `data/sync_state` directory for change tracking

### Recovery Procedures

#### Local Data Loss
```python
from sync.startup import create_sync_system

async def recover_from_s3():
    startup = create_sync_system()
    await startup.initialize()
    
    # Force re-sync all documents from S3
    # (Implementation depends on specific recovery needs)
    
    await startup.start()
```

#### S3 Data Recovery
```bash
# Download latest backup
aws s3 sync s3://atom-lancedb-backup/users/user123/ ./recovery/user123/
```

## Security Considerations

### Access Control
- Use IAM roles instead of access keys when possible
- Restrict S3 bucket policies to specific users/roles
- Use environment variables for sensitive configuration
- Implement API authentication for management endpoints

### Data Encryption
- Enable S3 server-side encryption
- Consider client-side encryption for sensitive documents
- Use HTTPS for API endpoints

### Network Security
- Restrict API endpoint access to trusted networks
- Use VPC endpoints for S3 access in AWS
- Implement rate limiting for API endpoints

## Troubleshooting with Backend Location

### Common Issues

**Backend Location Detection Failing**
- Check environment variables for cloud indicators
- Verify `BACKEND_LOCATION` is set explicitly if needed
- Review cloud platform documentation for environment variables

**Web App with Local Backend Requires S3**
- Error: "Web app frontend requires S3 storage to be enabled"
- Solution: Set `BACKEND_LOCATION=local` and `S3_STORAGE_ENABLED=false`

**Desktop App Trying to Use S3 Primary**
- Error: Configuration validation fails
- Solution: Desktop apps should always have `USE_S3_AS_PRIMARY=false`

**Cloud Backend Without S3 Storage**
- Error: "Cloud backend requires S3 storage to be enabled"
- Solution: Enable S3 storage or set `BACKEND_LOCATION=local`

### Debug Mode
Enable detailed logging to see backend location detection:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

from sync import get_config
config = get_config()
print(f"Detected backend: {config.backend_location}")
print(f"Storage mode: {config.get_recommended_storage_mode()}")
```

### Common Issues

### S3 Storage Issues
```bash
# Check S3 connectivity for primary storage
aws s3 ls s3://your-primary-bucket

# Check S3 connectivity for backup
aws s3 ls s3://your-backup-bucket

# Verify credentials
aws sts get-caller-identity

# Check bucket permissions
aws s3api get-bucket-policy --bucket your-primary-bucket
aws s3api get-bucket-policy --bucket your-backup-bucket
```

#### Storage Service Issues
```python
# Check storage service connectivity
from sync.lancedb_storage_service import get_storage_service
storage_service = await get_storage_service()
status = await storage_service.get_storage_status("test_user")
print(f"Storage status: {status}")
```

#### Source Monitoring Issues
```bash
# Check if sources are configured
curl http://localhost:8000/api/v1/sources

# Force source scan
curl -X POST http://localhost:8000/api/v1/sources/local_filesystem/documents/scan
```

### Debug Mode
Enable debug logging for detailed troubleshooting:
```python
import logging
logging.getLogger('sync').setLevel(logging.DEBUG)
```

## Performance Optimization

### Tuning Parameters
- **`MAX_CONCURRENT_PROCESSING`**: Increase for multi-core systems
- **`CHUNK_SIZE_MB`**: Adjust based on document sizes
- **`SYNC_INTERVAL`**: Balance between freshness and performance
- **`DEFAULT_POLL_INTERVAL`**: Adjust based on source update frequency
- **`USE_S3_AS_PRIMARY`**: Set to true for cloud-native applications
- **`LOCAL_CACHE_ENABLED`**: Set to false for pure cloud storage
- **`S3_STORAGE_ENABLED`**: Enable S3 as storage backend
- **`S3_BACKUP_ENABLED`**: Enable S3 backup for local storage

### Resource Monitoring
Monitor:
- Memory usage during large document processing
- Disk I/O for local LanceDB operations
- Network bandwidth for S3 storage operations
- CPU usage during embedding generation
- S3 API request rates and costs
- Storage backend performance metrics

## Scaling Considerations

### Horizontal Scaling
- Deploy multiple API instances behind load balancer
- Use S3 as primary storage for shared access
- Implement distributed locking for source monitoring
- Use S3 for cross-instance data sharing

### Vertical Scaling
- Increase memory for larger document sets
- Use faster storage (SSD) for local LanceDB
- Scale CPU for concurrent processing
- Optimize S3 transfer settings for large files
- Use S3 transfer acceleration if needed

## Maintenance

### Regular Tasks
1. Monitor sync system logs
2. Check S3 storage usage and costs (both primary and backup)
3. Verify source connectivity
4. Clean up failed sync operations
5. Update configuration as needed
6. Monitor S3 API usage and costs
7. Verify storage backend performance

### Storage Maintenance
```python
# Clean up old data
from sync.lancedb_storage_service import get_storage_service

async def cleanup_old_documents():
    storage_service = await get_storage_service()
    # Implement cleanup logic based on your retention policy
    # The storage service handles both local and S3 cleanup
    pass
```

## Support

For issues and questions:
1. Check system logs in `sync_system.log`
2. Verify environment configuration
3. Test individual components
4. Consult API documentation at `/docs` endpoint

Remember to test your deployment thoroughly in a staging environment before moving to production.
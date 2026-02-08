# Background Task Queue Guide

> **Last Updated**: February 6, 2026
> **Purpose**: Complete guide to RQ (Redis Queue) setup, monitoring, and debugging in Atom

---

## Overview

Atom uses **RQ (Redis Queue)** for background job processing, primarily for:
- Scheduled social media posts
- Async workflow processing
- Long-running tasks
- Batch operations

### Architecture

```
API Request → Queue → Redis → Worker → Job Execution → Result
```

### Key Components

1. **Redis**: Job queue backend and result storage
2. **Workers**: Process jobs from queues
3. **Queues**: `social_media`, `workflows`, `default`
4. **Monitoring**: API endpoints and CLI tools

---

## Redis Setup

### Installation

#### macOS
```bash
brew install redis
brew services start redis
```

#### Ubuntu/Debian
```bash
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis  # Auto-start on boot
```

#### Docker
```bash
docker run -d -p 6379:6379 redis:alpine
```

### Verification

```bash
# Check if Redis is running
redis-cli ping  # Should return "PONG"

# Check Redis info
redis-cli info server

# Monitor Redis commands
redis-cli monitor
```

### Configuration

**Environment Variables**:
```bash
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0
export REDIS_PASSWORD=                    # Optional
export REDIS_URL=redis://localhost:6379/0  # Full URL
```

**Redis with Password**:
```bash
export REDIS_URL=redis://:password@localhost:6379/0
```

**Redis with SSL**:
```bash
export REDIS_URL=rediss://localhost:6379/0
```

---

## Worker Management

### Starting Workers

#### Manual Start

```bash
cd backend
chmod +x start_workers.sh
./start_workers.sh
```

#### Background Start

```bash
# Start in background
nohup ./start_workers.sh > logs/rq-worker.log 2>&1 &

# Check process
ps aux | grep rq
```

#### systemd (Production)

Create `/etc/systemd/system/atom-workers.service`:

```ini
[Unit]
Description=Atom RQ Workers
After=network.target redis.service

[Service]
Type=simple
User=atom
WorkingDirectory=/path/to/atom/backend
ExecStart=/path/to/atom/backend/start_workers.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start and enable:
```bash
sudo systemctl daemon-reload
sudo systemctl start atom-workers
sudo systemctl enable atom-workers
sudo systemctl status atom-workers
```

### Worker Configuration

**File**: `backend/start_workers.sh`

```bash
#!/bin/bash
# Worker configuration
QUEUES="social_media workflows default"
WORKER_NAME="atom-worker"
TIMEOUT=300  # 5 minutes
LOG_FILE="logs/rq-worker.log"

# Start worker
rq worker $QUEUES \
  --name $WORKER_NAME \
  --url $REDIS_URL \
  --timeout $TIMEOUT \
  --log-level INFO \
  >> $LOG_FILE 2>&1
```

### Multiple Workers

```bash
# Start multiple workers for high throughput
WORKER_1_PID=$(rq worker social_media --name worker-1 --url $REDIS_URL &)
WORKER_2_PID=$(rq worker workflows --name worker-2 --url $REDIS_URL &)
WORKER_3_PID=$(rq worker default --name worker-3 --url $REDIS_URL &)
```

---

## Job Management

### Enqueueing Jobs

**Python Code**:
```python
from core.task_queue import task_queue
from datetime import datetime, timedelta

# Simple job
job = task_queue.enqueue(
    'process_scheduled_post',
    post_id='post_123',
    user_id='user_456'
)

# Scheduled job (delay)
job = task_queue.enqueue_in(
    timedelta(minutes=30),
    'process_scheduled_post',
    post_id='post_123',
    user_id='user_456'
)

# Scheduled job (specific time)
job = task_queue.enqueue_at(
    datetime(2026, 2, 6, 14, 30),
    'process_scheduled_post',
    post_id='post_123',
    user_id='user_456'
)
```

### Job Status

```python
from core.task_queue import get_job_status

status = get_job_status(job_id)
# Returns: {
#     'job_id': '...',
#     'status': 'queued' | 'started' | 'finished' | 'failed',
#     'created_at': '2026-02-06T10:00:00',
#     'enqueued_at': '2026-02-06T10:00:00',
#     'started_at': '2026-02-06T10:00:05',
#     'ended_at': '2026-02-06T10:00:10',
#     'result': {...},
#     'error': None
# }
```

### Canceling Jobs

```python
from core.task_queue import cancel_job

cancel_job(job_id)
```

---

## Monitoring

### CLI Monitoring

```bash
# View queue statistics
rq info --url redis://localhost:6379/0

# View specific queue
rq info --url redis://localhost:6379/0 --queue social_media

# View worker status
rq workers --url redis://localhost:6379/0

# View scheduled jobs
rq scheduler --url redis://localhost:6379/0

# Empty a queue (CAUTION!)
rq empty --url redis://localhost:6379/0 --queue social_media

# Requeue all failed jobs
rq requeue --url redis://localhost:6379/0 --queue social_media
```

### API Monitoring

**List Scheduled Posts**:
```bash
curl http://localhost:8000/api/v1/tasks/scheduled-posts
```

**Get Job Status**:
```bash
curl http://localhost:8000/api/v1/tasks/scheduled-posts/{post_id}/status
```

**Get Queue Statistics**:
```bash
curl http://localhost:8000/api/v1/tasks/queues
```

**Response**:
```json
{
  "queues": [
    {
      "name": "social_media",
      "queued": 5,
      "started": 2,
      "finished": 150,
      "failed": 3
    },
    {
      "name": "workflows",
      "queued": 1,
      "started": 1,
      "finished": 45,
      "failed": 0
    }
  ]
}
```

### Log Monitoring

```bash
# Worker logs
tail -f logs/rq-worker.log

# Filter for errors
tail -f logs/rq-worker.log | grep ERROR

# Filter for specific job
tail -f logs/rq-worker.log | grep "post_123"
```

---

## Debugging

### Common Issues

#### 1. Worker Not Processing Jobs

**Symptoms**: Jobs queued but not processing

**Diagnosis**:
```bash
# Check if worker is running
ps aux | grep rq

# Check if Redis is running
redis-cli ping

# Check queue status
rq info --url redis://localhost:6379/0
```

**Solutions**:
- Start worker: `./start_workers.sh`
- Check Redis connection: Verify `REDIS_URL`
- Check worker logs: `tail -f logs/rq-worker.log`

#### 2. Jobs Failing

**Symptoms**: Jobs move to failed queue

**Diagnosis**:
```bash
# View failed jobs
rq failed --url redis://localhost:6379/0

# View specific failed job
rq failed --url redis://localhost:6379/0 --job-id <job_id>
```

**Solutions**:
- Check error message in failed job details
- Fix code issue and restart worker
- Requeue job: `rq requeue --url redis://localhost:6379/0 --job-id <job_id>`

#### 3. Memory Issues

**Symptoms**: Worker crashes with out of memory error

**Diagnosis**:
```bash
# Check worker memory usage
ps aux | grep rq

# Check Redis memory usage
redis-cli info memory
```

**Solutions**:
- Increase worker timeout
- Process jobs in batches
- Add more workers
- Increase Redis memory limit

#### 4. Connection Issues

**Symptoms**: Worker can't connect to Redis

**Diagnosis**:
```bash
# Test Redis connection
redis-cli -h localhost -p 6379 ping

# Check if Redis is listening
netstat -an | grep 6379
```

**Solutions**:
- Verify Redis is running: `systemctl status redis`
- Check firewall rules
- Verify `REDIS_URL` environment variable

### Job Testing

```python
# Test job function directly
from integrations.social_media_scheduler import process_scheduled_post

result = process_scheduled_post(
    post_id='test_post',
    user_id='test_user'
)
print(result)
```

### Worker Testing

```bash
# Start worker in burst mode (process all jobs then exit)
rq worker --burst --url redis://localhost:6379/0

# Start worker with verbose logging
rq worker --verbose --url redis://localhost:6379/0
```

---

## Performance Tuning

### Worker Optimization

**Increase Worker Count**:
```bash
# Start 5 workers
for i in {1..5}; do
  rq worker --name worker-$i --url $REDIS_URL &
done
```

**Adjust Timeout**:
```bash
# Increase timeout for long-running jobs
rq worker --timeout 600 --url $REDIS_URL
```

**Limit Job Count**:
```bash
# Process 100 jobs then exit
rq worker --max-jobs 100 --burst --url $REDIS_URL
```

### Queue Optimization

**Priority Queues**:
```bash
# High priority queue
rq worker high_priority default --url $REDIS_URL
```

**Queue-Specific Workers**:
```bash
# Dedicated worker for social media
rq worker social_media --name social-worker --url $REDIS_URL
```

### Redis Optimization

**Configuration** (`/etc/redis/redis.conf`):
```conf
# Maximum memory
maxmemory 256mb

# Eviction policy
maxmemory-policy allkeys-lru

# Persistence (disable for speed)
save ""

# Enable if persistence needed
save 900 1
save 300 10
save 60 10000
```

---

## Best Practices

### Job Design

1. **Keep Jobs Idempotent**: Jobs should be safe to retry
2. **Use Timeouts**: Prevent jobs from running forever
3. **Handle Failures**: Catch exceptions and log errors
4. **Avoid Long-Running Jobs**: Break into smaller chunks
5. **Use Job Metadata**: Store job context for debugging

### Error Handling

```python
def process_scheduled_post(post_id: str, user_id: str):
    try:
        # Process post
        result = publish_post(post_id, user_id)

        # Log success
        logger.info(f"Successfully published post {post_id}")
        return result

    except Exception as e:
        # Log error
        logger.error(f"Failed to publish post {post_id}: {e}")

        # Re-raise to mark job as failed
        raise
```

### Monitoring

1. **Set up alerts**: Monitor failed job count
2. **Track queue depth**: Alert if jobs accumulate
3. **Monitor worker health**: Restart if worker crashes
4. **Log analysis**: Review worker logs regularly

### Security

1. **Redis Authentication**: Use `REDIS_PASSWORD`
2. **Redis SSL**: Use `rediss://` for production
3. **Network Isolation**: Keep Redis on private network
4. **Access Control**: Limit Redis client connections

---

## Production Deployment

### Checklist

- [ ] Redis installed and configured
- [ ] Redis configured for persistence (if needed)
- [ ] Worker systemd service created
- [ ] Worker auto-restart enabled
- [ ] Log rotation configured
- [ ] Monitoring set up (Prometheus, Grafana)
- [ ] Alerts configured (failed jobs, queue depth)
- [ ] Backup strategy for Redis data

### systemd Service

**File**: `/etc/systemd/system/atom-workers.service`

```ini
[Unit]
Description=Atom RQ Workers
After=network.target redis.service
Requires=redis.service

[Service]
Type=simple
User=atom
Group=atom
WorkingDirectory=/var/www/atom/backend
Environment="PATH=/var/www/atom/venv/bin"
Environment="REDIS_URL=redis://localhost:6379/0"
ExecStart=/var/www/atom/backend/start_workers.sh
Restart=always
RestartSec=10
StandardOutput=append:/var/log/atom/rq-worker.log
StandardError=append:/var/log/atom/rq-worker-error.log

[Install]
WantedBy=multi-user.target
```

### Log Rotation

**File**: `/etc/logrotate.d/atom-workers`

```
/var/log/atom/rq-worker*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 atom atom
    sharedscripts
    postrotate
        systemctl reload atom-workers > /dev/null 2>&1 || true
    endscript
}
```

---

## References

### Official Documentation
- [RQ Documentation](https://python-rq.org/)
- [Redis Documentation](https://redis.io/documentation)

### Atom Documentation
- [DEVELOPMENT.md](DEVELOPMENT.md) - Background Task Queue section
- [backend/docs/INCOMPLETE_IMPLEMENTATIONS.md](../backend/docs/INCOMPLETE_IMPLEMENTATIONS.md) - Task queue implementation
- [backend/core/task_queue.py](../backend/core/task_queue.py) - Core implementation

### API Endpoints
- `GET /api/v1/tasks/scheduled-posts` - List scheduled posts
- `GET /api/v1/tasks/scheduled-posts/{id}/status` - Get job status
- `DELETE /api/v1/tasks/scheduled-posts/{id}/cancel` - Cancel job
- `GET /api/v1/tasks/queues` - Queue statistics

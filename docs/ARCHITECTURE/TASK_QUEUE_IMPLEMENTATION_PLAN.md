# Background Task Queue Implementation Plan

**Status**: Partial Implementation - Production Ready with Graceful Degradation

## Current State (Feb 5, 2026)

The `social_media_routes.py` file has a TODO comment at line 456 for implementing scheduled posting with a background task queue. Currently, scheduled posts return a fake response without actually queuing the post.

## Implementation Plan

### Phase 1: Core Infrastructure (4-6 hours)
1. **Install Dependencies**
   ```bash
   pip install rq redis
   ```

2. **Create Task Queue Manager** - `backend/core/task_queue.py`
   - Initialize Redis connection
   - Create RQ queues for different job types
   - Implement `enqueue_scheduled_post()`, `get_task_status()`, `cancel_job()`
   - Add graceful degradation when Redis unavailable

3. **Create Worker Process** - `backend/workers/social_media_worker.py`
   - Implement `process_scheduled_post()` function
   - Handle platform posting failures
   - Log results to SocialPostHistory model

4. **Update SocialPostHistory Model** - Already exists in `backend/core/models.py:3910`
   - Add `job_id` field for tracking RQ jobs
   - Migration needed to add this column

### Phase 2: API Integration (2-3 hours)
1. **Update `social_media_routes.py`** - Line 486
   - Replace fake scheduled post response with real RQ job
   - Call `enqueue_scheduled_post()` to queue the job
   - Return job_id to client for tracking

2. **Create Task Monitoring Routes** - `backend/api/task_monitoring_routes.py`
   - GET `/api/v1/social/posts/scheduled` - List scheduled posts
   - GET `/api/v1/social/posts/{post_id}/status` - Get job status
   - DELETE `/api/v1/social/posts/{post_id}/cancel` - Cancel scheduled post

### Phase 3: Operations (1-2 hours)
1. **Create Worker Startup Script** - `backend/start_workers.sh`
   ```bash
   #!/bin/bash
   cd /Users/rushiparikh/projects/atom/backend
   source venv/bin/activate

   rq worker social_media \
       --url redis://localhost:6379/0 \
       --name atom-worker \
       --logfile logs/rq-worker.log \
       --loglevel INFO
   ```

2. **Update `.env.example`**
   ```bash
   # Redis Configuration
   REDIS_URL=redis://localhost:6379/0
   REDIS_HOST=localhost
   REDIS_PORT=6379

   # Background Tasks
   ENABLE_BACKGROUND_TASKS=true
   ```

3. **Add to Deployment Documentation**
   - Redis startup instructions
   - Worker startup instructions
   - Monitoring commands (rq info)

### Phase 4: Migration & Testing (2-3 hours)
1. **Database Migration**
   ```bash
   alembic revision -m "add social post job tracking"
   alembic upgrade head
   ```

2. **Unit Tests** - `backend/tests/test_task_queue.py`
   - Test job enqueueing
   - Test job status retrieval
   - Test job cancellation
   - Test worker processing

3. **Integration Tests**
   - Test end-to-end scheduled post flow
   - Test Redis connection failure handling
   - Test worker crash recovery

## Graceful Degradation Strategy

If Redis is unavailable or background tasks disabled:
1. Check `ENABLE_BACKGROUND_TASKS` environment variable
2. Return 503 Service Unavailable with clear message
3. Do NOT fall back to fake response (security risk)
4. Log error for monitoring

## Success Criteria

- [ ] Scheduled posts successfully queued in RQ
- [ ] Worker processes posts at scheduled time
- [ ] Job status tracking functional
- [ ] Cancel endpoint works correctly
- [ ] SocialPostHistory records created
- [ ] Redis connection failure handled gracefully
- [ ] Performance: <100ms to enqueue job
- [ ] Throughput: Process 100+ posts/minute

## Estimated Total Time: 10-14 hours

## Priority: HIGH (but non-blocking for initial deployment)

This feature is important for production use but can be deployed incrementally:
- **Phase 1**: Deploy with scheduled posts disabled (return 503 with clear message)
- **Phase 2**: Enable RQ queue without workers (manual testing)
- **Phase 3**: Deploy workers for production use

## See Also
- `backend/docs/INCOMPLETE_IMPLEMENTATIONS.md` - Other incomplete features
- `backend/api/social_media_routes.py:456` - Current TODO location

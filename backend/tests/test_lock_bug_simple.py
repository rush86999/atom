"""Quick test to confirm threading.Lock bug in async context."""
import asyncio
import sys
sys.path.insert(0, '/Users/rushiparikh/projects/atom/backend')

from core.governance_cache import GovernanceCache

async def test_lock_bug():
    cache = GovernanceCache(max_size=100, ttl_seconds=60)

    lock_holder_running = asyncio.Event()
    second_task_started = asyncio.Event()
    violations = []

    async def lock_holder():
        lock_holder_running.set()
        with cache._lock:
            # Hold lock and sleep to let other tasks run
            await asyncio.sleep(0.1)
            if second_task_started.is_set():
                violations.append('Second task ran while lock was held!')

    async def cache_modifier():
        await lock_holder_running.wait()
        second_task_started.set()
        # This should be blocked by lock, but isn't in asyncio
        with cache._lock:
            cache.set('test', 'action', {'data': 'modified'})

    await asyncio.gather(lock_holder(), cache_modifier())

    print(f'Violations: {violations}')
    if violations:
        print('BUG CONFIRMED: threading.Lock does NOT properly block async tasks!')
        return True
    else:
        print('Lock appears to work (but may be unreliable due to timing)')
        return False

if __name__ == '__main__':
    result = asyncio.run(test_lock_bug())
    exit(0 if result else 1)

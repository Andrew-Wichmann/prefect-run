from prefect import flow, get_run_logger
from prefect.runtime import flow_run

from joule import audit, cache


@flow(name="cleanup-cache")
def cleanup_cache():
    """Delete stage results whose job retention has run out, and record each deletion in the audit log."""
    evicted = cache.evict_expired()
    audit.record_evicted(evicted, flow_run.id)
    get_run_logger().info(f"evicted {len(evicted)} expired cache entries")
    return len(evicted)

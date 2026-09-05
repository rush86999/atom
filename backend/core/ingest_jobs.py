"""Shared background ingest-job registry for the storage/drive integrations.

One phantom-500 root cause, one general fix: ingesting a file or a folder
tree takes minutes (download + parse + chunk + embed + per-chunk GraphRAG),
while the Next.js dev proxy hard-aborts proxied requests at 30s
(proxy-request.js ``proxyTimeout: 30000``) and synthesizes a 500 to the
browser ("Failed to proxy ... socket hang up") while the backend is still
working. Synchronous ingest endpoints therefore surfaced as phantom 500s on
every drive integration, not just one.

The general mechanism (first built for zoho-workdrive, 2026-09-04):

- Each integration's ingest POST starts a job in THIS registry and returns
  its id immediately; heavy work runs in a request-background task.
- A repeat POST for the same file/folder while its job is running is
  COALESCED into the running job (double clicks used to race parallel tree
  walks and double the quota-limited API load).
- Each integration's router mounts the shared read routes via
  ``register_ingest_job_routes(router, integration_id)``:
    GET /ingest/jobs              recent jobs for the current user
    GET /ingest/jobs/{job_id}     job snapshot
    GET /ingest-folder/jobs/{job_id}  alias (the zoho panel's poll path)
- Durable "already ingested" badges: ``register_ingested_ids_route(router,
  source)`` exposes POST /ingested-ids, probing the document store under the
  write identity key (ext_sha1(source:external_id), incl. ::c0 chunks).

Jobs are in-process: a backend restart loses them and pollers get a 404 the
UI reports as "interrupted (the server restarted)".
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from core.auth import get_current_user, User

logger = logging.getLogger(__name__)

registry: Dict[str, Dict[str, Any]] = {}

_FINISHED_CAP = 50   # bound the registry: oldest finished jobs are dropped
_LIST_CAP = 20       # per-user cap on the recent-jobs list


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ids_key(ids: List[str]) -> str:
    return ",".join(sorted(ids))


def _prune() -> None:
    finished = sorted(
        (j for j in registry.values() if j["status"] != "running"),
        key=lambda j: j.get("finished_at") or "",
    )
    for old in finished[:-_FINISHED_CAP]:
        registry.pop(old["job_id"], None)


def create_job(
    integration_id: str,
    user_id: str,
    kind: str,
    ids: List[str],
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    job_id = uuid.uuid4().hex[:12]
    job: Dict[str, Any] = {
        "job_id": job_id,
        "integration": integration_id,
        "user_id": user_id,
        "status": "running",
        "kind": kind,
        "ids_key": ids_key(ids),
        "started_at": _now(),
        "finished_at": None,
        "result": None,
        "error": None,
    }
    job.update(extra or {})
    registry[job_id] = job
    return job


def find_running(
    integration_id: str, user_id: str, kind: str, ids: List[str]
) -> Optional[Dict[str, Any]]:
    """One ingestion of a given folder/file at a time: a second POST for the
    same target while its job runs must coalesce, not race it."""
    key = ids_key(ids)
    for job in registry.values():
        if (job["status"] == "running"
                and job.get("integration") == integration_id
                and job.get("user_id") == user_id
                and job.get("kind") == kind
                and job.get("ids_key") == key):
            return job
    return None


def start_job(job: Dict[str, Any], runner: Callable[[], Any]) -> None:
    """Run ``runner`` (zero-arg async callable returning the result dict) in
    the request background; its ``success`` flag decides completed/failed.
    Feedback recording stays with the caller's runner."""
    async def _run():
        try:
            result = await runner()
            job["status"] = "completed" if result.get("success") else "failed"
            job["result"] = result
        except Exception as e:  # noqa: BLE001 — failures land in the job record
            logger.error(f"Ingest job {job['job_id']} ({job.get('integration')}) failed: {e}")
            job["status"] = "failed"
            job["error"] = str(e)[:200]
        finally:
            job["finished_at"] = _now()
            _prune()

    asyncio.create_task(_run())


def snapshot(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "integration": job.get("integration"),
        "kind": job.get("kind"),
        "folder_ids": job.get("folder_ids"),
        "file_id": job.get("file_id"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "result": job.get("result"),
        "error": job.get("error"),
    }


def get_owned(job_id: str, integration_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    job = registry.get(job_id)
    if job is None or job.get("user_id") != user_id:
        return None
    if integration_id and job.get("integration") != integration_id:
        return None
    return job


def list_for(integration_id: str, user_id: str, cap: int = _LIST_CAP) -> List[Dict[str, Any]]:
    mine = [j for j in registry.values()
            if j.get("user_id") == user_id
            and (not integration_id or j.get("integration") == integration_id)]
    running = [j for j in mine if j["status"] == "running"]
    finished = sorted(
        (j for j in mine if j["status"] != "running"),
        key=lambda j: j.get("finished_at") or j.get("started_at") or "",
        reverse=True,
    )
    return [snapshot(j) for j in (running + finished)[:cap]]


def started_payload(job: Dict[str, Any], coalesced: bool = False, **extra: Any) -> Dict[str, Any]:
    """Standard POST response for a job-backed ingest endpoint. The UI parses
    ``job_id`` from ``data`` (or top level for older payloads)."""
    data: Dict[str, Any] = {"job_id": job["job_id"], "status": "started", **extra}
    if coalesced:
        data["coalesced"] = True
    return {"success": True, "data": data,
            "message": "Ingestion already running — poll the jobs endpoint"
            if coalesced else "Ingestion started — poll the jobs endpoint"}


def register_ingest_job_routes(router: Any, integration_id: str) -> None:
    """Mount the shared read routes on an integration's router. Each router's
    prefix scopes the paths (e.g. /api/onedrive/ingest/jobs)."""

    @router.get("/ingest/jobs", summary=f"Recent {integration_id} ingestion jobs (running first)")
    async def _ingest_jobs_list(current_user: User = Depends(get_current_user)):
        return {"success": True, "data": list_for(integration_id, str(current_user.id))}

    @router.get("/ingest/jobs/{job_id}", summary="Status of an ingestion job")
    @router.get("/ingest-folder/jobs/{job_id}", summary="Status of a folder ingestion job (alias)")
    async def _ingest_job_status(job_id: str, current_user: User = Depends(get_current_user)):
        job = get_owned(job_id, integration_id, str(current_user.id))
        if job is None:
            raise HTTPException(status_code=404, detail=f"Ingestion job not found: {job_id}")
        return {"success": True, "data": snapshot(job)}


class IngestedIdsRequest(BaseModel):
    file_ids: List[str] = Field(..., min_length=1, max_length=2000,
                                description="Source-native file IDs to check against ATOM memory")


def register_ingested_ids_route(router: Any, source: str) -> None:
    """Mount POST /ingested-ids: which of these source-native file ids already
    have documents in ATOM memory. Durable source of truth for the panels'
    "already ingested" badges (session-only React state resets on reload)."""

    @router.post("/ingested-ids", summary=f"Which {source} files are already in ATOM memory")
    async def _ingested_ids(body: IngestedIdsRequest, current_user: User = Depends(get_current_user)):
        from core.auto_document_ingestion import AutoDocumentIngestionService

        ingestor = AutoDocumentIngestionService()
        found = await ingestor.ingested_external_ids(source, body.file_ids)
        return {"success": True, "data": {"ingested": found}}

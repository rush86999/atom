# -*- coding: utf-8 -*-
"""Strict direct WorkDrive proof for the issue-620 workbook replay.

The strict answer is produced ONLY by the existing read path:

    UniversalIntegrationService._read_storage_file
        -> storage_service.download_file(...)          (bytes in this execution)
        -> workbook_read_artifact.inspect_workbook_bytes(...)
        -> the structured workbook answer

There is no parallel download after the answer and no materialized-copy
fallback. ``_read_storage_file`` emits a receipt (schema
``workdrive-direct-receipt-1``) beside the downloaded workbook artifact; the
proof below verifies that receipt against the artifact, the exact resource id,
the exact execution id, and the SHA-256 of the downloaded bytes.

Nothing here accepts a materialized-copy hash, a filename, or a reply
citation as direct proof.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Optional

SCHEMA = "workdrive-direct-proof-2"
RECEIPT_SCHEMA = "workdrive-direct-receipt-1"
DIRECT_KIND = "direct_download"
MATERIALIZED_KIND = "materialized_copy"
DOWNLOADED_KIND = "downloaded_bytes"
PROVIDER = "zoho_workdrive"
OPERATION = "read_storage_file"
SHA256_SOURCE = "downloaded_bytes_sha256"
ANSWER_SOURCE = "downloaded_bytes"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")


class WorkDriveProofError(ValueError):
    """The storage-read result cannot establish a direct-download proof."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _text(value).lower()


def _sha256(value: Any) -> str:
    return _lower(value)


def _sha1(value: Any) -> str:
    return _lower(value)


def build_workdrive_proof(
    *,
    resource_id: str,
    downloaded_sha256: str,
    downloaded_bytes: int,
    execution_id: str,
    file_name: Optional[str] = None,
    downloaded_sha1: Optional[str] = None,
    provider: str = PROVIDER,
    operation: str = OPERATION,
    version: Optional[str] = None,
    access: str = "granted",
    evidence_kind: str = DIRECT_KIND,
    downloaded_at: Optional[str] = None,
    receipt: Optional[Dict[str, Any]] = None,
    answer_source: str = ANSWER_SOURCE,
) -> Dict[str, Any]:
    """Build a verified proof from a same-execution storage read.

    Raises ``WorkDriveProofError`` when the observation is incomplete or when
    the caller attempts to label a materialized copy as direct proof.
    """
    resource_id = _text(resource_id)
    execution_id = _text(execution_id)
    sha256 = _sha256(downloaded_sha256)
    sha1 = _sha1(downloaded_sha1)
    kind = _lower(evidence_kind)
    if not resource_id:
        raise WorkDriveProofError("resource_id is required")
    if not execution_id:
        raise WorkDriveProofError("execution_id is required")
    if not _SHA256_RE.match(sha256):
        raise WorkDriveProofError("downloaded_sha256 must be 64 hex characters")
    if sha1 and not _SHA1_RE.match(sha1):
        raise WorkDriveProofError("downloaded_sha1 must be 40 hex characters")
    try:
        size = int(downloaded_bytes)
    except (TypeError, ValueError):
        raise WorkDriveProofError("downloaded_bytes must be an integer")
    if size <= 0:
        raise WorkDriveProofError("downloaded_bytes must be positive")
    if kind != DIRECT_KIND or kind == MATERIALIZED_KIND:
        raise WorkDriveProofError(
            "direct proof requires downloaded bytes, not a materialized copy")
    if _lower(access) != "granted":
        raise WorkDriveProofError("direct proof requires an authorized read")
    if _lower(provider) != PROVIDER:
        raise WorkDriveProofError(f"provider must be {PROVIDER}")
    if _lower(operation) != OPERATION:
        raise WorkDriveProofError(f"operation must be {OPERATION}")
    if _lower(answer_source) != ANSWER_SOURCE:
        raise WorkDriveProofError(
            "the delivered answer must be derived from the downloaded bytes")
    receipt = dict(receipt or {})
    return {
        "schema": SCHEMA,
        "status": "verified",
        "evidence_kind": DIRECT_KIND,
        "provider": PROVIDER,
        "operation": OPERATION,
        "resource_id": resource_id,
        "file_name": _text(file_name) or None,
        "version": _text(version) or None,
        "access": "granted",
        "downloaded_sha256": sha256,
        "downloaded_sha1": sha1 or None,
        "downloaded_bytes": size,
        "sha256_source": SHA256_SOURCE,
        "answer_source": ANSWER_SOURCE,
        "execution_id": execution_id,
        "downloaded_at": downloaded_at,
        "materialized": False,
        "receipt_schema": _text(receipt.get("schema")) or None,
        "receipt": receipt or None,
    }


def proof_from_storage_read_result(
    read_result: Any,
    *,
    execution_id: str,
    expected_resource_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify a strict ``_read_storage_file`` result and prove its download.

    The receipt, the workbook artifact, and the storage-read result must all
    name the same resource and the same SHA-256, and the receipt must carry the
    exact execution id. Any materialized-copy marker is rejected.
    """
    if not isinstance(read_result, dict):
        raise WorkDriveProofError("storage read result is not an object")
    if isinstance(read_result.get("data"), dict):
        read_result = read_result["data"]
    if _lower(read_result.get("evidence_kind")) == MATERIALIZED_KIND:
        raise WorkDriveProofError(
            "strict proof cannot use a materialized-copy result")
    if read_result.get("served") is not True:
        raise WorkDriveProofError("storage read was not served")
    if read_result.get("read_completed") is not True:
        raise WorkDriveProofError("storage read did not complete")

    receipt = read_result.get("strict_read_receipt")
    if not isinstance(receipt, dict):
        raise WorkDriveProofError("strict read receipt is missing")
    if _text(receipt.get("schema")) != RECEIPT_SCHEMA:
        raise WorkDriveProofError("strict read receipt schema is not recognized")
    if _lower(receipt.get("provider")) != PROVIDER:
        raise WorkDriveProofError("read receipt is not from Zoho WorkDrive")
    if _lower(receipt.get("operation")) != OPERATION:
        raise WorkDriveProofError("read receipt is not a storage_file read")
    if _lower(receipt.get("evidence_kind")) != DOWNLOADED_KIND:
        raise WorkDriveProofError(
            "read receipt was not produced from downloaded bytes")
    if bool(receipt.get("materialized")):
        raise WorkDriveProofError("read receipt marks a materialized fallback")

    artifact = read_result.get("workbook_read")
    if not isinstance(artifact, dict):
        raise WorkDriveProofError("downloaded workbook artifact is missing")
    if _lower(artifact.get("provider")) != PROVIDER:
        raise WorkDriveProofError("workbook artifact is not from Zoho WorkDrive")
    if _lower(artifact.get("content_hash_algorithm")) not in ("", "sha256"):
        raise WorkDriveProofError(
            "workbook artifact was not hashed with SHA-256")

    receipt_sha256 = _sha256(receipt.get("sha256"))
    data_sha256 = _sha256(read_result.get("content_sha256"))
    artifact_sha256 = _sha256(
        artifact.get("sha256") or artifact.get("content_hash"))
    if not _SHA256_RE.match(receipt_sha256):
        raise WorkDriveProofError("read receipt has no downloaded SHA-256")
    if receipt_sha256 != data_sha256:
        raise WorkDriveProofError(
            "read receipt sha256 does not match the storage read content")
    if receipt_sha256 != artifact_sha256:
        raise WorkDriveProofError(
            "read receipt sha256 does not match the workbook artifact")

    try:
        receipt_bytes = int(receipt.get("bytes"))
    except (TypeError, ValueError):
        raise WorkDriveProofError("read receipt has no byte count")
    try:
        artifact_bytes = int(artifact.get("byte_length"))
    except (TypeError, ValueError):
        raise WorkDriveProofError("workbook artifact has no byte count")
    if receipt_bytes <= 0 or receipt_bytes != artifact_bytes:
        raise WorkDriveProofError(
            "read receipt byte count does not match the workbook artifact")

    receipt_resource = _text(receipt.get("resource_id"))
    data_resource = _text(
        read_result.get("resource_id") or read_result.get("file_id"))
    artifact_resource = _text(artifact.get("resource_id"))
    if not receipt_resource:
        raise WorkDriveProofError("read receipt has no resource id")
    if expected_resource_id and receipt_resource != _text(expected_resource_id):
        raise WorkDriveProofError(
            "read receipt resource id does not match the workbook resource")
    if data_resource and receipt_resource != data_resource:
        raise WorkDriveProofError(
            "read receipt resource id does not match the storage read")
    if artifact_resource and receipt_resource != artifact_resource:
        raise WorkDriveProofError(
            "read receipt resource id does not match the workbook artifact")

    receipt_execution = _text(receipt.get("execution_id"))
    expected_execution = _text(execution_id)
    if not expected_execution:
        raise WorkDriveProofError("proof requires the execution id")
    if receipt_execution != expected_execution:
        raise WorkDriveProofError(
            "read receipt was not produced by this execution")

    return build_workdrive_proof(
        resource_id=receipt_resource,
        downloaded_sha256=receipt_sha256,
        downloaded_sha1=receipt.get("sha1"),
        downloaded_bytes=receipt_bytes,
        execution_id=receipt_execution,
        file_name=(
            _text(artifact.get("file_name"))
            or _text(read_result.get("file_name"))
            or None
        ),
        version=receipt.get("version"),
        access="granted",
        receipt=receipt,
        downloaded_at=receipt.get("retrieved_at"),
    )


def join_proof_to_record(
    record: Any, proof: Any,
) -> Any:
    """Join a verified proof into an existing structured workbook record.

    The read's own ``evidence_kind`` is never rewritten — a strict read is
    stamped ``downloaded_bytes`` by its builder, and the direct proof rides
    beside it as separately-labelled evidence.
    """
    if not isinstance(record, dict) or not isinstance(proof, dict):
        return record
    joined = dict(record)
    joined["direct_source_proof"] = dict(proof)
    if _text(proof.get("status")) != "verified":
        return joined
    source_identity = dict(joined.get("source_identity") or {})
    source_identity.update({
        "download_sha256": proof.get("downloaded_sha256"),
        "download_sha1": proof.get("downloaded_sha1"),
        "download_resource_id": proof.get("resource_id"),
        "download_execution_id": proof.get("execution_id"),
        "proof_evidence_kind": DIRECT_KIND,
        "direct_source_proof": dict(proof),
    })
    joined["source_identity"] = source_identity
    return joined


def strict_workdrive_proof_checks(
    *,
    proof: Any,
    identity: Any,
    structured_result: Any = None,
    execution_id: Optional[str] = None,
    expected_resource_id: Optional[str] = None,
    expected_sha256: Optional[str] = None,
) -> Dict[str, bool]:
    """Checks for a persisted result that claims a strict WorkDrive proof.

    Every check is False when the proof is missing, materialized, or not joined
    to the same execution/resource/SHA-256 as the delivered answer.
    """
    proof = proof if isinstance(proof, dict) else {}
    identity = identity if isinstance(identity, dict) else {}
    structured = structured_result if isinstance(structured_result, dict) else {}
    source_identity = (
        structured.get("source_identity")
        if isinstance(structured.get("source_identity"), dict) else {}
    )
    receipt = proof.get("receipt") if isinstance(proof.get("receipt"), dict) else {}

    proof_status = _lower(proof.get("status"))
    verified = proof_status == "verified"
    proof_kind = _lower(proof.get("evidence_kind"))
    proof_resource = _text(proof.get("resource_id"))
    proof_sha256 = _sha256(proof.get("downloaded_sha256"))
    identity_resource = _text(
        identity.get("resource_id") or identity.get("file_id"))
    structured_resource = _text(
        source_identity.get("resource_id")
        or source_identity.get("file_id"))
    identity_sha256 = _sha256(
        identity.get("content_sha256") or identity.get("content_hash"))
    structured_sha256 = _sha256(
        source_identity.get("content_sha256")
        or source_identity.get("content_hash")
        or (source_identity.get("direct_source_proof") or {}).get(
            "downloaded_sha256"))
    identity_execution = _text(identity.get("execution_id"))
    proof_execution = _text(proof.get("execution_id"))
    expected_execution = _text(execution_id)
    proof_bytes = proof.get("downloaded_bytes")
    try:
        proof_bytes_int = int(proof_bytes)
    except (TypeError, ValueError):
        proof_bytes_int = 0
    receipt_sha256 = _sha256(receipt.get("sha256"))
    receipt_resource = _text(receipt.get("resource_id"))
    receipt_execution = _text(receipt.get("execution_id"))
    identity_evidence = _lower(identity.get("evidence_kind"))
    structured_evidence = _lower(source_identity.get("evidence_kind"))

    checks = {
        "strict_workdrive_proof_present": bool(proof),
        "strict_workdrive_proof_verified": verified,
        "strict_workdrive_proof_schema": _text(proof.get("schema")) == SCHEMA,
        "strict_workdrive_proof_direct": (
            verified and proof_kind == DIRECT_KIND
            and _lower(proof.get("operation")) == OPERATION
            and _lower(proof.get("provider")) == PROVIDER
            and not bool(proof.get("materialized"))
        ),
        "strict_workdrive_proof_authorized": (
            verified and _lower(proof.get("access")) == "granted"),
        "strict_workdrive_proof_sha256_source": (
            verified and _lower(proof.get("sha256_source")) == SHA256_SOURCE),
        "strict_workdrive_proof_answer_source": (
            verified
            and _lower(proof.get("answer_source")) == ANSWER_SOURCE
            and structured_evidence == DOWNLOADED_KIND
            and (not identity_evidence or identity_evidence == DOWNLOADED_KIND)
        ),
        "strict_workdrive_proof_bytes": verified and proof_bytes_int > 0,
        "strict_workdrive_proof_receipt": (
            verified
            and _text(receipt.get("schema")) == RECEIPT_SCHEMA
            and bool(receipt)
            and receipt_sha256 == proof_sha256
            and receipt_resource == proof_resource
            and receipt_execution == proof_execution
        ),
        "strict_workdrive_proof_resource_id": (
            verified and bool(proof_resource)
            and proof_resource == identity_resource
            and (
                not structured
                or (bool(structured_resource)
                    and proof_resource == structured_resource)
            )
            and (
                not expected_resource_id
                or proof_resource == _text(expected_resource_id)
            )
        ),
        "strict_workdrive_proof_downloaded_sha256": (
            verified and bool(_SHA256_RE.match(proof_sha256))
            and (
                not expected_sha256
                or proof_sha256 == _sha256(expected_sha256)
            )
        ),
        "strict_workdrive_proof_sha256_joined": (
            verified and bool(proof_sha256)
            and proof_sha256 == identity_sha256
            and (
                not structured
                or (bool(structured_sha256)
                    and proof_sha256 == structured_sha256)
            )
        ),
        "strict_workdrive_proof_same_execution": (
            verified and bool(proof_execution)
            and proof_execution == identity_execution
            and (
                not expected_execution
                or proof_execution == expected_execution
            )
        ),
        "strict_workdrive_no_materialized_fallback": (
            verified
            and proof_kind != MATERIALIZED_KIND
            and not bool(proof.get("materialized"))
            and _lower(proof.get("answer_source")) == ANSWER_SOURCE
            and structured_evidence == DOWNLOADED_KIND
            and identity_evidence != MATERIALIZED_KIND
            and structured_evidence != MATERIALIZED_KIND
        ),
    }
    checks["strict_workdrive_all_pass"] = all(checks.values())
    return checks


async def read_workdrive_workbook_direct(
    *,
    user_id: Optional[str],
    workspace_id: Optional[str],
    resource_id: str,
    file_name: Optional[str],
    query: str,
    context: Optional[Dict[str, Any]] = None,
    execution_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    storage_service: Any = None,
) -> Dict[str, Any]:
    """Run the existing storage read and return its downloaded-bytes proof.

    This is the ONLY strict retrieval path: it calls
    ``UniversalIntegrationService._read_storage_file`` (which downloads the
    exact resource and calls ``inspect_workbook_bytes`` on those bytes), then
    verifies the emitted receipt. It performs no answer computation itself.
    """
    if not _text(resource_id):
        return {"status": "error", "error": "resource_id is required", "data": {}}
    if not _text(execution_id):
        return {"status": "error", "error": "execution_id is required", "data": {}}
    try:
        from integrations.universal_integration_service import (
            UniversalIntegrationService,
        )

        if storage_service is None:
            from core.integration_registry import IntegrationRegistry

            registry = IntegrationRegistry()
            storage_service = await registry.get_service_instance(
                PROVIDER, tenant_id or workspace_id or "default")
        if storage_service is None:
            return {
                "status": "error",
                "error": "WorkDrive service is unavailable",
                "data": {},
            }
        service = UniversalIntegrationService(
            workspace_id=workspace_id or "default")
        read_context = dict(context or {})
        read_context.update({
            "user_id": user_id,
            "workspace_id": workspace_id or read_context.get("workspace_id")
            or "default",
            "tenant_id": tenant_id or read_context.get("tenant_id") or "default",
            "execution_id": _text(execution_id),
            "strict_workdrive_proof": True,
        })
        params = {
            "file_id": _text(resource_id),
            "file_name": file_name,
            "query": query,
            "identity_verified": True,
        }
        result = await service._read_storage_file(
            PROVIDER,
            storage_service,
            getattr(storage_service, "access_token", None),
            params,
            read_context,
        )
    except Exception as exc:  # noqa: BLE001 — surface the failure honestly
        return {
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "data": {},
        }

    if not isinstance(result, dict) or result.get("status") != "success":
        return {
            "status": "error",
            "error": _text((result or {}).get("message")) or "storage read failed",
            "data": (result or {}).get("data") or {},
        }
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    try:
        proof = proof_from_storage_read_result(
            data,
            execution_id=_text(execution_id),
            expected_resource_id=_text(resource_id),
        )
    except WorkDriveProofError as exc:
        return {
            "status": "success",
            "data": data,
            "proof": None,
            "error": str(exc),
        }
    return {"status": "success", "data": data, "proof": proof, "error": ""}

"""
Small shared HTTP + multipart helpers for the md-simulation skill.

Keeps scripts stdlib-only (urllib) and avoids duplication across scripts.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from security_utils import validate_results_payload


def http_json(
    base_url: str,
    method: str,
    path: str,
    *,
    api_key: str,
    body: dict | None = None,
    auth: bool = True,
    timeout: float = 120.0,
    accept_codes: tuple[int, ...] = (200, 201),
) -> dict:
    """
    Perform an HTTP call and return a JSON object (validated as dict).

    Exits the process (non-zero) on network, auth, or unexpected HTTP errors
    so scripts fail loudly instead of silently producing garbage.
    """
    headers: dict[str, str] = {"Accept": "application/json"}
    if auth:
        headers["X-API-Key"] = api_key
    data: bytes | None = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    url = f"{base_url.rstrip('/')}{path}"
    request = Request(url=url, method=method, headers=headers, data=data)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.getcode()
    except HTTPError as error:
        status = error.code
        raw = error.read().decode("utf-8", errors="replace")
    except URLError as error:
        sys.exit(f"Error: Network error while requesting {url}: {error.reason}")

    if status == 401:
        sys.exit("Error: Unauthorized. Check FASTFOLD_API_KEY.")
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        sys.exit(f"Error: API returned invalid JSON from {url} (status {status}).")
    if status not in accept_codes:
        message = (
            payload.get("message")
            if isinstance(payload, dict) and payload.get("message")
            else raw
        )
        sys.exit(f"Error: {status} from {method} {url} - {message}")
    return validate_results_payload(payload)


def http_upload_file(
    base_url: str,
    path: str,
    *,
    api_key: str,
    file_path: Path,
    field_name: str = "files",
    timeout: float = 180.0,
) -> dict:
    """Upload a single file via multipart/form-data and return JSON response."""
    if not file_path.exists() or not file_path.is_file():
        sys.exit(f"Error: file not found: {file_path}")
    boundary = "----FastFoldBoundary" + uuid.uuid4().hex
    filename = file_path.name
    lower = filename.lower()
    if lower.endswith(".pdb"):
        content_type = "chemical/x-pdb"
    elif lower.endswith(".cif") or lower.endswith(".mmcif"):
        content_type = "chemical/x-cif"
    elif lower.endswith(".json"):
        content_type = "application/json"
    elif lower.endswith(".fasta") or lower.endswith(".fa"):
        content_type = "text/x-fasta"
    elif lower.endswith(".csv"):
        content_type = "text/csv"
    else:
        content_type = "application/octet-stream"

    body = (
        f"--{boundary}\r\n".encode()
        + f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode()
        + f"Content-Type: {content_type}\r\n\r\n".encode()
        + file_path.read_bytes()
        + b"\r\n"
        + f"--{boundary}--\r\n".encode()
    )
    headers = {
        "X-API-Key": api_key,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
    }
    url = f"{base_url.rstrip('/')}{path}"
    request = Request(url=url, method="POST", headers=headers, data=body)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.getcode()
    except HTTPError as error:
        status = error.code
        raw = error.read().decode("utf-8", errors="replace")
    except URLError as error:
        sys.exit(f"Error: Network error while uploading to {url}: {error.reason}")

    if status == 401:
        sys.exit("Error: Unauthorized. Check FASTFOLD_API_KEY.")
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        sys.exit(f"Error: API returned invalid JSON from {url} (status {status}).")
    if status not in (200, 201):
        message = (
            payload.get("message")
            if isinstance(payload, dict) and payload.get("message")
            else raw
        )
        sys.exit(f"Error: {status} from POST {url} - {message}")
    return validate_results_payload(payload)


def create_library_file_item(
    base_url: str,
    *,
    api_key: str,
    name: str,
    file_type: str,
) -> str:
    payload = http_json(
        base_url,
        "POST",
        "/v1/library/create",
        api_key=api_key,
        body={
            "name": name,
            "type": "file",
            "fileType": file_type,
            "origin": "USER_UPLOAD",
            "metadata": {},
        },
    )
    item_id = str(payload.get("id") or "").strip()
    if not item_id:
        sys.exit("Error: /library/create did not return an id.")
    return item_id


def upload_library_file_and_get_ref(
    base_url: str,
    *,
    api_key: str,
    file_path: Path,
    file_type: str,
    item_name: str | None = None,
) -> dict:
    """Create a library item, upload the file, and return {libraryItemId, fileName}."""
    base_name = (item_name or f"openmm-input-{file_path.stem}-{uuid.uuid4().hex[:8]}").strip()
    item_id = create_library_file_item(
        base_url,
        api_key=api_key,
        name=base_name,
        file_type=file_type,
    )
    http_upload_file(
        base_url,
        f"/v1/library/{item_id}/upload-files",
        api_key=api_key,
        file_path=file_path,
    )
    item = http_json(base_url, "GET", f"/v1/library/{item_id}", api_key=api_key)
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    files = metadata.get("files") if isinstance(metadata, dict) else None
    stored_file_name = ""
    if isinstance(files, list) and files:
        stored_file_name = str((files[0] or {}).get("file_name") or "").strip()
    if not stored_file_name:
        sys.exit("Error: uploaded library item metadata.files is empty.")
    return {"libraryItemId": item_id, "fileName": stored_file_name}


def extract_fold_job_ids(job_results: dict) -> tuple[str, str]:
    """
    From /v1/jobs/{jobId}/results, return (jobRunId, sequenceId).

    Sequence selection prefers the protein chain; falls back to the first sequence.
    """
    job_run_id = str(job_results.get("jobRunId") or "").strip()
    if not job_run_id:
        nested = job_results.get("job") if isinstance(job_results.get("job"), dict) else {}
        job_run_id = str((nested or {}).get("jobRunId") or "").strip()
    if not job_run_id:
        params = job_results.get("parameters") if isinstance(job_results.get("parameters"), dict) else {}
        job_run_id = str((params or {}).get("jobRunId") or "").strip()

    sequence_id = ""
    sequences = job_results.get("sequences") if isinstance(job_results.get("sequences"), list) else []
    for row in sequences:
        if not isinstance(row, dict):
            continue
        seq_type = str(row.get("type") or row.get("sequenceType") or "").strip().lower()
        if seq_type == "protein":
            sequence_id = str(row.get("id") or row.get("sequenceId") or row.get("sequence_id") or "").strip()
            if sequence_id:
                break
    if not sequence_id and sequences:
        first = sequences[0]
        if isinstance(first, dict):
            sequence_id = str(first.get("id") or first.get("sequenceId") or first.get("sequence_id") or "").strip()
    return job_run_id, sequence_id


TERMINAL_WORKFLOW_STATES = {"COMPLETED", "FAILED", "STOPPED"}

DASHBOARD_RESULTS_URL_TEMPLATE = "https://cloud.fastfold.ai/openmm/results/{workflow_id}"
PUBLIC_SHARE_URL_TEMPLATE = "https://cloud.fastfold.ai/openmm/results/{workflow_id}?shared=true"
PY2DMOL_URL_TEMPLATE = "https://cloud.fastfold.ai/py2dmol/new?from=openmm_workflow&workflow_id={workflow_id}"
PY2DMOL_INVITATION = (
    "Trajectory is available for this run to visualize simulation, "
    "generate animations, and use playback controls in Py2DMol."
)


def build_result_links(workflow_id: str, *, is_public: bool = False) -> dict:
    """Return canonical cloud URLs for a completed MD workflow."""
    return {
        "dashboard_url": DASHBOARD_RESULTS_URL_TEMPLATE.format(workflow_id=workflow_id),
        "public_share_url": (
            PUBLIC_SHARE_URL_TEMPLATE.format(workflow_id=workflow_id) if is_public else ""
        ),
        "py2dmol_url": PY2DMOL_URL_TEMPLATE.format(workflow_id=workflow_id),
        "py2dmol_invitation": PY2DMOL_INVITATION,
    }


def summarize_task_result(result_raw_json: Any) -> dict:
    """Extract artifacts + metrics summary from a task's result_raw_json."""
    if not isinstance(result_raw_json, dict):
        return {
            "has_metrics": False,
            "has_metricsJson": False,
            "artifact_count": 0,
            "artifacts": [],
        }
    metrics = result_raw_json.get("metrics") if isinstance(result_raw_json.get("metrics"), dict) else {}
    metrics_json = result_raw_json.get("metricsJson") if isinstance(result_raw_json.get("metricsJson"), dict) else {}
    artifacts = result_raw_json.get("artifacts") if isinstance(result_raw_json.get("artifacts"), list) else []
    normalized_artifacts = []
    for entry in artifacts:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "").strip()
        if not path:
            continue
        normalized_artifacts.append(
            {
                "path": path,
                "sizeBytes": entry.get("sizeBytes"),
                "url": entry.get("url"),
            }
        )
    return {
        "has_metrics": bool(metrics),
        "has_metricsJson": bool(metrics_json),
        "metrics": metrics,
        "metricsJson": metrics_json,
        "artifact_count": len(normalized_artifacts),
        "artifacts": normalized_artifacts,
    }

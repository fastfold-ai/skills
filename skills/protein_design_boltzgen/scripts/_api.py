"""
HTTP helpers for BoltzGen workflow scripts.

Stdlib-only implementation (urllib + multipart encoder).
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TERMINAL_WORKFLOW_STATUSES = {"COMPLETED", "FAILED", "STOPPED", "CANCELLED"}
TERMINAL_TASK_STATUSES = {"COMPLETED", "FAILED", "STOPPED", "CANCELLED"}


def resolve_urls(base_url: str | None, ui_base_url: str | None) -> tuple[str, str]:
    default_api = "https://api.fastfold.ai"
    default_ui = "https://cloud.fastfold.ai"
    api = (base_url or default_api).strip().rstrip("/")
    ui = (ui_base_url or default_ui).strip().rstrip("/")
    _validate_base_url(api)
    _validate_base_url(ui)
    return api, ui


def _validate_base_url(url: str) -> None:
    if not re.match(r"^https?://[A-Za-z0-9._:-]+$", url):
        raise ValueError(f"Invalid base URL: {url}")


def request_json(
    base_url: str,
    method: str,
    path: str,
    *,
    api_key: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 120.0,
    accept_codes: tuple[int, ...] = (200, 201),
) -> dict[str, Any]:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    final_headers = {"Accept": "application/json", **(headers or {})}
    if body is not None and "Content-Type" not in final_headers:
        final_headers["Content-Type"] = "application/json"
    final_headers["X-API-Key"] = api_key
    status, text = _request_once(
        f"{base_url.rstrip('/')}{path}",
        method,
        final_headers,
        payload,
        timeout,
    )
    if status not in accept_codes:
        _fail_http(method, base_url, path, status, text)
    try:
        parsed = json.loads(text) if text else {}
    except json.JSONDecodeError:
        sys.exit(f"Error: API returned non-JSON response for {method} {path} (status {status}).")
    if not isinstance(parsed, dict):
        sys.exit(f"Error: Expected JSON object from {method} {path}.")
    return parsed


def request_text(
    base_url: str,
    method: str,
    path: str,
    *,
    api_key: str,
    content_type: str = "text/plain",
    text_body: str = "",
    timeout: float = 180.0,
    accept_codes: tuple[int, ...] = (200, 201),
) -> str:
    headers = {"Content-Type": content_type, "Accept": "application/json", "X-API-Key": api_key}
    status, text = _request_once(
        f"{base_url.rstrip('/')}{path}",
        method,
        headers,
        text_body.encode("utf-8"),
        timeout,
    )
    if status not in accept_codes:
        _fail_http(method, base_url, path, status, text)
    return text


def request_text_response(
    base_url: str,
    method: str,
    path: str,
    *,
    api_key: str,
    accept: str = "text/plain",
    content_type: str | None = None,
    text_body: str | None = None,
    timeout: float = 180.0,
) -> tuple[int, str]:
    """Return raw HTTP status and text body for text endpoints.

    Useful for polling log endpoints where 404/204 can be expected while
    a run is starting, and callers need to handle those states explicitly.
    """
    headers: dict[str, str] = {"Accept": accept, "X-API-Key": api_key}
    payload: bytes | None = None
    if text_body is not None:
        payload = text_body.encode("utf-8")
        headers["Content-Type"] = content_type or "text/plain"
    elif content_type:
        headers["Content-Type"] = content_type

    return _request_once(
        f"{base_url.rstrip('/')}{path}",
        method,
        headers,
        payload,
        timeout,
    )


def upload_file(
    base_url: str,
    path: str,
    *,
    api_key: str,
    file_path: Path,
    logical_name: str,
    field_name: str = "files",
    timeout: float = 180.0,
) -> dict[str, Any]:
    if not file_path.exists() or not file_path.is_file():
        sys.exit(f"Error: file not found: {file_path}")
    boundary = "----FastFoldBoundary" + uuid.uuid4().hex
    content_type = _guess_content_type(logical_name)
    body = (
        f"--{boundary}\r\n".encode()
        + f'Content-Disposition: form-data; name="{field_name}"; filename="{logical_name}"\r\n'.encode()
        + f"Content-Type: {content_type}\r\n\r\n".encode()
        + file_path.read_bytes()
        + b"\r\n"
        + f"--{boundary}--\r\n".encode()
    )
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
        "X-API-Key": api_key,
    }
    status, text = _request_once(
        f"{base_url.rstrip('/')}{path}",
        "POST",
        headers,
        body,
        timeout,
    )
    if status not in (200, 201):
        _fail_http("POST", base_url, path, status, text)
    try:
        parsed = json.loads(text) if text else {}
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def create_library_item(
    base_url: str,
    *,
    api_key: str,
    name: str,
    file_type: str,
    parent_id: str | None,
) -> str:
    payload = {
        "name": name,
        "type": "file",
        "fileType": file_type,
        "origin": "USER_UPLOAD",
        "metadata": {},
    }
    if parent_id:
        payload["parent_id"] = parent_id
    response = request_json(
        base_url,
        "POST",
        "/v1/library/create",
        api_key=api_key,
        body=payload,
    )
    item_id = str(response.get("id") or "").strip()
    if not item_id:
        sys.exit("Error: /v1/library/create did not return an item id.")
    return item_id


def get_library_stored_file_name(
    base_url: str,
    *,
    api_key: str,
    item_id: str,
) -> str:
    response = request_json(
        base_url,
        "GET",
        f"/v1/library/{item_id}",
        api_key=api_key,
        accept_codes=(200,),
    )
    metadata = response.get("metadata")
    if not isinstance(metadata, dict):
        sys.exit(f"Error: Missing metadata for library item {item_id}.")
    files = metadata.get("files")
    if not isinstance(files, list) or not files:
        sys.exit(f"Error: No file metadata available for library item {item_id}.")
    first = files[0]
    if not isinstance(first, dict):
        sys.exit(f"Error: Invalid files metadata format for library item {item_id}.")
    stored_name = str(first.get("file_name") or "").strip()
    if not stored_name:
        sys.exit(f"Error: Missing file_name metadata for library item {item_id}.")
    return stored_name


def resolve_fastfold_folder_id(
    base_url: str,
    *,
    api_key: str,
    workspace_id: str | None,
) -> str | None:
    if not workspace_id:
        return None
    response = request_json(
        base_url,
        "GET",
        f"/v1/library/{workspace_id}",
        api_key=api_key,
        accept_codes=(200,),
    )
    children = response.get("children")
    if not isinstance(children, list):
        return workspace_id
    for child in children:
        if not isinstance(child, dict):
            continue
        if child.get("type") == "folder" and child.get("name") == ".fastfold":
            folder_id = str(child.get("id") or "").strip()
            if folder_id:
                return folder_id
    return workspace_id


def composer_url(ui_base_url: str, workflow_id: str) -> str:
    return f"{ui_base_url.rstrip('/')}/workflow/composer/{workflow_id}"


def _request_once(
    url: str,
    method: str,
    headers: dict[str, str],
    data: bytes | None,
    timeout: float,
) -> tuple[int, str]:
    request = Request(url=url, method=method, headers=headers, data=data)
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.getcode(), response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return error.code, body
    except URLError as error:
        sys.exit(f"Error: Network error while requesting {url}: {error.reason}")


def _fail_http(method: str, base_url: str, path: str, status: int, text: str) -> None:
    detail = text.strip()
    if detail:
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict) and parsed.get("message"):
                detail = str(parsed["message"])
        except Exception:
            pass
    if status == 401:
        sys.exit("Error: Unauthorized. Check FASTFOLD_API_KEY.")
    sys.exit(f"Error: {status} from {method} {base_url.rstrip('/')}{path} - {detail or 'empty response'}")


def _guess_content_type(file_name: str) -> str:
    lower = file_name.lower()
    if lower.endswith(".pdb"):
        return "chemical/x-pdb"
    if lower.endswith(".cif") or lower.endswith(".mmcif"):
        return "chemical/x-cif"
    if lower.endswith(".json"):
        return "application/json"
    if lower.endswith(".fasta") or lower.endswith(".fa"):
        return "text/x-fasta"
    if lower.endswith(".csv"):
        return "text/csv"
    if lower.endswith(".yaml") or lower.endswith(".yml"):
        return "text/yaml"
    return "application/octet-stream"

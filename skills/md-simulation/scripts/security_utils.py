"""
Security helpers for FastFold MD simulation scripts.

Validate untrusted input (CLI args + API responses) before side-effecting
operations such as network requests and file writes.
"""

from __future__ import annotations

import sys
import uuid
from urllib.parse import urlparse


def validate_uuid(value: str, *, kind: str = "id") -> str:
    """Require RFC4122 UUID format for IDs."""
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError):
        sys.exit(f"Error: {kind} must be a valid UUID.")


def validate_job_id(job_id: str) -> str:
    return validate_uuid(job_id, kind="job_id")


def validate_workflow_id(workflow_id: str) -> str:
    return validate_uuid(workflow_id, kind="workflow_id")


def validate_library_item_id(item_id: str) -> str:
    return validate_uuid(item_id, kind="library_item_id")


def validate_base_url(base_url: str) -> str:
    """Basic safety checks for API base URL."""
    parsed = urlparse(base_url)
    if parsed.scheme not in ("https", "http"):
        sys.exit("Error: base URL must use http or https.")
    if not parsed.netloc:
        sys.exit("Error: base URL must include a host.")
    if parsed.username or parsed.password:
        sys.exit("Error: base URL must not include credentials.")
    if parsed.query or parsed.fragment:
        sys.exit("Error: base URL must not include query or fragment.")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def validate_results_payload(data: object) -> dict:
    """Ensure results payload is an object before field access."""
    if not isinstance(data, dict):
        sys.exit("Error: API returned unexpected response type.")
    return data


def validate_artifact_url(url: str) -> str:
    """
    Validate artifact URL before download.
    Allow only FastFold-hosted HTTPS URLs (CloudFront / S3 / *.fastfold.ai).
    """
    if not isinstance(url, str) or not url:
        sys.exit("Error: Missing artifact URL.")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        sys.exit("Error: Artifact URL must use https.")
    host = (parsed.hostname or "").lower()
    allowed = (
        host == "artifacts.fastfold.ai"
        or host.endswith(".fastfold.ai")
        or host.endswith(".amazonaws.com")
        or host.endswith(".cloudfront.net")
    )
    if not allowed:
        sys.exit("Error: Artifact URL host is not allowed.")
    if parsed.username or parsed.password:
        sys.exit("Error: Artifact URL must not include credentials.")
    return url

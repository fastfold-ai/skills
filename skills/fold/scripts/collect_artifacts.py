#!/usr/bin/env python3
"""
Collect and optionally download all fold artifact links in a consistent format.

Usage:
    collect_artifacts.py JOB_ID [--base-url URL] [--json]
    collect_artifacts.py JOB_ID --download-dir /workspace/fastfold-artifacts/fold/<job_id>

Behavior:
1) Fetches GET /v1/jobs/{jobId}/results using FASTFOLD_API_KEY when available.
2) Extracts URLs from top-level and per-sequence prediction payloads for all models.
3) Recursively scans payload JSON for additional URL fields.
4) Captures embedded non-URL affinity payloads (e.g., affinity_result_raw_json).
4) Validates links against FastFold HTTPS hosts for safe download.
5) Optionally downloads all safe links to --download-dir.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse

from load_env import resolve_fastfold_api_key
from security_utils import (
    validate_base_url,
    validate_fastfold_artifact_url,
    validate_job_id,
    validate_results_payload,
)


KNOWN_FIELD_LABELS = {
    "cif_url": "Primary CIF",
    "pdb_url": "Primary PDB",
    "msa_coverage_plot_url": "MSA Coverage Plot",
    "pae_plot_url": "PAE Plot",
    "plddt_plot_url": "pLDDT Plot",
    "metrics_json_url": "Fold Metrics JSON",
    "config_json_url": "Fold Config JSON",
    "citations_bibtex_url": "Citations BibTeX",
    "plots_url": "Plots Bundle",
}


def get_results(base_url: str, api_key: str | None, job_id: str) -> dict:
    url = f"{base_url.rstrip('/')}/v1/jobs/{job_id}/results"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            response_text = resp.read().decode("utf-8", errors="replace")
            status = resp.getcode()
    except urllib.error.HTTPError as error:
        status = error.code
        response_text = error.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as error:
        sys.exit(f"Error: Network error while fetching results: {error.reason}")

    if status == 401:
        if api_key:
            sys.exit("Error: Unauthorized. Check FASTFOLD_API_KEY.")
        sys.exit("Error: Unauthorized. This job is likely private; set FASTFOLD_API_KEY.")
    if status == 404:
        sys.exit("Error: Job not found.")
    if status >= 400:
        sys.exit(f"Error: {status} - {response_text}")
    try:
        return validate_results_payload(json.loads(response_text))
    except json.JSONDecodeError:
        sys.exit(f"Error: API returned invalid JSON (status {status}).")


def _looks_like_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in ("https", "http") and bool(parsed.netloc)


def _iter_url_candidates(node: object, path: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else str(key)
            if isinstance(value, str):
                if value.strip() and (key == "url" or key.endswith("_url") or _looks_like_url(value.strip())):
                    found.append((child, value.strip()))
            elif isinstance(value, (dict, list)):
                found.extend(_iter_url_candidates(value, child))
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            child = f"{path}[{idx}]"
            if isinstance(item, str):
                if item.strip() and _looks_like_url(item.strip()):
                    found.append((child, item.strip()))
            elif isinstance(item, (dict, list)):
                found.extend(_iter_url_candidates(item, child))
    return found


def _field_name_from_path(source_path: str) -> str:
    match = re.search(r"([A-Za-z0-9_]+)(?:\[\d+\])?$", source_path)
    return match.group(1) if match else "artifact"


def _label_for_link(source_path: str, url: str) -> str:
    field = _field_name_from_path(source_path)
    if field in KNOWN_FIELD_LABELS:
        if "sequences[" in source_path:
            seq_match = re.search(r"sequences\[(\d+)\]", source_path)
            if seq_match:
                seq_num = int(seq_match.group(1)) + 1
                return f"Sequence {seq_num} {KNOWN_FIELD_LABELS[field]}"
        return KNOWN_FIELD_LABELS[field]
    if "affinity_result_raw_json" in source_path:
        return "Affinity Result Artifact"
    filename = _filename_from_url(url)
    if filename:
        return filename
    return field.replace("_", " ").title()


def _filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = os.path.basename(parsed.path or "")
    if not name:
        return ""
    name = unquote(name).strip()
    if not name:
        return ""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def _suggest_file_name(source_path: str, url: str, fallback_index: int) -> str:
    from_url = _filename_from_url(url)
    if from_url:
        return from_url
    field = _field_name_from_path(source_path)
    ext = os.path.splitext(urlparse(url).path or "")[1]
    ext = ext if ext else ".bin"
    safe_field = re.sub(r"[^A-Za-z0-9._-]+", "_", field) or "artifact"
    return f"{fallback_index:03d}_{safe_field}{ext}"


def collect_artifact_links(results_payload: dict) -> list[dict]:
    by_url: dict[str, dict] = {}
    ordered_candidates: list[tuple[str, str]] = []

    top_pred = results_payload.get("predictionPayload")
    if isinstance(top_pred, dict):
        ordered_candidates.extend(_iter_url_candidates(top_pred, "predictionPayload"))

    sequences = results_payload.get("sequences")
    if isinstance(sequences, list):
        for idx, seq in enumerate(sequences):
            pp = (seq or {}).get("predictionPayload") if isinstance(seq, dict) else None
            if isinstance(pp, dict):
                ordered_candidates.extend(_iter_url_candidates(pp, f"sequences[{idx}].predictionPayload"))

    # Extra coverage for model-specific fields not captured above.
    ordered_candidates.extend(_iter_url_candidates(results_payload, "results"))

    for source_path, url in ordered_candidates:
        if not isinstance(url, str) or not url:
            continue
        entry = by_url.get(url)
        if entry is None:
            entry = {
                "label": _label_for_link(source_path, url),
                "url": url,
                "source_paths": [source_path],
            }
            by_url[url] = entry
        elif source_path not in entry["source_paths"]:
            entry["source_paths"].append(source_path)

    artifact_links: list[dict] = []
    for idx, entry in enumerate(by_url.values(), start=1):
        url = entry["url"]
        safe = True
        unsafe_reason = ""
        try:
            validate_fastfold_artifact_url(url)
        except SystemExit as error:
            safe = False
            unsafe_reason = str(error)
        artifact_links.append(
            {
                "label": entry["label"],
                "url": url,
                "source_paths": entry["source_paths"],
                "safe_to_download": safe,
                "unsafe_reason": unsafe_reason,
                "suggested_file_name": _suggest_file_name(entry["source_paths"][0], url, idx),
            }
        )
    return artifact_links


def collect_embedded_artifacts(results_payload: dict) -> list[dict]:
    embedded: list[dict] = []

    top_pred = results_payload.get("predictionPayload")
    if isinstance(top_pred, dict):
        affinity = top_pred.get("affinity_result_raw_json")
        if isinstance(affinity, dict) and affinity:
            embedded.append(
                {
                    "label": "Affinity Results JSON",
                    "source_path": "predictionPayload.affinity_result_raw_json",
                    "suggested_file_name": "affinity_result_raw.json",
                    "content": affinity,
                }
            )

    sequences = results_payload.get("sequences")
    if isinstance(sequences, list):
        for idx, seq in enumerate(sequences, start=1):
            if not isinstance(seq, dict):
                continue
            pp = seq.get("predictionPayload")
            if not isinstance(pp, dict):
                continue
            affinity = pp.get("affinity_result_raw_json")
            if isinstance(affinity, dict) and affinity:
                embedded.append(
                    {
                        "label": f"Sequence {idx} Affinity Results JSON",
                        "source_path": f"sequences[{idx-1}].predictionPayload.affinity_result_raw_json",
                        "suggested_file_name": f"sequence_{idx}_affinity_result_raw.json",
                        "content": affinity,
                    }
                )
    return embedded


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _download_file(url: str, out_path: Path, max_bytes: int) -> None:
    req = urllib.request.Request(url=url, method="GET")
    opener = urllib.request.build_opener(_NoRedirectHandler())
    try:
        with opener.open(req, timeout=120) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and ("html" in content_type or "javascript" in content_type):
                raise RuntimeError(f"unexpected artifact content-type: {content_type}")
            content_len = response.headers.get("Content-Length")
            if content_len:
                try:
                    if int(content_len) > max_bytes:
                        raise RuntimeError(f"artifact exceeds size limit ({max_bytes} bytes)")
                except ValueError:
                    pass
            written = 0
            with out_path.open("wb") as handle:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > max_bytes:
                        raise RuntimeError(f"artifact exceeds size limit ({max_bytes} bytes)")
                    handle.write(chunk)
    except urllib.error.HTTPError as error:
        if 300 <= error.code < 400:
            raise RuntimeError("redirects are not allowed for artifact downloads") from error
        raise RuntimeError(f"download failed (HTTP {error.code})") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"network error while downloading: {error.reason}") from error


def download_artifacts(artifact_links: list[dict], download_dir: Path, max_bytes: int) -> dict:
    download_dir.mkdir(parents=True, exist_ok=True)
    used_names: dict[str, int] = {}
    downloaded: list[dict] = []
    failed: list[dict] = []

    for item in artifact_links:
        if not item.get("safe_to_download"):
            continue
        base_name = str(item.get("suggested_file_name") or "artifact.bin")
        stem, ext = os.path.splitext(base_name)
        count = used_names.get(base_name, 0)
        used_names[base_name] = count + 1
        file_name = base_name if count == 0 else f"{stem}_{count}{ext}"
        out_path = download_dir / file_name
        try:
            _download_file(str(item["url"]), out_path, max_bytes=max_bytes)
            downloaded.append(
                {
                    "label": item["label"],
                    "url": item["url"],
                    "path": str(out_path),
                }
            )
        except Exception as error:
            failed.append(
                {
                    "label": item["label"],
                    "url": item["url"],
                    "error": str(error),
                }
            )

    return {"downloaded": downloaded, "failed": failed}


def write_embedded_artifacts(embedded_artifacts: list[dict], download_dir: Path) -> list[dict]:
    download_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict] = []
    used_names: dict[str, int] = {}
    for item in embedded_artifacts:
        base_name = str(item.get("suggested_file_name") or "embedded_artifact.json")
        stem, ext = os.path.splitext(base_name)
        count = used_names.get(base_name, 0)
        used_names[base_name] = count + 1
        file_name = base_name if count == 0 else f"{stem}_{count}{ext}"
        out_path = download_dir / file_name
        out_path.write_text(json.dumps(item.get("content", {}), indent=2), encoding="utf-8")
        written.append(
            {
                "label": item.get("label"),
                "path": str(out_path),
                "source_path": item.get("source_path"),
            }
        )
    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect and optionally download all safe fold artifact URLs.",
    )
    parser.add_argument("job_id", help="FastFold job ID (UUID)")
    parser.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON payload")
    parser.add_argument("--download-dir", default=None, help="Optional output directory for artifact downloads")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=200_000_000,
        help="Maximum bytes per downloaded artifact (default 200000000)",
    )
    args = parser.parse_args()

    api_key = resolve_fastfold_api_key()
    if args.max_bytes <= 0:
        sys.exit("Error: --max-bytes must be > 0.")

    job_id = validate_job_id(args.job_id)
    base_url = validate_base_url(args.base_url)
    results = get_results(base_url, api_key, job_id)

    job_info = results.get("job", {}) if isinstance(results.get("job"), dict) else {}
    artifact_links = collect_artifact_links(results)
    embedded_artifacts = collect_embedded_artifacts(results)
    safe_links = [item for item in artifact_links if item.get("safe_to_download")]
    unsafe_links = [item for item in artifact_links if not item.get("safe_to_download")]

    payload: dict = {
        "job_id": job_id,
        "status": job_info.get("status"),
        "is_complex": bool(job_info.get("isComplex")),
        "artifact_count": len(artifact_links),
        "safe_artifact_count": len(safe_links),
        "unsafe_artifact_count": len(unsafe_links),
        "artifacts": artifact_links,
        "embedded_artifact_count": len(embedded_artifacts),
        "embedded_artifacts": [
            {
                "label": item["label"],
                "source_path": item["source_path"],
                "suggested_file_name": item["suggested_file_name"],
                "keys": sorted(item.get("content", {}).keys()),
            }
            for item in embedded_artifacts
        ],
    }

    if args.download_dir:
        download_summary = download_artifacts(
            artifact_links,
            download_dir=Path(args.download_dir).expanduser(),
            max_bytes=args.max_bytes,
        )
        embedded_written = write_embedded_artifacts(
            embedded_artifacts,
            download_dir=Path(args.download_dir).expanduser(),
        )
        payload["downloads"] = download_summary
        payload["embedded_downloads"] = embedded_written

    if args.json:
        print(json.dumps(payload, indent=2))
        return

    print(f"job_id: {payload['job_id']}")
    print(f"status: {payload['status']}")
    print(f"artifacts: {payload['artifact_count']}")
    print(f"safe_artifacts: {payload['safe_artifact_count']}")
    if payload["embedded_artifact_count"]:
        print(f"embedded_artifacts: {payload['embedded_artifact_count']}")
    if unsafe_links:
        print(f"unsafe_artifacts: {payload['unsafe_artifact_count']}")

    for item in artifact_links:
        marker = "SAFE" if item.get("safe_to_download") else "UNSAFE"
        print(f"- {marker} {item['label']}: {item['url']}")
        if not item.get("safe_to_download"):
            print(f"  reason: {item.get('unsafe_reason')}")

    if args.download_dir and isinstance(payload.get("downloads"), dict):
        downloaded = payload["downloads"].get("downloaded", [])
        failed = payload["downloads"].get("failed", [])
        print(f"downloaded: {len(downloaded)}")
        for item in downloaded:
            print(f"  - {item['label']}: {item['path']}")
        if failed:
            print(f"download_failed: {len(failed)}")
            for item in failed:
                print(f"  - {item['label']}: {item['error']}")
        embedded_written = payload.get("embedded_downloads", [])
        if isinstance(embedded_written, list) and embedded_written:
            print(f"embedded_written: {len(embedded_written)}")
            for item in embedded_written:
                print(f"  - {item['label']}: {item['path']}")


if __name__ == "__main__":
    main()

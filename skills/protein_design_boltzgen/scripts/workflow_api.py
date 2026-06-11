#!/usr/bin/env python3
"""
BoltzGen workflow API helper for FastFold Composer-equivalent runs.

Flow:
1) example-files -> resolve bundled local preset files
2) new      -> create draft workflow
3) upload   -> upload CIF/YAML files to workflow workspace
4) build-spec -> generate valid workflow.yml from official template + uploads
5) upsert   -> save graph YAML in one transaction
6) draft-review -> show draft link + inputs + params + YAML previews for user validation
7) execute  -> launch workflow
8) wait     -> poll until terminal
9) logs     -> fetch live workflow logs and explain key markers
10) results -> summarize candidates, metrics, and structure links
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from _api import (
    TERMINAL_TASK_STATUSES,
    TERMINAL_WORKFLOW_STATUSES,
    composer_url,
    create_library_item,
    get_library_stored_file_name,
    request_json,
    request_text,
    request_text_response,
    resolve_fastfold_folder_id,
    resolve_urls,
    upload_file,
)
from load_env import resolve_fastfold_api_key


DEFAULT_STATE_FILE = Path("/tmp/protein_design_boltzgen_state.json")
ACTIVE_WORKFLOW_STATUSES = {"RUNNING", "INITIALIZED", "PENDING", "QUEUED"}

PRESET_EXAMPLE_FILES: dict[str, list[str]] = {
    "vanilla_target_binding_site": [
        "vanilla_target_binding_site/beetletert.yaml",
        "vanilla_target_binding_site/5cqg.cif",
    ],
    "vanilla_protein": [
        "vanilla_protein/1g13prot.yaml",
        "vanilla_protein/1g13.cif",
    ],
    "binding_disordered_peptides": [
        "binding_disordered_peptides/tpp4.yaml",
    ],
    "protein_binding_small_molecule": [
        "protein_binding_small_molecule/chorismite.yaml",
    ],
    "small_molecule_from_file_and_smiles": [
        "small_molecule_from_file_and_smiles/4g37.yaml",
        "small_molecule_from_file_and_smiles/4g37.pdb",
    ],
    "cyclic_against_hiv_antibody_site": [
        "cyclic_against_hiv_antibody_site/9d3d.yaml",
        "cyclic_against_hiv_antibody_site/9d3d.cif",
    ],
    "nanobody_against_penguinpox_multi_spec": [
        "nanobody_against_penguinpox_multi_spec/penguinpox.yaml",
        "nanobody_against_penguinpox_multi_spec/9bkq-assembly2.cif",
        "nanobody_scaffolds/7eow.yaml",
        "nanobody_scaffolds/7eow.cif",
        "nanobody_scaffolds/7xl0.yaml",
        "nanobody_scaffolds/7xl0.cif",
        "nanobody_scaffolds/gontivimab.yaml",
        "nanobody_scaffolds/gontivimab.cif",
        "nanobody_scaffolds/isecarosmab.yaml",
        "nanobody_scaffolds/isecarosmab.cif",
        "nanobody_scaffolds/sonelokimab.yaml",
        "nanobody_scaffolds/sonelokimab.cif",
    ],
}

PRESET_ALIASES: dict[str, str] = {
    "5cqg": "vanilla_target_binding_site",
    "vanilla_peptide": "vanilla_target_binding_site",
    "simple_peptide_binder": "vanilla_target_binding_site",
}

PRESET_TEMPLATE_FILES: dict[str, str] = {
    "vanilla_target_binding_site": "vanilla_target_binding_site.workflow.yml",
    "vanilla_protein": "vanilla_protein.workflow.yml",
    "binding_disordered_peptides": "binding_disordered_peptides.workflow.yml",
    "protein_binding_small_molecule": "protein_binding_small_molecule.workflow.yml",
    "small_molecule_from_file_and_smiles": "small_molecule_from_file_and_smiles.workflow.yml",
    "cyclic_against_hiv_antibody_site": "cyclic_against_hiv_antibody_site.workflow.yml",
    "nanobody_against_penguinpox_multi_spec": "nanobody_against_penguinpox.workflow.yml",
}

PRESET_TOKEN_FILE_MAP: dict[str, dict[str, str]] = {
    "vanilla_target_binding_site": {
        "BEETLETERT": "beetletert.yaml",
        "5CQG_CIF": "5cqg.cif",
    },
    "vanilla_protein": {
        "1G13PROT": "1g13prot.yaml",
        "1G13_CIF": "1g13.cif",
    },
    "binding_disordered_peptides": {
        "TPP4": "tpp4.yaml",
    },
    "protein_binding_small_molecule": {
        "CHORISMITE": "chorismite.yaml",
    },
    "small_molecule_from_file_and_smiles": {
        "4G37": "4g37.yaml",
        "4G37_PDB": "4g37.pdb",
    },
    "cyclic_against_hiv_antibody_site": {
        "9D3D": "9d3d.yaml",
        "9D3D_CIF": "9d3d.cif",
    },
    "nanobody_against_penguinpox_multi_spec": {
        "7EOW": "7eow.yaml",
        "7XL0": "7xl0.yaml",
        "GONTIVIMAB": "gontivimab.yaml",
        "ISECAROSMAB": "isecarosmab.yaml",
        "SONELOKIMAB": "sonelokimab.yaml",
        "PENGUINPOX_MAIN": "penguinpox.yaml",
        "7EOW_CIF": "7eow.cif",
        "7XL0_CIF": "7xl0.cif",
        "GONTIVIMAB_CIF": "gontivimab.cif",
        "ISECAROSMAB_CIF": "isecarosmab.cif",
        "SONELOKIMAB_CIF": "sonelokimab.cif",
        "9BKQ_ASSEMBLY2_CIF": "9bkq-assembly2.cif",
    },
}


def _examples_root() -> Path:
    return Path(__file__).resolve().parents[1] / "references" / "examples"


def _workflow_specs_root() -> Path:
    return Path(__file__).resolve().parents[1] / "references" / "workflow_specs"


def _file_kind_from_name(path_value: str) -> str:
    lower = path_value.lower()
    if lower.endswith((".yaml", ".yml")):
        return "yml"
    if lower.endswith((".cif", ".mmcif", ".pdb", ".ent")):
        return "protein"
    return "other"


def _resolve_preset_name(raw: str | None) -> str:
    value = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not value:
        return ""
    if value in PRESET_EXAMPLE_FILES:
        return value
    return PRESET_ALIASES.get(value, "")


def cmd_example_files(args: argparse.Namespace) -> None:
    root = _examples_root()
    presets = sorted(PRESET_EXAMPLE_FILES.keys())

    if args.list or not args.preset:
        payload = {
            "examples_root": str(root),
            "presets": presets,
            "aliases": PRESET_ALIASES,
        }
        if args.json:
            print(json.dumps(payload, indent=2))
            return
        print(f"examples_root={root}")
        print("presets:")
        for preset in presets:
            print(f"- {preset}")
        if PRESET_ALIASES:
            print("aliases:")
            for alias, mapped in sorted(PRESET_ALIASES.items()):
                print(f"- {alias} -> {mapped}")
        return

    preset = _resolve_preset_name(args.preset)
    if not preset:
        known = ", ".join(presets)
        sys.exit(f"Error: Unknown preset '{args.preset}'. Known presets: {known}")

    files: list[dict[str, Any]] = []
    missing: list[str] = []
    for rel in PRESET_EXAMPLE_FILES[preset]:
        abs_path = (root / rel).resolve()
        exists = abs_path.exists() and abs_path.is_file()
        if not exists:
            missing.append(rel)
        files.append(
            {
                "relative_path": rel,
                "absolute_path": str(abs_path),
                "exists": exists,
                "kind": _file_kind_from_name(rel),
            }
        )

    payload = {
        "preset": preset,
        "requested_preset": args.preset,
        "examples_root": str(root),
        "files": files,
        "missing_files": missing,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"preset={preset}")
        print(f"examples_root={root}")
        print("files:")
        for item in files:
            print(f"- {item['relative_path']} ({item['kind']}): {item['absolute_path']}")

    if missing:
        missing_txt = ", ".join(missing)
        sys.exit(f"Error: Missing bundled example file(s): {missing_txt}")


def _lookup_uploaded_meta(uploads: dict[str, Any], logical_name: str) -> dict[str, Any] | None:
    candidate = uploads.get(logical_name)
    if isinstance(candidate, dict):
        return candidate

    for key, meta in uploads.items():
        if not isinstance(meta, dict):
            continue
        key_name = str(key or "").strip()
        file_name = str(meta.get("fileName") or "").strip()
        if key_name == logical_name or file_name == logical_name:
            return meta
    return None


def _is_yaml_name(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith(".yml") or lowered.endswith(".yaml")


def _build_yaml_preview(text: str, *, max_lines: int = 120, max_chars: int = 6000) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""

    lines = normalized.splitlines()
    trimmed_lines = lines[:max_lines]
    truncated = len(lines) > max_lines

    preview = "\n".join(trimmed_lines)
    if len(preview) > max_chars:
        preview = preview[:max_chars]
        truncated = True
    preview = preview.rstrip()
    if truncated:
        preview += "\n# ... preview truncated ..."
    return preview


def _load_yaml_preview_from_upload_files(
    files: Any,
    uploads: dict[str, Any],
) -> tuple[str, str] | tuple[None, None]:
    if not isinstance(files, list):
        return (None, None)

    for file_entry in files:
        if not isinstance(file_entry, dict):
            continue
        logical_name = str(file_entry.get("fileName") or "").strip()
        if not logical_name or not _is_yaml_name(logical_name):
            continue
        meta = _lookup_uploaded_meta(uploads, logical_name)
        if not isinstance(meta, dict):
            continue
        local_path = str(meta.get("localPath") or "").strip()
        if not local_path:
            continue
        path = Path(local_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            continue
        try:
            preview = _build_yaml_preview(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if preview:
            return (logical_name, preview)
    return (None, None)


def cmd_build_spec(args: argparse.Namespace) -> None:
    state = load_state(args.state_file)
    preset = _resolve_preset_name(args.preset)
    if not preset:
        known = ", ".join(sorted(PRESET_EXAMPLE_FILES.keys()))
        sys.exit(f"Error: Unknown preset '{args.preset}'. Known presets: {known}")

    template_name = PRESET_TEMPLATE_FILES.get(preset, "")
    if not template_name:
        sys.exit(f"Error: No workflow template configured for preset '{preset}'.")

    template_path = (_workflow_specs_root() / template_name).resolve()
    if not template_path.exists() or not template_path.is_file():
        sys.exit(f"Error: Missing workflow template file: {template_path}")

    template_text = template_path.read_text(encoding="utf-8")
    uploads = state.get("uploads")
    if not isinstance(uploads, dict):
        uploads = {}

    token_map = PRESET_TOKEN_FILE_MAP.get(preset, {})
    missing_uploads: set[str] = set()
    unresolved_tokens: set[str] = set()

    placeholder_pattern = re.compile(r"__([A-Z0-9_]+)__")

    def _replace(match: re.Match[str]) -> str:
        token = match.group(1)
        prefix_field_pairs = (
            ("SPEC_ITEM_ID_", "libraryItemId"),
            ("SPEC_FILE_NAME_", "fileName"),
            ("TARGET_ITEM_ID_", "libraryItemId"),
            ("TARGET_FILE_NAME_", "fileName"),
        )
        for prefix, field in prefix_field_pairs:
            if not token.startswith(prefix):
                continue
            suffix = token[len(prefix):]
            logical_name = token_map.get(suffix)
            if not logical_name:
                unresolved_tokens.add(token)
                return match.group(0)
            meta = _lookup_uploaded_meta(uploads, logical_name)
            if not meta:
                missing_uploads.add(logical_name)
                return match.group(0)
            value = str(meta.get(field) or "").strip()
            if not value:
                if field == "fileName":
                    value = logical_name
                else:
                    missing_uploads.add(logical_name)
                    return match.group(0)
            return value
        return match.group(0)

    rendered = placeholder_pattern.sub(_replace, template_text)
    remaining_tokens = sorted(set(placeholder_pattern.findall(rendered)))
    unresolved_tokens.update(remaining_tokens)

    payload = {
        "preset": preset,
        "requested_preset": args.preset,
        "template": str(template_path),
        "out_path": str(Path(args.out).expanduser().resolve()),
        "required_uploads": sorted(set(token_map.values())),
        "missing_uploads": sorted(missing_uploads),
        "unresolved_placeholders": sorted(unresolved_tokens),
    }

    if payload["missing_uploads"] or payload["unresolved_placeholders"]:
        if args.json:
            print(json.dumps(payload, indent=2))
        missing_text = ", ".join(payload["missing_uploads"]) or "none"
        unresolved_text = ", ".join(payload["unresolved_placeholders"]) or "none"
        sys.exit(
            "Error: Could not render workflow spec from template.\n"
            f"Missing uploads: {missing_text}\n"
            f"Unresolved placeholders: {unresolved_text}\n"
            "Tip: upload bundled example files first using `example-files --preset <id> --json`."
        )

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")

    state["last_built_spec"] = {
        "preset": preset,
        "template": str(template_path),
        "out_path": str(out_path),
    }
    save_state(args.state_file, state)

    payload["missing_uploads"] = []
    payload["unresolved_placeholders"] = []
    if args.json:
        print(json.dumps(payload, indent=2))
        return
    print(f"preset={preset}")
    print(f"template={template_path}")
    print(f"spec={out_path}")


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        sys.exit(f"Error: Invalid JSON in state file: {path}")
    if not isinstance(payload, dict):
        sys.exit(f"Error: State file must contain a JSON object: {path}")
    return payload


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def require_api_key(cli_key: str | None) -> str:
    key = (cli_key or "").strip()
    if key:
        return key
    resolved = resolve_fastfold_api_key()
    if resolved:
        return resolved
    sys.exit(
        "Error: FASTFOLD_API_KEY is not configured. Set it in environment/.env "
        "or provide --api-key."
    )


def require_workflow_id(args: argparse.Namespace, state: dict[str, Any]) -> str:
    workflow_id = (args.workflow_id or state.get("workflow_id") or "").strip()
    if not workflow_id:
        sys.exit("Error: Missing workflow id. Run `new` first or pass --workflow-id.")
    return workflow_id


def build_workflow_name(args: argparse.Namespace) -> str:
    explicit = str(args.name or "").strip()
    if explicit:
        return explicit

    preset = str(args.preset or "").strip()
    goal = str(args.goal or "").strip()

    label = preset.replace("_", " ").strip() if preset else goal
    if not label:
        label = "BoltzGen protein design"
    return f"API - {label}"


def cmd_new(args: argparse.Namespace) -> None:
    api_key = require_api_key(args.api_key)
    api_base, ui_base = resolve_urls(args.base_url, args.ui_base_url)
    state = load_state(args.state_file)
    workflow_name = build_workflow_name(args)

    payload = {
        "workflow_name": "boltzgen_v1",
        "name": workflow_name,
        "create_mode": "api",
    }
    response = request_json(
        api_base,
        "POST",
        "/v1/workflows/graph/add",
        api_key=api_key,
        body=payload,
    )
    workflow_id = str(response.get("workflow_id") or "").strip()
    if not workflow_id:
        sys.exit("Error: workflow create response missing workflow_id.")
    workspace_id = str(response.get("library_item_workspace_id") or "").strip() or None
    fastfold_id = resolve_fastfold_folder_id(
        api_base,
        api_key=api_key,
        workspace_id=workspace_id,
    )
    state.update(
        {
            "api_base_url": api_base,
            "ui_base_url": ui_base,
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "naming": {
                "preset": args.preset,
                "goal": args.goal,
            },
            "workspace_id": workspace_id,
            "fastfold_id": fastfold_id,
        }
    )
    state.setdefault("uploads", {})
    save_state(args.state_file, state)

    print(json.dumps(
        {
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "workspace_id": workspace_id,
            "fastfold_id": fastfold_id,
            "composer_url": None,
            "note": "Composer link is emitted after a non-empty graph upsert.",
            "state_file": str(args.state_file),
        },
        indent=2,
    ))


def cmd_upload(args: argparse.Namespace) -> None:
    api_key = require_api_key(args.api_key)
    state = load_state(args.state_file)
    api_base, _ = resolve_urls(args.base_url or state.get("api_base_url"), args.ui_base_url or state.get("ui_base_url"))
    workflow_id = require_workflow_id(args, state)

    workflow_resp = request_json(
        api_base,
        "GET",
        f"/v1/workflows/{workflow_id}",
        api_key=api_key,
        accept_codes=(200,),
    )
    workspace_id = str(workflow_resp.get("library_item_workspace_id") or "").strip() or state.get("workspace_id")
    fastfold_id = args.parent_id or state.get("fastfold_id")
    if not fastfold_id:
        fastfold_id = resolve_fastfold_folder_id(
            api_base,
            api_key=api_key,
            workspace_id=workspace_id,
        )
    if not fastfold_id:
        sys.exit("Error: Could not resolve workflow workspace/.fastfold folder for upload.")

    local_path = Path(args.file).expanduser().resolve()
    if not local_path.exists() or not local_path.is_file():
        sys.exit(f"Error: File not found: {local_path}")
    logical_name = (args.logical_name or local_path.name).strip()
    if not logical_name:
        sys.exit("Error: logical file name is empty.")

    item_id = create_library_item(
        api_base,
        api_key=api_key,
        name=logical_name,
        file_type=args.file_type,
        parent_id=fastfold_id,
    )
    upload_file(
        api_base,
        f"/v1/library/{item_id}/upload-files",
        api_key=api_key,
        file_path=local_path,
        logical_name=logical_name,
    )
    stored_name = get_library_stored_file_name(
        api_base,
        api_key=api_key,
        item_id=item_id,
    )

    uploads = state.setdefault("uploads", {})
    if not isinstance(uploads, dict):
        uploads = {}
    uploads[logical_name] = {
        "libraryItemId": item_id,
        "fileName": logical_name,  # use logical name in workflow input payload
        "storedFileName": stored_name,
        "fileType": args.file_type,
        "localPath": str(local_path),
    }

    state["uploads"] = uploads
    state["workflow_id"] = workflow_id
    state["workspace_id"] = workspace_id
    state["fastfold_id"] = fastfold_id
    state["api_base_url"] = api_base
    save_state(args.state_file, state)

    print(json.dumps(
        {
            "workflow_id": workflow_id,
            "logical_name": logical_name,
            "libraryItemId": item_id,
            "fileName_for_inputPayload": logical_name,
            "stored_file_name": stored_name,
            "state_file": str(args.state_file),
        },
        indent=2,
    ))


def cmd_upsert(args: argparse.Namespace) -> None:
    api_key = require_api_key(args.api_key)
    state = load_state(args.state_file)
    api_base, ui_base = resolve_urls(
        args.base_url or state.get("api_base_url"),
        args.ui_base_url or state.get("ui_base_url"),
    )
    workflow_id = require_workflow_id(args, state)

    spec_path = Path(args.spec).expanduser().resolve()
    if not spec_path.exists() or not spec_path.is_file():
        sys.exit(f"Error: workflow spec file not found: {spec_path}")
    spec_text = spec_path.read_text(encoding="utf-8")

    response_text = request_text(
        api_base,
        "POST",
        f"/v1/workflows/{workflow_id}/workflow.yml",
        api_key=api_key,
        content_type="text/yaml",
        text_body=spec_text,
    )

    try:
        response_json = json.loads(response_text) if response_text else {}
    except json.JSONDecodeError:
        response_json = {"raw": response_text}

    state["last_upsert_spec_path"] = str(spec_path)
    state["last_upsert_response"] = response_json
    state["workflow_id"] = workflow_id
    state["api_base_url"] = api_base
    state["ui_base_url"] = ui_base
    graph_nodes = _safe_graph_count(response_json, "nodes")
    if graph_nodes > 0:
        state["composer_url"] = composer_url(ui_base, workflow_id)
    else:
        state["composer_url"] = None
    save_state(args.state_file, state)

    print(json.dumps(
        {
            "workflow_id": workflow_id,
            "spec_path": str(spec_path),
            "upsert_ok": True,
            "graph_nodes": graph_nodes,
            "graph_edges": _safe_graph_count(response_json, "edges"),
            "composer_url": state.get("composer_url"),
        },
        indent=2,
    ))


def _safe_graph_count(payload: dict[str, Any], key: str) -> int:
    graph = payload.get("graph")
    if not isinstance(graph, dict):
        return 0
    value = graph.get(key)
    return len(value) if isinstance(value, list) else 0


def _build_draft_review_payload(state: dict[str, Any], workflow_id: str, ui_base: str) -> dict[str, Any]:
    graph = (state.get("last_upsert_response") or {}).get("graph") or {}
    nodes = graph.get("nodes") if isinstance(graph, dict) else []
    if not isinstance(nodes, list):
        nodes = []

    composer = str(state.get("composer_url") or "")
    if not composer:
        composer = composer_url(ui_base, workflow_id)

    uploads = state.get("uploads")
    upload_list: list[dict[str, Any]] = []
    uploads_dict: dict[str, Any] = uploads if isinstance(uploads, dict) else {}
    if uploads_dict:
        for logical_name, meta in uploads.items():
            if not isinstance(meta, dict):
                continue
            upload_list.append(
                {
                    "logical_name": logical_name,
                    "file_type": meta.get("fileType"),
                    "library_item_id": meta.get("libraryItemId"),
                    "stored_file_name": meta.get("storedFileName"),
                }
            )

    pipeline_params: list[dict[str, Any]] = []
    design_specs: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        data = node.get("data") if isinstance(node.get("data"), dict) else {}
        input_payload = node.get("inputPayload") if isinstance(node.get("inputPayload"), dict) else {}
        workflow_task_type_id = str(node.get("workflowTaskTypeId") or "")
        label = str(data.get("label") or "")
        subtype = str(data.get("subType") or "")
        node_id = str(node.get("id") or "")

        if workflow_task_type_id == "pipeline_run_boltzgen_v1" or subtype == "boltzgen":
            pipeline_params.append(
                {
                    "node_id": node_id,
                    "label": label,
                    "inputPayload": input_payload,
                }
            )
        if workflow_task_type_id == "input_design_spec_boltzgen_v1" or subtype == "design_specification_yml":
            input_yml = input_payload.get("inputYML")
            yaml_source = "inputPayload.inputYML"
            yaml_preview = ""
            if isinstance(input_yml, str) and input_yml.strip():
                yaml_preview = _build_yaml_preview(input_yml)
            else:
                source_name, file_preview = _load_yaml_preview_from_upload_files(
                    input_payload.get("files"),
                    uploads_dict,
                )
                if file_preview:
                    yaml_preview = file_preview
                    yaml_source = f"uploaded file ({source_name})"

            design_specs.append(
                {
                    "node_id": node_id,
                    "label": label,
                    "inputYML": input_yml,
                    "inputYMLLibraryItemId": input_payload.get("inputYMLLibraryItemId"),
                    "files": input_payload.get("files"),
                    "yaml_preview_source": yaml_source,
                    "yaml_preview": yaml_preview,
                }
            )

    workflow_spec_preview = ""
    spec_path_raw = str(state.get("last_upsert_spec_path") or "").strip()
    if spec_path_raw:
        spec_path = Path(spec_path_raw).expanduser().resolve()
        if spec_path.exists() and spec_path.is_file():
            try:
                workflow_spec_preview = _build_yaml_preview(spec_path.read_text(encoding="utf-8"))
            except OSError:
                workflow_spec_preview = ""

    return {
        "workflow_id": workflow_id,
        "workflow_name": state.get("workflow_name"),
        "composer_url": composer,
        "graph_nodes": len(nodes),
        "uploaded_inputs": upload_list,
        "workflow_spec_preview": workflow_spec_preview,
        "design_spec_nodes": design_specs,
        "pipeline_nodes": pipeline_params,
        "action_required": (
            "Review the draft in Composer, including YAML previews (workflow + design spec), "
            "validate inputs/params, and confirm before execute."
        ),
    }


def cmd_draft_review(args: argparse.Namespace) -> None:
    state = load_state(args.state_file)
    workflow_id = require_workflow_id(args, state)
    _, ui_base = resolve_urls(args.base_url or state.get("api_base_url"), args.ui_base_url or state.get("ui_base_url"))

    graph_nodes = _safe_graph_count(state.get("last_upsert_response") or {}, "nodes")
    if graph_nodes <= 0:
        sys.exit("Error: Draft review is available after a non-empty upsert. Run upsert first.")

    payload = _build_draft_review_payload(state, workflow_id, ui_base)
    state["last_draft_review"] = payload
    save_state(args.state_file, state)

    if args.json:
        print(json.dumps(payload, indent=2))
        return

    print(f"workflow_id={payload['workflow_id']}")
    print(f"workflow_name={payload.get('workflow_name')}")
    print(f"composer_url={payload['composer_url']}")
    print(f"graph_nodes={payload['graph_nodes']}")
    print("uploaded_inputs:")
    for entry in payload["uploaded_inputs"]:
        print(
            f"- {entry.get('logical_name')} "
            f"(type={entry.get('file_type')}, libraryItemId={entry.get('library_item_id')})"
        )
    print("pipeline_params:")
    for node in payload["pipeline_nodes"]:
        print(f"- node={node.get('label')} ({node.get('node_id')}): {json.dumps(node.get('inputPayload', {}))}")
    workflow_spec_preview = str(payload.get("workflow_spec_preview") or "").strip()
    if workflow_spec_preview:
        print("workflow_spec_preview_yaml:")
        print("```yaml")
        print(workflow_spec_preview)
        print("```")
    design_nodes = payload.get("design_spec_nodes")
    if isinstance(design_nodes, list):
        for node in design_nodes:
            if not isinstance(node, dict):
                continue
            yaml_preview = str(node.get("yaml_preview") or "").strip()
            if not yaml_preview:
                continue
            print(
                f"design_spec_preview_yaml:"
                f" node={node.get('label')} ({node.get('node_id')}) "
                f"source={node.get('yaml_preview_source')}"
            )
            print("```yaml")
            print(yaml_preview)
            print("```")
    print("action_required=Review draft in Composer and confirm before run.")


def cmd_execute(args: argparse.Namespace) -> None:
    api_key = require_api_key(args.api_key)
    state = load_state(args.state_file)
    api_base, _ = resolve_urls(args.base_url or state.get("api_base_url"), args.ui_base_url or state.get("ui_base_url"))
    workflow_id = require_workflow_id(args, state)

    response = request_json(
        api_base,
        "POST",
        "/v1/workflows/execute",
        api_key=api_key,
        body={"workflowId": workflow_id},
    )
    state["last_execute_response"] = response
    state["workflow_id"] = workflow_id
    state["api_base_url"] = api_base
    save_state(args.state_file, state)

    print(json.dumps(
        {
            "workflow_id": workflow_id,
            "status": response.get("status"),
            "name": response.get("name"),
        },
        indent=2,
    ))


def cmd_status(args: argparse.Namespace) -> None:
    api_key = require_api_key(args.api_key)
    state = load_state(args.state_file)
    api_base, _ = resolve_urls(args.base_url or state.get("api_base_url"), args.ui_base_url or state.get("ui_base_url"))
    workflow_id = require_workflow_id(args, state)

    status_payload = request_json(
        api_base,
        "GET",
        f"/v1/workflows/status/{workflow_id}",
        api_key=api_key,
        accept_codes=(200,),
    )
    if args.json:
        print(json.dumps(status_payload, indent=2))
        return

    workflow_status = str(status_payload.get("status") or "").upper()
    tasks = status_payload.get("tasks")
    print(f"workflow_id={workflow_id}")
    print(f"status={workflow_status}")
    if isinstance(tasks, list):
        for task in tasks:
            if not isinstance(task, dict):
                continue
            print(
                f"- {task.get('task_type')} | "
                f"status={str(task.get('status') or '').upper()} | "
                f"task_id={task.get('task_id')}"
            )


def _all_tasks_terminal(tasks: Any) -> bool:
    if not isinstance(tasks, list) or not tasks:
        return False
    for task in tasks:
        if not isinstance(task, dict):
            return False
        status = str(task.get("status") or "").upper()
        if status not in TERMINAL_TASK_STATUSES:
            return False
    return True


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_percent(value: Any) -> float | None:
    numeric = _to_float(value)
    if numeric is None:
        return None
    if numeric <= 1.0:
        numeric = numeric * 100.0
    return numeric


def _fmt_numeric(value: Any, digits: int = 5) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return "-"
    return f"{numeric:.{digits}f}"


def _fmt_percent(value: Any) -> str:
    numeric = _to_percent(value)
    if numeric is None:
        return "-"
    if abs(numeric - round(numeric)) < 1e-9:
        return f"{int(round(numeric))}%"
    return f"{numeric:.2f}%"


def _sort_rank_key(candidate: dict[str, Any]) -> tuple[float, float]:
    final_rank = _to_float(candidate.get("final_rank"))
    secondary_rank = _to_float(candidate.get("secondary_rank"))
    return (
        final_rank if final_rank is not None else float("inf"),
        secondary_rank if secondary_rank is not None else float("inf"),
    )


def _tail_lines(text: str, count: int) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if count <= 0 or len(lines) <= count:
        return normalized.strip("\n")
    return "\n".join(lines[-count:]).strip("\n")


def _extract_log_insights(log_text: str) -> list[str]:
    if not log_text.strip():
        return ["No log lines yet. This is common right after workflow start."]

    lines = [line for line in log_text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if line.strip()]
    if not lines:
        return ["No log lines yet. This is common right after workflow start."]

    def _matches(pattern: str) -> list[str]:
        rx = re.compile(pattern, re.IGNORECASE)
        return [line for line in lines if rx.search(line)]

    errors = _matches(r"\b(error|exception|traceback|failed|failure)\b")
    warnings = _matches(r"\b(warn|warning|deprecated|retry)\b")
    progress = _matches(r"\b(start|running|loading|design|sample|candidate|step|progress|complete|done)\b")

    insights: list[str] = []
    if errors:
        insights.append(f"Found {len(errors)} error/failure marker line(s). Check the newest one first.")
    else:
        insights.append("No explicit ERROR/Traceback markers found in this snapshot.")

    if warnings:
        insights.append(f"Found {len(warnings)} warning/retry marker line(s).")
    else:
        insights.append("No warning/retry markers detected.")

    if progress:
        insights.append(f"Found {len(progress)} progress-like line(s), suggesting active execution updates.")
    else:
        insights.append("No obvious progress markers detected yet.")

    if errors:
        insights.append("If errors repeat while status stays RUNNING, check whether retries eventually recover.")
    else:
        insights.append("If status is RUNNING and log size keeps growing, the workflow is likely still progressing.")
    return insights


def _fetch_workflow_status_summary(api_base: str, api_key: str, workflow_id: str) -> dict[str, Any]:
    payload = request_json(
        api_base,
        "GET",
        f"/v1/workflows/status/{workflow_id}",
        api_key=api_key,
        accept_codes=(200,),
    )
    tasks = payload.get("tasks")
    return {
        "workflow_status": str(payload.get("status") or "").upper(),
        "tasks": tasks if isinstance(tasks, list) else [],
    }


def cmd_logs(args: argparse.Namespace) -> None:
    api_key = require_api_key(args.api_key)
    state = load_state(args.state_file)
    api_base, _ = resolve_urls(args.base_url or state.get("api_base_url"), args.ui_base_url or state.get("ui_base_url"))
    workflow_id = require_workflow_id(args, state)

    deadline = time.time() + max(args.timeout_seconds, 1)
    last_snapshot = ""
    final_payload: dict[str, Any] | None = None

    while True:
        status_summary = _fetch_workflow_status_summary(api_base, api_key, workflow_id)
        workflow_status = status_summary["workflow_status"]

        log_http_status, log_text = request_text_response(
            api_base,
            "GET",
            f"/v1/workflows/logs/{workflow_id}",
            api_key=api_key,
            accept="text/plain",
            timeout=60.0,
        )

        normalized = log_text.replace("\r\n", "\n").replace("\r", "\n")
        if log_http_status == 200:
            tail_text = _tail_lines(normalized, args.tail_lines)
            lines_total = len(normalized.split("\n")) if normalized else 0
        elif log_http_status in (204, 404):
            tail_text = ""
            lines_total = 0
        else:
            tail_text = _tail_lines(normalized, args.tail_lines)
            lines_total = len(normalized.split("\n")) if normalized else 0

        insights = _extract_log_insights(tail_text if tail_text else normalized)
        payload = {
            "workflow_id": workflow_id,
            "workflow_status": workflow_status,
            "logs_http_status": log_http_status,
            "logs_available": log_http_status == 200 and bool(normalized.strip()),
            "log_bytes": len(normalized.encode("utf-8", errors="ignore")),
            "log_lines_total": lines_total,
            "tail_lines": args.tail_lines,
            "log_tail": tail_text,
            "insights": insights,
        }
        final_payload = payload

        snapshot_key = f"{workflow_status}|{log_http_status}|{payload['log_bytes']}"
        should_emit = (not args.watch) or (snapshot_key != last_snapshot)
        if should_emit:
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(f"workflow_id={workflow_id}")
                print(f"workflow_status={workflow_status}")
                print(f"logs_http_status={log_http_status}")
                print(f"log_lines_total={lines_total}")
                if tail_text:
                    print("log_tail:")
                    print("```text")
                    print(tail_text)
                    print("```")
                else:
                    print("log_tail=<empty>")
                print("log_insights:")
                for item in insights:
                    print(f"- {item}")
            last_snapshot = snapshot_key

        if not args.watch:
            break

        terminal = workflow_status in TERMINAL_WORKFLOW_STATUSES
        timed_out = time.time() >= deadline
        if terminal or timed_out:
            break
        time.sleep(max(args.poll_seconds, 1))

    if final_payload is not None:
        state["last_logs"] = final_payload
        state["workflow_id"] = workflow_id
        state["api_base_url"] = api_base
        save_state(args.state_file, state)

    if (
        args.watch
        and final_payload is not None
        and time.time() >= deadline
        and final_payload["workflow_status"] in ACTIVE_WORKFLOW_STATUSES
    ):
        sys.exit("Error: Timed out while watching logs.")


def cmd_wait(args: argparse.Namespace) -> None:
    api_key = require_api_key(args.api_key)
    state = load_state(args.state_file)
    api_base, _ = resolve_urls(args.base_url or state.get("api_base_url"), args.ui_base_url or state.get("ui_base_url"))
    workflow_id = require_workflow_id(args, state)

    deadline = time.time() + args.timeout_seconds
    last_state = ""
    final_payload: dict[str, Any] | None = None
    while True:
        status_payload = request_json(
            api_base,
            "GET",
            f"/v1/workflows/status/{workflow_id}",
            api_key=api_key,
            accept_codes=(200,),
        )
        workflow_status = str(status_payload.get("status") or "").upper()
        tasks = status_payload.get("tasks")
        summary = workflow_status + "|" + ",".join(
            str((t or {}).get("status") or "").upper()
            for t in (tasks if isinstance(tasks, list) else [])
            if isinstance(t, dict)
        )
        if summary != last_state:
            print(f"status={workflow_status}")
            if isinstance(tasks, list):
                for task in tasks:
                    if not isinstance(task, dict):
                        continue
                    print(
                        f"- {task.get('task_type')}={str(task.get('status') or '').upper()} "
                        f"(task_id={task.get('task_id')})"
                    )
            last_state = summary

        if workflow_status in TERMINAL_WORKFLOW_STATUSES and _all_tasks_terminal(tasks):
            final_payload = status_payload
            break
        if time.time() >= deadline:
            sys.exit(
                f"Error: Timeout after {args.timeout_seconds}s waiting for workflow "
                f"{workflow_id}. Last status={workflow_status}."
            )
        time.sleep(args.poll_seconds)

    state["final_status"] = final_payload
    state["workflow_id"] = workflow_id
    state["api_base_url"] = api_base
    save_state(args.state_file, state)
    print("terminal=true")


def cmd_results(args: argparse.Namespace) -> None:
    api_key = require_api_key(args.api_key)
    state = load_state(args.state_file)
    api_base, ui_base = resolve_urls(
        args.base_url or state.get("api_base_url"),
        args.ui_base_url or state.get("ui_base_url"),
    )
    workflow_id = require_workflow_id(args, state)

    results_payload = request_json(
        api_base,
        "GET",
        f"/v1/workflows/task-results/{workflow_id}",
        api_key=api_key,
        accept_codes=(200,),
    )
    tasks = results_payload.get("tasksResults")
    if not isinstance(tasks, list):
        tasks = []
    pipeline_tasks = [
        task
        for task in tasks
        if isinstance(task, dict) and str(task.get("task_type") or "") == "pipeline_run_boltzgen_v1"
    ]
    parsed_candidates: list[dict[str, Any]] = []
    output_refs: list[dict[str, str]] = []
    for pipeline in pipeline_tasks:
        parsed = pipeline.get("parsed_results")
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    parsed_candidates.append(item)
        out_items = pipeline.get("output_library_items")
        if isinstance(out_items, list):
            for entry in out_items:
                if not isinstance(entry, dict):
                    continue
                item_id = str(entry.get("libraryItemId") or "").strip()
                file_name = str(entry.get("fileName") or "").strip()
                if item_id and file_name:
                    output_refs.append({"libraryItemId": item_id, "fileName": file_name})

    draft_link = str(state.get("composer_url") or "")
    if not draft_link:
        draft_link = composer_url(ui_base, workflow_id)
    candidate_summaries: list[dict[str, Any]] = []
    ranked_candidates = sorted(
        [candidate for candidate in parsed_candidates if isinstance(candidate, dict)],
        key=_sort_rank_key,
    )
    for candidate in ranked_candidates:
        file_ref = candidate.get("file") if isinstance(candidate.get("file"), dict) else {}
        file_id = str((file_ref or {}).get("libraryItemId") or "").strip()
        file_name = str((file_ref or {}).get("fileName") or "").strip()
        structure_url = ""
        molstar_url = ""
        if file_id and file_name:
            structure_url = (
                f"{ui_base}/api/structure?itemId={quote(file_id)}&fileName={quote(file_name)}"
            )
            molstar_url = f"{ui_base}/mol/{quote(file_id)}?from=library"
        candidate_summaries.append(
            {
                "final_rank": candidate.get("final_rank"),
                "secondary_rank": candidate.get("secondary_rank"),
                "id": candidate.get("id"),
                "designed_sequence": candidate.get("designed_sequence"),
                "iptm": candidate.get("iptm"),
                "ptm": candidate.get("ptm"),
                "design_iiptm": candidate.get("design_iiptm"),
                "interaction_pae": candidate.get("interaction_pae"),
                "min_interaction_pae": candidate.get("min_interaction_pae"),
                "helix": candidate.get("helix"),
                "sheet": candidate.get("sheet"),
                "loop": candidate.get("loop"),
                "file": file_ref if isinstance(file_ref, dict) else None,
                "structure_url": structure_url,
                "molstar_url": molstar_url,
            }
        )

    ranked_table = []
    for candidate in candidate_summaries:
        ranked_table.append(
            {
                "Rank": candidate.get("final_rank"),
                "Sequence": candidate.get("designed_sequence"),
                "iPTM": candidate.get("iptm"),
                "pTM": candidate.get("ptm"),
                "Min Interaction PAE": candidate.get("min_interaction_pae"),
                "Helix %": _fmt_percent(candidate.get("helix")),
                "Sheet %": _fmt_percent(candidate.get("sheet")),
                "Loop %": _fmt_percent(candidate.get("loop")),
                "Molstar Link": candidate.get("molstar_url"),
            }
        )

    payload = {
        "workflow_id": workflow_id,
        "composer_url": draft_link,
        "candidate_count": len(candidate_summaries),
        "metric_field_names": sorted(
            {
                key
                for candidate in parsed_candidates
                for key in (candidate.keys() if isinstance(candidate, dict) else [])
            }
        ),
        "parsed_results_raw": parsed_candidates,
        "candidates": candidate_summaries,
        "ranked_table": ranked_table,
        "output_files": output_refs,
    }
    state["final_task_results"] = results_payload
    state["results_summary"] = payload
    state["workflow_id"] = workflow_id
    state["api_base_url"] = api_base
    state["ui_base_url"] = ui_base
    save_state(args.state_file, state)

    if args.json:
        print(json.dumps(payload, indent=2))
        return

    print(f"workflow_id={workflow_id}")
    print(f"composer_url={draft_link}")
    print(f"candidates={len(candidate_summaries)}")
    if ranked_table:
        print("ranked_results_table:")
        print("| Rank | Sequence | iPTM | pTM | Min Interaction PAE | Helix % | Sheet % | Loop % | Molstar Link |")
        print("|---:|---|---:|---:|---:|---:|---:|---:|---|")
        for row in ranked_table:
            sequence = str(row.get("Sequence") or "").replace("|", "\\|")
            molstar = str(row.get("Molstar Link") or "-")
            print(
                f"| {row.get('Rank')} | {sequence} | {_fmt_numeric(row.get('iPTM'))} | "
                f"{_fmt_numeric(row.get('pTM'))} | {_fmt_numeric(row.get('Min Interaction PAE'))} | "
                f"{row.get('Helix %')} | {row.get('Sheet %')} | {row.get('Loop %')} | {molstar} |"
            )
    for idx, candidate in enumerate(candidate_summaries[: args.top_n], start=1):
        print(
            f"[{idx}] rank={candidate.get('final_rank')} id={candidate.get('id')} "
            f"iptm={candidate.get('iptm')} ptm={candidate.get('ptm')} "
            f"design_iiptm={candidate.get('design_iiptm')} "
            f"interaction_pae={candidate.get('interaction_pae')}"
        )
        print(
            "    secondary_structure="
            f"Helix {_fmt_percent(candidate.get('helix'))} • "
            f"Sheet {_fmt_percent(candidate.get('sheet'))} • "
            f"Loop {_fmt_percent(candidate.get('loop'))}"
        )
        if candidate.get("structure_url"):
            print(f"    structure={candidate['structure_url']}")
        if candidate.get("molstar_url"):
            print(f"    molstar={candidate['molstar_url']}")
    if output_refs:
        print("output_files:")
        for entry in output_refs:
            print(f"- {entry['fileName']} (libraryItemId={entry['libraryItemId']})")


def cmd_composer_link(args: argparse.Namespace) -> None:
    state = load_state(args.state_file)
    _, ui_base = resolve_urls(args.base_url or state.get("api_base_url"), args.ui_base_url or state.get("ui_base_url"))
    workflow_id = require_workflow_id(args, state)
    graph_nodes = _safe_graph_count(state.get("last_upsert_response") or {}, "nodes")
    if graph_nodes <= 0:
        sys.exit("Error: Composer link is shared after a non-empty graph upsert. Run upsert first.")
    print(composer_url(ui_base, workflow_id))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BoltzGen workflow API helper")
    parser.add_argument("--base-url", default="https://api.fastfold.ai", help="API base URL.")
    parser.add_argument("--ui-base-url", default="https://cloud.fastfold.ai", help="UI base URL for composer/structure links.")
    parser.add_argument("--api-key", default=None, help="FastFold API key (otherwise FASTFOLD_API_KEY).")
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_FILE,
        help=f"State file path (default: {DEFAULT_STATE_FILE})",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Create draft workflow.")
    p_new.add_argument("--name", default=None, help="Workflow name override.")
    p_new.add_argument("--preset", default=None, help="Preset label for auto naming (e.g. vanilla_target_binding_site).")
    p_new.add_argument("--goal", default="protein design", help="Human-readable goal label used in auto naming.")
    p_new.set_defaults(func=cmd_new)

    p_examples = sub.add_parser(
        "example-files",
        help="List bundled example files for a preset.",
    )
    p_examples.add_argument(
        "--preset",
        default=None,
        help=(
            "Preset id (e.g. vanilla_target_binding_site). "
            "Aliases include: 5cqg, vanilla_peptide, simple_peptide_binder."
        ),
    )
    p_examples.add_argument("--list", action="store_true", help="List supported preset ids.")
    p_examples.add_argument("--json", action="store_true", help="Print JSON output.")
    p_examples.set_defaults(func=cmd_example_files)

    p_build_spec = sub.add_parser(
        "build-spec",
        help="Build a valid workflow.yml from official preset template + uploaded files.",
    )
    p_build_spec.add_argument(
        "--preset",
        required=True,
        help=(
            "Preset id (e.g. vanilla_target_binding_site). "
            "Aliases include: 5cqg, vanilla_peptide, simple_peptide_binder."
        ),
    )
    p_build_spec.add_argument(
        "--out",
        default="/tmp/boltzgen_workflow.yml",
        help="Output path for rendered workflow.yml.",
    )
    p_build_spec.add_argument("--json", action="store_true", help="Print JSON output.")
    p_build_spec.set_defaults(func=cmd_build_spec)

    p_upload = sub.add_parser("upload", help="Upload a CIF/YAML file to workflow workspace.")
    p_upload.add_argument("--workflow-id", default=None, help="Workflow id (optional if in state).")
    p_upload.add_argument("--file", required=True, help="Local file path.")
    p_upload.add_argument("--file-type", required=True, choices=["protein", "yml"], help="Library file type.")
    p_upload.add_argument("--logical-name", default=None, help="Logical name used in workflow payload.")
    p_upload.add_argument("--parent-id", default=None, help="Optional parent folder id override.")
    p_upload.set_defaults(func=cmd_upload)

    p_upsert = sub.add_parser("upsert", help="Save graph spec YAML in a single upsert.")
    p_upsert.add_argument("--workflow-id", default=None, help="Workflow id (optional if in state).")
    p_upsert.add_argument("--spec", required=True, help="Path to workflow.yml spec.")
    p_upsert.set_defaults(func=cmd_upsert)

    p_review = sub.add_parser(
        "draft-review",
        help="Show draft link + inputs + params + YAML previews for user validation.",
    )
    p_review.add_argument("--workflow-id", default=None, help="Workflow id (optional if in state).")
    p_review.add_argument("--json", action="store_true", help="Print JSON review payload.")
    p_review.set_defaults(func=cmd_draft_review)

    p_execute = sub.add_parser("execute", help="Execute workflow (run after draft-review and user confirmation).")
    p_execute.add_argument("--workflow-id", default=None, help="Workflow id (optional if in state).")
    p_execute.set_defaults(func=cmd_execute)

    p_status = sub.add_parser("status", help="Read workflow status.")
    p_status.add_argument("--workflow-id", default=None, help="Workflow id (optional if in state).")
    p_status.add_argument("--json", action="store_true", help="Print raw status JSON.")
    p_status.set_defaults(func=cmd_status)

    p_wait = sub.add_parser("wait", help="Wait for terminal status.")
    p_wait.add_argument("--workflow-id", default=None, help="Workflow id (optional if in state).")
    p_wait.add_argument("--poll-seconds", type=int, default=30, help="Polling interval.")
    p_wait.add_argument("--timeout-seconds", type=int, default=7200, help="Timeout.")
    p_wait.set_defaults(func=cmd_wait)

    p_logs = sub.add_parser("logs", help="Fetch workflow logs and explain current log meaning.")
    p_logs.add_argument("--workflow-id", default=None, help="Workflow id (optional if in state).")
    p_logs.add_argument("--watch", action="store_true", help="Poll logs until terminal status or timeout.")
    p_logs.add_argument("--poll-seconds", type=int, default=30, help="Polling interval when --watch is set.")
    p_logs.add_argument("--timeout-seconds", type=int, default=1800, help="Timeout when --watch is set.")
    p_logs.add_argument("--tail-lines", type=int, default=120, help="Number of trailing log lines to display.")
    p_logs.add_argument("--json", action="store_true", help="Print JSON payload.")
    p_logs.set_defaults(func=cmd_logs)

    p_results = sub.add_parser("results", help="Summarize candidates and metrics.")
    p_results.add_argument("--workflow-id", default=None, help="Workflow id (optional if in state).")
    p_results.add_argument("--json", action="store_true", help="Print JSON summary.")
    p_results.add_argument("--top-n", type=int, default=10, help="Top N candidates in text output.")
    p_results.set_defaults(func=cmd_results)

    p_link = sub.add_parser("composer-link", help="Print composer link for the workflow.")
    p_link.add_argument("--workflow-id", default=None, help="Workflow id (optional if in state).")
    p_link.set_defaults(func=cmd_composer_link)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

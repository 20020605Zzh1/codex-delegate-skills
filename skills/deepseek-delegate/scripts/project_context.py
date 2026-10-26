"""Resolve task-owned paths from the current Codex project, never a saved root."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve(strict=True)):
        raise ValueError(f"Path is outside the selected project: {resolved}")
    return resolved


def token(value: str, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", value):
        raise ValueError(f"{label} must contain 1-100 letters, digits, underscores or hyphens")
    return value


def save(path: Path, value: object) -> None:
    pending = path.with_name(path.name + "." + uuid.uuid4().hex[:8] + ".tmp")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    pending.replace(path)


@dataclass(frozen=True)
class TaskContext:
    project_root: Path
    task_directory: Path
    workspace: Path
    artifacts: Path
    home: Path
    metadata: dict


def load_task(task_directory: Path) -> TaskContext:
    task = task_directory.resolve(strict=True)
    metadata = json.loads((task / "task.json").read_text(encoding="utf-8"))
    # Version 1 contexts were created by the earlier Low-only bridge.
    metadata.setdefault("reasoning_effort", "low")
    project = Path(metadata["project_root"]).resolve(strict=True)
    expected = within(project / "deepseek_tasks" / token(metadata["conversation_key"], "conversation key")
                      / token(metadata["task_id"], "task id"), project)
    if task != expected:
        raise ValueError("Task location does not match its recorded project and conversation")
    workspace = within(task / "workspace", project)
    artifacts = within(workspace / "artifacts", project)
    home = within(task.parent / ".harness_home", project)
    for field, actual in {"task_directory": task, "workspace": workspace,
                          "artifact_directory": artifacts, "home": home}.items():
        if Path(metadata[field]).resolve() != actual:
            raise ValueError(f"Task metadata changed its {field}")
    return TaskContext(project, task, workspace, artifacts, home, metadata)


def prepare(project_root: Path, conversation_key: str, task_id: str, title: str,
            inputs: list[Path], model: str, conversation_id: str | None = None,
            reasoning_effort: str = "max") -> TaskContext:
    if not project_root.is_absolute():
        raise ValueError("Pass the absolute project directory from the current Codex conversation")
    project = project_root.resolve(strict=True)
    if not project.is_dir():
        raise ValueError("Project root must be a directory")
    key, task_id = token(conversation_key, "conversation key"), token(task_id, "task id")
    task = within(project / "deepseek_tasks" / key / task_id, project)
    workspace = within(task / "workspace", project)
    artifacts = within(workspace / "artifacts", project)
    home = within(task.parent / ".harness_home", project)
    selected_inputs = [within(item.resolve(strict=True), project) for item in inputs]
    if not all(item.is_file() for item in selected_inputs):
        raise ValueError("Each input must be a regular file inside the current project")
    info_path = task / "task.json"
    if info_path.exists():
        context = load_task(task)
        metadata = dict(context.metadata)
        if (metadata["model"] != model or metadata.get("codex_conversation_id") != conversation_id
                or metadata["reasoning_effort"] != reasoning_effort):
            raise ValueError("An existing task cannot change its model, reasoning effort or Codex conversation")
    else:
        metadata = {"version": 2, "project_root": str(project), "conversation_key": key,
                    "codex_conversation_id": conversation_id, "task_id": task_id, "title": title,
                    "task_directory": str(task), "workspace": str(workspace),
                    "artifact_directory": str(artifacts), "home": str(home),
                    "session_id": "codex-ds-" + uuid.uuid4().hex, "model": model, "reasoning_effort": reasoning_effort,
                    "maintenance_owner": "Codex", "execution_status": "NOT_RUN",
                    "review_status": "PENDING_CODEX_REVIEW", "input_manifest": [], "created_at_utc": now()}
    snapshot_dir = within(workspace / "inputs", project)
    for directory in [snapshot_dir, artifacts, home, task / "runs"]:
        directory.mkdir(parents=True, exist_ok=True)
    for original in selected_inputs:
        raw = original.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        destination = within(snapshot_dir / f"{original.stem}-{digest[:12]}{original.suffix}", project)
        if destination.exists() and destination.read_bytes() != raw:
            raise ValueError("Input snapshot name collision; keep the existing file")
        if not destination.exists():
            destination.write_bytes(raw)
        entry = {"source": str(original), "snapshot": str(destination), "sha256": digest, "size_bytes": len(raw)}
        if entry not in metadata["input_manifest"]:
            metadata["input_manifest"].append(entry)
    metadata["updated_at_utc"] = now()
    save(info_path, metadata)
    return load_task(task)


def record_manifest(context: TaskContext, run_id: str, turn: int, finish_reason: str | None) -> dict:
    entries = []
    for candidate in sorted(context.artifacts.rglob("*")):
        if not candidate.is_file():
            continue
        file_path = within(candidate, context.project_root)
        file_path.relative_to(context.artifacts.resolve())
        digest = hashlib.sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        entries.append({"path": str(file_path), "project_relative_path": str(file_path.relative_to(context.project_root)),
                        "size_bytes": file_path.stat().st_size, "sha256": digest.hexdigest(),
                        "review_status": "PENDING_CODEX_REVIEW"})
    manifest = {"project_root": str(context.project_root), "conversation_key": context.metadata["conversation_key"],
                "codex_conversation_id": context.metadata["codex_conversation_id"],
                "session_id": context.metadata["session_id"], "run_id": run_id, "turn": turn,
                "reasoning_effort": context.metadata["reasoning_effort"],
                "model_finish_reason": finish_reason, "recorded_at_utc": now(),
                "maintenance_owner": "Codex", "review_status": "PENDING_CODEX_REVIEW", "artifacts": entries}
    save(context.task_directory / "artifact_manifest.json", manifest)
    history = context.task_directory / "runs" / run_id
    save(history / f"turn_{turn:02d}_artifact_manifest.json", manifest)
    metadata = json.loads((context.task_directory / "task.json").read_text(encoding="utf-8"))
    metadata.update(execution_status=finish_reason, review_status="PENDING_CODEX_REVIEW", last_run_id=run_id)
    save(context.task_directory / "task.json", metadata)
    return manifest

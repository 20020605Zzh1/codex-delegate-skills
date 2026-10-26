"""Register a closed project-owned session with the existing Harness Desktop."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from desktop_client import DesktopClient
from project_context import load_task, save, within

SCRIPTS = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--launch-log", type=Path)
    parser.add_argument("--desktop-executable", type=Path)
    parser.add_argument("--desktop-home", type=Path)
    args = parser.parse_args()
    run = args.run.resolve(strict=True)
    context = load_task(run.parents[1])
    within(run, context.task_directory / "runs")
    config = json.loads((run / "run.json").read_text(encoding="utf-8"))
    if config["status"] != "CLOSED":
        raise ValueError("Close the Harness writer before registering its log")
    if (config["session_id"] != context.metadata["session_id"]
            or Path(config["workspace"]).resolve() != context.workspace
            or Path(config["home"]).resolve() != context.home):
        raise ValueError("Run metadata does not belong to this project task")
    receipt_path = run / "desktop_sync.json"
    receipt = {"status": "DESKTOP_SYNC_PENDING", "project_root": str(context.project_root),
               "conversation_key": context.metadata["conversation_key"], "session_id": config["session_id"],
               "title": args.title, "ui_visibility": "NATIVE_UI_CHECK_PENDING", "mode": "CLOSED_SESSION_SYNC"}
    try:
        codex_home = Path(os.environ.get("CODEX_HOME") or str(Path.home() / ".codex"))
        launch_log = args.launch_log
        if launch_log is None:
            settings = json.loads((codex_home / "cache" / "deepseek-delegate" / "connection.json").read_text(encoding="utf-8-sig"))
            launch_log = Path(settings["desktop_launch_log"])
        client = DesktopClient(launch_log)
        executable = args.desktop_executable or Path(os.environ["LOCALAPPDATA"]) / "Programs" / "DeepSeek Harness" / "DeepSeek Harness.exe"
        conversion = subprocess.run([str(executable), "--expose-internals", str(SCRIPTS / "convert_closed_session.cjs"),
                                     str(context.home / "sessions"), config["session_id"], str(run / "desktop_format")],
                                    env=dict(os.environ, ELECTRON_RUN_AS_NODE="1"), capture_output=True,
                                    encoding="utf-8", timeout=30, check=True)
        proof = json.loads(conversion.stdout.strip())
        if proof["status"] != "COMPRESSED_ALL_ROWS_READBACK_PASS":
            raise RuntimeError("Compressed log conversion did not pass verification")
        converted = within(Path(proof["destination"]), run / "desktop_format")
        desktop_home = (args.desktop_home or Path(os.environ["USERPROFILE"]) / ".dsh").resolve(strict=True)
        destination = within(desktop_home / "sessions" / converted.relative_to(run / "desktop_format"), desktop_home)
        if destination.exists():
            if destination.read_bytes() != converted.read_bytes():
                raise RuntimeError("The Desktop copy has changed; keep the live conversation untouched")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(converted, destination)
        workspace = client.call("workspace", "create", {"request": {"path": str(context.workspace)}})
        workspace_info = workspace["workspace"]
        if Path(workspace_info["path"]).resolve() != context.workspace:
            raise RuntimeError("Desktop workspace does not match the current task")
        workspace_id = workspace_info["workspaceId"]
        if workspace["created"]:
            client.call("workspace", "rename", {"request": {"workspaceId": workspace_id,
                        "title": f"{context.project_root.name} / {context.metadata['title']}"}})
        adopted = client.call("session", "create", {"request": {
            "sessionId": config["session_id"], "workspaceId": workspace_id}})
        renamed = client.call("session", "rename", {"request": {
            "sessionId": config["session_id"], "title": args.title}})
        receipt.update(status="DESKTOP_REGISTERED_API_READBACK_PASS", conversion=proof,
                       desktop_session_path=str(destination), workspace_id=workspace_id,
                       adopted=adopted, renamed=renamed,
                       compressed_sha256_before_activation=hashlib.sha256(converted.read_bytes()).hexdigest())
    except Exception as exc:
        receipt["error"] = re.sub(r"token=[^\s&]+", "token=[REDACTED]", str(exc))
        save(receipt_path, receipt)
        print(json.dumps({"status": receipt["status"], "error": receipt["error"]}, ensure_ascii=False))
        return 1
    save(receipt_path, receipt)
    print(json.dumps({"status": receipt["status"], "session_id": config["session_id"],
                      "workspace_id": receipt["workspace_id"], "title": args.title}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

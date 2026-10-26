"""Prepare a task inside the current Codex conversation's project."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from project_context import prepare


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--conversation-key", required=True)
    parser.add_argument("--conversation-id")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--input", action="append", default=[], type=Path)
    parser.add_argument("--model", default="deepseek-flash")
    parser.add_argument("--reasoning-effort", default="max")
    args = parser.parse_args()
    context = prepare(args.project_root, args.conversation_key, args.task_id,
                      args.title, args.input, args.model, args.conversation_id, args.reasoning_effort)
    print(json.dumps({"status": "PREPARED_NOT_RUN", **context.metadata}, ensure_ascii=False))


if __name__ == "__main__":
    main()

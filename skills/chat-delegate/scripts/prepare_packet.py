"""Create a local Markdown packet and short message; never send anything."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ALIASES = {"高": "high", "high": "high", "极高": "xhigh", "xhigh": "xhigh",
           "低": "low", "low": "low", "中": "medium", "medium": "medium",
           "pro": "pro", "保持": "keep", "keep": "keep"}
TEXT_SUFFIXES = {".md", ".markdown", ".txt"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_text(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    if "\x00" in text:
        raise ValueError(f"Not a UTF-8 text file: {path}")
    return raw, text


def nonempty(value: str) -> str:
    value = value.strip()
    if not value:
        raise argparse.ArgumentTypeError("Must not be empty")
    return value


def prepare(args: argparse.Namespace) -> dict:
    target_dir = args.output_dir.expanduser().resolve()
    names = ("attachment.md", "message.txt", "manifest.json")
    for name in names:
        if (target_dir / name).exists():
            raise FileExistsError(f"Keep the existing round; choose a new output directory: {target_dir / name}")

    instruction_path = args.instruction_file.expanduser().resolve(strict=True)
    _, instruction = read_text(instruction_path)
    instruction = instruction.strip()
    if not instruction:
        raise ValueError("The instruction file is empty")

    thinking = ALIASES.get(args.thinking_level.casefold(), args.thinking_level)
    records = []
    packet_parts = [f"# {args.title}\n\n下面按来源编号提供本轮材料，各来源正文保持原文。\n".encode("utf-8")]
    position = len(packet_parts[0])
    seen = set()
    for index, value in enumerate(args.source, start=1):
        path = value.expanduser().resolve(strict=True)
        if path in seen:
            raise ValueError(f"Source supplied twice: {path}")
        seen.add(path)
        if path.suffix.lower() not in TEXT_SUFFIXES:
            raise ValueError(f"Convert and verify this format first; expected Markdown/TXT: {path}")
        raw, content = read_text(path)
        if not content.strip():
            raise ValueError(f"Source is empty: {path}")
        source_id = f"SOURCE-{index:03d}"
        digest = sha256(raw)
        prefix = (f"\n\n## {source_id} · {path.name}\n\n"
                  f"原文件 SHA-256：`{digest}`\n\n"
                  f"<!-- {source_id} BEGIN -->\n").encode("utf-8")
        body = content.encode("utf-8")
        suffix = f"\n<!-- {source_id} END -->\n".encode("utf-8")
        position += len(prefix)
        records.append({
            "id": source_id, "path": str(path), "filename": path.name,
            "source_bytes": len(raw), "source_sha256": digest,
            "content_characters": len(content), "content_sha256": sha256(body),
            "utf8_bom_removed": raw.startswith(b"\xef\xbb\xbf"),
            "attachment_content_byte_start": position,
            "attachment_content_byte_end": position + len(body),
        })
        packet_parts.extend((prefix, body, suffix))
        position += len(body) + len(suffix)

    attachment = b"".join(packet_parts)
    message = f"请阅读附件 attachment.md，按以下要求处理。\n\n{instruction}"
    message_bytes = message.encode("utf-8")
    manifest = {
        "schema_version": 1,
        "status": "PREPARED_NOT_SENT",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "chat_target_requested": args.chat_target,
        "chat_url_observed": None,
        "model_requested": args.model,
        "model_observed": None,
        "thinking_level_requested": thinking,
        "thinking_level_observed": None,
        "settings_evidence": None,
        "settings_verified": False,
        "attachment_uploaded": False,
        "message_sent": False,
        "reply_complete": False,
        "attachment": {"path": str(target_dir / names[0]), "bytes": len(attachment),
                       "characters": len(attachment.decode("utf-8")), "sha256": sha256(attachment)},
        "message": {"path": str(target_dir / names[1]), "characters": len(message),
                    "sha256": sha256(message_bytes)},
        "instruction_source": str(instruction_path),
        "sources": records,
        "content_preservation": "Full source text, preserving line endings; optional leading UTF-8 BOM removed.",
    }
    target_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {names[0]: attachment, names[1]: message_bytes,
                 names[2]: (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")}
    for name, data in artifacts.items():
        with (target_dir / name).open("xb") as handle:
            handle.write(data)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", type=Path, required=True, help="Repeat for each UTF-8 Markdown/TXT source")
    parser.add_argument("--instruction-file", type=Path, required=True, help="Short instruction; put long requirements in a source file")
    parser.add_argument("--chat-target", type=nonempty, required=True, help="Authorized Chat URL, ID, exact title, or new")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--thinking-level", type=nonempty, default="high", help="Default: high / 高; UI verification is separate")
    parser.add_argument("--model", type=nonempty, default="keep", help="Default: keep the actual model")
    parser.add_argument("--title", type=nonempty, default="Chat 任务材料")
    args = parser.parse_args()
    try:
        result = prepare(args)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(2, f"Preparation stopped: {exc}\n")
    print(json.dumps({"status": result["status"], "output_dir": str(args.output_dir.resolve()),
                      "thinking_level_requested": result["thinking_level_requested"],
                      "source_count": len(result["sources"]),
                      "attachment_bytes": result["attachment"]["bytes"],
                      "message_characters": result["message"]["characters"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

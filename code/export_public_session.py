"""Render authentic public Codex/OpenCode records without private reasoning."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b|(?i:Bearer)\s+[A-Za-z0-9._~-]{20,}")


def redact(text):
    return TOKEN.sub("[REDACTED CREDENTIAL]", text)


def fence(text, language=""):
    text = str(text)
    delimiter = "`" * max(3, 1 + max((len(m[0]) for m in re.finditer(r"`+", text)), default=0))
    return f"{delimiter}{language}\n{text.rstrip()}\n{delimiter}\n"


def export_codex(source, target):
    records = []
    for ordinal, line in enumerate(source.read_text().splitlines(), 1):
        record = json.loads(line)
        payload = record.get("payload", {})
        if record.get("type") == "session_meta":
            records.append({"type": "source_metadata", "payload": {k: payload[k] for k in ("id", "timestamp", "cwd", "originator", "cli_version") if k in payload}})
        if record.get("type") != "response_item":
            continue
        kind = payload.get("type")
        if kind == "message":
            if payload.get("role") not in ("user", "assistant") or payload.get("channel") == "analysis":
                continue
            if payload.get("phase", "commentary") not in ("commentary", "final", None):
                continue
            payload = {k: payload[k] for k in ("type", "role", "content", "phase") if k in payload}
        elif kind not in ("function_call", "function_call_output", "custom_tool_call", "custom_tool_call_output"):
            continue
        records.append({"timestamp": record.get("timestamp"), "ordinal": ordinal, "type": "response_item", "payload": payload})
    target.write_text(redact(json.dumps(records, indent=2, ensure_ascii=False)) + "\n")
    return records


def render_codex(records, title):
    parts = [f"# {title}\n\nActual public Codex session records, rendered in the question session Markdown style.\nThe agent identity remains Codex.\nPrivate reasoning, system/developer setup and automatic approval-review internals are excluded.\nOriginal public tool inputs and outputs are retained, with credential-pattern redaction.\n"]
    for ordinal, record in enumerate(records, 1):
        p = record["payload"]
        if record["type"] == "source_metadata":
            parts.append("\n## Source metadata\n\n" + fence(json.dumps(p, indent=2), "json"))
            continue
        kind = p.get("type")
        parts.append(f"\n## Record {ordinal} - {record.get('timestamp', '')}\n")
        if kind == "message":
            parts.append(f"\n**{p['role'].title()}**\n\n")
            for block in p.get("content", []):
                if block.get("type") in ("input_text", "output_text", "text"):
                    parts.append(block.get("text", "").rstrip() + "\n")
                else:
                    parts.append(fence(json.dumps(block, ensure_ascii=False, indent=2), "json"))
        elif kind in ("function_call", "custom_tool_call"):
            parts.append(f"\n**Tool** `{p.get('name')}`\n\n**Input**\n\n" + fence(p.get("arguments", p.get("input", ""))))
        else:
            parts.append("\n**Tool output**\n\n" + fence(p.get("output", "")))
    return redact("\n".join(parts))


def render_opencode(data):
    parts = [f"# OpenCode session {data['info']['id']}\n\nRendered from the actual OpenCode JSON export.\nCredential-pattern redaction is applied; no missing implementation conversation is reconstructed.\n"]
    for ordinal, message in enumerate(data["messages"], 1):
        parts.append(f"\n## Turn {ordinal} - {message['info']['role'].title()}\n")
        for part in message.get("parts", []):
            if part["type"] == "text":
                parts.append(part.get("text", "").rstrip() + "\n")
            elif part["type"] == "tool":
                state=part.get("state", {})
                parts.append(f"\n**Tool** `{part.get('tool')}` ({state.get('status', '')})\n\n**Input**\n\n" + fence(json.dumps(state.get("input", {}), indent=2, ensure_ascii=False), "json"))
                parts.append("\n**Output**\n\n" + fence(state.get("output", state.get("error", ""))))
            elif part["type"] != "reasoning":
                parts.append(fence(json.dumps(part, indent=2, ensure_ascii=False), "json"))
    return redact("\n".join(parts))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path, help="Output Markdown inside this repository")
    parser.add_argument("--format", choices=("codex-jsonl", "codex-public-json", "opencode"), required=True)
    args=parser.parse_args(argv)
    if not args.target.resolve().is_relative_to(ROOT):
        parser.error("Session exports must remain inside the repository")
    args.target.parent.mkdir(parents=True, exist_ok=True)
    target_json=args.target.with_suffix('.json')
    if args.format=='codex-jsonl':
        data=export_codex(args.source,target_json)
    else:
        data=json.loads(redact(args.source.read_text()))
        target_json.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n')
    text=render_opencode(data) if args.format=='opencode' else render_codex(data,args.target.stem)
    args.target.write_text('\n'.join(line.rstrip() for line in text.splitlines()).rstrip()+'\n')
    print(f"Exported {args.target.resolve().relative_to(ROOT)}; public JSON SHA-256 {hashlib.sha256(target_json.read_bytes()).hexdigest()}")


if __name__=='__main__':
    main()

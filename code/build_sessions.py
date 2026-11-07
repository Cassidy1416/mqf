"""Assemble the root evidence document from authentic saved public exports."""
from __future__ import annotations
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parts=["""# Session exports and evidence provenance

This document includes genuine public implementation, integration and repair transcripts, with question-local evidence linked below.
OpenCode and Codex identities are retained honestly; Markdown presentation does not change which agent performed the work.
Credential patterns are redacted, and Codex private reasoning and automatic approval-review internals are excluded from public exports.
The raw public JSON accompanies every newly recovered or exported transcript.

| Question | Evidence | Historical limitation |
| --- | --- | --- |
| Q1 | [Session](questions/q1/SESSION.md), [original summary](questions/q1/SESSION.original.md), actual later OpenCode verification | Original full implementation conversation unavailable |
| Q2 | [Original OpenCode and recovered Codex completion](questions/q2/SESSION.md) | The previously omitted later public completion traces have now been recovered |
| Q4 | [Session](questions/q4/SESSION.md), [original summary](questions/q4/SESSION.original.md), actual later OpenCode verification | Original full implementation conversation unavailable |

The user approved Q1 expanded monthly chains and SHIBOR curves, Q4 future-link prediction plus a separate static benchmark, and direct Codex repair completion after the OpenCode quota was exhausted.
The approval is present in the actual public repair transcript below.
This local exception does not establish instructor acceptance under the examination's approved-agent rule.
Unavailable Q1/Q4 original implementation exports cannot be reconstructed from summaries; later verification records are not presented as those missing conversations.
Exported transcripts are finite checkpoints through their last saved record; final evidence-packaging operations can occur after that checkpoint.
The original Git ancestry and original session summaries remain preserved.

## Question-local sessions

"""]
    for q in ('q1','q2','q4'):
        text=(ROOT/f'questions/{q}/SESSION.md').read_text()
        text=re.sub(r'\]\((?!https?://|#)([^)]+)\)',lambda m:f'](questions/{q}/{m[1]})',text)
        parts.append(text)
    parts.append('\n# Integration and interrupted OpenCode repair sessions\n\nThese are actual exports, including quota failures and interrupted attempts.\n')
    for path in sorted((ROOT/'sessions/opencode').glob('*.md')):
        parts.append(path.read_text())
    parts.append('\n# Recovered Q2 public Codex completion sessions\n\nThese are actual historical records recovered from local Codex traces, not recreated prompts.\n')
    for path in sorted((ROOT/'questions/q2/sessions').glob('codex-completion-*.md')):
        parts.append(path.read_text())
    parts.append('\n# Current public audit, integration and repair session\n\n')
    parts.append((ROOT/'sessions/codex-repairs.md').read_text())
    (ROOT/'SESSION.md').write_text('\n'.join(line.rstrip() for line in '\n\n'.join(parts).splitlines())+'\n')
    print('Assembled root SESSION.md from genuine saved session records.')


if __name__=='__main__':
    main()

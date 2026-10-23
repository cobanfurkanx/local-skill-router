# Local Skill Router

A proactive, local-first skill router for coding agents. Native adapters surface installed workflows; when something useful is missing, **your agent** can discover a candidate on skills.sh, review an immutable source, and install it globally under your chosen policy.

**Your model makes the selection; the tool does not call another model.** Using no skill is a valid outcome. Popularity is not quality, and this project does not promise the optimal skill, better output, or fewer tokens on every task. Initial release: **0.1.0**.

## Quick start

Requirements: **Python 3.11+**. Clone or download the repository, then preview native integration:

```sh
git clone https://github.com/cobanfurkanx/local-skill-router.git
cd local-skill-router
python scripts/setup.py install --agent codex --agent claude --agent antigravity --agent opencode --dry-run
```

Remove `--dry-run` to install the selected adapters. Keep the returned operation ID for undo. Restart those client sessions. Setup adds a small managed rule, Claude's prompt hook, and OpenCode's message plugin; preserves unrelated settings; creates a private, versioned runtime copy; and primes its local index. It refuses malformed settings rather than repairing them silently.

Default remote installation policy is **ask**. To grant your agent standing permission to install third-party skills after content review and digest acknowledgement:

```sh
python scripts/setup.py install --agent codex --agent opencode --remote-policy reviewed
```

This is a real global-install authorization, not a security certificate. Use `--remote-policy ask` to revoke it. Host permissions always apply. The agent chooses the query and candidate; hooks never send your prompts to skills.sh.

No `pip install`, RTK, API key, additional model, telemetry service or resident daemon is needed. Remote search sends a short agent-selected query to skills.sh; source inspection downloads public GitHub content. OpenCode runs its adapter in its existing JavaScript runtime. The core is Python standard-library-only.

## Integration coverage

| Profile | Proactive mechanism | Scope / caveat |
|---|---|---|
| Codex | Global `AGENTS.md` + native skill | Instruction-driven; model must follow the rule |
| Claude Code | Global rule + `UserPromptSubmit` exec-form hook | Current Claude versions supporting hook `args`; injected local candidates |
| OpenCode | Global rule + local `chat.message` plugin | Injected local candidates; tested plugin contract |
| Antigravity App / CLI | Global `GEMINI.md` + skills in both native locations | Instruction-driven; native skill refresh may require restart |
| Hermes / Copilot CLI | Global instruction + native skill | Instruction-driven compatibility profiles |
| Cursor | Always-apply project rule + user skill | Supply `--project PATH` before `install`; global GUI rules are not edited |
| OpenClaude | Claude-like instruction profile | Experimental compatibility; not a Claude hook implementation |
| TRAE | User skill only | Manual rule setup in the client; automatic global trigger is **not claimed** |

No independent process can force every model/client to follow instructions. This is proactive integration inside supported hosts, not a cross-platform background agent service. [Setup, recovery and integration details](docs/integrations.md).

## Remote discovery workflow

```text
task → useful local skill? → use it
              ↓ no
      agent searches skills.sh
              ↓
      inspect pinned source → agent reviews content/tools/license
              ↓
      owner policy allows install? → install globally → refresh → validate task output
```

```sh
python scripts/remote.py search "python testing" --limit 3
python scripts/remote.py inspect --repo owner/repository --skill exact-skill-name
python scripts/remote.py install PATH_TO_INSPECTION --reviewed EXACT_DIGEST --agent codex
```

With `ask`, the last command prints a plan; use `--yes` only with genuine owner authorization. With `reviewed`, acknowledged sources can be installed automatically. Sources are pinned, staged and hashed before review; changed bytes, archive path escapes, selected symlinks and existing destinations are refused. No downloaded helper is executed during installation. [Remote operation and limits](references/remote.md).

## Standalone skill / local CLI

Preview a copy into a **new** directory:

```sh
python scripts/install_skill.py --target ~/.agents/skills/local-skill-router --agent any --dry-run
```

Remove `--dry-run` to copy the self-contained skill, helpers, reference files, plugin template and MIT notice. **This standalone copier does not activate proactive integration.** Use `setup.py install` above for that. It refuses an existing destination; a failed new copy is left for inspection rather than deleting user data.

| Client convention | Possible skill directory |
|---|---|
| Shared Agent Skills | `~/.agents/skills/local-skill-router` |
| Codex | `~/.codex/skills/local-skill-router` |
| Claude Code | `~/.claude/skills/local-skill-router` |
| OpenCode | `~/.config/opencode/skills/local-skill-router` |
| Other clients | Their configured native skill directory |

These are integration starting points. Check the current client version and its discovery rules. CLI `--agent` modes filter skill metadata; they do not establish native client support or supply missing tools. An installed skill may require a new client session before it is discovered.

The CLI also works without any native integration:

```sh
python scripts/router.py refresh
python scripts/router.py query "Python debugging and regression testing" --agent codex --text
python scripts/router.py plan --task "React accessible UI" --task "browser runtime verification" --text
```

For standalone-copy updates use a new directory. Proactive setup updates only its managed rule/runtime, records prior bytes privately and leaves unrelated text/settings intact. `python scripts/setup.py undo OPERATION_ID` restores an unchanged installation; it refuses subsequent user-edit conflicts. Source skill updates are not automatic.

## How it works

1. Index skill names, descriptions, headings, requirements, paths and content hashes locally.
2. Rank using BM25-style lexical scoring, English/Turkish aliases, project preference and optional verified outcomes.
3. Return a small candidate set with tool/runtime caveats.
4. Let the agent read applicable files, perform the task and validate its output.

Duplicate content is collapsed, project skills can override global definitions, explicit-only invocation policies are respected, and changed skill text is rechecked before selection. Existing `SKILL.routed.md` files can be found, but the router never hides or renames native skills.

See [configuration, learning, privacy and hooks](references/usage.md) for advanced use. Global flags come **before** the command:

```sh
python scripts/router.py --config my-config.json --state-dir ./local-state query "task terms" --text
```

For sensitive or shell-heavy local task text, use `--task-file` instead of interpolating a raw prompt into a shell command. Do not send private text through remote search. No background monitoring or model experiments run automatically.

## What the pilot actually found

One synthetic Python bug-fix task was run with routing on/off in two native clients. Both conditions passed the same 25 initial checks; every solution failed a supplemental large-number precision check. Reported token totals fell in one client and rose in the other. The sample cannot establish a general quality or cost benefit.

Read [the anonymized pilot and limitations](docs/evaluation.md). Raw conversations, private libraries, local paths, learned routes and experiment databases are intentionally excluded.

## Development

```sh
python -m unittest discover -s tests -v
python -m compileall -q scripts tests
git diff --check
```

Tests create synthetic libraries and isolated state; they never call another model or install this skill globally. GitHub Actions is configured for Python 3.11/3.14 on Windows/Linux. Local success does not mean remote CI has run.

Contributions: keep runtime dependencies at zero unless a demonstrated need justifies one; add a regression test for behavior changes; do not include generated state or claim quality improvements without an appropriate comparison. See [AGENTS.md](AGENTS.md) and [SECURITY.md](SECURITY.md).

Licensed under the [MIT License](LICENSE). See [research attribution](docs/research.md).

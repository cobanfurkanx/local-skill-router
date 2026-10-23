# Optional modes

Use Python 3.11 or later. No packages or API keys are required. Commands below run from the skill/repository directory; from another working directory use the absolute `scripts/router.py` path.

## Configuration and state

The bundled `config.json` lists common user skill directories; missing directories are ignored. Proactive setup generates a private copy using the selected home and supported native path overrides. Agent names filter metadata compatibility, not OS permissions. No client is launched automatically. Provider plugin caches are not scanned by default: a cached skill does not establish that its tools are enabled.

For another library, create a separate JSON config:

```json
{
  "roots": [
    {"path": "./my-skills", "source": "shared", "agents": ["any"]}
  ]
}
```

Root paths may use `~` or environment variables; relative paths resolve against the config file, not the current working directory. The parser supports the simple scalar frontmatter used by skills, not all YAML features.

```sh
python scripts/router.py --config my-config.json --state-dir ./local-state refresh
python scripts/router.py --config my-config.json --state-dir ./local-state query "database migration" --text
```

Global flags (`--config`, `--state-dir`) come before the command. Other flags come after it. Default state is `$XDG_STATE_HOME/local-skill-router`, or `~/.local/state/local-skill-router` if unset. `SKILL_ROUTER_STATE_DIR` overrides the default; `--state-dir` overrides both. Use a separate state directory when comparing different configs or experiments.

The index contains names, descriptions, headings, paths, requirements and content hashes from local skills. It does not contain a complete copy of each skill. Query and hook calls do not save the raw prompt. Results printed to the terminal include local paths and snippets; the host agent may log them. Do not publish generated state.

Project skill folders are searched from `--cwd` to the nearest Git root; without a Git boundary only that directory is searched. Project definitions win over same-name global definitions. Duplicate content is shown once. Existing `SKILL.routed.md` files are readable by the router, but this package never renames or hides skills.

## Query and plan

```sh
python scripts/router.py query "Python regression testing" --agent codex --text
python scripts/router.py query --task-file task.txt --agent opencode --text --verbose
python scripts/router.py plan --task "React accessible interface" --task "browser runtime verification" --text
```

Query task files are UTF-8 text. Plan task files contain a JSON array of 1–8 nonempty strings. JSON output is the default; `--text` is compact and `--text --verbose` includes longer descriptions. Paths in candidate output are data; do not interpolate them into shell commands without quoting.

Search is lexical, using weighted name/description/headings, configurable aliases, project preference and optional recorded outcomes. The minimum score is scaled down for libraries smaller than 50 skills because BM25 IDF is smaller there. Scores are not calibrated confidence or proof of utility. `estimated_tokens` is a byte-count/4 heuristic for full skill files, not tokenizer output or a model bill. Decomposition and final selection belong to the calling agent.

`disable-model-invocation: true` and `agents/openai.yaml` with `allow_implicit_invocation: false` exclude a skill from implicit results. `--explicit NAME` permits retrieval for a user-named skill; it does not bypass host permissions. Unreadable or changed policy files are rechecked before selection. This is compatibility handling, not a complete policy engine.

## Opt-in outcomes

Only after a useful, verified result:

```sh
python scripts/router.py learn --task "generic task type" --skill skill-name --agent codex --evidence "specific check that passed"
python scripts/router.py learn --task "generic task type" --skill first --skill second --scope project --cwd ./project --evidence "observed validation"
python scripts/router.py record --task "generic task type" --skill skill-name --outcome unhelpful
```

Learning stores tokenized task terms, selected names/paths/hashes and the evidence string you provide. Feedback stores tokenized task terms. These can still be sensitive: use generic task types, omit secrets/personal information, and keep state private. Learning is local user feedback, not statistically validated training. Changed content invalidates saved matches. Project-scoped learning stays inside the recorded project boundary. Compatible global routes can be reused across clients.

## Claude-compatible prompt hook

The `hook` command accepts a JSON object on stdin with `prompt`, optional `cwd`, and optional `session_id`. It emits Claude-style `hookSpecificOutput.additionalContext`. Other clients must use their own adapter/protocol; the agent name alone does not translate hook schemas.

Run `refresh` first. Hooks intentionally skip rebuilding a missing or configuration-mismatched index. Their selected files and invocation policies are still checked at retrieval time; new files require a query or refresh. Without a session ID every relevant event can emit context. With an ID, unchanged suggestions are suppressed for 15 minutes using hashed session identity and content signatures. No raw prompt/session ID is written to this dedup cache. Hosts may retain their normal session logs independently.

Proactive setup installs a current Claude exec-form hook and OpenCode adapter. To wire another hook manually, use an absolute Python/router path and `hook --agent claude`; review the host's current schema first. The output shape remains Claude-compatible; other clients need an adapter such as the supplied OpenCode plugin.

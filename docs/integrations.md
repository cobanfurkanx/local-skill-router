# Proactive setup and recovery

Run `python scripts/setup.py install --agent NAME` from a trusted checkout. Repeat `--agent` for multiple profiles. `--dry-run` validates and previews all writes without changing files. `--state-dir PATH` before `install` selects private runtime/backup storage; `--home PATH` is provided for isolated testing and ignores real-user path overrides.

State normally lives outside the repository. Setup stores a content-identified runtime copy under `state/apps/`, small native skill adapters, and a marker-delimited instruction block. It preserves text outside its own block. On repeated installation unchanged files are not rewritten. A changed router version creates a new runtime copy so old operations remain recoverable. Unrelated application permissions are never widened.

## Profiles

- Codex: `$CODEX_HOME/AGENTS.md` and `skills/` (default `~/.codex`). Instructions request a local query for substantial unfamiliar tasks.
- Claude: `~/.claude/CLAUDE.md`, `skills/`, and additive `settings.json` prompt hook. Existing unrelated hooks/permissions remain. The hook uses `command` plus an argument array, avoiding shell quoting; use a current Claude Code version supporting exec-form hooks. Old clients may require an upgrade; no compatibility with clients ignoring `args` is claimed.
- OpenCode: `$OPENCODE_CONFIG_DIR`, or `$XDG_CONFIG_HOME/opencode`, or `~/.config/opencode`. A local `.js` plugin uses the documented plugin interface and `chat.message` callback to invoke the cached Python hook over stdin. It appends synthetic local candidate context, fails open on errors/timeouts, and uses no npm dependency or shell interpolation. No remote discovery occurs in the plugin.
- Antigravity: `~/.gemini/GEMINI.md`, App skills in `~/.gemini/config/skills`, CLI skills in `~/.gemini/antigravity-cli/skills`. Legacy paths remain searchable through custom configuration if needed.
- Hermes: `$HERMES_HOME/SOUL.md` and `skills/`, default `~/.hermes`.
- Copilot CLI: `~/.copilot/copilot-instructions.md` and `skills/`.
- Cursor: supply `--project PATH` before `install`; `.cursor/rules/local-skill-router.mdc` is an always-apply project rule. The native user skill lives in `~/.cursor/skills`. This release does not programmatically edit Cursor's account-synced GUI user rules.
- OpenClaude: `~/.openclaude` instruction/skill compatibility template, experimental; no prompt hook assumed.
- TRAE: `~/.trae/skills` only. Put the emitted skill's routing instruction in the client's own rules UI if desired. Setup reports `manual-rule`, not a working automatic global hook.

Instruction-driven profiles rely on the host loading/following the rule; native project/session policies and filesystem permissions still take precedence. A copied file, a validated hook contract, and actual live client behavior are different evidence levels. See release notes for what was tested; do not infer verification of every client from unit tests.

## Authorization and data

`--remote-policy reviewed` records the owner's standing permission for digest-reviewed global third-party installs. Default `ask` prints a plan until actual authorization is supplied. These settings guide a trusted local agent; they do not sandbox a malicious process already running as the same OS user. `--yes` is an authorization acknowledgement, not proof a human read the source. Review is performed by the calling agent and can be mistaken.

Local hooks use existing index metadata, recheck current files/policies and suppress unchanged suggestions for 15 minutes when a session ID exists. No prompt/session ID is written to that cache. Hosts can log their normal conversations. The Python router does not invoke a model, install skills, or access the network from a hook. Network discovery happens only when the agent explicitly calls `remote.py search/inspect`.

Journal files contain **prior native settings**, potentially including private content. They are stored under a private `state/operations/` directory and never belong in Git. App snapshots contain generated local paths; they also stay outside the repository. Do not upload your state directory when reporting an issue.

## Doctor and undo

```sh
python scripts/setup.py doctor
python scripts/setup.py undo OPERATION_ID
```

Pass the same `--state-dir` and, for Cursor, `--project` used at install. Doctor reports presence of skills/rules/index; it does not certify the model followed them. For a fresh missing cache run the installed router's `refresh` command; hooks deliberately avoid expensive global refresh on every prompt.

Every write is journaled before application with prior bytes and expected resulting hashes. Partial file-write failure rolls back unchanged files. Undo validates all recorded file hashes/allowed paths before restoration, refuses changed files, and can recover a prepared partial operation. Only recorded newly created empty directories are removed; there is no recursive deletion. Existing user edits are preserved even when that means a manual recovery is required. Derived indexes and private operation journals remain after undo.

Undo also rechecks each file immediately before restoring it. A detected concurrent edit stops recovery; earlier files may already have been restored. Keep the journal for review. This is not an operating-system lock against concurrent writers.

## Current primary sources

- [Claude hooks, exec form](https://code.claude.com/docs/en/hooks)
- [OpenCode global rules](https://opencode.ai/docs/rules/) and [local plugins](https://opencode.ai/docs/plugins/)
- [Antigravity skill locations](https://www.antigravity.google/docs/skills)
- [Cursor project/user rules](https://cursor.com/help/customization/rules)
- [Upstream Skills CLI discovery implementation](https://github.com/vercel-labs/skills/blob/main/src/find.ts) and [skills.sh docs](https://www.skills.sh/docs)

Client versions and discovery APIs change; unsupported interfaces fail visibly or remain manual rather than being represented as universal automatic support.

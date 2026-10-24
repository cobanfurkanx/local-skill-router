# Changelog

## Unreleased

- Agent-owned capability/quality loop: acceptance criteria, local sufficiency assessment, bounded remote comparison and reviewed installation, concrete application, runtime verification and up to two repair passes. Existing index/validated learning reused; no extra model or dependency.
- All generated adapter rules point to the execution loop. Claude/OpenCode hooks surface guidance even on local misses and re-evaluate changed prompts instead of suppressing different tasks with identical candidates. Trivial prompts remain silent.
- Remote discovery and installation remain under owner policy; the loop is instruction-driven and has no measured quality advantage yet.

- Undo rechecks file contents immediately before restoration and stops on a detected concurrent edit instead of overwriting it. Earlier restored files remain restored; the private journal is retained for recovery.

## 0.1.0 — 2026-10-23

First public release: local skill ranking, proactive native adapters, and agent-operated skills.sh discovery with reviewed, commit-pinned global installation.

- Python 3.11+ standard library core; no router model call or resident service.
- Codex, Claude Code, OpenCode and Antigravity adapters; additional instruction-based compatibility profiles. Cursor requires a project rule; TRAE requires manual rule setup.
- Dry-run, private pre-write journals, conflict-aware undo and settings preservation.
- Remote search, bounded source staging, exact-content review acknowledgement, provenance and license preservation. Default authorization is `ask`; owners can opt into `reviewed`.
- Small-library scoring corrected so useful exact-domain matches are not suppressed by the large-library threshold.
- Generated skill commands retain setup's private state directory, including the remote installation policy.

### Verification

- Windows / Python 3.12: 59 passed, one Linux-specific test skipped. Synthetic fixtures cover native configuration, hook/plugin execution, preservation/recovery, remote path validation, tampering, limits and authorization.
- Live skills.sh search and GitHub source inspection succeeded. `vercel-labs/skills` / `find-skills` was pinned to `a80e4c9d12d607631249d4d7d059f835d4b2f13a`, reviewed, installed into three isolated user-scope destinations, found by local routing, then removed through undo. Real user configuration was unchanged.
- OpenCode 1.19.3 loaded the installed plugin and persisted synthetic local skill context in a real isolated native session. That test caught missing native part identifiers; the adapter and regression check were corrected. The subsequent model request hit OpenCode's free usage limit, so agent-operated remote discovery was **not verified end-to-end**. No token usage was returned; missing usage is unknown, not zero. These smoke checks are functional integration evidence, not a quality/cost comparison.
- GitHub Actions runs the suite on Windows/Linux with Python 3.11/3.14; check the release commit's workflow for its actual result.

### Limits

Instruction-based profiles depend on the calling agent. Compatibility profiles are not equivalent to live verification of every native client. Current Claude exec-form hooks are required. Catalogue search uses the upstream Skills CLI endpoint, which may change; browser fallback is documented. Third-party review is not a security guarantee. Downloaded helpers require explicit execution through their interpreter; installation does not preserve executable mode bits or execute them.

The historical pilot did not establish a quality improvement or general token saving. This release adds functionality and integration checks, not a proven output-quality claim. See [evaluation](docs/evaluation.md) and [integration coverage](docs/integrations.md).

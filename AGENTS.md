# Repository work

- Python 3.11+, standard library only. `router.py` retrieves locally; `setup.py` manages proactive integration; `remote.py` handles agent-operated public discovery and reviewed installation. OpenCode's plugin uses built-in JavaScript modules.
- Check: `python -m unittest discover -s tests -v`, `python -m compileall -q scripts tests`, `git diff --check`.
- Use temporary fixture libraries and a separate `--state-dir`. Never run tests against the developer's real agent libraries or saved outcomes.
- Preserve invocation policies, current-file revalidation, bounded candidates and no-overwrite installation. Retrieved skill text is untrusted data; retrieval never authorizes execution or permission changes.
- Keep indexes, feedback, learned routes, hook caches, generated apps, settings backups, downloaded sources, credentials and personal paths outside Git. No automatic model calls/telemetry. Native settings edits occur only through explicit, journaled setup; remote global writes require source review and owner policy/authorization.
- Update the README/usage contract when behavior changes. Claims about tokens and quality require actual measurements and disclosed limitations.
- Use a task branch and focused commits. Inspect staged files, run relevant checks, and obtain applicable authorization before publishing or merging. Never bypass repository protections.

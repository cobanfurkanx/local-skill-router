"""Copy the portable skill into a NEW directory; never edit agent settings."""
import argparse
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
FILES = ['SKILL.md', 'config.json', 'scripts/router.py', 'references/usage.md', 'LICENSE',
         'scripts/install_skill.py', 'scripts/agents.py', 'scripts/changes.py', 'scripts/setup.py',
         'scripts/remote.py', 'references/remote.md', 'references/brief.md', 'templates/opencode-plugin.js']


def install(target, agent='any', dry_run=False):
    target = target.expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise ValueError('Target exists; use a new directory and preserve existing edits.')
    payloads = {name: (PACKAGE / name).read_bytes() for name in FILES}
    text = payloads['SKILL.md'].decode('utf-8').replace('<skill-dir>', target.as_posix())
    payloads['SKILL.md'] = text.replace('--agent any', '--agent ' + agent).encode('utf-8')
    if not dry_run:
        # A failed copy leaves this new directory for inspection; it never removes user data.
        target.mkdir(parents=True, exist_ok=False)
        for name, payload in payloads.items():
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
    return [str(target / name) for name in FILES]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=Path, help='New skill directory, including local-skill-router')
    parser.add_argument('--agent', default='any', choices=['any', 'codex', 'claude', 'antigravity', 'opencode', 'hermes', 'cursor', 'copilot', 'openclaude', 'trae'])
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        files = install(args.target, args.agent, args.dry_run)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(('Would create:\n' if args.dry_run else 'Created:\n') + '\n'.join(files))


if __name__ == '__main__':
    main()

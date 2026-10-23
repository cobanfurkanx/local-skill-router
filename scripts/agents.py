"""Native paths; names identify integration profiles, not permission grants."""
from pathlib import Path

AGENTS = ('codex', 'claude', 'antigravity', 'opencode', 'hermes', 'copilot', 'cursor', 'openclaude', 'trae')


def locations(agent, home, project=None, env=None):
    env = env or {}
    codex = Path(env.get('CODEX_HOME') or home / '.codex')
    config = Path(env.get('OPENCODE_CONFIG_DIR') or Path(env.get('XDG_CONFIG_HOME') or home / '.config') / 'opencode')
    hermes = Path(env.get('HERMES_HOME') or home / '.hermes')
    profiles = {
        'codex': ([codex / 'skills'], codex / 'AGENTS.md', 'instruction'),
        'claude': ([home / '.claude/skills'], home / '.claude/CLAUDE.md', 'hook'),
        'antigravity': ([home / '.gemini/config/skills', home / '.gemini/antigravity-cli/skills'], home / '.gemini/GEMINI.md', 'instruction'),
        'opencode': ([config / 'skills'], config / 'AGENTS.md', 'plugin'),
        'hermes': ([hermes / 'skills'], hermes / 'SOUL.md', 'instruction'),
        'copilot': ([home / '.copilot/skills'], home / '.copilot/copilot-instructions.md', 'instruction'),
        'openclaude': ([home / '.openclaude/skills'], home / '.openclaude/CLAUDE.md', 'experimental-instruction'),
        'cursor': ([home / '.cursor/skills'], Path(project) / '.cursor/rules/local-skill-router.mdc' if project else None, 'project-rule'),
        'trae': ([home / '.trae/skills'], None, 'manual-rule'),
    }
    if agent not in profiles:
        raise ValueError('Unknown integration profile: ' + agent)
    return profiles[agent]

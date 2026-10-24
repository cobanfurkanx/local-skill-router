"""Install proactive native adapters, inspect status, or undo a recorded operation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import agents
import changes
import install_skill
import router

START = '<!-- local-skill-router:start -->'
END = '<!-- local-skill-router:end -->'


def section(before, body):
    text = before.decode('utf-8-sig') if before else ''
    if text.count(START) != text.count(END) or text.count(START) > 1:
        raise ValueError('Malformed managed section; preserve it for review.')
    block = START + '\n' + body + '\n' + END
    if START in text:
        first, last = text.index(START), text.index(END) + len(END)
        if first >= last:
            raise ValueError('Reversed managed section markers.')
        return (text[:first] + block + text[last:]).encode('utf-8')
    return (text.rstrip() + ('\n\n' if text.strip() else '') + block + '\n').encode('utf-8')


def rule(app, state, agent):
    command = f'python "{app.as_posix()}/scripts/router.py" --state-dir "{state.as_posix()}"'
    return (f'For substantial work, follow `{app.as_posix()}/SKILL.md`: define acceptance criteria, assess local capability gaps, apply skills, verify output and repair at most twice. '
            f'Reuse suitable loaded skills; otherwise run `{command} query "task + domain" --agent {agent} --text` or plan separate deliverables. '
            'A match is not sufficient capability. For a concrete gap, the calling agent compares up to three skills.sh candidates, reviews a pinned source, and installs globally only under owner policy. '
            'Never send raw conversations/secrets in remote queries. Session/project instructions and host permissions prevail.')


def adapter(app, state, agent):
    return ('---\nname: local-skill-router\ndescription: Assess capability gaps, select local or reviewed remote skills, apply them and verify task output with bounded repairs.\n---\n\n'
            + rule(app, state, agent) + '\n').encode('utf-8')


def plan(home, state, selected, project=None, env=None, remote_policy=None):
    payloads = {name: (install_skill.PACKAGE / name).read_bytes() for name in install_skill.FILES}
    config = json.loads(payloads['config.json'])
    config['roots'] = [{'path':str(home / '.agents/skills'), 'source':'shared', 'agents':['any']}]
    for profile in agents.AGENTS:
        for folder in agents.locations(profile, home, project, env)[0]:
            config['roots'].append({'path':str(folder), 'source':profile,
                                    'agents':['codex'] if profile == 'codex' else ['any']})
    payloads['config.json'] = json.dumps(config, indent=2).encode()
    identity = hashlib.sha256(b''.join(name.encode() + payload for name, payload in sorted(payloads.items()))).hexdigest()[:16]
    app = state / 'apps' / identity
    planned = {}
    roots = [home, state] + ([project] if project else [])

    def put(path, after):
        before = changes.current(path)
        planned[path] = (path, before, after)

    for name, payload in payloads.items():
        if name == 'SKILL.md':
            payload = payload.replace(b'<skill-dir>', app.as_posix().encode())
            for helper in ('router', 'remote'):
                command = f'{app.as_posix()}/scripts/{helper}.py"'
                payload = payload.replace(command.encode(), (command + f' --state-dir "{state.as_posix()}"').encode())
            payload += f'\nConfigured private state: `{state.as_posix()}`. Keep this `--state-dir` in every helper command, including commands from reference examples.\n'.encode()
        put(app / name, payload)
    policy_path = state / 'remote-policy.json'
    if remote_policy is not None or not policy_path.exists():
        put(policy_path, (json.dumps({'global_install':remote_policy or 'ask'}) + '\n').encode())
    profiles = []
    for agent in dict.fromkeys(selected):
        skill_roots, instructions, mode = agents.locations(agent, home, project, env)
        if agent == 'cursor' and project is None:
            raise ValueError('Cursor requires --project PATH for its supported always-apply rule; global GUI rules are not edited.')
        for skill_root in skill_roots:
            roots.append(skill_root)
            target = skill_root / 'local-skill-router/SKILL.md'
            before = changes.current(target)
            if before is not None and b'name: local-skill-router' not in before:
                raise ValueError('Existing unrelated skill directory: ' + str(target))
            put(target, adapter(app, state, agent))
            put(target.parent / 'LICENSE', payloads['LICENSE'])
        if instructions is not None:
            roots.append(instructions.parent)
            before = changes.current(instructions)
            if mode == 'project-rule' and before is None:
                before = b'---\ndescription: "Local specialist skill discovery"\nalwaysApply: true\n---\n'
            updated = section(before, rule(app, state, agent))
            put(instructions, updated)
        if agent == 'claude':
            settings_path = home / '.claude/settings.json'
            before = changes.current(settings_path)
            settings = json.loads(before.decode('utf-8-sig')) if before else {}
            if not isinstance(settings, dict):
                raise ValueError('Claude settings must be a JSON object.')
            hooks = settings.setdefault('hooks', {})
            if not isinstance(hooks, dict):
                raise ValueError('Claude hooks must be a JSON object; no files changed.')
            events = hooks.setdefault('UserPromptSubmit', [])
            if not isinstance(events, list):
                raise ValueError('Claude UserPromptSubmit hooks must be an array.')
            for event in events:
                if not isinstance(event, dict) or not isinstance(event.get('hooks'), list):
                    raise ValueError('Invalid existing Claude hook; no settings repaired automatically.')
                if not all(isinstance(h,dict) for h in event['hooks']):
                    raise ValueError('Invalid existing Claude handler; no files changed.')
                event['hooks'] = [h for h in event['hooks'] if not (isinstance(h.get('args'), list) and
                    any(str(state / 'apps') in str(a) and str(a).endswith('router.py') for a in h['args']))]
            events[:] = [event for event in events if event['hooks']]
            # Current Claude exec-form hooks avoid shell interpolation on every OS.
            events.append({'hooks':[{'type':'command', 'command':sys.executable,
                          'args':[str(app / 'scripts/router.py'), '--state-dir', str(state), 'hook', '--agent', 'claude'],
                          'timeout':8}]})
            put(settings_path, (json.dumps(settings, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        if agent == 'opencode':
            plugin = instructions.parent / 'plugins/local-skill-router.js'
            argv = [sys.executable, str(app / 'scripts/router.py'), '--state-dir', str(state), 'hook', '--agent', 'opencode']
            put(plugin, payloads['templates/opencode-plugin.js'].replace(b'__ROUTER_ARGV__', json.dumps(argv).encode()))
        profiles.append({'agent':agent, 'mode':mode, 'instructions':str(instructions) if instructions else None})
    return list(planned.values()), roots, app, profiles


def install(home, state, selected, project=None, env=None, dry_run=False, remote_policy=None):
    planned, roots, app, profiles = plan(home, state, selected, project, env, remote_policy)
    if dry_run:
        return {'dry_run':True, 'profiles':profiles, 'changes':[str(p) for p, before, after in planned if before != after]}
    result = changes.apply(state, planned, roots, 'setup')
    with_base = router.BASE
    try:
        router.BASE = state
        config = router.load_config(app / 'config.json')
        index = router.build_index(config)
    finally:
        router.BASE = with_base
    return dict(result, app=str(app), profiles=profiles, indexed_files=len(index['records']), index_errors=len(index['errors']),
                next_step='Restart the selected client sessions. TRAE needs its manual rule; Cursor rules apply to the selected project.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, help='Alternate user home for isolated testing')
    parser.add_argument('--state-dir', type=Path, default=router.BASE)
    parser.add_argument('--project', type=Path, help='Required for Cursor project rules; also needed when undoing that operation')
    commands = parser.add_subparsers(dest='command', required=True)
    installing = commands.add_parser('install')
    installing.add_argument('--agent', action='append', choices=agents.AGENTS, required=True)
    installing.add_argument('--dry-run', action='store_true')
    installing.add_argument('--remote-policy', choices=['ask','reviewed'], help='reviewed authorizes the agent to install digest-reviewed third-party skills globally; ask requires per-install authorization')
    undoing = commands.add_parser('undo')
    undoing.add_argument('operation')
    commands.add_parser('doctor')
    args = parser.parse_args()
    home = (args.home or Path.home()).expanduser().resolve()
    state = args.state_dir.expanduser().resolve()
    project = args.project.expanduser().resolve() if args.project else None
    env = {} if args.home else os.environ
    try:
        if args.command == 'install':
            result = install(home, state, args.agent, project, env, args.dry_run, args.remote_policy)
        elif args.command == 'undo':
            roots = [home, state] + ([project] if project else [])
            for agent in agents.AGENTS:
                skill_roots, instructions, _ = agents.locations(agent, home, project, env)
                roots.extend(skill_roots)
                if instructions:
                    roots.append(instructions.parent)
            result = changes.undo(state, args.operation, roots)
        else:
            result = {'python':sys.version.split()[0], 'state_dir':str(state), 'index_exists':(state / 'index.json').is_file(),
                      'profiles':[{'agent':agent, 'mode':mode, 'skill_present':all((r / 'local-skill-router/SKILL.md').is_file() for r in roots),
                                   'rule_present':bool(path and path.is_file() and START in path.read_text(encoding='utf-8-sig'))}
                                  for agent in agents.AGENTS for roots,path,mode in [agents.locations(agent,home,project,env)]]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()

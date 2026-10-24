"""Local, dependency-free skill retrieval. Never executes retrieved skills."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import unicodedata

PACKAGE = Path(__file__).resolve().parents[1]
BASE = Path(os.environ.get('SKILL_ROUTER_STATE_DIR') or
            str(Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'local-skill-router')).expanduser()
VERSION = 2
RELEASE = '0.1.0'
WORKFLOW = ('For product builds/redesigns, infer a product brief before retrieval, even when design is unspecified; use plan --brief-file. '
            'Assess each deliverable against acceptance criteria; a match is not proof of sufficient capability. '
            'For concrete gaps, follow ' + (PACKAGE / 'SKILL.md').as_posix() +
            ': compare bounded remote candidates under owner policy, apply selected workflows, verify output and repair at most twice.')
STOP = set('a an the and or to of for with in on from use when using is are this that your you it as be by at into can should user task work needs need yapmak yap bir bu su ve ile icin olan olarak bana benim sen sana nasil lutfen simdi istiyorum olsun et yapar misin mi dosya'.split())


def normalize(value):
    value = str(value).lower().replace('ı', 'i')
    return ''.join(c for c in unicodedata.normalize('NFKD', value) if not unicodedata.combining(c))


def tokens(value):
    return [t for t in re.findall(r'[a-z0-9]+', normalize(value)) if len(t) > 1 and t not in STOP]


def load_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return fallback


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, separators=(',', ':'))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def state_lock():
    """Serialize outcome writes from different local agents."""
    BASE.mkdir(parents=True, exist_ok=True)
    lock = BASE / '.learning.lock'
    deadline = time.monotonic() + 4
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if lock.exists() and time.time() - lock.stat().st_mtime > 60:
                try:
                    lock.unlink()
                except FileNotFoundError:
                    pass
            elif time.monotonic() >= deadline:
                raise RuntimeError('Learning state is busy; retry later.')
            else:
                time.sleep(0.05)
    try:
        yield
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def frontmatter(text):
    match = re.match(r'^---\s*\n(.*?)\n---\s*(?:\n|$)', text, re.S)
    if not match:
        return {}, text
    lines = match.group(1).splitlines()
    data = {}
    for i, line in enumerate(lines):
        item = re.match(r'^([\w-]+):\s*(.*)$', line)
        if not item:
            continue
        key, value = item.groups()
        if value in ('', '|', '>', '|-', '>-', '|+', '>+'):
            continuation = []
            for following in lines[i + 1:]:
                if following and not following[0].isspace():
                    break
                continuation.append(following.strip())
            value = ' '.join(continuation)
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                value = value.strip('"')
        elif value.startswith("'"):
            value = value.strip("'").replace("''", "'")
        data[key] = value
    # Product invocation policy is nested in agents/openai.yaml, not frontmatter.
    return data, text[match.end():]


def walk_skills(root):
    """Follow shared directory links, break cycles, avoid unrelated code trees."""
    if not root.is_dir():
        return
    visited = set()
    for folder, dirs, files in os.walk(root, followlinks=True):
        try:
            stat = os.stat(folder)
        except OSError:
            dirs[:] = []
            continue
        real = (stat.st_dev, stat.st_ino) if stat.st_ino else str(Path(folder).resolve()).casefold()
        if real in visited:
            dirs[:] = []
            continue
        visited.add(real)
        dirs[:] = sorted(d for d in dirs if d not in
                         {'.git', 'node_modules', '__pycache__', '.venv', 'backups'})
        if 'SKILL.md' in files:
            yield Path(folder) / 'SKILL.md'
        elif 'SKILL.routed.md' in files:
            yield Path(folder) / 'SKILL.routed.md'


def parse_skill(path, root):
    try:
        text = path.read_text(encoding='utf-8-sig').replace('\r\n', '\n')
        stat = path.stat()
    except (OSError, UnicodeError):
        return None
    metadata, body = frontmatter(text)
    name = str(metadata.get('name') or path.parent.name).strip()
    if name in {'auto-skill-router', 'local-skill-router'}:
        return None
    description = str(metadata.get('description') or '').strip()
    if not description:
        description = ' '.join(line.strip('# ') for line in body.splitlines() if line.strip())[:400]
    policy = path.parent / 'agents' / 'openai.yaml'
    policy_text = policy.read_text(encoding='utf-8-sig') if policy.is_file() else ''
    explicit = normalize(metadata.get('disable-model-invocation', 'false')) in {'true', 'yes', 'on', '1'}
    explicit |= bool(re.search(r'allow_implicit_invocation:\s*false\b', policy_text, re.I))
    headings = ' '.join(re.findall(r'^#{1,3}\s+(.+)$', body, re.M))[:1400]
    requirements = []
    # Only clear dependencies are extracted; the consuming agent checks actual tools.
    for line in text.splitlines():
        if re.search(r'\b(requires?|prerequisites?|must be configured)\b', line, re.I):
            cleaned = line.strip('# *-')
            if len(cleaned) <= 350:
                requirements.append(cleaned)
    if root.get('runtime'):
        requirements.insert(0, 'Provider runtime: ' + root['runtime'])
    return {
        'name': name, 'description': description[:1600], 'headings': headings,
        'digest': hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'explicit_only': explicit, 'requirements': requirements[:3],
        'path': str(path), 'source': root['source'], 'agents': root.get('agents', ['any']),
        'runtime': root.get('runtime'), 'mtime_ns': stat.st_mtime_ns, 'bytes': stat.st_size,
        'policy_mtime_ns': policy.stat().st_mtime_ns if policy.is_file() else None,
        'terms': dict(Counter(tokens(name) * 4 + tokens(description[:1600]) * 2 + tokens(headings))),
    }


def build_index(config, cache_path=None):
    cache_path = cache_path or BASE / 'index.json'
    previous = load_json(cache_path, {})
    old = {r['path']: r for r in previous.get('records', [])}
    records, errors, counts = [], [], {}
    seen = set()
    for root in config['roots']:
        count = 0
        for path in walk_skills(Path(os.path.expandvars(os.path.expanduser(root['path'])))):
            key = os.path.normcase(str(path))
            if key in seen:
                continue
            seen.add(key)
            try:
                stat = path.stat()
                policy = path.parent / 'agents' / 'openai.yaml'
                policy_time = policy.stat().st_mtime_ns if policy.is_file() else None
                cached = old.get(str(path))
                if previous.get('version') == VERSION and cached and cached['mtime_ns'] == stat.st_mtime_ns and cached['bytes'] == stat.st_size and cached.get('policy_mtime_ns') == policy_time and cached['source'] == root['source']:
                    record = dict(cached, agents=root.get('agents', ['any']), runtime=root.get('runtime'))
                else:
                    record = parse_skill(path, root)
                if record:
                    records.append(record)
                    count += 1
            except (OSError, UnicodeError) as error:
                errors.append({'path': str(path), 'error': type(error).__name__})
        counts[root['source']] = counts.get(root['source'], 0) + count
    index = {'version': VERSION, 'built_at': time.time(), 'config_digest': hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
             'records': records, 'counts': counts, 'errors': errors}
    atomic_json(cache_path, index)
    return index


def get_index(config):
    index = load_json(BASE / 'index.json', {})
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    if index.get('version') != VERSION or index.get('config_digest') != digest or time.time() - index.get('built_at', 0) > config.get('max_age_seconds', 3600):
        index = build_index(config)
    return index


def project_records(cwd):
    if not cwd:
        return []
    cwd = Path(cwd).resolve()
    boundary = next((p for p in [cwd, *cwd.parents] if (p / '.git').exists()), cwd)
    chain = []
    current = cwd
    while True:
        chain.append(current)
        if current == boundary:
            break
        current = current.parent
    records = []
    for folder in chain:
        for relative in ['.agents/skills', '.claude/skills', '.hermes/skills', '.openclaude/skills', '.opencode/skills', '.agent/skills', '.cursor/skills', '.github/skills', '.copilot/skills', '.trae/skills']:
            root = {'source': 'project', 'agents': ['any']}
            for path in walk_skills(folder / relative):
                record = parse_skill(path, root)
                if record:
                    records.append(record)
    return records


def expanded_query(query, config):
    original = tokens(query)
    normalized = ' '.join(original)
    weights = {token: 1.0 for token in original}
    for rule in matching_rules(query, config):
        if rule:
            for token in tokens(rule['expand']):
                weights[token] = max(weights.get(token, 0), 0.7)
    return weights


def matches_phrase(term, normalized):
    pattern = re.escape(normalize(term)).replace(r'\*', r'\w*')
    return bool(re.search(r'\b' + pattern + r'\b', normalized))


def matching_rules(query, config):
    normalized = ' '.join(tokens(query))
    return [rule for rule in config.get('aliases', [])
            if any(matches_phrase(term, normalized) for term in rule['match'])
            and not any(matches_phrase(term, normalized) for term in rule.get('exclude', []))]


def compatible(record, agent):
    return agent == 'any' or 'any' in record['agents'] or agent in record['agents']


def choose_records(records, agent, explicit):
    # Same logical name loads once. Different authored variants stay in the index.
    groups = {}
    explicit = {normalize(name) for name in explicit}
    preference = {'project': 10, 'shared': 8, agent: 9, 'hermes-legacy': 5}
    for record in records:
        if not compatible(record, agent):
            continue
        # Hooks reuse the index; invocation policy and selected text must stay current.
        path = Path(record['path'])
        try:
            stat = path.stat()
            policy = path.parent / 'agents' / 'openai.yaml'
            policy_time = policy.stat().st_mtime_ns if policy.is_file() else None
            if (record.get('mtime_ns'), record.get('bytes'), record.get('policy_mtime_ns')) != (stat.st_mtime_ns, stat.st_size, policy_time):
                record = parse_skill(path, record)
        except (OSError, UnicodeError):
            continue
        if not record or (record['explicit_only'] and normalize(record['name']) not in explicit):
            continue
        priority = preference.get(record['source'], 6)
        # Shared cross-agent sources take precedence over opaque provider caches.
        if record.get('runtime'):
            priority -= 2
        key = normalize(record['name'])
        existing = groups.get(key)
        if not existing or priority > existing[0] or (priority == existing[0] and record['path'] > existing[1]['path']):
            groups[key] = (priority, record)
    return [item[1] for item in groups.values()]


def feedback_adjustment(skill, query_tokens, feedback):
    values = []
    for event in feedback:
        if event.get('skill') != skill:
            continue
        recorded = set(event.get('tokens', []))
        if len(recorded & query_tokens) / max(1, len(recorded | query_tokens)) >= 0.25:
            values.append(1 if event['outcome'] == 'helpful' else -1)
    # Evidence only nudges matching; it never manufactures relevance.
    return max(-0.15, min(0.15, sum(values) / max(5, len(values)) * 0.15))


def project_boundary(cwd):
    current = Path(cwd).resolve()
    return next((p for p in [current, *current.parents] if (p / '.git').exists()), current)


def learned_matches(query_weights, records, agent, cwd):
    saved = load_json(BASE / 'learned-routes.json', {'routes': []})
    result = {}
    by_name = {normalize(record['name']):record for record in records}
    query_set = set(query_weights)
    for route in saved.get('routes', []):
        if route.get('project') and (not cwd or route['project'] != str(project_boundary(cwd))):
            continue
        recorded = set(route.get('tokens', []))
        similarity = len(recorded & query_set) / max(1, len(recorded), len(query_set))
        if similarity < 0.68:
            continue
        for skill in route['skills']:
            name = normalize(skill['name'])
            record = by_name.get(name)
            if not record or record['digest'] != skill['digest']:
                continue
            try:
                current_text = Path(record['path']).read_text(encoding='utf-8-sig').replace('\r\n','\n')
            except (OSError, UnicodeError):
                continue
            if hashlib.sha256(current_text.encode('utf-8')).hexdigest() != skill['digest']:
                continue
            result[name] = max(result.get(name, 0), similarity)
    return result


def learn(task, names, agent, cwd, scope, evidence, config, index):
    available = choose_records(index['records'] + project_records(cwd), agent, explicit=names)
    by_name = {normalize(r['name']):r for r in available}
    selected = []
    for name in names:
        record = by_name.get(normalize(name))
        if not record:
            raise ValueError('Unknown or incompatible skill: ' + name)
        # Save the content actually present after the task, not an old catalogue hash.
        root = {'source':record['source'],'agents':record['agents'],'runtime':record.get('runtime')}
        current = parse_skill(Path(record['path']), root)
        if not current:
            raise ValueError('Unreadable skill: ' + name)
        selected.append({'name':current['name'],'digest':current['digest'],'path':current['path']})
    query_tokens = sorted(expanded_query(task, config))
    project = str(project_boundary(cwd)) if scope == 'project' else None
    key = hashlib.sha256(json.dumps([query_tokens,project]).encode()).hexdigest()[:20]
    route = {'key':key,'tokens':query_tokens,'project':project,'skills':selected,'agent':agent,
             'saved_at':time.time(),'evidence':evidence[:500]}
    with state_lock():
        state = load_json(BASE / 'learned-routes.json', {'version':1,'routes':[]})
        state['routes'] = [r for r in state['routes'] if r['key'] != key] + [route]
        state['routes'] = state['routes'][-200:]
        atomic_json(BASE / 'learned-routes.json',state)
    return {'saved':True,'skills':[r['name'] for r in selected],'scope':scope}


def prepare_search(index, agent, cwd, explicit):
    all_records = index['records'] + project_records(cwd)
    records = choose_records(all_records, agent, explicit)
    weighted, df = [], Counter()
    for record in records:
        counts = Counter(record.get('terms') or tokens(record['name']) * 4 + tokens(record['description']) * 2 + tokens(record['headings']))
        weighted.append(counts)
        df.update(counts.keys())
    avg = sum(sum(c.values()) for c in weighted) / max(1, len(records))
    return all_records, records, weighted, df, avg


def search(query, config, index, agent='any', cwd=None, limit=3, explicit=(), feedback=(), prepared=None):
    normalized_query = normalize(query).strip(' ?.!')
    if any(re.fullmatch(pattern, normalized_query) for pattern in config.get('skip_patterns', [])):
        return {'agent': agent, 'candidates': [], 'trivial': True, 'instruction': 'Trivial task: answer directly.'}
    all_records, records, weighted, df, avg = prepared or prepare_search(index, agent, cwd, explicit)
    query_weights = expanded_query(query, config)
    learned = learned_matches(query_weights, records, agent, cwd)
    exact_saved = [record for record in records if learned.get(normalize(record['name']),0) >= 0.98]
    if exact_saved:
        # A verified equivalent route avoids rebuilding/ranking the whole corpus.
        return {'agent':agent,'candidates':[
                    {'name':record['name'],'path':record['path'],'score':None,
                     'description':record['description'][:320],'matched':[],
                     'requirements':record['requirements'],'source':record['source'],
                     'reused_successful_route':True,'estimated_tokens':math.ceil(record['bytes']/4)}
                    for record in exact_saved[:max(1,min(limit,5))]],
                'learned_matches':len(exact_saved),'fast_path':True,
                'instruction':WORKFLOW + ' Reused task-type route; validate this output separately.',
                'indexed_names':len({normalize(r['name']) for r in all_records})}
    preferred = {normalize(name) for rule in matching_rules(query, config) for name in rule.get('prefer', [])}
    ranked = []
    for record, counts in zip(records, weighted):
        score, matched = 0.0, []
        for term, weight in query_weights.items():
            tf = counts[term]
            if not tf:
                continue
            idf = math.log(1 + (len(records) - df[term] + 0.5) / (df[term] + 0.5))
            score += weight * idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * sum(counts.values()) / max(1, avg)))
            matched.append(term)
        name = normalize(record['name'])
        if name in normalize(query):
            score += 10
        if not matched:
            continue
        if name in preferred:
            score += 12
        if name in learned:
            score += 30 * learned[name]
        specificity = len(set(tokens(record['name'])) & set(query_weights))
        score *= 1 + min(0.25, specificity * 0.06)
        if record['source'] == 'project':
            score *= 1.12
        score *= 1 + feedback_adjustment(record['name'], set(query_weights), feedback)
        ranked.append((score, record, matched))
    ranked.sort(key=lambda entry: (-entry[0], entry[1]['name']))
    top = ranked[0][0] if ranked else 0
    candidates = []
    seen_digests = set()
    # BM25 IDF shrinks in tiny personal libraries; the large-corpus cutoff must shrink too.
    minimum = config.get('min_score', 3.5) * min(1, math.log1p(len(records)) / math.log(50))
    for score, record, matched in ranked:
        if score < minimum or score < top * config.get('relative_threshold', 0.38):
            continue
        if record['digest'] in seen_digests:
            continue
        seen_digests.add(record['digest'])
        name = normalize(record['name'])
        candidates.append({'name': record['name'], 'path': record['path'], 'score': round(score, 2),
                           'description': record['description'][:320], 'matched': matched[:8],
                           'requirements': record['requirements'], 'source': record['source'],
                           'reused_successful_route': name in learned,
                           'estimated_tokens': math.ceil(record['bytes'] / 4)})
        if len(candidates) >= max(1, min(limit, 5)):
            break
    return {'agent': agent, 'candidates': candidates, 'learned_matches':len(learned),
            'instruction': WORKFLOW + ' Candidates only; verify tools and invocation policies.',
            'indexed_names': len({normalize(r['name']) for r in all_records})}


def read_feedback():
    path = BASE / 'feedback.jsonl'
    events = []
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines()[-1000:]:
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
    return events


def hook_changed(event, result, agent, config):
    """Suppress duplicate suggestions, never skill reads or permission checks."""
    session = event.get('session_id')
    cache = config.get('hook_cache_dir')
    if not isinstance(session, str) or not session or not cache:
        return True
    key = hashlib.sha256(json.dumps([agent, session, event.get('cwd')]).encode()).hexdigest()
    path = Path(cache) / (key + '.json')
    try:
        signature = hashlib.sha256(json.dumps([normalize(event.get('prompt', '')), [
            [c['path'], hashlib.sha256(Path(c['path']).read_bytes()).hexdigest()]
            for c in result['candidates']]]).encode()).hexdigest()
        previous = load_json(path, {})
        now = time.time()
        if previous.get('signature') == signature and 0 <= now - previous.get('time', 0) < 900:
            return False
        atomic_json(path, {'signature': signature, 'time': now})
    except (OSError, ValueError):
        return True
    return True


def plan(tasks, config, index, agent='any', cwd=None, explicit=(), feedback=()):
    """Retrieve each agent-defined deliverable separately, sharing duplicate reads."""
    if not tasks or len(tasks) > 8 or any(not isinstance(task, str) or not task.strip() for task in tasks):
        raise ValueError('Provide 1-8 non-empty task strings.')
    steps, reads = [], {}
    prepared = prepare_search(index, agent, cwd, explicit)
    for task in dict.fromkeys(task.strip() for task in tasks):
        result = search(task, config, index, agent, cwd, explicit=explicit, feedback=feedback, prepared=prepared)
        candidates = result['candidates']
        steps.append({'task': task, 'candidates': candidates,
                      'status': 'review_candidates' if candidates else 'no_match'})
        if candidates:
            first = candidates[0]
            entry = reads.setdefault(first['path'], dict(first, tasks=[]))
            entry['tasks'].append(task)
    return {'agent': agent, 'steps': steps, 'suggested_reads': list(reads.values()),
            'estimated_tokens': sum(c['estimated_tokens'] for c in reads.values()),
            'instruction': WORKFLOW + ' Provisional first choices, not automatic invocation; learn only after output validation.'}


def plan_brief(brief, config, index, agent='any', cwd=None, explicit=(), feedback=()):
    """Route agent-inferred needs; validate structure, never claim semantic judgment."""
    def text(value):
        return isinstance(value, str) and 0 < len(value.strip()) <= 1000

    def strings(value, minimum=0):
        return isinstance(value, list) and minimum <= len(value) <= 8 and all(text(v) for v in value)

    required = {'product', 'users', 'jobs', 'constraints', 'assumptions', 'interface', 'needs'}
    if not isinstance(brief, dict) or not required <= brief.keys() or brief.keys() - required - {'design'}:
        raise ValueError('Brief requires product, users, jobs, constraints, assumptions, interface and needs; optional design.')
    if not all(text(brief[k]) for k in ('product', 'users')) or not strings(brief['jobs'], 1):
        raise ValueError('Brief needs a product, users and 1-8 primary jobs.')
    if not all(strings(brief[k]) for k in ('constraints', 'assumptions')) or type(brief['interface']) is not bool:
        raise ValueError('constraints/assumptions must be string arrays; interface must be boolean.')
    design = brief.get('design')
    if brief['interface'] or design is not None:
        if (not isinstance(design, dict) or set(design) != {'direction', 'reason', 'avoid'}
                or not text(design['direction']) or not text(design['reason']) or not strings(design['avoid'], 1)):
            raise ValueError('Interface briefs require design: direction, product-specific reason, and avoid (1-8 strings).')
    needs = brief['needs']
    if not isinstance(needs, list) or not 1 <= len(needs) <= 8:
        raise ValueError('Provide 1-8 brief needs.')
    for need in needs:
        if (not isinstance(need, dict) or set(need) != {'query', 'reason', 'acceptance'}
                or not text(need['query']) or not text(need['reason']) or not strings(need['acceptance'], 1)):
            raise ValueError('Each need requires query, reason and 1-8 observable acceptance criteria.')
    result = plan([n['query'] for n in needs], config, index, agent, cwd, explicit, feedback)
    by_query = {step['task']: step for step in result['steps']}
    result['steps'] = [dict(by_query[n['query'].strip()], reason=n['reason'], acceptance=n['acceptance']) for n in needs]
    result['brief'] = {k: v for k, v in brief.items() if k != 'needs'}
    result['instruction'] += ' Brief assumptions and design rationale are agent-authored, not independently verified. Coverage still requires content review.'
    return result


def render(result, verbose=False):
    if 'brief' in result:
        brief = result['brief']
        lines = ['Product: ' + brief['product'], 'Users: ' + brief['users'],
                 'Primary jobs: ' + '; '.join(brief['jobs']),
                 'Constraints: ' + ('; '.join(brief['constraints']) or 'none stated'),
                 'Assumptions (verify): ' + ('; '.join(brief['assumptions']) or 'none')]
        if brief.get('design'):
            design = brief['design']
            lines += ['Design: ' + design['direction'], 'Why: ' + design['reason'], 'Avoid: ' + '; '.join(design['avoid'])]
        for step in result['steps']:
            lines += ['Need: ' + step['task'] + ' | Why: ' + step['reason'], 'Verify: ' + '; '.join(step['acceptance'])]
        lines.append(render({k: v for k, v in result.items() if k != 'brief'}, verbose))
        return '\n'.join(lines)
    if result.get('trivial'):
        return result['instruction']
    if not verbose:
        lines = [WORKFLOW, 'Candidates, not automatic invocation. Read relevant files; verify tools.']
        steps = result.get('steps', [result])
        unique = {}
        for step in steps:
            ids = []
            for candidate in step['candidates']:
                if candidate['path'] not in unique:
                    unique[candidate['path']] = (len(unique) + 1, candidate)
                ids.append(str(unique[candidate['path']][0]))
            if 'task' in step:
                lines.append('Task: ' + step['task'] + ' -> ' + (','.join(ids) or 'no match'))
        for number, candidate in unique.values():
            description = candidate['description']
            if len(description) > 110:
                description = description[:107] + '...'
            lines.append(f"{number}. {candidate['name']} | {candidate['path']} | {description}")
            if candidate['requirements']:
                lines.append('Check: ' + '; '.join(candidate['requirements']))
        if not unique:
            lines.append('No match. Refine the task or continue without a skill.')
        return '\n'.join(lines)
    if 'steps' in result:
        lines = [result['instruction']]
        for step in result['steps']:
            lines.extend(['\nTask: ' + step['task'], render(step, verbose=True)])
        lines.append('\nSuggested unique reads: ' + str(len(result['suggested_reads'])) +
                     '; approximate tokens: ' + str(result['estimated_tokens']))
        return '\n'.join(lines)
    lines = [WORKFLOW, 'Skill candidates (verify relevance and tool availability):']
    for candidate in result['candidates']:
        lines.append(f"- {candidate['name']} | {candidate['path']} | {candidate['description']}")
        if candidate['requirements']:
            lines.append('  Check: ' + '; '.join(candidate['requirements']))
    if not result['candidates']:
        lines.append('No strong match. Continue normally or retry with precise English task terms.')
    return '\n'.join(lines)


def load_config(path):
    """Validate local JSON and resolve relative paths against its containing directory."""
    config = load_json(path, None)
    if not isinstance(config, dict) or not isinstance(config.get('roots'), list):
        raise ValueError('Config must be a JSON object with a roots array.')
    for root in config['roots']:
        if not isinstance(root, dict) or not all(isinstance(root.get(k), str) and root[k].strip() for k in ('path', 'source')):
            raise ValueError('Each root needs nonempty path and source strings.')
        agents = root.get('agents', ['any'])
        if not isinstance(agents, list) or not agents or not all(isinstance(a, str) and a for a in agents):
            raise ValueError('Root agents must be a nonempty array of strings.')
        if root.get('runtime') is not None and not isinstance(root['runtime'], str):
            raise ValueError('Root runtime must be a string.')
        expanded = Path(os.path.expandvars(os.path.expanduser(root['path'])))
        root['path'] = str((expanded if expanded.is_absolute() else path.resolve().parent / expanded).resolve())
    for name, default in [('min_score', 4.2), ('relative_threshold', 0.4), ('max_age_seconds', 3600)]:
        value = config.get(name, default)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
            raise ValueError(name + ' must be a finite nonnegative number.')
    aliases = config.get('aliases', [])
    if not isinstance(aliases, list):
        raise ValueError('aliases must be an array.')
    for rule in aliases:
        if not isinstance(rule, dict) or not isinstance(rule.get('expand'), str):
            raise ValueError('Each alias needs an expand string.')
        for key in ('match', 'exclude', 'prefer'):
            values = rule.get(key, [])
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise ValueError('Alias ' + key + ' must be an array of strings.')
        if not rule.get('match'):
            raise ValueError('Each alias needs at least one match.')
    patterns = config.get('skip_patterns', [])
    if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
        raise ValueError('skip_patterns must be an array of regular-expression strings.')
    try:
        for pattern in patterns:
            re.compile(pattern)
    except re.error as error:
        raise ValueError('Invalid skip pattern: ' + str(error)) from error
    cache = config.get('hook_cache_dir')
    if cache is not None and not isinstance(cache, str):
        raise ValueError('hook_cache_dir must be a path string.')
    cache_path = Path(os.path.expandvars(os.path.expanduser(cache))) if cache else BASE / 'hooks'
    config['hook_cache_dir'] = str(cache_path if cache_path.is_absolute() else path.resolve().parent / cache_path)
    return config


def main():
    global BASE
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version='local-skill-router ' + RELEASE)
    parser.add_argument('--config', type=Path, default=PACKAGE / 'config.json')
    parser.add_argument('--state-dir', type=Path, default=BASE, help='Local index and opt-in feedback directory')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('refresh')
    commands.add_parser('stats')
    query = commands.add_parser('query')
    query.add_argument('task', nargs='?', default='')
    query.add_argument('--task-file', type=Path)
    query.add_argument('--agent', default='any')
    query.add_argument('--cwd', default=os.getcwd())
    query.add_argument('--limit', type=int, default=3)
    query.add_argument('--explicit', action='append', default=[])
    query.add_argument('--text', action='store_true')
    query.add_argument('--verbose', action='store_true', help='Full candidate descriptions with --text')
    planning = commands.add_parser('plan', help='Route distinct deliverables separately')
    inputs = planning.add_mutually_exclusive_group()
    inputs.add_argument('--task', action='append', default=[])
    inputs.add_argument('--task-file', type=Path, help='UTF-8 JSON array of task strings')
    inputs.add_argument('--brief-file', type=Path, help='Agent-authored product brief JSON, at most 32 KiB; see references/brief.md')
    planning.add_argument('--agent', default='any')
    planning.add_argument('--cwd', default=os.getcwd())
    planning.add_argument('--explicit', action='append', default=[])
    planning.add_argument('--text', action='store_true')
    planning.add_argument('--verbose', action='store_true')
    hook = commands.add_parser('hook')
    hook.add_argument('--agent', required=True)
    record = commands.add_parser('record')
    record.add_argument('--skill', required=True)
    record.add_argument('--outcome', choices=['helpful', 'unhelpful'], required=True)
    record.add_argument('--task', required=True)
    learning = commands.add_parser('learn')
    learning.add_argument('--task', required=True, help='Generic task type, not raw conversation or secrets')
    learning.add_argument('--skill', action='append', required=True)
    learning.add_argument('--agent', default='any')
    learning.add_argument('--cwd', default=os.getcwd())
    learning.add_argument('--scope', choices=['global','project'], default='global')
    learning.add_argument('--evidence', required=True, help='Observed validation or why the workflow helped')
    args = parser.parse_args()
    BASE = args.state_dir.expanduser().resolve()
    try:
        config = load_config(args.config)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.command == 'record':
        query_tokens = set(expanded_query(args.task, config))
        with state_lock():
            with (BASE / 'feedback.jsonl').open('a', encoding='utf-8') as handle:
                handle.write(json.dumps({'time': time.time(), 'skill': args.skill, 'outcome': args.outcome,
                                         'tokens': sorted(query_tokens)[:80]}) + '\n')
            if args.outcome == 'unhelpful':
                state = load_json(BASE / 'learned-routes.json', {'version':1,'routes':[]})
                for route in state['routes']:
                    recorded = set(route['tokens'])
                    if len(recorded & query_tokens) / max(1,len(recorded | query_tokens)) >= 0.25:
                        route['skills'] = [r for r in route['skills'] if normalize(r['name']) != normalize(args.skill)]
                state['routes'] = [r for r in state['routes'] if r['skills']]
                atomic_json(BASE / 'learned-routes.json',state)
        print('Outcome recorded.')
        return
    # Keep prompt hooks fast even when an hourly global refresh would be due.
    # Normal query/refresh commands maintain the cache; installer builds it first.
    index = load_json(BASE / 'index.json', {}) if args.command == 'hook' else (
        build_index(config) if args.command == 'refresh' else get_index(config))
    if args.command == 'hook' and not isinstance(index.get('records'), list):
        return
    if args.command == 'hook' and (index.get('version') != VERSION or index.get('config_digest') != hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()):
        return
    if args.command in {'refresh', 'stats'}:
        print(json.dumps({'files': len(index['records']), 'unique_contents': len({r['digest'] for r in index['records']}),
                          'unique_names': len({normalize(r['name']) for r in index['records']}),
                          'roots': index['counts'], 'errors': len(index['errors']),
                          'learned_routes':len(load_json(BASE / 'learned-routes.json',{'routes':[]})['routes'])}, ensure_ascii=False))
        return
    if args.command == 'learn':
        try:
            result = learn(args.task,args.skill,args.agent,args.cwd,args.scope,args.evidence,config,index)
        except (OSError, ValueError, RuntimeError) as error:
            parser.error(str(error))
        print(json.dumps(result,ensure_ascii=False))
        return
    if args.command == 'plan':
        try:
            if args.brief_file:
                with args.brief_file.open('rb') as handle:
                    raw = handle.read(32769)
                if len(raw) > 32768:
                    raise ValueError('Brief exceeds 32 KiB.')
                result = plan_brief(json.loads(raw.decode('utf-8-sig')), config, index, args.agent, args.cwd, args.explicit, read_feedback())
            else:
                tasks = json.loads(args.task_file.read_text(encoding='utf-8-sig')) if args.task_file else args.task
                if not isinstance(tasks, list):
                    raise ValueError('Task file must contain a JSON array.')
                result = plan(tasks, config, index, args.agent, args.cwd, args.explicit, read_feedback())
        except (OSError, UnicodeError, ValueError) as error:
            parser.error(str(error))
        print(render(result, verbose=args.verbose) if args.text else json.dumps(result, ensure_ascii=False))
        return
    if args.command == 'hook':
        try:
            event = json.load(sys.stdin)
        except ValueError:
            return
        if not isinstance(event, dict) or not isinstance(event.get('prompt', ''), str) or (event.get('cwd') is not None and not isinstance(event['cwd'], str)):
            return
        task, cwd = str(event.get('prompt', '')), event.get('cwd')
        # Hooks return context only; no blocking, no permission changes, no execution.
        if len(tokens(task)) <= 1:
            return
        result = search(task, config, index, args.agent, cwd, feedback=read_feedback())
        if not result.get('trivial') and hook_changed(event, result, args.agent, config):
            print(json.dumps({'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit',
                  'additionalContext': render(result)}}, ensure_ascii=False))
        return
    try:
        task = args.task_file.read_text(encoding='utf-8-sig') if args.task_file else args.task
    except (OSError, UnicodeError) as error:
        parser.error(str(error))
    result = search(task, config, index, args.agent, args.cwd, args.limit, args.explicit, read_feedback())
    print(render(result, verbose=args.verbose) if args.text else json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

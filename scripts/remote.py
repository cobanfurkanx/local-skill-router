"""Agent-operated skills.sh discovery and reviewed, commit-pinned global installation."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import agents
import changes
import router

HOSTS = {'skills.sh', 'www.skills.sh', 'api.github.com', 'codeload.github.com'}
MAX_ARCHIVE = 25 * 1024 * 1024
MAX_SKILL = 8 * 1024 * 1024
NAME = re.compile(r'[a-z0-9][a-z0-9-]{0,63}\Z')


def safe_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Only fixed HTTPS skills.sh/GitHub service hosts are supported.')
    return url


class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return super().redirect_request(request, fp, code, message, headers, safe_url(newurl))


def fetch(url, limit=2 * 1024 * 1024):
    request = urllib.request.Request(safe_url(url), headers={'User-Agent':'local-skill-router/' + router.RELEASE, 'Accept':'application/json'})
    with urllib.request.build_opener(Redirects()).open(request, timeout=20) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Remote response exceeds the configured size limit.')
    return data


def repository(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}', value) or value.split('/')[1] in {'.','..'}:
        raise ValueError('Expected a public GitHub owner/repository identifier.')
    return value


def relative(value):
    path = PurePosixPath(value)
    reserved = {'con','prn','aux','nul',*[f'com{i}' for i in range(1,10)],*[f'lpt{i}' for i in range(1,10)]}
    if not value or path.is_absolute() or any(p.casefold() in {'','.','..','.git','.local-skill-router-source.json'} or p.endswith((' ','.')) or any(c in p for c in ':\\<>"|?*') or any(ord(c)<32 or ord(c)==127 for c in p) or p.split('.')[0].lower() in reserved for p in value.split('/')):
        raise ValueError('Unsafe or nonportable archive path.')
    return path


def search(query, limit=3):
    if not 2 <= len(query.strip()) <= 200:
        raise ValueError('Use a 2–200 character generic task query, never a raw conversation.')
    url = 'https://skills.sh/api/search?' + urllib.parse.urlencode({'q':query, 'limit':max(1,min(limit,5))})
    result = json.loads(fetch(url))
    if not isinstance(result, dict) or not isinstance(result.get('skills'), list):
        raise ValueError('skills.sh search response changed; use the browser fallback.')
    candidates = []
    for row in result['skills'][:max(1,min(limit,5))]:
        if not isinstance(row, dict):
            continue
        try:
            source = repository(str(row.get('source','')))
        except ValueError:
            continue
        slug = str(row.get('skillId') or row.get('id','').rsplit('/',1)[-1])
        if not NAME.fullmatch(slug):
            continue
        candidates.append({'repo':source, 'skill':slug, 'name':str(row.get('name') or slug)[:120],
                           'installs':row.get('installs'), 'url':'https://skills.sh/' + source + '/' + slug})
    return {'candidates':candidates, 'instruction':'Popularity is not quality. The calling agent must inspect source, tool fit, license and invocation policy before installing. No installation occurred.'}


def payloads_from_archive(data, selected=None, skill=None):
    payloads = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if not entries or len(entries) > 30000:
            raise ValueError('Empty or oversized repository archive.')
        prefix = entries[0].filename.split('/')[0] + '/'
        candidates = [e for e in entries if e.filename.startswith(prefix) and e.filename.endswith('SKILL.md') and not e.is_dir()]
        if selected is None:
            if not skill or not NAME.fullmatch(skill) or len(candidates) > 500:
                raise ValueError('Supply --path for a large repository, or --skill with an exact name.')
            matches = []
            for entry in candidates:
                if entry.file_size > 128 * 1024:
                    continue
                metadata, _ = router.frontmatter(archive.read(entry).decode('utf-8-sig'))
                folder = PurePosixPath(entry.filename).parent
                if metadata.get('name') == skill or folder.name == skill:
                    matches.append(str(folder.relative_to(prefix.rstrip('/'))))
            if len(matches) != 1:
                raise ValueError('Skill directory is missing or ambiguous; inspect the repository and supply --path.')
            selected = matches[0]
        if selected == '.':
            selected = ''
        elif selected:
            relative(selected)
        base = prefix + (selected.rstrip('/') + '/' if selected else '')
        total = 0
        seen = set()
        for entry in entries:
            if entry.is_dir() or not entry.filename.startswith(base):
                continue
            name = entry.filename[len(base):]
            relative(name)
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError('Symlinks are not installed from remote archives.')
            if name.casefold() in seen:
                raise ValueError('Duplicate/case-conflicting archive entries.')
            seen.add(name.casefold())
            total += entry.file_size
            if len(seen) > 250 or total > MAX_SKILL:
                raise ValueError('Selected skill exceeds file or size limits.')
            payloads[name] = archive.read(entry)
        if 'SKILL.md' not in payloads:
            raise ValueError('Selected directory must contain SKILL.md.')
        for name in ('LICENSE','LICENSE.md','LICENSE.txt','COPYING','NOTICE'):
            root_entry = next((e for e in entries if e.filename == prefix + name and e.file_size < 256*1024), None)
            if root_entry and name not in payloads:
                if stat.S_ISLNK(root_entry.external_attr >> 16):
                    raise ValueError('Repository license symlink refused.')
                payloads[name] = archive.read(root_entry)
    return payloads, selected or '.'


def review_digest(manifest):
    material = {k:manifest[k] for k in ('repo','commit','path','name','files')}
    return hashlib.sha256(json.dumps(material,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def inspect(repo, state, skill=None, selected=None, ref='HEAD'):
    repo = repository(repo)
    if not re.fullmatch(r'[A-Za-z0-9_./-]{1,160}',ref):
        raise ValueError('Invalid Git ref.')
    commit_data = json.loads(fetch('https://api.github.com/repos/' + repo + '/commits/' + urllib.parse.quote(ref,safe='')))
    commit = commit_data.get('sha','')
    if not re.fullmatch(r'[0-9a-f]{40}',commit):
        raise ValueError('GitHub did not resolve the source to an immutable commit.')
    data = fetch('https://codeload.github.com/' + repo + '/zip/' + commit, MAX_ARCHIVE)
    payloads, selected = payloads_from_archive(data,selected,skill)
    metadata, _ = router.frontmatter(payloads['SKILL.md'].decode('utf-8-sig'))
    name = str(metadata.get('name',''))
    if not NAME.fullmatch(name) or name in {'local-skill-router','auto-skill-router'}:
        raise ValueError('Invalid/reserved skill name. Review source manually.')
    manifest = {'repo':repo,'commit':commit,'path':selected,'name':name,
                'description':str(metadata.get('description',''))[:400],
                'files':{name:changes.digest(data) for name,data in sorted(payloads.items())}}
    manifest['review_digest'] = review_digest(manifest)
    destination = state / 'incoming' / manifest['review_digest']
    if destination.exists():
        existing = json.loads((destination / 'manifest.json').read_text(encoding='utf-8'))
        if existing != manifest or any(changes.digest((destination/'files'/name).read_bytes()) != digest for name,digest in manifest['files'].items()):
            raise ValueError('Existing inspection changed; preserve it and use a clean state directory.')
    else:
        destination.mkdir(parents=True, mode=0o700)
        for name,payload in payloads.items():
            target = destination / 'files' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        router.atomic_json(destination / 'manifest.json',manifest)
    return dict(manifest, inspection=str(destination),
                instruction='Untrusted source staged, not installed or executed. Read SKILL.md, referenced files, executable helpers and license. A digest acknowledges exact bytes, not safety or quality.')


def install(inspection, reviewed, selected, home, state, env=None, yes=False):
    inspection = inspection.resolve()
    if inspection.parent != (state / 'incoming').resolve():
        raise ValueError('Only a locally staged inspection in this state directory can be installed.')
    manifest = json.loads((inspection / 'manifest.json').read_text(encoding='utf-8'))
    if reviewed != review_digest(manifest) or reviewed != manifest['review_digest'] or inspection.name != reviewed:
        raise ValueError('Review digest does not match the staged source.')
    if not NAME.fullmatch(manifest['name']):
        raise ValueError('Unsafe skill name.')
    payloads = {}
    if len(manifest['files']) > 255 or (inspection / 'files').is_symlink():
        raise ValueError('Unsafe or oversized staged source.')
    for name,digest in manifest['files'].items():
        relative(name)
        path = inspection / 'files' / name
        if not path.resolve().is_relative_to((inspection/'files').resolve()) or path.is_symlink():
            raise ValueError('Staged source escaped its directory.')
        payload = path.read_bytes()
        if changes.digest(payload) != digest:
            raise ValueError('Staged source changed after review.')
        payloads[name] = payload
    destinations = {home / '.agents/skills' / manifest['name']}
    for agent in selected:
        destinations.update(root / manifest['name'] for root in agents.locations(agent,home,env=env)[0])
    for target in destinations:
        if target.exists() or target.is_symlink():
            raise ValueError('Global skill already exists; no overwrite: ' + str(target))
    authorized = yes or policy(state)['global_install'] == 'reviewed'
    plan = {'name':manifest['name'],'repo':manifest['repo'],'commit':manifest['commit'],
            'review_digest':reviewed,'destinations':sorted(map(str,destinations)), 'approval_required':not authorized}
    if not authorized:
        return plan
    if manifest['name'] in {'local-skill-router','auto-skill-router'}:
        raise ValueError('Cannot replace the router with a remotely supplied skill.')
    changed = []
    for target in destinations:
        for name,payload in payloads.items():
            changed.append((target / name, None, payload))
        receipt = {k:manifest[k] for k in ('repo','commit','path','review_digest')}
        changed.append((target / '.local-skill-router-source.json',None,json.dumps(receipt,indent=2).encode()))
    applied = changes.apply(state,changed,[home,*destinations], 'remote-skill')
    return dict(plan, **applied, installed=True,
                instruction='Global files installed. Read the exact installed path for this task and refresh the router. Native discovery may need a new client session. No skill helper was executed.')


def policy(state):
    path = state / 'remote-policy.json'
    value = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'global_install':'ask'}
    if not isinstance(value, dict) or value.get('global_install') not in {'ask','reviewed'}:
        raise ValueError('Invalid remote installation policy; no global installation authorized.')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir',type=Path,default=router.BASE)
    parser.add_argument('--home',type=Path,help='Alternate user home for isolated testing')
    commands = parser.add_subparsers(dest='command',required=True)
    commands.add_parser('policy')
    searching = commands.add_parser('search')
    searching.add_argument('query')
    searching.add_argument('--limit',type=int,default=3)
    inspecting = commands.add_parser('inspect')
    inspecting.add_argument('--repo',required=True)
    inspecting.add_argument('--skill')
    inspecting.add_argument('--path')
    inspecting.add_argument('--ref',default='HEAD')
    installing = commands.add_parser('install')
    installing.add_argument('inspection',type=Path)
    installing.add_argument('--reviewed',required=True)
    installing.add_argument('--agent',action='append',choices=agents.AGENTS,required=True)
    installing.add_argument('--yes',action='store_true',help='Use only with actual user authorization for global installation')
    args = parser.parse_args()
    state = args.state_dir.expanduser().resolve()
    home = (args.home or Path.home()).expanduser().resolve()
    try:
        if args.command == 'policy':
            result = policy(state)
        elif args.command == 'search':
            result = search(args.query,args.limit)
        elif args.command == 'inspect':
            result = inspect(args.repo,state,args.skill,args.path,args.ref)
        else:
            result = install(args.inspection,args.reviewed,args.agent,home,state,{} if args.home else os.environ,args.yes)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except urllib.error.HTTPError as error:
        parser.error(f'Remote service returned HTTP {error.code}; stop/retry later or use browser discovery. No TLS bypass.')
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()

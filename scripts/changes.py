"""Small recoverable file transaction. Never recursively deletes directories."""
import base64
import hashlib
import json
from pathlib import Path
import re
import uuid
from router import atomic_json


def digest(payload):
    return hashlib.sha256(payload).hexdigest() if payload is not None else None


def current(path):
    if path.is_symlink():
        raise ValueError('Refusing to replace a symbolic-link file: ' + str(path))
    return path.read_bytes() if path.exists() else None


def within(path, roots):
    return any(path.resolve().is_relative_to(root.resolve()) for root in roots)


def write(path, payload):
    if payload is None:
        if path.exists():
            path.unlink()
        return
    # Use the same atomic replacement mechanism as JSON state, without recoding bytes.
    import os
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(payload)
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def apply(state, changes, roots, kind):
    changes = [(p, before, after) for p, before, after in changes if before != after]
    for path, before, _ in changes:
        if not within(path, roots) or current(path) != before:
            raise ValueError('Path escaped allowed roots or changed while planning: ' + str(path))
    if not changes:
        return {'changed_files': 0, 'operation': None}
    operation = uuid.uuid4().hex
    journal = state / 'operations' / (operation + '.json')
    journal.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    record = {'operation': operation, 'kind': kind, 'phase': 'prepared', 'files': [
        {'path': str(p), 'before': base64.b64encode(before).decode() if before is not None else None,
         'after_sha256': digest(after)} for p, before, after in changes]}
    created = set()
    for path, _, _ in changes:
        parent = path.parent
        while not parent.exists() and within(parent, roots):
            created.add(str(parent))
            parent = parent.parent
    record['created_dirs'] = sorted(created, key=lambda p:len(Path(p).parts), reverse=True)
    atomic_json(journal, record)
    completed = []
    try:
        for path, before, after in changes:
            if current(path) != before:
                raise ValueError('File changed during install: ' + str(path))
            write(path, after)
            completed.append((path, before, after))
    except Exception as error:
        # Preserve concurrent user edits rather than undoing over them.
        for path, before, after in reversed(completed):
            try:
                if digest(current(path)) == digest(after):
                    write(path, before)
            except (OSError, ValueError):
                pass  # The prepared journal retains recovery bytes; preserve newer edits.
        raise OSError(f'Write failed; recovery operation {operation}: {error}') from error
    record['phase'] = 'applied'
    atomic_json(journal, record)
    return {'changed_files': len(changes), 'operation': operation}


def undo(state, operation, roots):
    if not re.fullmatch(r'[0-9a-f]{32}', operation):
        raise ValueError('Expected a local operation ID, not a manifest path.')
    journal = state / 'operations' / (operation + '.json')
    record = json.loads(journal.read_text(encoding='utf-8'))
    if not all(within(Path(directory),roots) for directory in record.get('created_dirs', [])):
        raise ValueError('Recorded directory escaped allowed roots.')
    restore = []
    for entry in record['files']:
        path = Path(entry['path'])
        before = base64.b64decode(entry['before'], validate=True) if entry['before'] is not None else None
        actual = current(path)
        if not within(path, roots) or digest(actual) not in {digest(before), entry['after_sha256']}:
            raise ValueError('Undo refused; preserve changed file: ' + str(path))
        if actual != before:
            restore.append((path, before))
    for path, before in reversed(restore):
        write(path, before)
    for directory in record.get('created_dirs', []):
        path = Path(directory)
        if not within(path, roots):
            raise ValueError('Recorded directory escaped allowed roots.')
        try:
            path.rmdir()
        except OSError:
            pass  # Leave directories containing later user files untouched.
    record['phase'] = 'undone'
    atomic_json(journal, record)
    return {'restored_files': len(restore), 'operation': operation}

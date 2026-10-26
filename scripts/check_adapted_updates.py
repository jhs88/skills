#!/usr/bin/env python3
"""Read-only upstream check for adapted collections: 0=current, 1=updates, 2=failure.

Adapted from Pi's check_tstack_updates.py. Fetch into disposable bare repositories;
never execute upstream code, replace skills, or advance either local lockfile.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'tstack': ('https://github.com/t3dotgg/tstack', 'skills/', 'LICENSE'),
    'pstack': ('https://github.com/cursor/plugins', 'pstack/skills/', 'pstack/LICENSE'),
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ['git', '-C', str(repo), *args], capture_output=True, timeout=120,
        env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'},
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace').strip()
                           or f'git failed with exit {result.returncode}')
    return result.stdout


def valid_path(path: str) -> bool:
    return (isinstance(path, str) and bool(path) and not path.startswith('/')
            and '\\' not in path and all(x not in ('', '.', '..') for x in path.split('/'))
            and all(ord(c) >= 32 and ord(c) != 127 for c in path))


def skill_names(files: dict[str, str]) -> set[str]:
    return {p.split('/')[0] for p in files if p.count('/') == 1 and p.endswith('/SKILL.md')}


def snapshot(repo: Path, revision: str, prefix: str) -> dict[str, str]:
    """Inventory the complete skill collection, including all support files."""
    files = {}
    for row in git(repo, 'ls-tree', '-rz', '--full-tree', revision).split(b'\0'):
        if not row:
            continue
        meta, raw_path = row.split(b'\t', 1)
        mode, kind, oid = meta.decode('ascii').split()
        path = raw_path.decode('utf-8')
        if not path.startswith(prefix):
            continue
        relative = path[len(prefix):]
        if (mode not in ('100644', '100755') or kind != 'blob'
                or not valid_path(relative)):
            raise ValueError(f'Unsupported upstream skill entry: {path} ({mode} {kind})')
        files[relative] = digest(git(repo, 'cat-file', 'blob', oid))
    if not skill_names(files):
        raise ValueError('No upstream skills found; refusing an empty inventory')
    return files


def validate_collection(name: str, spec: dict) -> None:
    expected = SOURCES[name]
    if tuple(spec.get(k) for k in ('upstream', 'prefix', 'license_path')) != expected:
        raise ValueError(f'Unexpected upstream URL or layout for {name}')
    for revision in [spec.get('revision'), *spec.get('skill_revisions', {}).values()]:
        if not isinstance(revision, str) or not re.fullmatch(r'[0-9a-f]{40}', revision):
            raise ValueError('Revision must be an exact 40-character lowercase Git SHA')
    files = spec.get('source_files')
    if not isinstance(files, dict) or not files or not skill_names(files):
        raise ValueError('source_files must be a nonempty skill inventory')
    for path, value in {**files, spec['license_path']: spec.get('license_sha256')}.items():
        if (not valid_path(path) or not isinstance(value, str)
                or not re.fullmatch(r'[0-9a-f]{64}', value)):
            raise ValueError('Invalid source path or SHA-256 digest')
    for skill in spec.get('skill_revisions', {}):
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', skill) or skill not in skill_names(files):
            raise ValueError('Invalid per-skill revision override')


def compare(spec: dict, head: str, current: dict[str, str], license_hash: str) -> dict:
    baseline = spec['source_files']
    old_skills, new_skills = skill_names(baseline), skill_names(current)
    added = sorted(current.keys() - baseline.keys())
    removed = sorted(baseline.keys() - current.keys())
    changed = sorted(p for p in current.keys() & baseline.keys() if current[p] != baseline[p])
    touched = added + removed + changed
    license_changed = license_hash != spec['license_sha256']
    return {
        'upstream': spec['upstream'], 'branch': 'main',
        'pinned_revision': spec['revision'], 'skill_revisions': spec.get('skill_revisions', {}),
        'main_revision': head, 'updates_available': bool(touched) or license_changed,
        'new_skills': sorted(new_skills - old_skills),
        'removed_skills': sorted(old_skills - new_skills),
        'modified_skills': sorted(n for n in old_skills & new_skills
                                 if any(p.startswith(n + '/') for p in touched)),
        'added_files': added, 'removed_files': removed, 'changed_files': changed,
        'license_changed': license_changed,
        'compare_url': f"{spec['upstream']}/compare/{spec['revision']}...{head}",
    }


def check_collection(name: str, spec: dict) -> dict:
    validate_collection(name, spec)
    with tempfile.TemporaryDirectory(prefix=f'{name}-update-check-') as directory:
        repo = Path(directory)
        git(repo, 'init', '--bare', '--quiet')
        git(repo, 'fetch', '--quiet', '--no-tags', '--depth=1', spec['upstream'], 'refs/heads/main')
        head = git(repo, 'rev-parse', 'FETCH_HEAD').decode().strip()
        if not re.fullmatch(r'[0-9a-f]{40}', head):
            raise ValueError('Invalid upstream main revision')
        for pin in sorted({spec['revision'], *spec.get('skill_revisions', {}).values()} - {head}):
            git(repo, 'fetch', '--quiet', '--no-tags', '--depth=1', spec['upstream'], pin)
        pinned = snapshot(repo, spec['revision'], spec['prefix'])
        # Pstack's two selected adaptations intentionally have distinct source pins.
        for skill, pin in spec.get('skill_revisions', {}).items():
            alternate = snapshot(repo, pin, spec['prefix'])
            if skill not in skill_names(alternate):
                raise ValueError(f'Missing pinned skill: {skill}')
            pinned = {p: h for p, h in pinned.items() if not p.startswith(skill + '/')}
            pinned.update({p: h for p, h in alternate.items() if p.startswith(skill + '/')})
        if pinned != spec['source_files']:
            raise ValueError('Manifest hashes/inventory do not match pinned upstream revisions')
        for pin in {spec['revision'], *spec.get('skill_revisions', {}).values()}:
            if digest(git(repo, 'show', f"{pin}:{spec['license_path']}")) != spec['license_sha256']:
                raise ValueError('Pinned license hash mismatch')
        current = snapshot(repo, head, spec['prefix'])
        license_hash = digest(git(repo, 'show', f"{head}:{spec['license_path']}"))
        report = compare(spec, head, current, license_hash)
        report['repository_changed_files'] = sorted(filter(None, git(
            repo, 'diff', '--name-only', '-z', spec['revision'], head,
            '--', spec['prefix'].rstrip('/'), spec['license_path'],
        ).decode().split('\0')))
        return report


def check(manifest: dict) -> dict:
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
        raise ValueError('Invalid adaptation manifest schema')
    collections = manifest.get('collections')
    if not isinstance(collections, dict) or set(collections) != set(SOURCES):
        raise ValueError('Manifest must contain exactly tstack and pstack collections')
    # Validate both before allowing any network access.
    for name, spec in collections.items():
        validate_collection(name, spec)
    reports, errors = {}, {}
    for name, spec in collections.items():
        try:
            reports[name] = check_collection(name, spec)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            errors[name] = str(error)
    return {'status': 'check_failed' if errors else 'complete', 'collections': reports,
            'errors': errors, 'updates_available': any(r['updates_available'] for r in reports.values())}


def render(report: dict) -> str:
    lines = ['# Adapted skill upstream check', '',
             'Read-only. Human reconciliation required; no local skills or pins were changed.',
             'Only collection files and licenses decide updates; unrelated repository commits do not.',
             'New upstream skills are review candidates, not automatically selected imports.']
    for name, entry in report['collections'].items():
        lines += ['', f'## {name}', f"Upstream main: {entry['main_revision']}",
                  f"Baseline pin: {entry['pinned_revision']}",
                  f"Per-skill pins: {json.dumps(entry['skill_revisions'], sort_keys=True)}",
                  'Updates available.' if entry['updates_available'] else 'Selected collection is current.',
                  f"License changed: {entry['license_changed']}"]
        for key in ['new_skills', 'removed_skills', 'modified_skills', 'added_files',
                    'removed_files', 'changed_files', 'repository_changed_files']:
            values = entry[key]
            lines.append(f"{key} ({len(values)}): " + (', '.join(values) or 'none'))
        lines.append(entry['compare_url'])
    for name, error in report['errors'].items():
        lines += ['', f'## {name} failed', error]
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'adaptations.lock.json')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = check(json.loads(args.manifest.read_text()))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        report = {'status': 'check_failed', 'collections': {}, 'errors': {'manifest': str(error)},
                  'updates_available': False}
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 2 if report['errors'] else 1 if report['updates_available'] else 0


if __name__ == '__main__':
    sys.exit(main())

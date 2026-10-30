#!/usr/bin/env python3
"""Copy Matt's published skills through the pinned npm CLI, or check the local catalog."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CLI = Path(os.environ.get('SKILLS_CLI', ROOT / 'node_modules/skills/bin/cli.mjs'))
SHA = r'[0-9a-f]{40}'
NAME = r'[a-z0-9]+(?:-[a-z0-9]+)*'


def read_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique)


def safe(root, relative):
    path = Path(relative)
    if (not isinstance(relative, str) or not relative or path.is_absolute()
            or '..' in path.parts or '\\' in relative or any(ord(c) < 32 for c in relative)):
        raise ValueError(f'Unsafe path: {relative!r}')
    current = root
    for part in ('.', *path.parts):
        current /= part
        if current.is_symlink():
            raise ValueError(f'Symlink forbidden: {current}')
    return current


def regular(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f'Not a regular file: {path}')
    return path.read_bytes()


def files(directory):
    """Transient byte/mode comparison, never a persisted hash inventory."""
    safe(directory, '.')
    result = {}
    for path in sorted(directory.rglob('*')):
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        safe(directory, str(path.relative_to(directory)))
        if not path.is_dir():
            result[str(path.relative_to(directory))] = (regular(path), stat.S_IMODE(path.stat().st_mode))
    return result


def load_sources(path=ROOT / 'sources.json'):
    sources = read_json(regular(path))
    if not isinstance(sources, dict) or set(sources) != {'mattpocock', 'tstack', 'pstack', 'cursor-team-kit'}:
        raise ValueError('Expected mattpocock, tstack, pstack and cursor-team-kit sources')
    for name, spec in sources.items():
        if not re.fullmatch(SHA, spec['revision']):
            raise ValueError(f'Invalid revision: {name}')
        if not isinstance(spec['repository'], str) or not spec['repository'] or spec['repository'].startswith('-'):
            raise ValueError(f'Invalid repository: {name}')
        if spec['destination'] != f'skills/{name}':
            raise ValueError(f'Invalid destination: {name}')
        safe(ROOT, spec['license'])
        if spec['mode'] == 'published' and name == 'mattpocock':
            safe(ROOT, spec['manifest'])
        elif spec['mode'] == 'adapted' and name != 'mattpocock':
            safe(ROOT, spec['path'])
            names = spec['selected']
            if (not isinstance(names, list) or not names or any(not isinstance(n, str) or not re.fullmatch(NAME, n) for n in names)
                    or len(set(names)) != len(names)):
                raise ValueError(f'Invalid selection: {name}')
            for skill, revision in spec.get('skill_revisions', {}).items():
                if skill not in names or not re.fullmatch(SHA, revision):
                    raise ValueError(f'Invalid skill revision: {skill}')
        else:
            raise ValueError(f'Invalid source mode: {name}')
    return sources


def parse_manifest(data):
    obj = read_json(data)
    paths = obj.get('skills') if isinstance(obj, dict) else None
    if not isinstance(paths, list) or not paths:
        raise ValueError('Manifest skills must be a nonempty explicit list')
    selected = {}
    for path in paths:
        match = re.fullmatch(r'\./skills/(engineering|productivity)/(' + NAME + ')', path) if isinstance(path, str) else None
        if not match or match[2] in selected:
            raise ValueError(f'Invalid or duplicate published path: {path!r}')
        selected[match[2]] = path[2:]
    return selected


def validate_skill(directory):
    inventory = files(directory)
    text = (directory / 'SKILL.md').read_text()
    match = re.match(r'---\n(.*?)\n---(?:\n|$)', text, re.S)
    if (not match or not re.search(r'^name: [\'"]?' + re.escape(directory.name) + r'[\'"]?\s*$', match[1], re.M)
            or not re.search(r'^description: \S', match[1], re.M)):
        raise ValueError(f'Missing skill name/description frontmatter: {directory}')
    return len(inventory)


def validate(root=ROOT):
    spec = load_sources(root / 'sources.json')['mattpocock']
    directory = safe(root, spec['destination'])
    selected = sorted(p.name for p in directory.iterdir())
    if not selected or any(not re.fullmatch(NAME, name) or not (directory / name).is_dir() for name in selected):
        raise ValueError('Catalog must contain nonempty named skill directories')
    notices = regular(safe(root, 'LICENSES.md'))
    if b'Copyright (c) 2026 Matt Pocock' not in notices or b'Permission is hereby granted' not in notices:
        raise ValueError('Missing Matt Pocock MIT notice in LICENSES.md')
    return {'skills': len(selected), 'files': sum(validate_skill(directory / n) for n in selected), 'revision': spec['revision']}


def git(*args, cwd=None):
    return subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', *args], cwd=cwd, check=True,
                          capture_output=True, text=True, timeout=180,
                          env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}).stdout.strip()


def clean(root, spec):
    scope = [spec['destination'], 'LICENSES.md', 'sources.json', 'scripts', 'tests',
             'package.json', 'package-lock.json', '.github/workflows', 'README.md', 'docs', 'GLOSSARY.md']
    if git('status', '--porcelain', '--untracked-files=all', '--', *scope, cwd=root):
        raise ValueError('Dirty sync scope; commit or stash scoped changes before syncing')


def run_cli(source, name, project):
    package = read_json((CLI.parent.parent / 'package.json').read_bytes())
    if (package.get('name'), package.get('version')) != ('skills', '1.7.4'):
        raise ValueError('Install pinned skills@1.7.4 with npm ci --ignore-scripts')
    home = project / 'home'
    home.mkdir(parents=True, exist_ok=True)
    env = {'PATH': os.environ.get('PATH', ''), 'HOME': str(home), 'TMPDIR': str(home),
           'XDG_CONFIG_HOME': str(home / '.config'), 'XDG_CACHE_HOME': str(home / '.cache'),
           'XDG_DATA_HOME': str(home / '.local/share'), 'DISABLE_TELEMETRY': '1',
           'DO_NOT_TRACK': '1', 'CI': '1', 'NO_COLOR': '1'}
    result = subprocess.run(['node', str(CLI), 'add', str(source), '--skill', name,
                             '-a', 'codex', '-y', '--copy'], cwd=project, env=env,
                            capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise ValueError(f'skills CLI failed: {result.stderr}\n{result.stdout}')


def sync(source, root, revision):
    if not re.fullmatch(SHA, revision):
        raise ValueError('Revision must be a full lowercase 40-character commit SHA')
    sources = load_sources(root / 'sources.json')
    spec = sources['mattpocock']
    clean(root, spec)
    with tempfile.TemporaryDirectory(prefix='skills-stage-') as temp:
        stage = Path(temp)
        manifest = regular(safe(source, spec['manifest']))
        selected = parse_manifest(manifest)
        license_data = regular(safe(source, spec['license']))
        if b'MIT License' not in license_data or b'Permission is hereby granted' not in license_data:
            raise ValueError('Upstream MIT license missing or changed; review required')
        notices = regular(safe(root, 'LICENSES.md'))
        if license_data not in notices:
            raise ValueError('Upstream license differs from LICENSES.md; human review required before syncing')
        # Validate every selected input before installation, and the complete output before replacement.
        for name, relative in selected.items():
            validate_skill(safe(source, relative))
        for name, relative in selected.items():
            run_cli(source / relative, name, stage / 'cli')
            if files(stage / 'cli/.agents/skills' / name) != files(source / relative):
                raise ValueError(f'CLI changed or omitted source bytes/modes: {name}')
        destination = stage / spec['destination']
        destination.parent.mkdir(parents=True)
        shutil.move(stage / 'cli/.agents/skills', destination)
        (stage / 'LICENSES.md').write_bytes(notices)
        raw = (root / 'sources.json').read_bytes()
        if spec['revision'] != revision:
            spec['revision'] = revision
            raw = (json.dumps(sources, indent=2) + '\n').encode()
        (stage / 'sources.json').write_bytes(raw)
        validate(stage)
        targets = [spec['destination'], 'sources.json']
        for relative in targets:
            safe(root, relative)
        def content(path):
            return files(path) if path.is_dir() else path.read_bytes()
        changed = [r for r in targets if not (root / r).exists() or content(root / r) != content(stage / r)]
        clean(root, spec)
        saved, installed = [], []
        try:
            for i, relative in enumerate(changed):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    backup = stage / f'backup-{i}'
                    os.replace(target, backup)
                    saved.append((target, backup))
                os.replace(stage / relative, target)
                installed.append(target)
        except BaseException:
            for target in reversed(installed):
                shutil.rmtree(target) if target.is_dir() else target.unlink()
            for target, backup in reversed(saved):
                os.replace(backup, target)
            raise
        return bool(changed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='trusted checkout or synthetic fixture, never executes upstream scripts')
    parser.add_argument('--revision', help='full commit SHA; fixture callers assert provenance')
    parser.add_argument('--check', action='store_true', help='offline structural catalog validation, no CLI installation')
    args = parser.parse_args()
    try:
        if args.check:
            if args.source or args.revision:
                raise ValueError('--check cannot be combined with source/revision')
            print(json.dumps({'status': 'valid', **validate()}))
            return
        spec = load_sources()['mattpocock']
        clean(ROOT, spec)
        if args.revision and not re.fullmatch(SHA, args.revision):
            raise ValueError('Revision must be a full lowercase 40-character commit SHA')
        if args.source:
            changed = sync(args.source.absolute(), ROOT, args.revision or git('rev-parse', 'HEAD', cwd=args.source))
        else:
            revision = args.revision or git('ls-remote', spec['repository'], 'HEAD').partition('\t')[0]
            if not re.fullmatch(SHA, revision):
                raise ValueError('Invalid upstream HEAD revision')
            with tempfile.TemporaryDirectory(prefix='matt-upstream-') as temp:
                source = Path(temp) / 'upstream'
                git('init', '--quiet', str(source))
                git('fetch', '--quiet', '--depth=1', spec['repository'], revision, cwd=source)
                git('checkout', '--quiet', '--detach', 'FETCH_HEAD', cwd=source)
                if git('rev-parse', 'HEAD', cwd=source) != revision:
                    raise ValueError('Fetched commit differs from requested revision')
                changed = sync(source, ROOT, revision)
        print(json.dumps({'status': 'updated' if changed else 'unchanged', **validate()}))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
        parser.exit(1, f'sync failed: {error}\n')


if __name__ == '__main__':
    main()

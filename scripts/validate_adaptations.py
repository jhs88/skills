#!/usr/bin/env python3
"""Validate adapted imports offline. Does not install or activate skills."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    'tstack': {'babysit-pr', 'council', 'file-pr', 'full-send', 'full-stop',
               'leaving-pr-comments', 'modernize', 'sol-loop', 'takeover'},
    'pstack': {'technical-writing', 'unslop'},
}
HELPER_HASH = '90393f85b95b78bff1b039744bdfb09dc88ff2b430e1c3df687ee6f449c97214'


def inventory(directory: Path) -> dict[str, str]:
    files = {}
    if directory.is_symlink():
        raise ValueError(f'Symlinked import directory: {directory}')
    for path in sorted(directory.rglob('*')):
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise ValueError(f'Unsupported imported entry: {path}')
        if path.is_file():
            files[path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(root: Path = ROOT) -> dict:
    manifest = json.loads((root / 'adaptations.lock.json').read_text())
    require(manifest['schema_version'] == 1, 'Unsupported adaptation schema')
    require('dirty working tree' in manifest['source']['state'], 'Working-tree provenance missing')
    require(bool(re.fullmatch(r'[0-9a-f]{40}', manifest['source']['head'])), 'Invalid Pi HEAD')
    skills = manifest['skills']
    require(len(skills) == 11, 'Expected exactly 11 adaptations')
    for family, names in EXPECTED.items():
        entries = [s for s in skills if s['collection'] == family]
        require(len(entries) == len(names) and {s['name'] for s in entries} == names,
                f'Unexpected {family} manifest inventory')
        directory = root / 'skills' / family
        require(directory.is_dir() and not directory.is_symlink(), f'Unsupported {family} directory')
        discovered = {p.parent.name for p in directory.rglob('SKILL.md')}
        require(discovered == names, f'Unexpected {family} skill discovery')
        require({p.name for p in directory.iterdir()} == names, f'Unexpected {family} content')
        license_file = root / 'third_party' / family / 'LICENSE'
        require(hashlib.sha256(license_file.read_bytes()).hexdigest()
                == manifest['collections'][family]['license_sha256'], f'{family} license mismatch')
        notices = (root / 'third_party' / family / 'NOTICE.md').read_text()
        require('LICENSE' in notices and 'adaptations.lock.json' in notices, 'Missing license/provenance reference')
        require('Theo Browne' in notices if family == 'tstack' else 'Lauren Tan' in notices,
                'Missing upstream attribution')
        for entry in entries:
            name = entry['name']
            require(entry['destination'] == f'skills/{family}/{name}', 'Unexpected destination')
            require(entry['source_path'] == f'agent/skills/{name}', 'Unexpected source path')
            require(set(entry['files']) == set(entry['source_files']), 'Incomplete source import')
            for value in entry['source_files'].values():
                require(bool(re.fullmatch(r'[0-9a-f]{64}', value)), 'Invalid source digest')
            require(entry['adapted_files'] == sorted(p for p in entry['files']
                    if entry['files'][p] != entry['source_files'][p]), 'Adaptation log mismatch')
            require(inventory(directory / name) == entry['files'], f'File hashes/inventory differ: {name}')
            text = (directory / name / 'SKILL.md').read_text()
            require(text.startswith('---\n'), f'Invalid frontmatter: {name}')
            frontmatter = text.split('---', 2)[1]
            keys = set(re.findall(r'^([a-z][a-z-]*):', frontmatter, re.M))
            expected_keys = {'name', 'description'} | ({'disable-model-invocation'} if name == 'technical-writing' else set())
            require(keys == expected_keys and f'name: {name}\n' in frontmatter, f'Unexpected metadata: {name}')
            if name == 'technical-writing':
                require('disable-model-invocation: true' in frontmatter, 'Manual invocation intent lost')
            for rel in entry['files']:
                path = directory / name / rel
                content = path.read_text()
                require(not re.search(r'/home/|~?/\.pi/|~/\.pi/|llamacpp|CLIProxyAPI|pi --list-models', content),
                        f'Runtime-bound private dependency: {path}')
                require(not re.search(r'agent-gauntlet|Uncle Bob|uncle-bob', content, re.I),
                        f'Excluded workflow in discovery: {path}')
                if path.suffix == '.md':
                    targets = re.findall(r'\]\(([^)#]+)(?:#[^)]*)?\)', content)
                    targets += re.findall(r'`((?:\.\./|references/)[^`]+\.md)`', content)
                    for target in targets:
                        if not target.startswith(('http:', 'https:')):
                            require((path.parent / target).is_file(), f'Broken reference: {path}: {target}')
    helper = root / 'skills/tstack/babysit-pr/scripts/pr-wait'
    require(hashlib.sha256(helper.read_bytes()).hexdigest() == HELPER_HASH, 'Upstream helper bytes changed')
    require(helper.stat().st_mode & 0o111 != 0, 'Helper lost executable mode')
    council = (root / 'skills/tstack/council/SKILL.md').read_text()
    for model in ['gpt-6.1-sol', 'gpt-6-astra', 'gpt-6-luna']:
        require(model in council, 'Council roster changed')
    require('instead of substituting' in council and 'existing configured GPT' in council,
            'Council discovery/fail-closed contract missing')
    require('Never merge' in (root / 'skills/tstack/full-stop/SKILL.md').read_text(), 'Full-stop merge restriction lost')
    require(not any(re.search(r'agent-gauntlet|uncle-bob', str(p), re.I)
                    for p in (root / 'skills').rglob('SKILL.md')), 'Excluded skill is discoverable')
    return {'skills': len(skills), 'files': sum(len(s['files']) for s in skills),
            'adapted_files': sum(len(s['adapted_files']) for s in skills), 'status': 'valid'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.root), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'Adaptation validation failed: {error}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

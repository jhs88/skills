#!/usr/bin/env python3
"""Validate the adapted catalog offline, without installing or invoking skills."""
import argparse
import json
from pathlib import Path
import re

from sync_mattpocock import ROOT, files, load_sources, regular, safe, validate_skill


def validate(root=ROOT):
    count = total = 0
    notices = regular(safe(root, 'LICENSES.md'))
    authors = {'tstack': b'Copyright (c) 2026 Theo Browne', 'pstack': b'Copyright (c) 2026 Lauren Tan'}
    for name, spec in load_sources(root / 'sources.json').items():
        if spec['mode'] != 'adapted':
            continue
        directory = safe(root, spec['destination'])
        if {p.name for p in directory.iterdir()} != set(spec['selected']):
            raise ValueError(f'Catalog differs from source selection: {name}')
        if authors[name] not in notices or b'Permission is hereby granted' not in notices:
            raise ValueError(f'Missing MIT notice in LICENSES.md: {name}')
        for skill in spec['selected']:
            folder = directory / skill
            total += validate_skill(folder)
            count += 1
            for relative, (data, mode) in files(folder).items():
                path = folder / relative
                if data.startswith(b'#!') and not mode & 0o111:
                    raise ValueError(f'Helper is not executable: {path}')
                if path.suffix != '.md':
                    continue
                text = data.decode('utf-8')
                targets = re.findall(r'\]\(([^)#]+)(?:#[^)]*)?\)', text)
                targets += re.findall(r'`((?:\.\./|references/)[^`]+\.md|[a-zA-Z0-9_-]+\.md)`', text)
                for target in targets:
                    if not target.startswith(('https:', 'http:', 'mailto:')) and not (path.parent / target).is_file():
                        raise ValueError(f'Broken reference: {path}: {target}')
    return {'skills': count, 'files': total, 'status': 'valid'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.root), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f'Adaptation validation failed: {error}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

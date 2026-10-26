#!/usr/bin/env python3
"""Read-only adapted upstream check: 0=current, 1=updates, 2=failure."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from sync_mattpocock import ROOT, git, load_sources


def skill_names(inventory):
    return {p.split('/')[0] for p in inventory if p.count('/') == 1 and p.endswith('/SKILL.md')}


def snapshot(repo, revision, prefix):
    """Reconstruct each inventory from Git objects, including support files and modes."""
    rows = subprocess.run(['git', '-C', str(repo), 'ls-tree', '-rz', revision, '--', prefix + '/'],
                          check=True, capture_output=True, timeout=120).stdout
    inventory = {}
    for row in rows.split(b'\0'):
        if not row:
            continue
        meta, raw_path = row.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        path = raw_path.decode('utf-8')
        if mode not in ('100644', '100755') or kind != 'blob':
            raise ValueError(f'Unsupported upstream entry: {path} ({mode} {kind})')
        inventory[path[len(prefix) + 1:]] = (mode, oid)
    if not skill_names(inventory):
        raise ValueError('No upstream skills found; refusing an empty inventory')
    return inventory


def check_collection(spec):
    with tempfile.TemporaryDirectory(prefix='adapted-check-') as temp:
        repo = Path(temp)
        git('init', '--bare', '--quiet', cwd=repo)
        git('fetch', '--quiet', '--no-tags', '--depth=1', spec['repository'], 'refs/heads/main', cwd=repo)
        head = git('rev-parse', 'FETCH_HEAD', cwd=repo)
        overrides = spec.get('skill_revisions', {})
        for pin in sorted({spec['revision'], *overrides.values()} - {head}):
            git('fetch', '--quiet', '--no-tags', '--depth=1', spec['repository'], pin, cwd=repo)
        baseline = snapshot(repo, spec['revision'], spec['path'])
        for skill, pin in overrides.items():
            alternate = snapshot(repo, pin, spec['path'])
            if skill not in skill_names(alternate):
                raise ValueError(f'Missing skill at override pin: {skill}')
            baseline = {p: v for p, v in baseline.items() if not p.startswith(skill + '/')}
            baseline.update({p: v for p, v in alternate.items() if p.startswith(skill + '/')})
        if not set(spec['selected']) <= skill_names(baseline):
            raise ValueError('Missing selected skills at baseline pins')
        current = snapshot(repo, head, spec['path'])
        added = sorted(current.keys() - baseline.keys())
        removed = sorted(baseline.keys() - current.keys())
        changed = sorted(p for p in baseline.keys() & current.keys() if baseline[p] != current[p])
        # Compare raw license bytes, not text normalized by subprocess decoding.
        def license_at(revision):
            return subprocess.run(['git', '-C', str(repo), 'show', f"{revision}:{spec['license']}"],
                                  check=True, capture_output=True, timeout=120).stdout
        license_changed = license_at(spec['revision']) != license_at(head)
        old_names, new_names = skill_names(baseline), skill_names(current)
        touched = added + removed + changed
        return {
            'upstream': spec['repository'], 'pinned_revision': spec['revision'],
            'skill_revisions': overrides, 'main_revision': head,
            'updates_available': bool(touched) or license_changed,
            'new_skills': sorted(new_names - old_names), 'removed_skills': sorted(old_names - new_names),
            'modified_skills': sorted(n for n in old_names & new_names if any(p.startswith(n + '/') for p in touched)),
            'added_files': added, 'removed_files': removed, 'changed_files': changed,
            'license_changed': license_changed,
            'compare_url': f"{spec['repository']}/compare/{spec['revision']}...{head}",
        }


def check(sources):
    reports, errors = {}, {}
    for name, spec in sources.items():
        if spec['mode'] != 'adapted':
            continue
        try:
            reports[name] = check_collection(spec)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            errors[name] = str(error)
    return {'status': 'check_failed' if errors else 'complete', 'collections': reports,
            'errors': errors, 'updates_available': any(r['updates_available'] for r in reports.values())}


def render(report):
    lines = ['Read-only upstream check. No skills or pins changed.']
    for name, entry in report['collections'].items():
        lines += [f"\n{name}: {'updates available' if entry['updates_available'] else 'current'}",
                  f"main: {entry['main_revision']}", f"baseline: {entry['pinned_revision']}",
                  f"skill pins: {json.dumps(entry['skill_revisions'], sort_keys=True)}"]
        for key in ('new_skills', 'removed_skills', 'modified_skills', 'added_files', 'removed_files', 'changed_files'):
            lines.append(f"{key}: {', '.join(entry[key]) or 'none'}")
        lines += [f"license_changed: {entry['license_changed']}", entry['compare_url']]
    lines += [f'\n{name} failed: {error}' for name, error in report['errors'].items()]
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'sources.json')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        report = check(load_sources(args.manifest))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        report = {'status': 'check_failed', 'collections': {}, 'errors': {'manifest': str(error)}, 'updates_available': False}
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 2 if report['errors'] else 1 if report['updates_available'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

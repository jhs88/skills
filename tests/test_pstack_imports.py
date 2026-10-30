"""Packaging and portability contracts for the selected Pstack additions."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SELECTED = {'bro', 'blast-radius', 'how', 'why', 'recall', 'typescript-best-practices'}


class PstackImports(unittest.TestCase):
    def test_selection_and_pins_preserve_existing_skills(self):
        sources = json.loads((ROOT / 'sources.json').read_text())
        spec = sources['pstack']
        self.assertEqual(set(spec['selected']), SELECTED | {'technical-writing', 'unslop'})
        self.assertNotIn('reflect', spec['selected'])
        self.assertNotIn('teach', spec['selected'])
        for name in SELECTED:
            self.assertRegex(spec['skill_revisions'][name], r'^[0-9a-f]{40}$')
        self.assertTrue((ROOT / 'skills/mattpocock/teach/SKILL.md').is_file())

    def test_no_cursor_runtime_or_unselected_skill_dependencies(self):
        forbidden = [r'~?/\.cursor/', r'pstack-models\.mdc', r'generalPurpose',
                     r'grok-4\.7', r'claude-opus-5', r'poteto-mode', r'`arena`',
                     r'host.{0,20}tools', r'active model', r'native delegation',
                     r'tool catalog', r'connector status',
                     r'\*\*type-system-discipline\*\*', r'\*\*boundary-discipline\*\*']
        for name in SELECTED:
            for path in (ROOT / 'skills/pstack' / name).rglob('*.md'):
                text = path.read_text()
                for pattern in forbidden:
                    with self.subTest(file=str(path), pattern=pattern):
                        self.assertIsNone(re.search(pattern, text))

    def test_workflows_are_platform_neutral_and_preserve_evidence_safeguards(self):
        for name in ['how', 'why', 'blast-radius', 'recall']:
            text = (ROOT / 'skills/pstack' / name / 'SKILL.md').read_text()
            with self.subTest(skill=name):
                self.assertIn('does not prescribe tools or models', text)
                self.assertRegex(text, r'unavailable|sequentially')
        why = (ROOT / 'skills/pstack/why/SKILL.md').read_text()
        self.assertIn('Keep the investigation read-only', why)
        self.assertIn('Do not assume any integration exists', why)
        recall = (ROOT / 'skills/pstack/recall/SKILL.md').read_text()
        self.assertIn('untrusted evidence', recall)
        self.assertIn('Do not assume a filesystem layout', recall)

    def test_names_are_unique_for_cli_discovery(self):
        names = []
        for path in (ROOT / 'skills').rglob('SKILL.md'):
            match = re.search(r'^name: [\'"]?([^\n\'"]+)', path.read_text(), re.M)
            if match is None:
                self.fail(f'Missing skill name: {path}')
            else:
                names.append(match[1])
        self.assertEqual(len(names), len(set(names)))


if __name__ == '__main__':
    unittest.main()

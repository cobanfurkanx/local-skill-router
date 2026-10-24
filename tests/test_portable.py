"""Public-package contracts using synthetic files only."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('portable_router', ROOT / 'scripts/router.py')
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)
spec = importlib.util.spec_from_file_location('portable_install', ROOT / 'scripts/install_skill.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class PortableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'tests')
        self.root = Path(self.temp.name)
        self.state = self.root / 'private state'
        self.config = self.root / 'config.json'
        self.config.write_text(json.dumps({'roots':[{'path':'./library','source':'shared','agents':['any']}],
                                          'min_score':0.1}), encoding='utf-8')
        self.skill = self.root / 'library/python-debug/SKILL.md'
        self.skill.parent.mkdir(parents=True)
        self.skill.write_text('---\nname: python-debug\ndescription: Python debugging regression verification\n---\n# Workflow\n', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args, input=None, script=None, config=None):
        env = os.environ.copy()
        env['PYTHONUTF8'] = '1'
        return subprocess.run([sys.executable, str(script or ROOT / 'scripts/router.py'),
                               '--config', str(config or self.config), '--state-dir', str(self.state), *args],
                              cwd=self.root, input=input, capture_output=True, text=True,
                              encoding='utf-8', env=env, timeout=20)

    def test_relative_config_roots_and_private_state_cli(self):
        proc = self.cli('query', 'Python debugging', '--agent', 'opencode')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result['candidates'][0]['path'], str(self.skill.resolve()))
        self.assertTrue((self.state / 'index.json').is_file())
        self.assertFalse((self.skill.parent / 'index.json').exists())

    def test_default_threshold_works_in_a_small_personal_library(self):
        self.config.write_text(json.dumps({'roots':[{'path':'./library','source':'shared'}]}),encoding='utf-8')
        found = self.cli('query','Python debugging regression verification')
        self.assertEqual(len(json.loads(found.stdout)['candidates']),1)
        missing = self.cli('query','xylophone orchestration')
        self.assertEqual(json.loads(missing.stdout)['candidates'],[])

    def test_plan_deduplicated_and_uncovered_cli(self):
        proc = self.cli('plan', '--task', 'Python debugging', '--task', 'xylophone')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(len(result['suggested_reads']), 1)
        self.assertEqual(result['steps'][1]['status'], 'no_match')

    def test_empty_libraries_are_valid(self):
        self.config.write_text('{"roots":[]}', encoding='utf-8')
        proc = self.cli('query', 'Python')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['candidates'], [])

    def test_malformed_configs_rejected_before_state_write(self):
        for config in [[], {'roots':None}, {'roots':['bad']}, {'roots':[{'path':'x'}]},
                       {'roots':[], 'min_score':-1}, {'roots':[], 'relative_threshold':True},
                       {'roots':[], 'skip_patterns':['[']}, {'roots':[], 'aliases':[{'match':'x','expand':'y'}]},
                       {'roots':[], 'hook_cache_dir':[]}]:
            with self.subTest(config=config):
                self.config.write_text(json.dumps(config), encoding='utf-8')
                proc = self.cli('stats')
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertNotIn('Traceback', proc.stderr)
                self.assertFalse(self.state.exists())

    def test_missing_task_file_is_clear_cli_error(self):
        proc = self.cli('query', '--task-file', str(self.root / 'absent.txt'))
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn('Traceback', proc.stderr)

    def test_plan_file_schema_and_utf8_text(self):
        path = self.root / 'tasks.json'
        path.write_text('["Python debugging", "regression verification"]', encoding='utf-8')
        proc = self.cli('plan', '--task-file', str(path), '--text')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.count(str(self.skill.resolve())), 1)
        path.write_text('{}', encoding='utf-8')
        self.assertEqual(self.cli('plan', '--task-file', str(path)).returncode, 2)

    def test_hook_requires_refresh_and_rejects_invalid_events(self):
        event = json.dumps({'prompt':'Python debugging','cwd':str(self.root),'session_id':'synthetic-session'})
        self.assertEqual(self.cli('hook','--agent','claude',input=event).stdout, '')
        self.assertEqual(self.cli('refresh').returncode, 0)
        for invalid in ['[]', 'null', '{', '{"prompt":[],"cwd":3}']:
            proc = self.cli('hook','--agent','claude',input=invalid)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, '')
        first = self.cli('hook','--agent','claude',input=event)
        self.assertIn('additionalContext', first.stdout)
        second = self.cli('hook','--agent','claude',input=event)
        self.assertEqual(second.stdout, '')
        cached = ''.join(p.read_text(encoding='utf-8') for p in (self.state / 'hooks').glob('*.json'))
        self.assertNotIn('synthetic-session', cached)
        self.assertNotIn('Python debugging', cached)

    def test_hook_does_not_use_another_configs_index(self):
        self.assertEqual(self.cli('refresh').returncode, 0)
        self.config.write_text('{"roots":[]}', encoding='utf-8')
        proc = self.cli('hook','--agent','claude',input='{"prompt":"Python debugging"}')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, '')

    def test_hook_observes_changed_invocation_policy(self):
        self.assertEqual(self.cli('refresh').returncode, 0)
        policy = self.skill.parent / 'agents/openai.yaml'
        policy.parent.mkdir()
        policy.write_text('policy:\n  allow_implicit_invocation: false\n', encoding='utf-8')
        proc = self.cli('hook','--agent','claude',input='{"prompt":"Python debugging"}')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        explicit = self.cli('query','Python debugging','--explicit','python-debug')
        context = json.loads(proc.stdout)['hookSpecificOutput']['additionalContext']
        self.assertNotIn('python-debug', context)
        self.assertNotIn(str(self.skill), context)
        self.assertIn('No match', context)
        self.assertEqual(len(json.loads(explicit.stdout)['candidates']), 1)

    def test_feedback_on_fresh_state_and_learning(self):
        proc = self.cli('record','--task','Python debugging','--skill','python-debug','--outcome','helpful')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        learned = self.cli('learn','--task','Python debugging','--skill','python-debug','--agent','codex',
                           '--evidence','Synthetic behavior checks passed')
        self.assertEqual(learned.returncode, 0, learned.stderr)
        result = self.cli('query','Python debugging','--agent','codex')
        self.assertTrue(json.loads(result.stdout)['fast_path'])
        self.skill.write_text('---\nname: python-debug\ndescription: completely different workflow\n---\n', encoding='utf-8')
        result = self.cli('query','Python debugging','--agent','codex')
        self.assertNotIn('fast_path', json.loads(result.stdout))

    def test_index_default_uses_current_state_directory(self):
        with patch.object(router, 'BASE', self.state):
            router.build_index(router.load_config(self.config))
        self.assertTrue((self.state / 'index.json').is_file())

    def test_unknown_learning_skill_is_clear_error(self):
        proc = self.cli('learn','--task','Python debugging','--skill','absent', '--evidence','fixture')
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn('Traceback', proc.stderr)
        self.assertFalse((self.state / 'learned-routes.json').exists())

    @unittest.skipIf(os.name == 'nt', 'Case-sensitive filesystem contract')
    def test_case_distinct_libraries_are_not_collapsed(self):
        upper = self.root / 'LIBRARY/second/SKILL.md'
        upper.parent.mkdir(parents=True)
        upper.write_text('---\nname: second\ndescription: distinct second workflow\n---\n', encoding='utf-8')
        config = {'roots':[{'path':str(self.root / 'library'),'source':'one'},
                          {'path':str(self.root / 'LIBRARY'),'source':'two'}]}
        with patch.object(router, 'BASE', self.state):
            result = router.build_index(config)
        self.assertEqual(len(result['records']), 2)

    def test_existing_routed_file_is_searchable_without_renaming(self):
        archived = self.skill.with_name('SKILL.routed.md')
        self.skill.rename(archived)
        result = self.cli('query','Python debugging')
        self.assertEqual(Path(json.loads(result.stdout)['candidates'][0]['path']), archived.resolve())
        self.assertTrue(archived.exists())
        self.assertFalse(self.skill.exists())

    def test_skill_directory_symlink_cycles_do_not_repeat(self):
        link = self.skill.parent / 'loop'
        try:
            link.symlink_to(self.root / 'library', target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Directory symlinks unavailable in this environment')
        self.assertEqual(len(list(router.walk_skills(self.root / 'library'))), 1)

    def test_installer_dry_run_and_no_overwrite(self):
        target = self.root / 'installed skill'
        result = installer.install(target, 'opencode', dry_run=True)
        self.assertEqual(len(result), len(installer.FILES))
        self.assertFalse(target.exists())
        installer.install(target, 'opencode')
        self.assertEqual((target / 'LICENSE').read_bytes(), (ROOT / 'LICENSE').read_bytes())
        contents = (target / 'SKILL.md').read_text(encoding='utf-8')
        self.assertIn(target.as_posix(), contents)
        self.assertIn('--agent opencode', contents)
        self.assertNotIn('<skill-dir>', contents)
        snapshot = (target / 'SKILL.md').read_bytes()
        with self.assertRaises(ValueError):
            installer.install(target, 'claude')
        self.assertEqual((target / 'SKILL.md').read_bytes(), snapshot)
        proc = self.cli('query','Python debugging',script=target / 'scripts/router.py')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['candidates'][0]['name'], 'python-debug')

    def test_installer_reads_all_payloads_before_creating_target(self):
        target = self.root / 'must stay absent'
        with patch.object(installer, 'PACKAGE', self.root / 'absent source'):
            with self.assertRaises(OSError):
                installer.install(target)
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()

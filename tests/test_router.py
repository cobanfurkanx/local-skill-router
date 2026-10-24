"""Isolated routing checks. Run with the standard library unittest runner."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import io


ROUTER = Path(__file__).resolve().parents[1] / 'scripts/router.py'
spec = importlib.util.spec_from_file_location('router', ROUTER)
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.root = Path(self.temp.name)
        self.old_base, router.BASE = router.BASE, self.root
        self.config = {'roots': [], 'min_score': 0.01, 'relative_threshold': 0.1}

    def tearDown(self):
        router.BASE = self.old_base
        self.temp.cleanup()

    def skill(self, name, description, source='shared', agents=None, explicit=False):
        path = self.root / source / name / 'SKILL.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'---\nname: {name}\ndescription: {description}\ndisable-model-invocation: {str(explicit).lower()}\n---\n# Workflow\n', encoding='utf-8')
        return router.parse_skill(path, {'source': source, 'agents': agents or ['any']})

    def search(self, task, records, **kw):
        return router.search(task, self.config, {'records': records}, **kw)['candidates']

    def test_plan_covers_distinct_deliverables(self):
        records = [self.skill('frontend', 'React interface accessibility'), self.skill('browser', 'browser runtime verification')]
        result = router.plan(['React interface', 'browser verification'], self.config, {'records': records})
        self.assertEqual({s['name'] for s in result['suggested_reads']}, {'frontend', 'browser'})
        self.assertEqual(len(result['steps']), 2)

    def test_hook_cache_rechecks_changed_task_with_same_candidates(self):
        config = dict(self.config,hook_cache_dir=str(self.root/'hooks'))
        record = self.skill('frontend','React interface accessibility')
        result = {'candidates':[record]}
        event = {'session_id':'one','prompt':'React interface','cwd':str(self.root)}
        self.assertTrue(router.hook_changed(event,result,'codex',config))
        self.assertFalse(router.hook_changed(event,result,'codex',config))
        self.assertTrue(router.hook_changed(dict(event,prompt='React accessibility'),result,'codex',config))
        Path(record['path']).write_text('changed skill',encoding='utf-8')
        self.assertTrue(router.hook_changed(dict(event,prompt='React accessibility'),result,'codex',config))

    def test_guidance_covers_json_text_and_empty_library(self):
        result = router.search('interface design',self.config,{'records':[]})
        self.assertIn('acceptance criteria',result['instruction'])
        for verbose in (False,True):
            self.assertIn('concrete gaps',router.render(result,verbose))

    def test_plan_deduplicates_reads_and_tasks(self):
        record = self.skill('frontend', 'React interface accessibility')
        result = router.plan(['React interface', 'React interface', 'React accessibility'], self.config, {'records': [record]})
        self.assertEqual(len(result['steps']), 2)
        self.assertEqual(len(result['suggested_reads']), 1)
        self.assertEqual(len(result['suggested_reads'][0]['tasks']), 2)
        self.assertEqual(result['estimated_tokens'], result['suggested_reads'][0]['estimated_tokens'])

    def test_plan_exposes_uncovered_task(self):
        result = router.plan(['xylophone'], self.config, {'records': []})
        self.assertEqual(result['steps'][0]['status'], 'no_match')
        self.assertEqual(result['suggested_reads'], [])

    def test_plan_rejects_invalid_inputs(self):
        for tasks in ([], [''], ['   '], [3], ['task'] * 9):
            with self.subTest(tasks=tasks), self.assertRaises(ValueError):
                router.plan(tasks, self.config, {'records': []})

    def test_policy_change_blocks_cached_implicit_invocation(self):
        record = self.skill('deploy', 'deploy application')
        policy = Path(record['path']).parent / 'agents/openai.yaml'
        policy.parent.mkdir()
        policy.write_text('policy:\n  allow_implicit_invocation: false\n')
        self.assertEqual(self.search('deploy', [record]), [])
        self.assertEqual(len(self.search('deploy', [record], explicit=['DEPLOY'])), 1)

    def test_frontmatter_change_blocks_cached_implicit_invocation(self):
        record = self.skill('deploy', 'deploy application')
        self.skill('deploy', 'deploy application', explicit=True)
        self.assertEqual(self.search('deploy', [record]), [])

    def test_changed_content_is_used_immediately(self):
        record = self.skill('helper', 'React interface')
        self.skill('helper', 'Postgres database indexing and query analysis')
        self.assertEqual(self.search('React', [record]), [])
        self.assertEqual(len(self.search('Postgres', [record])), 1)

    def test_unreadable_policy_does_not_crash_or_select(self):
        record = self.skill('deploy', 'deploy application')
        policy = Path(record['path']).parent / 'agents/openai.yaml'
        policy.parent.mkdir()
        policy.write_bytes(b'\xff\xfe\x81')
        self.assertEqual(self.search('deploy', [record]), [])

    def test_agent_compatibility(self):
        record = self.skill('codex-only', 'image generation', agents=['codex'])
        self.assertEqual(self.search('image generation', [record], agent='claude'), [])
        self.assertEqual(len(self.search('image generation', [record], agent='codex')), 1)

    def test_project_override_preserved(self):
        global_record = self.skill('frontend', 'React interface')
        local_record = self.skill('frontend', 'React project interface', source='project')
        self.assertEqual(self.search('React', [global_record, local_record])[0]['source'], 'project')

    def test_deleted_skill_is_not_returned(self):
        record = self.skill('frontend', 'React interface')
        Path(record['path']).unlink()
        self.assertEqual(self.search('React', [record]), [])

    def test_learning_invalidated_after_content_changes(self):
        record = self.skill('frontend', 'React interface')
        index = {'records': [record]}
        router.learn('React interface', ['frontend'], 'codex', str(self.root), 'global', 'fixture verification', self.config, index)
        self.assertTrue(router.search('React interface', self.config, index, 'codex')['fast_path'])
        self.skill('frontend', 'Postgres database query tuning')
        result = router.search('React interface', self.config, index, 'codex')
        self.assertNotIn('fast_path', result)
        self.assertEqual(result['candidates'], [])

    def test_trivial_task_skips_skills(self):
        self.config['skip_patterns'] = ['hello']
        record = self.skill('greetings', 'hello greetings')
        self.assertEqual(self.search('hello', [record]), [])

    def test_plan_render_includes_tasks_and_limits(self):
        record = self.skill('frontend', 'React interface')
        result = router.plan(['React interface'], self.config, {'records': [record]})
        rendered = router.render(result)
        self.assertIn('Task: React interface', rendered)
        self.assertIn('not automatic invocation', rendered)

    def test_additional_project_skill_directories(self):
        for directory in ('.cursor', '.github', '.copilot', '.trae'):
            path = self.root / directory / 'skills/example/SKILL.md'
            path.parent.mkdir(parents=True)
            path.write_text('---\nname: example\ndescription: local workflow\n---\n')
        self.assertEqual(len(router.project_records(self.root)), 4)


    def test_hook_deduplicates_only_with_session_identity(self):
        record = self.skill('frontend', 'React interface')
        result = {'candidates': self.search('React', [record])}
        config = {'hook_cache_dir': str(self.root / 'hooks')}
        event = {'session_id': 'one', 'cwd': str(self.root)}
        self.assertTrue(router.hook_changed(event, result, 'codex', config))
        self.assertFalse(router.hook_changed(event, result, 'codex', config))
        self.assertTrue(router.hook_changed(dict(event, session_id='two'), result, 'codex', config))
        self.assertTrue(router.hook_changed(event, result, 'claude', config))
        self.assertTrue(router.hook_changed({}, result, 'codex', config))
        self.assertTrue(router.hook_changed({}, result, 'codex', config))

    def test_hook_change_or_expiry_emits_again_without_raw_prompt_storage(self):
        record = self.skill('frontend', 'React interface')
        result = {'candidates': self.search('React', [record])}
        config = {'hook_cache_dir': str(self.root / 'hooks')}
        event = {'session_id': 'one', 'cwd': str(self.root), 'prompt': 'private query'}
        self.assertTrue(router.hook_changed(event, result, 'codex', config))
        self.skill('frontend', 'React interface changed')
        self.assertTrue(router.hook_changed(event, result, 'codex', config))
        with patch.object(router.time, 'time', return_value=router.time.time() + 901):
            self.assertTrue(router.hook_changed(event, result, 'codex', config))
        self.assertNotIn('private query', ''.join(p.read_text() for p in (self.root / 'hooks').glob('*.json')))

    def test_plan_builds_corpus_once(self):
        record = self.skill('frontend', 'React interface')
        with patch.object(router, 'prepare_search', wraps=router.prepare_search) as prepare:
            router.plan(['React interface', 'React accessibility'], self.config, {'records': [record]})
        self.assertEqual(prepare.call_count, 1)

    def test_compact_output_preserves_requirements_and_deduplicates_paths(self):
        record = self.skill('frontend', 'React interface')
        record['requirements'] = ['Requires authorized browser access.']
        result = router.plan(['React interface', 'React accessibility'], self.config, {'records': [record]})
        compact = router.render(result)
        self.assertEqual(compact.count(record['path']), 1)
        self.assertIn('Requires authorized browser access.', compact)


if __name__ == '__main__':
    unittest.main()

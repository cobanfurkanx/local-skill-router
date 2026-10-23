"""Native adapter configuration and reversible installation, without private libraries."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'scripts'))
import agents
import changes
import setup


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'tests')
        self.root = Path(self.temp.name)
        self.home = self.root / 'test home'
        self.state = self.root / 'private state'
        self.project = self.root / 'project'
        self.home.mkdir()
        self.project.mkdir()
        skill = self.home / '.agents/skills/routing-probe/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('---\nname: routing-probe\ndescription: Python debugging regression testing verification\n---\n# Checks\nUse fixture checks.\n',encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def install(self, selected, **kw):
        return setup.install(self.home,self.state,selected,self.project,{},**kw)

    def test_dry_run_changes_no_files_or_state(self):
        result = self.install(['codex','claude','opencode','antigravity'],dry_run=True)
        self.assertTrue(result['changes'])
        self.assertFalse(self.state.exists())
        self.assertFalse((self.home / '.codex').exists())

    def test_all_profiles_and_idempotent_native_configuration(self):
        result = self.install(list(agents.AGENTS))
        self.assertEqual(result['indexed_files'],1)
        for agent in agents.AGENTS:
            roots,instruction,mode = agents.locations(agent,self.home,self.project,{})
            self.assertTrue(all((r / 'local-skill-router/SKILL.md').exists() for r in roots))
            if instruction:
                self.assertIn(setup.START,instruction.read_text(encoding='utf-8'))
        again = self.install(list(agents.AGENTS))
        self.assertEqual(again['changed_files'],0)

    def test_preserves_existing_instructions_hooks_and_permissions(self):
        instruction = self.home / '.claude/CLAUDE.md'
        instruction.parent.mkdir()
        instruction.write_text('Unrelated user instructions.\n',encoding='utf-8')
        settings = instruction.parent / 'settings.json'
        old = {'permissions':{'deny':['Bash(rm *)']},'hooks':{'UserPromptSubmit':[{'hooks':[{'type':'command','command':'other-hook'}]}]}}
        settings.write_text(json.dumps(old),encoding='utf-8')
        result = self.install(['claude'])
        installed = json.loads(settings.read_text())
        self.assertEqual(installed['permissions'],old['permissions'])
        self.assertEqual(installed['hooks']['UserPromptSubmit'][0],old['hooks']['UserPromptSubmit'][0])
        self.assertIn('Unrelated user instructions.',instruction.read_text())
        self.assertEqual(self.install(['claude'])['changed_files'],0)
        changes.undo(self.state,result['operation'],[self.home,self.state,self.project])
        self.assertEqual(json.loads(settings.read_text()),old)
        self.assertEqual(instruction.read_text(),'Unrelated user instructions.\n')

    def test_malformed_settings_refused_before_any_install(self):
        target = self.home / '.claude/settings.json'
        target.parent.mkdir()
        target.write_text('{broken',encoding='utf-8')
        with self.assertRaises(ValueError):
            self.install(['codex','claude'])
        self.assertFalse((self.home / '.codex').exists())
        self.assertFalse(self.state.exists())
        self.assertEqual(target.read_text(),'{broken')

    def test_undo_refuses_user_edits_without_partial_restore(self):
        result = self.install(['codex','opencode'])
        target = self.home / '.codex/AGENTS.md'
        target.write_text(target.read_text()+'new user edits\n',encoding='utf-8')
        with self.assertRaises(ValueError):
            changes.undo(self.state,result['operation'],[self.home,self.state,self.project])
        self.assertTrue((self.home / '.config/opencode/plugins/local-skill-router.js').exists())
        self.assertIn('new user edits',target.read_text())

    def test_nonobject_claude_hooks_refused_before_writes(self):
        target = self.home / '.claude/settings.json'
        target.parent.mkdir()
        target.write_text('{"hooks":[]}',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'hooks must be a JSON object'):
            self.install(['codex','claude'])
        self.assertFalse(self.state.exists())
        self.assertFalse((self.home / '.codex').exists())

    def test_undo_idempotent_and_does_not_remove_later_files(self):
        result = self.install(['codex'])
        keep = self.home / '.codex/keep.txt'
        keep.write_text('keep')
        undone = changes.undo(self.state,result['operation'],[self.home,self.state,self.project])
        self.assertGreater(undone['restored_files'],0)
        self.assertEqual(keep.read_text(),'keep')
        self.assertEqual(changes.undo(self.state,result['operation'],[self.home,self.state,self.project])['restored_files'],0)

    def test_transaction_rollback_after_simulated_write_failure(self):
        a,b = self.home/'a.txt',self.home/'b.txt'
        original = changes.write
        def fail(path, payload):
            if path==b and payload is not None:
                raise OSError('simulated lock')
            return original(path,payload)
        with patch.object(changes,'write',side_effect=fail):
            with self.assertRaises(OSError):
                changes.apply(self.state,[(a,None,b'one'),(b,None,b'two')],[self.home],'fixture')
        self.assertFalse(a.exists())
        self.assertFalse(b.exists())
        journal = next((self.state/'operations').glob('*.json'))
        changes.undo(self.state,journal.stem,[self.home])

    def test_undo_preserves_file_changed_during_restore(self):
        a,b = self.home/'a.txt',self.home/'b.txt'
        a.write_bytes(b'old a')
        b.write_bytes(b'old b')
        installed = changes.apply(self.state,[(a,b'old a',b'new a'),(b,b'old b',b'new b')],[self.home],'fixture')
        original = changes.write
        def edit_during_restore(path, payload):
            original(path,payload)
            if path == b:
                a.write_bytes(b'concurrent user edit')
        with patch.object(changes,'write',side_effect=edit_during_restore):
            with self.assertRaisesRegex(ValueError,'changed during undo'):
                changes.undo(self.state,installed['operation'],[self.home])
        self.assertEqual(a.read_bytes(),b'concurrent user edit')
        self.assertEqual(b.read_bytes(),b'old b')

    def test_native_claude_exec_form_produces_context_without_shell(self):
        self.install(['claude'])
        settings = json.loads((self.home/'.claude/settings.json').read_text())
        hook = settings['hooks']['UserPromptSubmit'][0]['hooks'][0]
        event = {'prompt':'Python debugging regression verification','cwd':str(self.project),'session_id':'fixture'}
        result = subprocess.run([hook['command'],*hook['args']],input=json.dumps(event),capture_output=True,text=True,encoding='utf-8',timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('routing-probe',result.stdout)

    @unittest.skipUnless(shutil.which('node'),'Node unavailable for the optional OpenCode plugin contract test')
    def test_opencode_plugin_injects_local_context_and_deduplicates(self):
        self.install(['opencode'])
        plugin = self.home / '.config/opencode/plugins/local-skill-router.js'
        module = self.root / 'plugin.mjs'
        module.write_bytes(plugin.read_bytes())
        harness = self.root / 'check.mjs'
        harness.write_text('''import { pathToFileURL } from 'node:url';
const { LocalSkillRouter } = await import(pathToFileURL(process.argv[2]));
const hooks = await LocalSkillRouter({ directory:process.argv[3] });
const first = { message:{id:'msg_fixture'}, parts:[{type:'text',text:'Python debugging regression verification'}] };
await hooks['chat.message']({sessionID:'fixture'},first);
const second = { message:{id:'msg_next'}, parts:[{type:'text',text:'Python debugging regression verification'}] };
await hooks['chat.message']({sessionID:'fixture'},second);
const added = first.parts.find(p=>p.synthetic && p.text.includes('routing-probe'));
if (!added || !added.id.startsWith('prt_') || added.sessionID!=='fixture' || added.messageID!=='msg_fixture' || second.parts.length!==1) process.exit(1);
''',encoding='utf-8')
        result = subprocess.run(['node',str(harness),str(module),str(self.project)],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_cursor_requires_project_and_trae_is_explicitly_manual(self):
        with self.assertRaises(ValueError):
            setup.plan(self.home,self.state,['cursor'],env={})
        result = self.install(['trae'])
        self.assertEqual(result['profiles'][0]['mode'],'manual-rule')
        self.assertIsNone(result['profiles'][0]['instructions'])

    def test_remote_policy_opt_in_and_revoke(self):
        installed = self.install(['codex'],remote_policy='reviewed')
        skill = (Path(installed['app']) / 'SKILL.md').read_text(encoding='utf-8')
        for helper in ('router','remote'):
            self.assertIn(f'/scripts/{helper}.py" --state-dir "{self.state.as_posix()}"',skill)
        self.assertEqual(json.loads((self.state/'remote-policy.json').read_text())['global_install'],'reviewed')
        self.install(['codex'])
        self.assertEqual(json.loads((self.state/'remote-policy.json').read_text())['global_install'],'reviewed')
        self.install(['codex'],remote_policy='ask')
        self.assertEqual(json.loads((self.state/'remote-policy.json').read_text())['global_install'],'ask')


if __name__=='__main__':
    unittest.main()

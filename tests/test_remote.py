"""Synthetic remote archives; no network or downloaded helpers execute in this suite."""
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import changes
import remote


def archive(extra=None, body=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output,'w') as z:
        z.writestr('repo-main/','')
        z.writestr('repo-main/skills/demo/SKILL.md',body or '---\nname: demo\ndescription: Fixture workflow\n---\n# Workflow\nRead scripts/helper.py.\n')
        z.writestr('repo-main/skills/demo/scripts/helper.py','raise RuntimeError("must not execute")\n')
        z.writestr('repo-main/LICENSE','MIT fixture notice')
        for name,payload in (extra or {}).items():
            z.writestr(name,payload)
    return output.getvalue()


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'tests')
        self.root = Path(self.temp.name)
        self.home = self.root/'home'
        self.state = self.root/'state'
        self.home.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def stage(self, body=None):
        with patch.object(remote,'fetch',side_effect=[json.dumps({'sha':'a'*40}).encode(),archive(body=body)]):
            return remote.inspect('example/fixtures',self.state,skill='demo')

    def test_search_returns_data_without_installation_or_raw_query_state(self):
        response = {'skills':[{'source':'example/fixtures','skillId':'demo','name':'demo','installs':42},
                              {'source':'unsupported.example','skillId':'other','name':'other'}]}
        with patch.object(remote,'fetch',return_value=json.dumps(response).encode()) as fetch:
            result = remote.search('generic fixture',3)
        self.assertEqual(len(result['candidates']),1)
        self.assertIn('q=generic+fixture',fetch.call_args.args[0])
        self.assertFalse(self.state.exists())
        self.assertFalse((self.home/'.agents').exists())

    def test_search_rejects_unbounded_query_and_changed_api_shape(self):
        for query in ['x','x'*201]:
            with self.assertRaises(ValueError):
                remote.search(query)
        with patch.object(remote,'fetch',return_value=b'{"other":[]}'):
            with self.assertRaises(ValueError):
                remote.search('generic fixture')

    def test_https_hosts_and_repository_identifiers_are_bounded(self):
        for url in ['http://skills.sh/','https://127.0.0.1/','https://skills.sh@evil.example/','https://skills.sh:8443/']:
            with self.assertRaises(ValueError):
                remote.safe_url(url)
        for repo in ['../escape','owner/repo; command','https://github.com/owner/repo','owner/..']:
            with self.assertRaises(ValueError):
                remote.repository(repo)

    def test_inspection_pins_content_and_keeps_helpers_unexecuted(self):
        result = self.stage()
        self.assertEqual(result['commit'],'a'*40)
        self.assertIn('LICENSE',result['files'])
        self.assertIn('scripts/helper.py',result['files'])
        self.assertTrue((Path(result['inspection'])/'files/SKILL.md').exists())
        self.assertFalse((self.home/'.agents').exists())

    def test_install_plan_is_not_installation(self):
        result = self.stage()
        planned = remote.install(Path(result['inspection']),result['review_digest'],['codex'],self.home,self.state,{})
        self.assertTrue(planned['approval_required'])
        self.assertFalse((self.home/'.agents').exists())

    def test_reviewed_global_install_provenance_and_undo(self):
        result = self.stage()
        installed = remote.install(Path(result['inspection']),result['review_digest'],['codex','opencode'],self.home,self.state,{},yes=True)
        self.assertTrue(installed['installed'])
        for target in [self.home/'.agents/skills/demo',self.home/'.codex/skills/demo',self.home/'.config/opencode/skills/demo']:
            self.assertEqual((target/'LICENSE').read_text(),'MIT fixture notice')
            source = json.loads((target/'.local-skill-router-source.json').read_text())
            self.assertEqual(source['commit'],'a'*40)
        changes.undo(self.state,installed['operation'],[self.home])
        self.assertFalse((self.home/'.agents/skills/demo').exists())
        self.assertTrue(Path(result['inspection']).exists())

    def test_tampering_or_wrong_review_digest_refused_before_global_write(self):
        result = self.stage()
        with self.assertRaises(ValueError):
            remote.install(Path(result['inspection']),'0'*64,['codex'],self.home,self.state,{},True)
        (Path(result['inspection'])/'files/scripts/helper.py').write_text('changed')
        with self.assertRaises(ValueError):
            remote.install(Path(result['inspection']),result['review_digest'],['codex'],self.home,self.state,{},True)
        self.assertFalse((self.home/'.agents').exists())

    def test_existing_global_skill_never_overwritten(self):
        result = self.stage()
        existing = self.home/'.codex/skills/demo/SKILL.md'
        existing.parent.mkdir(parents=True)
        existing.write_text('user edit')
        with self.assertRaises(ValueError):
            remote.install(Path(result['inspection']),result['review_digest'],['codex'],self.home,self.state,{},True)
        self.assertEqual(existing.read_text(),'user edit')
        self.assertFalse((self.home/'.agents').exists())

    def test_unsafe_paths_symlinks_and_duplicate_case_entries_rejected(self):
        for path in ['../escape','/absolute','C:/drive','scripts\\escape','scripts/../escape','AUX.txt','a\nb','a//b','.GIT/config','a?.py','.LOCAL-SKILL-ROUTER-SOURCE.JSON']:
            with self.subTest(path=path),self.assertRaises(ValueError):
                remote.relative(path)
        with self.assertRaises(ValueError):
            remote.payloads_from_archive(archive({'repo-main/skills/demo/../escape':b'no'}),selected='skills/demo')
        with self.assertRaises(ValueError):
            remote.payloads_from_archive(archive({'repo-main/skills/demo/skill.md':b'conflict'}),selected='skills/demo')
        output = io.BytesIO()
        with zipfile.ZipFile(output,'w') as z:
            z.writestr('repo-main/','')
            entry = zipfile.ZipInfo('repo-main/skills/demo/SKILL.md')
            entry.create_system=3
            entry.external_attr=(stat.S_IFLNK|0o777)<<16
            z.writestr(entry,'/outside')
        with self.assertRaises(ValueError):
            remote.payloads_from_archive(output.getvalue(),selected='skills/demo')

    def test_limits_and_ambiguous_skill_selection(self):
        with patch.object(remote,'MAX_SKILL',1),self.assertRaises(ValueError):
            remote.payloads_from_archive(archive(),selected='skills/demo')
        other = '---\nname: demo\ndescription: duplicate\n---\n'
        with self.assertRaises(ValueError):
            remote.payloads_from_archive(archive({'repo-main/other/demo/SKILL.md':other}),skill='demo')

    def test_explicit_only_frontmatter_is_preserved(self):
        body = '---\nname: demo\ndescription: Fixture\ndisable-model-invocation: true\n---\n'
        result = self.stage(body)
        installed = remote.install(Path(result['inspection']),result['review_digest'],['codex'],self.home,self.state,{},True)
        path = self.home/'.agents/skills/demo/SKILL.md'
        self.assertEqual(path.read_text(),body)
        self.assertTrue(installed['installed'])

    def test_standing_policy_authorization_and_fail_closed_schema(self):
        result = self.stage()
        (self.state/'remote-policy.json').write_text('{"global_install":"reviewed"}')
        installed = remote.install(Path(result['inspection']),result['review_digest'],['codex'],self.home,self.state,{})
        self.assertTrue(installed['installed'])
        (self.state/'remote-policy.json').write_text('{"global_install":"unknown"}')
        with self.assertRaises(ValueError):
            remote.policy(self.state)


if __name__=='__main__':
    unittest.main()

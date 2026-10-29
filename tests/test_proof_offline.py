import tempfile, unittest, subprocess
from pathlib import Path
from unittest import mock
from repo_proof import proof


class T(unittest.TestCase):
    def test_setup_logging_and_flow_offline(self):
        """No network: a fake clone + no deps; the logger must accept every setup event (10/29 'multiple values for step')."""
        t = Path(tempfile.mkdtemp()); (t / 'project').mkdir()
        def fake_run(argv, **kw):
            (t / 'project' / 'repo').mkdir(parents=True, exist_ok=True); (t / 'project' / 'repo' / 'package.json').write_text('{}')
            return subprocess.CompletedProcess(argv, 0, '', '')
        events = []
        with mock.patch('subprocess.run', fake_run), mock.patch('repo_proof.sandbox.run', lambda *a, **k: {'exit': 0, 'why': None, 'seconds': 0.1, 'output': 'ok'}):
            st = proof.setup(t, 'https://github.com/a/b', lambda step, **kw: events.append((step, kw)))
        self.assertTrue(st['ok']); self.assertEqual(events[0][0], 'setup')


if __name__ == '__main__':
    unittest.main()

import unittest
from repo_proof import plan as P


class T(unittest.TestCase):
    def test_validate_keeps_scratch_only(self):
        p, e = P.validate({'files': {'scratch/a.py': 'x', '../evil.py': 'y'}, 'checks': [{'cmd': 'true', 'pass': {'exit': 0}}]})
        self.assertIn('scratch/a.py', p['files']); self.assertNotIn('../evil.py', p['files']); self.assertTrue(e)

    def test_regex_list_and_contains(self):
        p, _ = P.validate({'checks': [{'cmd': 'x', 'pass': {'stdout_regex': ['A=\\d+', 'B=1'], 'stdout_contains': 'OK'}}]})
        ok, why = P.judge({'exit': 0, 'output': 'A=12 B=1 OK'}, p['checks'][0]['pass']); self.assertTrue(ok, why)

    def test_not_runnable_conditional(self):
        p, _ = P.validate({'checks': [{'cmd': 'x', 'needs': ['cuda'], 'pass': {'exit': 0}}]})
        self.assertEqual(P.verdict(p['checks'])[0], 'conditional')

    def test_local_model_needs_server(self):
        p, _ = P.validate({'checks': [{'cmd': 'x', 'needs': ['local_model'], 'pass': {'exit': 0}}]}, can=('none',))
        self.assertFalse(p['checks'][0]['runnable'])

    def test_folder_counts_as_file(self):
        ok, _ = P.judge({'exit': 0, 'output': ''}, {'files': ['scratch/outdir']}, exists=lambda f: True); self.assertTrue(ok)

    def test_verdicts(self):
        r = [{'id': 'c1', 'core': True, 'runnable': True, 'passed': True, 'needs': ['none']}, {'id': 'c2', 'core': False, 'runnable': True, 'passed': False, 'needs': ['none']}]
        self.assertEqual(P.verdict(r)[0], 'works')
        r[0]['passed'] = False; r[0]['why'] = ['exit 1 != 0']; self.assertEqual(P.verdict(r)[0], 'fails')


if __name__ == '__main__':
    unittest.main()

"""REPORT.md + report.json (+ evidence/ outputs kept in project/evidence)."""
import html, json
from pathlib import Path

LABEL = {'works': '✅ works', 'fails': '❌ fails', 'conditional': '⚠️ conditional', 'error': '⛔ could not run'}


def write(t, rep):
    t = Path(t)
    (t / 'report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
    L = ['# repo-proof: %s' % rep['url'], '', '**Verdict: %s** — %s' % (LABEL.get(rep['verdict'], rep['verdict']), rep['why']), '',
         '- Claim tested: %s' % (rep.get('claim') or '(none)'), '- Environment: %s%s' % (rep['environment'], (' · local model ' + rep['local_model']) if rep.get('local_model') else ''),
         '- Install: %s' % ', '.join('%s → %s' % (s['step'], s['exit']) for s in (rep.get('setup') or {}).get('steps', [])), '- Time: %s min' % rep['minutes'], '',
         '## Checks (commands run in the sandbox by code; pass/fail decided by the criteria, not by a model)']
    for x in rep.get('results') or []:
        st = 'passed' if x.get('passed') else ('not runnable here: ' + ', '.join(n for n in x['needs'] if n not in ('none', 'local_model'))) if not x['runnable'] else 'failed'
        L += ['### %s%s — %s' % (x['id'], ' (core)' if x['core'] else '', st), '- What: %s' % x['what'], '- Command: `%s`' % str(x.get('cmd'))[:300],
              '- Pass criteria: `%s`' % json.dumps(x['pass'], ensure_ascii=False)[:300]]
        if x['runnable']:
            L += ['- Exit %s · %s s%s' % (x.get('exit'), x.get('seconds'), ' · re-run after a plan fix' if x.get('fixed') else ''), '- Output (end):', '```', (x.get('output') or '')[-1500:].strip(), '```']
            if x.get('why'): L.append('- Differs from criteria: ' + '; '.join(x['why']))
        L.append('')
    (t / 'REPORT.md').write_text('\n'.join(L) + '\n')

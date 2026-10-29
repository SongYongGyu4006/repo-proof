"""Test plan: shape/safety validation, deterministic judging, verdict. The planner (an LLM) only writes the plan; everything here is code."""
import json, re

NEEDS_ALL = {'none', 'local_model', 'internet', 'cloud_key', 'linux', 'cuda', 'gui'}

PROMPT = '''You are planning a hands-on test of an open-source tool on the user's machine. Below: the README, the repository file list,
pyproject/package.json (if any) and excerpts of small source files.

Environment: {os}. Commands run from the trial folder `project/`; the repository is at `repo/`; Python dependencies are already installed
in `venv/` (use `venv/bin/python`); Node dependencies (if any) are in `repo/node_modules`. During the tests the internet is BLOCKED.
{model_line}

Write a plan that checks the tool's CORE VALUE — the main thing its README promises — with real, observable output:
- claim: the core promise in one line.
- extras: optional dependency groups (pyproject) the tests truly need ([] if none — do not list all; size matters).
- prefetch: a command to run ONCE with the internet open before the tests, if the tool downloads models/tokenizers/data on first run (else "").
- checks: 1-3 checks, the first is the core. Each: one shell command (cmd) run in project/, a timeout_s (<= {max_s}), what it shows,
  needs (none | local_model | internet | cloud_key | linux | cuda | gui) and machine-checkable pass criteria:
  pass: {{"exit": 0, "stdout_contains": ["..."], "stdout_regex": ["..."], "files": ["scratch/out.json"]}}.
  If the core value depends on a language model, the core check must really call the local model (needs local_model).
  `--help` working is not a core check. Prefer printing a measurable KEY=VALUE line and matching it with a regex.
- files: small helper scripts the checks need, as {{"scratch/name.py": "full content"}} (paths under scratch/ only).
Use only options and APIs that the README/source show. If a check needs something this machine lacks (internet, cloud_key, linux, cuda, gui),
say so in needs instead of working around it.{note}
Answer with ONE JSON object only:
{{"claim": "...", "extras": [], "prefetch": "", "files": {{}}, "checks": [{{"id": "c1", "core": true, "what": "...", "cmd": "...", "timeout_s": 300, "needs": ["none"], "pass": {{}}}}]}}

{packet}'''

FIX = '''Some planned checks failed. For each failed check below decide: is the failure a mistake in the PLAN (wrong path, option that does not exist,
script bug, missing argument)? Then fix only that: give new helper-file contents and/or a new command. Never change the pass criteria.
If the TOOL itself failed, answer null for that check.
Answer with ONE JSON object: {{"files": {{"scratch/x.py": "new content"}}, "commands": {{"c1": "new command or null"}}}}

Plan:
{plan}

Failed checks (command, exit code, end of output):
{failed}'''


def validate(d, max_s=600, can=('none', 'local_model')):
    err = []
    if not isinstance(d, dict): return None, ['plan is not an object']
    checks = [c for c in d.get('checks') or [] if isinstance(c, dict)][:3]
    if not checks: err.append('no checks')
    files = {}
    for k, v in (d.get('files') or {}).items():
        k = str(k)
        if not re.fullmatch(r'scratch/[\w./-]+', k) or '..' in k: err.append('file outside scratch/: %s' % k); continue
        if len(str(v)) > 20000: err.append('file too large: %s' % k); continue
        files[k] = str(v)
    out, seen = [], set()
    for i, c in enumerate(checks):
        cid = str(c.get('id') or 'c%d' % (i + 1))
        if cid in seen: cid = 'c%d' % (i + 1)
        seen.add(cid)
        needs = [n for n in (c.get('needs') or ['none']) if isinstance(n, str)]
        if [n for n in needs if n not in NEEDS_ALL]: err.append('%s: unknown needs' % cid)
        ps = c.get('pass') if isinstance(c.get('pass'), dict) else {}
        crit = {k: ps[k] for k in ('exit', 'stdout_contains', 'stdout_regex', 'files') if k in ps}
        if not crit: err.append('%s: no pass criteria' % cid)
        if 'stdout_regex' in crit:
            good = []
            for x in (crit['stdout_regex'] if isinstance(crit['stdout_regex'], list) else [crit['stdout_regex']]):
                try: re.compile(str(x)); good.append(str(x))
                except re.error: err.append('%s: bad regex %r' % (cid, str(x)[:40]))
            if good: crit['stdout_regex'] = good
            else: crit.pop('stdout_regex')
        for k in ('stdout_contains', 'files'):
            if k in crit and not isinstance(crit[k], list): crit[k] = [crit[k]]
        out.append({'id': cid, 'core': bool(c.get('core')) or i == 0, 'what': str(c.get('what') or '')[:300], 'cmd': str(c.get('cmd') or ''),
                    'timeout_s': max(30, min(int(c.get('timeout_s') or 300), max_s)), 'needs': needs, 'pass': crit,
                    'runnable': bool(c.get('cmd')) and all(n in can for n in needs)})
    extras = [str(x) for x in (d.get('extras') or []) if re.fullmatch(r'[A-Za-z0-9_.-]+', str(x))][:6]
    return {'claim': str(d.get('claim') or '')[:300], 'extras': extras, 'prefetch': str(d.get('prefetch') or '')[:500], 'files': files, 'checks': out}, err


def judge(ev, crit, exists=lambda f: False):
    why = []
    if 'exit' in crit and ev.get('exit') != crit['exit']: why.append('exit %s != %s' % (ev.get('exit'), crit['exit']))
    out = ev.get('output', '')
    for s in crit.get('stdout_contains') or []:
        if str(s) not in out: why.append('output lacks %r' % str(s)[:60])
    for x in crit.get('stdout_regex') or []:
        if not re.search(str(x), out): why.append('output does not match %r' % str(x)[:60])
    for f in crit.get('files') or []:
        if not exists(f): why.append('missing file %s' % f)
    return (not why), why


def verdict(results):
    """works = every core check ran and passed; fails = a core check ran and failed; conditional = a core check needs what this machine lacks."""
    core = [r for r in results if r['core']]
    if any(not r['runnable'] for r in core):
        return 'conditional', 'core check needs: ' + ', '.join(sorted({n for r in core if not r['runnable'] for n in r['needs'] if n not in ('none', 'local_model')}))
    if core and all(r.get('passed') for r in core): return 'works', 'all %d core check(s) passed' % len(core)
    return 'fails', 'core check failed: ' + '; '.join('%s (%s)' % (r['id'], ', '.join(r.get('why') or [])[:160]) for r in core if not r.get('passed'))


def parse_json(text):
    m = re.search(r'\{.*\}', text or '', re.S)
    try: return json.loads(m.group(0)) if m else None
    except Exception: return None

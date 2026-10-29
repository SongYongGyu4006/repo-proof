"""One proof run: clone -> install (sandbox, network on) -> plan (LLM) -> run checks (sandbox, network local only) -> one plan-fix round
-> verdict (code) -> report -> cleanup."""
import datetime, json, platform, re, shutil, subprocess, time
from pathlib import Path
from . import plan as P, planner as PL, sandbox as S, report as R


def packet(repo, limit_src=40, max_chars=60000):
    rd = next((f for f in (repo / 'README.md', repo / 'readme.md', repo / 'README.rst', repo / 'README') if f.is_file()), None)
    files = [str(f.relative_to(repo)) for f in sorted(repo.rglob('*')) if f.is_file() and '.git' not in f.relative_to(repo).parts][:600]
    parts = ['## README\n' + (rd.read_text(errors='replace')[:25000] if rd else '(none)'), '## FILES\n' + '\n'.join(files)]
    for n in ('pyproject.toml', 'package.json', 'setup.py', 'requirements.txt'):
        if (repo / n).is_file(): parts.append('## %s\n%s' % (n, (repo / n).read_text(errors='replace')[:6000]))
    n = 0
    for rel in files:
        f = repo / rel
        if n >= limit_src or sum(len(p) for p in parts) > max_chars: break
        if f.suffix in ('.py', '.ts', '.js', '.mjs') and f.stat().st_size < 20000 and not re.search(r'test|example|docs?/', rel, re.I) and rel.count('/') <= 3:
            parts.append('## %s (source excerpt)\n%s' % (rel, f.read_text(errors='replace')[:4000])); n += 1
    return '\n\n'.join(parts)[:max_chars]


def setup(t, url, log, no_sandbox=False, cap_gb=15):
    m = re.match(r'https?://github\.com/([\w.-]+/[\w.-]+?)(?:\.git)?/?$', url.strip())
    if not m: raise ValueError('expected a GitHub repository URL')
    c = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', 'clone', '--depth', '1', '--no-recurse-submodules', 'https://github.com/%s.git' % m.group(1), str(t / 'project' / 'repo')],
                       capture_output=True, text=True, timeout=900, env={'PATH': '/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin', 'GIT_TERMINAL_PROMPT': '0', 'HOME': str(t)})
    if c.returncode: raise RuntimeError('clone failed: ' + c.stderr[-300:])
    repo = t / 'project' / 'repo'; steps = []
    py = shutil.which('uv')
    if any((repo / n).is_file() for n in ('pyproject.toml', 'setup.py', 'requirements.txt')):
        venv = t / 'project' / 'venv'
        r = S.run(t, 'all', ([py, 'venv', '--python', '3.12', str(venv)] if py else ['python3', '-m', 'venv', str(venv)]), t, 600, no_sandbox=no_sandbox, cap_gb=cap_gb)
        steps.append(('venv', r))
        if r['exit'] == 0:
            pip = [py, 'pip', 'install', '--python', str(venv / 'bin' / 'python')] if py else [str(venv / 'bin' / 'pip'), 'install']
            cmd = pip + (['-e', str(repo)] if (repo / 'pyproject.toml').is_file() or (repo / 'setup.py').is_file() else ['-r', str(repo / 'requirements.txt')])
            steps.append(('pip', S.run(t, 'all', cmd, repo, 1500, no_sandbox=no_sandbox, cap_gb=cap_gb)))
    if (repo / 'package.json').is_file():
        steps.append(('npm', S.run(t, 'all', ['npm', 'install', '--ignore-scripts', '--no-audit', '--no-fund'], repo, 1500, no_sandbox=no_sandbox, cap_gb=cap_gb)))
    for name, r in steps: log('setup', part=name, exit=r['exit'], why=r['why'], seconds=r['seconds'], tail=r['output'][-300:])
    return {'ok': all(r['exit'] == 0 for _, r in steps), 'steps': [{'step': n, 'exit': r['exit'], 'why': r['why']} for n, r in steps]}


def run_check(t, c, cmd, local_url, no_sandbox, cap_gb):
    proj = t / 'project'
    env = {'PATH': '%s:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin' % (proj / 'venv' / 'bin'), 'VIRTUAL_ENV': str(proj / 'venv')}
    if local_url: env.update(OPENAI_BASE_URL=local_url, OPENAI_API_KEY='local')
    r = S.run(t, 'local', ['/bin/sh', '-c', cmd], proj, c['timeout_s'], env=env, no_sandbox=no_sandbox, cap_gb=cap_gb)
    (proj / 'evidence').mkdir(exist_ok=True); (proj / 'evidence' / ('%s.out.txt' % c['id'])).write_text(r['output'])
    return {'cmd': cmd, 'exit': r['exit'], 'seconds': r['seconds'], 'output': r['output'][-200000:]}


def prove(url, out_dir, planner=None, local_url=None, local_model=None, max_check_s=600, keep=False, no_sandbox=False, cap_gb=15, note='', log=print):
    planner = planner or {}
    out_dir = Path(out_dir).resolve(); slug = re.sub(r'\W+', '-', url.rstrip('/').split('github.com/')[-1]).strip('-').lower()
    t = out_dir / ('%s-%s' % (slug, datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))); (t / 'project').mkdir(parents=True)
    events = []
    def L(step, **kw):
        kw = {'step': step, 'at': datetime.datetime.now().isoformat(timespec='seconds'), **kw}; events.append(kw); log(json.dumps(kw, ensure_ascii=False)[:400])
    t0 = time.time()
    try:
        st = setup(t, url, L, no_sandbox, cap_gb)
        repo = t / 'project' / 'repo'
        model_line = ('A local OpenAI-compatible model server is available: base_url %s, api_key "local", model "%s" (slow: 10-60 s per answer).' % (local_url, local_model or 'local')
                      if local_url else 'No language model is available during the tests.')
        prompt = P.PROMPT.format(os='%s %s' % (platform.system(), platform.machine()), model_line=model_line, max_s=max_check_s,
                                 note=('\nThe user asked to check: ' + note) if note else '', packet=packet(repo))
        raw = PL.ask(prompt, **planner); L('plan', chars=len(raw or ''))
        pl, errs = P.validate(P.parse_json(raw), max_check_s, can=('none', 'local_model') if local_url else ('none',))
        if not pl or not pl['checks']: raise RuntimeError('no usable plan: %s' % errs)
        (t / 'project' / 'TESTPLAN.json').write_text(json.dumps(pl, ensure_ascii=False, indent=1))
        proj = t / 'project'; venvpy = proj / 'venv' / 'bin' / 'python'
        if pl['extras'] and venvpy.is_file() and (repo / 'pyproject.toml').is_file():
            pip = [shutil.which('uv'), 'pip', 'install', '--python', str(venvpy)] if shutil.which('uv') else [str(proj / 'venv' / 'bin' / 'pip'), 'install']
            r = S.run(t, 'all', pip + ['-e', '%s[%s]' % (repo, ','.join(pl['extras']))], repo, 1500, no_sandbox=no_sandbox, cap_gb=cap_gb); L('extras', exit=r['exit'], extras=pl['extras'])
        if pl['prefetch']:
            r = S.run(t, 'all', ['/bin/sh', '-c', pl['prefetch']], proj, 900, env={'PATH': '%s:/usr/bin:/bin:/opt/homebrew/bin' % (proj / 'venv' / 'bin')}, no_sandbox=no_sandbox, cap_gb=cap_gb); L('prefetch', exit=r['exit'])
        for k, v in pl['files'].items(): (proj / k).parent.mkdir(parents=True, exist_ok=True); (proj / k).write_text(v)
        results = []
        for c in pl['checks']:
            x = dict(c)
            if c['runnable']:
                ev = run_check(t, c, c['cmd'], local_url, no_sandbox, cap_gb); ok, why = P.judge(ev, c['pass'], lambda f: (proj / f).exists())
                x.update(ev, passed=ok, why=why); L('check', id=c['id'], exit=ev['exit'], passed=ok, seconds=ev['seconds'])
            results.append(x)
        failed = [x for x in results if x['runnable'] and not x['passed']]
        if failed:   # one repair round by the planner: the plan's own scripts/commands only, never the criteria
            fx = P.parse_json(PL.ask(P.FIX.format(plan=json.dumps(pl, ensure_ascii=False)[:20000], failed=json.dumps(
                [{'id': x['id'], 'cmd': x['cmd'], 'exit': x['exit'], 'output_end': x['output'][-3000:]} for x in failed], ensure_ascii=False)), **planner)) or {}
            for k, v in (fx.get('files') or {}).items():
                if re.fullmatch(r'scratch/[\w./-]+', str(k)) and '..' not in str(k): (proj / k).write_text(str(v))
            for x in failed:
                new = (fx.get('commands') or {}).get(x['id'], 'same')
                if new is None: continue
                c = next(c for c in pl['checks'] if c['id'] == x['id'])
                ev = run_check(t, c, c['cmd'] if new == 'same' else str(new), local_url, no_sandbox, cap_gb); ok, why = P.judge(ev, c['pass'], lambda f: (proj / f).exists())
                x.update(ev, passed=ok, why=why, fixed=True); L('recheck', id=x['id'], exit=ev['exit'], passed=ok)
        v, why = P.verdict(results)
    except Exception as e:
        st = locals().get('st') or {}; pl = locals().get('pl') or {'claim': '', 'checks': []}; results = locals().get('results') or []
        v, why = 'error', repr(e)[:400]; L('error', error=why)
    rep = {'url': url, 'verdict': v, 'why': why, 'claim': pl.get('claim'), 'setup': st, 'results': results, 'minutes': round((time.time() - t0) / 60, 1),
           'environment': '%s %s' % (platform.system(), platform.machine()), 'local_model': local_model if local_url else None, 'events': events}
    R.write(t, rep)
    if not keep:
        for rel in ('project/venv', 'project/repo', '.cache', 'home', 'tmp'): shutil.rmtree(t / rel, ignore_errors=True)
    return t, rep

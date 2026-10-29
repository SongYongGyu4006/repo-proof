"""Isolation for installing and running an untrusted repository.

macOS: sandbox-exec (Seatbelt) profile — writes only inside the trial folder (+ temp), secrets unreadable, and in the 'local' phase
outbound network only to localhost (your local model server). Linux: bubblewrap with the same intent (home hidden, trial folder bound
read-write, --unshare-net in the 'local' phase unless a localhost model is needed, then the host network namespace but no home).
"""
import os, platform, shutil, signal, subprocess, time
from pathlib import Path

HOME = str(Path.home())
SECRET_DIRS = ['.ssh', '.gnupg', '.aws', '.azure', '.config', '.kube', '.docker', '.netrc', '.npmrc', '.pypirc', '.git-credentials',
               '.zsh_history', '.bash_history', '.claude', '.claude.json', '.codex', '.gemini', 'Library/Keychains', 'Library/Cookies',
               'Library/Application Support', 'Library/Mail', 'Library/Messages', 'Documents', 'Desktop', 'Downloads', 'Pictures']


def seatbelt(trial, network, extra_secret=()):
    q = lambda p: '"%s"' % p
    secrets = [os.path.join(HOME, s) for s in SECRET_DIRS] + list(extra_secret)
    L = ['(version 1)', '(allow default)',
         '(deny file-write* (require-all (require-not (subpath %s)) (require-not (subpath "/private/var/folders")) (require-not (subpath "/private/tmp")) (require-not (subpath "/dev"))))' % q(trial),
         '(deny file-read-data %s)' % ' '.join('(subpath %s)' % q(s) for s in secrets),
         '(allow file-read-data (subpath %s))' % q(trial)]
    if network != 'all': L += ['(deny network-outbound (remote ip "*:*"))', '(allow network-outbound (remote ip "localhost:*"))']
    return '\n'.join(L) + '\n'


def wrap(trial, network, cmd):
    """Return the argv that runs cmd inside the sandbox for this platform."""
    trial = str(Path(trial).resolve())
    if platform.system() == 'Darwin':
        prof = Path(trial) / ('.sandbox-%s.sb' % network); prof.write_text(seatbelt(trial, network))
        return ['/usr/bin/sandbox-exec', '-f', str(prof)] + cmd
    bw = shutil.which('bwrap')
    if not bw: raise RuntimeError('no sandbox available: install bubblewrap (bwrap) or run with --no-sandbox at your own risk')
    a = [bw, '--ro-bind', '/usr', '/usr', '--ro-bind', '/etc', '/etc', '--ro-bind-try', '/lib', '/lib', '--ro-bind-try', '/lib64', '/lib64',
         '--ro-bind-try', '/bin', '/bin', '--ro-bind-try', '/sbin', '/sbin', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
         '--tmpfs', HOME, '--bind', trial, trial, '--chdir', trial, '--die-with-parent']
    if network != 'all' and network != 'local': a.append('--unshare-net')
    return a + cmd


def run(trial, network, cmd, cwd, timeout, env=None, cap_gb=15, no_sandbox=False):
    """Run cmd; output goes to a file (a full pipe can block); the whole process group is killed on timeout or when the folder passes cap_gb."""
    trial = Path(trial); (trial / 'tmp').mkdir(parents=True, exist_ok=True)
    e = {'HOME': str(trial / 'home'), 'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin', 'LANG': 'en_US.UTF-8', 'TMPDIR': str(trial / 'tmp') + '/',
         'UV_CACHE_DIR': str(trial / '.cache' / 'uv'), 'UV_PYTHON_INSTALL_DIR': str(trial / '.cache' / 'python'), 'npm_config_cache': str(trial / '.cache' / 'npm'),
         'PIP_CACHE_DIR': str(trial / '.cache' / 'pip'), 'HF_HOME': str(trial / '.cache' / 'hf'), 'XDG_CACHE_HOME': str(trial / '.cache'),
         'TORCH_HOME': str(trial / '.cache' / 'torch'), 'GIT_TERMINAL_PROMPT': '0', 'PYTHONUNBUFFERED': '1'}
    (trial / 'home').mkdir(exist_ok=True); e.update(env or {})
    argv = cmd if no_sandbox else wrap(trial, network, cmd)
    out = trial / 'tmp' / ('out-%d.log' % time.time_ns())
    with open(out, 'w') as fh:
        p = subprocess.Popen(argv, cwd=cwd, env=e, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
    t0 = time.time(); why = None
    while p.poll() is None:
        if time.time() - t0 > timeout: why = 'timeout'; break
        if size_gb(trial) > cap_gb: why = 'folder over %d GB' % cap_gb; break
        time.sleep(2)
    if why:
        try: os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError): p.kill()
    try: p.wait(timeout=30)
    except subprocess.TimeoutExpired: pass
    text = out.read_text(errors='replace'); out.unlink(missing_ok=True)
    return {'exit': 'timeout' if why == 'timeout' else (p.returncode if not why else -1), 'why': why, 'seconds': round(time.time() - t0, 1), 'output': text}


def size_gb(p):
    r = subprocess.run(['du', '-sk', str(p)], capture_output=True, text=True)
    try: return int(r.stdout.split()[0]) / 1024 / 1024
    except Exception: return 0.0

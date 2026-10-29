"""repo-proof run <github-url> [options]  — does this open-source tool really do what its README says? Find out on your machine, safely."""
import argparse, json, sys
from .proof import prove


def main(argv=None):
    ap = argparse.ArgumentParser(prog='repo-proof')
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run', help='install, plan, test and judge one repository')
    r.add_argument('url'); r.add_argument('--out', default='./proofs')
    r.add_argument('--planner', choices=['openai', 'anthropic', 'command'], default='openai')
    r.add_argument('--planner-model'); r.add_argument('--planner-url', help='OpenAI-compatible base URL (default OpenAI)'); r.add_argument('--planner-cmd', help='CLI that reads the prompt on stdin, e.g. "claude -p"')
    r.add_argument('--local-model-url', help='OpenAI-compatible URL of a local model the tool may use during tests, e.g. http://127.0.0.1:8000/v1')
    r.add_argument('--local-model', help='model name on that server')
    r.add_argument('--max-check-s', type=int, default=600); r.add_argument('--cap-gb', type=int, default=15)
    r.add_argument('--note', default='', help='what you especially want checked'); r.add_argument('--keep', action='store_true', help='keep repo/venv after the run')
    r.add_argument('--no-sandbox', action='store_true', help='run without OS isolation (not recommended)')
    a = ap.parse_args(argv)
    t, rep = prove(a.url, a.out, planner={'kind': a.planner, 'model': a.planner_model, 'url': a.planner_url, 'cmd': a.planner_cmd},
                   local_url=a.local_model_url, local_model=a.local_model, max_check_s=a.max_check_s, keep=a.keep, no_sandbox=a.no_sandbox,
                   cap_gb=a.cap_gb, note=a.note, log=lambda s: print(s, file=sys.stderr))
    print(json.dumps({'verdict': rep['verdict'], 'why': rep['why'], 'report': str(t / 'REPORT.md')}, ensure_ascii=False))
    return {'works': 0, 'conditional': 2, 'fails': 1}.get(rep['verdict'], 3)


if __name__ == '__main__':
    sys.exit(main())

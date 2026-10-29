# repo-proof

**Does this trending open-source tool really do what its README says? Find out on your own machine — safely, with evidence, judged by code.**

```bash
repo-proof run https://github.com/OWNER/REPO --planner openai --local-model-url http://127.0.0.1:8000/v1 --local-model my-model
```

1. **Install in a sandbox.** Shallow clone (git hooks off), Python deps into a venv inside the trial folder (`uv` if present), Node deps with `--ignore-scripts`. Network is open only for this step; a size cap stops runaway installs.
2. **Plan.** A planner model reads only text — README, file list, `pyproject`/`package.json`, small source excerpts — and writes a test plan: the core claim, 1–3 checks (one shell command each) with **machine-checkable pass criteria** (exit code, output strings, regexes, produced files). It runs nothing.
3. **Run.** Each check runs in the sandbox with the internet **blocked** — only `localhost` is reachable, so the tool can use your local model server. Full outputs are kept as evidence.
4. **One fix round.** If a check failed because of the *plan* (wrong path, nonexistent option, script bug), the planner may fix its own command/script once. It can never change the pass criteria.
5. **Judge by code.** `works` = every core check passed · `fails` = a core check ran and failed · `conditional` = the core needs what this machine lacks (CUDA, Linux, cloud key, internet, GUI).
6. **Report and clean up.** `REPORT.md` + `report.json` + `evidence/`; repo, venv and caches are deleted (use `--keep` to keep them).

## Sandbox

- **macOS**: `sandbox-exec` profile — writes only inside the trial folder and temp; reading `~/.ssh`, `~/.config`, `~/.aws`, `~/.gnupg`, keychains, cookies, mail, Documents/Desktop/Downloads is denied; during tests outbound network only to localhost.
- **Linux**: `bubblewrap` — your home is replaced by an empty tmpfs, only the trial folder is writable.
- `--no-sandbox` exists for machines without either; don't use it on code you don't trust.

## Planners

| `--planner` | how |
|---|---|
| `openai` (default) | any OpenAI-compatible chat API: `--planner-url` (default OpenAI), key from `$OPENAI_API_KEY` — a local server works too |
| `anthropic` | Anthropic Messages API, key from `$ANTHROPIC_API_KEY`, `--planner-model` |
| `command` | any CLI that reads the prompt on stdin and prints the answer: `--planner-cmd "claude -p"`, `"llm -m ..."` |

## Why not just ask an agent to try it?

Because the agent then also *grades* itself. Here the model only proposes what to check; the commands, the evidence and the verdict are code. When a check fails you see exactly which criterion and the output.

## Example

[`examples/humanize`](examples/humanize/REPORT.md): the planner turned the README's documented outputs into 24 assertions (`CORE_PASS=24/24`) plus a locale-switching check; the locale script failed once on a planning mistake, was fixed in the repair round and passed. 0.9 minutes, verdict **works**.

## Real findings (from running the same method on trending repos)

- A multi-agent trading framework ran end-to-end on a local 27B model (14–16 minutes per trading day, Korean debate output).
- A popular tutoring workspace: quiz generation worked with a local model, but its chat path crashed on a default install (a dependency only listed in the `dev` extra), and its knowledge base needs an embedding server.
- A context-compression proxy: worked as advertised, but in an agent loop with a prefix cache the savings did not turn into speed.
- Our own judging bugs we fixed on the way (a list of regexes compared as one string; an output *folder* counted as a missing file) are covered by the tests.

## Limits

One fix round, three checks, ten minutes per check by default (`--max-check-s`). The verdict is only as good as the criteria the planner wrote — read `TESTPLAN.json`. A failed check can still be the plan's fault after the fix round; the report shows the output so you can tell.

MIT · built while running a one-Mac AI content studio (커밋 한 모금).

---

## 한국어 요약

GitHub 주소 하나로: 격리된 곳에 설치 → 계획 담당 AI가 README 핵심 주장을 기계로 판정 가능한 시험으로 → 인터넷을 막은 상자에서 실제 실행(로컬 모델만 접근) → 계획 실수만 한 번 고침 → **판정은 코드가** → 보고서·증거 남기고 설치물 삭제.

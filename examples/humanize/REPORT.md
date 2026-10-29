# repo-proof: https://github.com/python-humanize/humanize

**Verdict: ✅ works** — all 1 core check(s) passed

- Claim tested: humanize turns numbers, sizes, durations and fractions into human-readable strings (e.g. 12345 -> '12,345', 1001s -> '17 minutes', 1000000 bytes -> '1.0 MB') and can switch locale at runtime.
- Environment: Darwin arm64
- Install: venv → 0, pip → 0
- Time: 0.9 min

## Checks (commands run in the sandbox by code; pass/fail decided by the criteria, not by a model)
### c1 (core) — passed
- What: Run README examples for number, time, size, fraction, scientific and list humanizers and compare to the documented outputs
- Command: `venv/bin/python scratch/core.py`
- Pass criteria: `{"exit": 0, "stdout_regex": ["CORE_PASS=24/24"]}`
- Exit 0 · 2.0 s
- Output (end):
```
CORE_PASS=24/24
```

### c2 — passed
- What: Runtime locale switching (ru_RU, tr_TR) changes output and deactivate restores English
- Command: `venv/bin/python scratch/i18n.py`
- Pass criteria: `{"exit": 0, "stdout_contains": ["LOCALE_OK=True", "BACK_TO_EN=True"]}`
- Exit 0 · 2.0 s · re-run after a plan fix
- Output (end):
```
EN=3 seconds ago
RU=3 секунды назад
TR=1.234.567,89
BACK_TO_EN=True
LOCALE_OK=True
```


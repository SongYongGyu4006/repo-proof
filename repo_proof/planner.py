"""Who writes the test plan. The planner only reads text we give it (README, file list, small sources) and answers JSON — it runs nothing.

  openai     any OpenAI-compatible chat API: --planner-url (default https://api.openai.com/v1), key from $OPENAI_API_KEY (or none for a local server)
  anthropic  Anthropic Messages API, key from $ANTHROPIC_API_KEY
  command    any CLI that reads the prompt on stdin and prints the answer, e.g. --planner-cmd "claude -p" or "llm -m gpt-5"
"""
import json, os, shlex, subprocess, urllib.request


def ask(prompt, kind='openai', model=None, url=None, cmd=None, timeout=900):
    if kind == 'command':
        if not cmd: raise ValueError('--planner-cmd is required for the command planner')
        p = subprocess.run(shlex.split(cmd), input=prompt, capture_output=True, text=True, timeout=timeout)
        if p.returncode: raise RuntimeError('planner command failed: ' + (p.stderr or p.stdout)[-300:])
        return p.stdout
    if kind == 'anthropic':
        key = os.environ.get('ANTHROPIC_API_KEY')
        if not key: raise RuntimeError('ANTHROPIC_API_KEY is not set')
        body = {'model': model or 'claude-sonnet-5-5', 'max_tokens': 8000, 'messages': [{'role': 'user', 'content': prompt}]}
        req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=json.dumps(body).encode(),
                                     headers={'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
        j = json.load(urllib.request.urlopen(req, timeout=timeout))
        return ''.join(b.get('text', '') for b in j.get('content', []))
    base = (url or 'https://api.openai.com/v1').rstrip('/')
    key = os.environ.get('OPENAI_API_KEY', 'local')
    body = {'model': model or 'gpt-5.6-terra', 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0}
    req = urllib.request.Request(base + '/chat/completions', data=json.dumps(body).encode(), headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    j = json.load(urllib.request.urlopen(req, timeout=timeout))
    return j['choices'][0]['message']['content']

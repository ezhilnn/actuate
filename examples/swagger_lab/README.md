# Actuate sample lab

Uses the **PyPI** package `actuate-ai` (not the local repo copy).

```powershell
pip install -r requirements.txt
cd examples\swagger_lab
python -m uvicorn app:app --reload --port 8090
```

Open http://127.0.0.1:8090/docs

- `POST /v1/mixed-graph` — catalog agents + 3 custom agents
- `POST /v1/custom-graph` — 10 custom agents

Each body sets `prompt` and `provider` (`stub`, `nvidia`, `openai`, …). Leave `api_base` empty unless you use Ollama or a custom host.

```json
{
  "prompt": "A clinic wants fewer missed appointments. 30-day plan.",
  "provider": "stub"
}
```

Response: `{ "pass": { status, reward, nodes[] }, "final_output": "..." }`.
`GET /health` shows the installed `actuate-ai` version and file path (should be under `site-packages`).

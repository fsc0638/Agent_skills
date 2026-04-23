# Agent Skills Monorepo

Welcome to the centralized repository for **LLM Agent Skills**. This repository uses a Monorepo architecture to manage all skills with a unified interface and automated indexing.

## Repository Structure

```text
Agent_skills/
├── shared/                   # Common utilities (e.g., streaming_utils.py)
├── skills/                   # Core skill bundles [provider]-[tool]
│   ├── mcp-python-executor/
│   ├── mcp-webapp-tester/
│   └── ...
├── scripts/                  # Management & automation scripts
├── tests/                    # Integration and unit tests
├── README.md                 # This file
├── .env.template             # Environment variables template
└── skills_manifest.json      # Pre-indexed skills for UMA Core
```

## Standard Skill Specs
Every skill must contain a `SKILL.md` in its root folder with the following YAML frontmatter:
- `runtime_requirements`: Array of needed Python libraries.
- `estimated_tokens`: Estimated context window usage.
- `requires_venv`: Boolean (default false).

### 🧾 Token Usage Reporting (MANDATORY for any skill that calls an LLM)

If a skill's `scripts/main.py` calls an LLM internally (OpenAI, Anthropic,
Gemini, or any API that charges per token), the JSON it prints to stdout
**must** include a top-level `"_usage"` field so WorkflowExecutor can fold
the cost into the admin analytics pipeline:

```json
{
  "status": "success",
  "output": "…analysis text…",
  "_usage": {
    "model": "gpt-4o-mini",
    "input_tokens": 2340,
    "output_tokens": 890,
    "total_tokens": 3230,
    "skill_total_tokens": 3230
  }
}
```

Field rules:
- `input_tokens` / `output_tokens` / `total_tokens` — copy from the
  provider's response (OpenAI: `response.usage.prompt_tokens`,
  `completion_tokens`, `total_tokens`; analogous for other providers).
- `skill_total_tokens` — sum across *all* LLM calls this invocation made
  (skills that chain multiple prompts must aggregate). For single-call
  skills this equals `total_tokens`.
- `model` — the actual model that handled the request (useful for cost
  allocation when a skill has fallback logic).

Skills that do NOT call an LLM (pure API wrappers like `mcp-web-search`,
local subprocess runners, PDF/DOCX extractors, `mcp-python-executor`)
should emit `_usage: {"total_tokens": 0}` so the absence is explicit
rather than ambiguous. Alternatively, leave `_usage` out entirely and
the executor will default to 0.

Why this matters: without `_usage`, tokens consumed inside a skill (e.g.
`mcp-meeting-to-notion` makes 3 sequential GPT-4o calls internally) are
invisible to `workspace/analytics/token_usage.jsonl` and therefore to
the admin Dashboard. Large chunks of real spend go unaccounted.

See `templates/main.py.template` for a boilerplate skill script with
usage reporting wired in.

## Management Scripts
- **Generate Manifest**: `python scripts/generate_manifest.py`
  - Scans all skills and updates `skills_manifest.json`.
  
## How to Add a New Skill
1. Use `templates/` to create a new folder in `skills/`.
2. Name it `mcp-[your-tool-name]`.
3. Run the manifest generator.

## Shared Utilities
Skills can import shared logic via `PYTHONPATH`. 
Example: `import shared.streaming_utils`

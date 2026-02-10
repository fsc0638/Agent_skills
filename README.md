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

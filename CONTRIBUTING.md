# Contributing to Computer Use Agent

Thanks for your interest in contributing! This document covers the development setup,
coding style, and PR process.

## Development setup

### Prerequisites

- Python 3.10+ (3.12 recommended)
- Git
- For Windows: [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
  (for `uiautomation` wheel)
- For Linux: `xvfb` if running headless tests

### Clone & install

```bash
git clone https://github.com/snake-aabb-wtf/computer-use-agent.git
cd computer-use-agent
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

### Run tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=computer_use_agent --cov-report=term-missing

# Run only non-integration tests
python -m pytest tests/ -v -m "not integration"
```

### Code quality

```bash
# Lint
ruff check computer_use_agent/ tests/
ruff format --check computer_use_agent/

# Type check
mypy computer_use_agent/ --ignore-missing-imports

# Security scan
bandit -r computer_use_agent/ -ll

# Dependency audit
pip-audit --strict
```

## Code style

We use `ruff` for linting and formatting. Configuration is in `pyproject.toml`.

### Rules

- **Line length**: 100 chars
- **Quotes**: double quotes for strings
- **Imports**: sorted (isort compatible)
- **Type hints**: encouraged for new code, required for public APIs
- **Docstrings**: Google style, required for public functions and classes
- **Naming**:
  - `snake_case` for functions, variables, modules
  - `PascalCase` for classes
  - `UPPER_SNAKE_CASE` for module-level constants
  - `_leading_underscore` for private/internal

### Example

```python
"""Module docstring describing purpose."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


class MyClass:
    """Class docstring.

    Args:
        name: Human-readable name.
        timeout: Request timeout in seconds.
    """

    def __init__(self, name: str, timeout: float = DEFAULT_TIMEOUT):
        self.name = name
        self.timeout = timeout

    def fetch(self, url: str) -> Optional[dict]:
        """Fetch JSON from URL.

        Args:
            url: The URL to fetch.

        Returns:
            Parsed JSON dict, or None on failure.
        """
        try:
            logger.debug(f"Fetching {url}")
            # ...
        except Exception as e:
            logger.warning(f"Fetch failed: {e}")
            return None
```

## Commit message convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**:
- `feat` — new feature
- `fix` — bug fix
- `docs` — documentation only
- `style` — formatting (no logic change)
- `refactor` — code change that neither fixes a bug nor adds a feature
- `perf` — performance improvement
- `test` — add or fix tests
- `chore` — build / tooling / deps
- `ci` — CI/CD changes

**Scopes** (optional): `agent`, `llm`, `executor`, `api`, `cli`, `mcp`, `plugins`,
`i18n`, `logger`, `config`, `tests`, `docs`, `ci`, `docker`, `deps`

**Examples**:

```
feat(api): add /cancel/<id> endpoint to cancel queued or running tasks

fix(agent): use BUDGET_CONFIG.max_history_chars for context_pct

docs(readme): add Docker quick-start section

ci: run pytest on Windows + Linux + macOS in GitHub Actions
```

## Pull request process

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make your changes**. Include:
   - Code + tests
   - Update relevant docs (`docs/`, `README.md`, `CHANGELOG.md`)
   - Add entry to `CHANGELOG.md` under `[Unreleased]`

3. **Verify locally**:
   ```bash
   ruff check computer_use_agent/ tests/
   ruff format --check computer_use_agent/
   python -m pytest tests/ -v -m "not integration"
   ```

4. **Commit** with a Conventional Commit message.

5. **Push** and **open a PR** against `main`.

6. **PR template** will be auto-populated. Fill in:
   - **What** — what does this PR do?
   - **Why** — what problem does it solve?
   - **How** — implementation notes (especially for non-trivial changes)
   - **Testing** — how did you verify?
   - **Screenshots / logs** — for UI / behavior changes

7. **CI must pass**: lint, tests across 3 OS × 3 Python versions.

8. **Review**: at least one approval required. Address feedback via
   [fixup commits](https://thoughtbot.com/blog/autosquashing-git-commits) or
   `git commit --fixup=<SHA>`.

9. **Squash and merge** by a maintainer (commit history is preserved in the PR).

## Reporting bugs

Open an [Issue](https://github.com/snake-aabb-wtf/computer-use-agent/issues) with:

- **Environment**: OS, Python version, CUA version (`cua --version`)
- **Config**: relevant `.env` values (REDACT secrets!)
- **Steps to reproduce**
- **Expected vs actual behavior**
- **Logs**: run with `LOG_LEVEL=DEBUG LOG_FORMAT=json` and attach the file

## Feature requests

Open a [Discussion](https://github.com/snake-aabb-wtf/computer-use-agent/discussions)
first to gauge interest. Once aligned, move to an Issue with a clear acceptance
criteria.

## Security issues

**Do not** open a public issue for security vulnerabilities. Email
[security contact] privately with:

- Description of the vulnerability
- Reproduction steps
- Impact assessment

We'll respond within 72 hours.

## Code of conduct

Be respectful. No harassment, no discrimination. We're all here to build a great
tool together.

## Release process

(Maintainers only)

1. Update `CHANGELOG.md`: move `[Unreleased]` items under a new version section
2. Update `__version__` in `computer_use_agent/__init__.py` and `pyproject.toml`
3. Commit: `chore(release): v0.X.0`
4. Tag: `git tag v0.X.0`
5. Push: `git push --tags`
6. CI will build sdist + wheel and publish to PyPI via OIDC (no manual upload)
7. GitHub Release is auto-generated

## Project structure

```
computer-use-agent/
├── computer_use_agent/       # Source package
│   ├── __init__.py
│   ├── __main__.py           # argparse CLI entry
│   ├── agent.py              # Main loop
│   ├── llm.py                # LLM client
│   ├── executor.py           # 12 actions
│   ├── screen.py             # Multi-monitor capture
│   ├── uia_tree.py           # Windows UIA
│   ├── api.py                # HTTP API
│   ├── cli.py                # REPL
│   ├── tui.py                # Live panel
│   ├── i18n.py               # Translations
│   ├── plugins.py            # Plugin system
│   ├── mcp_server.py         # MCP server
│   ├── replay.py             # Session replay
│   ├── webhook.py            # Notifications
│   ├── config.py             # Settings
│   ├── logger.py             # Logging
│   ├── prompts.py            # System prompts
│   ├── sanitization.py       # JSON repair
│   ├── token_budget.py       # Context budget
│   ├── guardrails.py         # Loop detection
│   ├── visual_effects.py     # Win32 overlay
│   └── notify.py             # Windows notification
├── tests/                    # Test suite
├── docs/                     # Documentation
├── .github/                  # CI / Dependabot / PR templates
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
└── requirements.txt
```

## Questions?

Open a [Discussion](https://github.com/snake-aabb-wtf/computer-use-agent/discussions)
or reach out to maintainers.

Thanks for contributing! 🎉

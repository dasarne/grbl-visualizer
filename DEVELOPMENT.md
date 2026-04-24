# Development Guide

## Environment Setup

> **Arch Linux / PEP 668:** Arch (and other modern distributions) enforce the
> "externally managed environment" policy which blocks system-wide `pip install`.
> You **must** use a virtual environment.  The steps below work on all platforms.

```bash
# 1. Clone the repository
git clone https://github.com/dasarne/grbl-visualizer.git gcode-lisa
cd gcode-lisa

# 2. Create a virtual environment (pyenv recommended)
python3 -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate

# 3. Install all dependencies
pip install -r requirements.txt
```

## Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage report
pytest tests/ --cov=src --cov-report=term-missing

# Run a specific test file
pytest tests/test_parser.py -v

# Run tests with XML coverage for CI
pytest tests/ --cov=src --cov-report=xml
```

## Local Linux Integration

Register desktop launcher and file associations (`*.gcode`, `*.nc`):

```bash
chmod +x scripts/install_linux.sh scripts/uninstall_linux.sh
./scripts/install_linux.sh
```

Undo integration:

```bash
./scripts/uninstall_linux.sh
```

## Development Workflow

1. Pick an issue from the GitHub issue tracker
2. Create a branch: `git checkout -b feature/issue-description`
3. Implement the feature in the relevant module under `src/`
4. Add or update tests in `tests/`
5. Run the full test suite and linters (see below)
6. Submit a PR using the pull request template

## Code Style

- **PEP 8** compliance is required for all Python files
- **black** is used for auto-formatting with a line length of 100
- **flake8** CI gate focuses on high-signal runtime errors (`E9,F63,F7,F82`)
- A stricter local flake8 run can still be used for style cleanup
- **mypy** is used for static type checking

```bash
# Format code
black src/ tests/ --line-length=100

# Lint (CI-equivalent gate)
flake8 src/ tests/ --select=E9,F63,F7,F82 --show-source --statistics

# Optional stricter lint (style-oriented)
flake8 src/ tests/ --max-line-length=100 --extend-ignore=E203

# Type check
mypy src/
```

## CI Monitoring (GitHub Actions)

Use GitHub CLI to inspect current and recent runs:

```bash
# Latest runs
gh run list --limit 20

# Follow the latest run interactively
gh run watch

# Inspect failed steps/logs of one run
gh run view <RUN_ID> --log-failed

# Structured output (script-friendly)
gh run list --limit 10 --json databaseId,workflowName,displayTitle,status,conclusion
```

Tip: CI emails can lag behind local state. Always verify the latest run list before debugging.

## Agent/Skill-Based Development

This project uses GitHub Copilot coding agent with structured skills:

- Feature requests are filed as GitHub Issues with a structured description
- A Copilot skill (or agent session) picks up the issue and implements the feature
- The agent follows the architecture in `ARCHITECTURE.md` and the GRBL reference in `GRBL_REFERENCE.md`
- Each agent session should run the test suite before committing

This workflow keeps implementation consistent and well-documented even across multiple contributors.

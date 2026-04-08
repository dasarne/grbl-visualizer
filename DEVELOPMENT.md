# Development Guide

## Environment Setup

```bash
# 1. Clone the repository
git clone https://github.com/dasarne/grbl-visualizer.git
cd grbl-visualizer

# 2. Create a virtual environment (pyenv recommended)
python3.10 -m venv .venv
source .venv/bin/activate

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
- **flake8** is used for linting with `--max-line-length=100 --extend-ignore=E203`
- **mypy** is used for static type checking

```bash
# Format code
black src/ tests/ --line-length=100

# Lint
flake8 src/ tests/ --max-line-length=100 --extend-ignore=E203

# Type check
mypy src/
```

## Agent/Skill-Based Development

This project uses GitHub Copilot coding agent with structured skills:

- Feature requests are filed as GitHub Issues with a structured description
- A Copilot skill (or agent session) picks up the issue and implements the feature
- The agent follows the architecture in `ARCHITECTURE.md` and the GRBL reference in `GRBL_REFERENCE.md`
- Each agent session should run the test suite before committing

This workflow keeps implementation consistent and well-documented even across multiple contributors.

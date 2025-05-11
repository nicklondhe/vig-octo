# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- Setup: `uv venv .venv && source .venv/bin/activate && uv pip install -r requirements.txt`
- Activate: `source .venv/bin/activate`
- Dev setup: `uv pip install -r requirements-dev.txt`
- Run server: `python server.py`
- Lint: `flake8 *.py`
- Type check: `mypy --strict *.py`
- Format code: `black *.py`
- Test: `pytest`
- Single test: `pytest test_file.py::test_function -v`

## Code Style Guidelines

- Use docstrings with triple single quotes `'''` for all modules, classes, and functions
- Follow PEP 8 style guidelines
- Imports: standard lib first, then third-party, then local
- Use type hints for all function parameters and return values
- Variables: snake_case for variables, CamelCase for classes
- SQLAlchemy models: suffix with "Model" (e.g., TaskModel)
- Pydantic models: no suffix (e.g., Task)
- Error handling: use try/except with specific exceptions
- Use SQLAlchemy ORM for database operations
- FastMCP for API endpoints
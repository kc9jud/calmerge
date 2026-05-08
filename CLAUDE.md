# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**calmerge** is a Python project. The repository is in its initial state — no source code, package configuration, or test infrastructure exists yet.

## Conventions inferred from `.gitignore`

The `.gitignore` is a standard Python template and includes entries for:
- **Linter**: `ruff` (`.ruff_cache/` is ignored)
- **Test runner**: `pytest` (`.pytest_cache/` is ignored)
- **Package managers**: `uv`, `poetry`, `pdm`, `pipenv`, `pixi` are all referenced — the one actually used will be determined once `pyproject.toml` or a lockfile is added

## When source code is added

Once the project is scaffolded, update this file with:
- How to install dependencies (e.g. `uv sync`, `pip install -e ".[dev]"`)
- How to run tests (e.g. `pytest` or `pytest tests/path/to/test_file.py::test_name`)
- How to run the linter (e.g. `ruff check .` and `ruff format .`)
- The high-level architecture (modules, data flow, key abstractions)

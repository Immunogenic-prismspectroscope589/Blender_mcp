.PHONY: help install sync check check-fast format format-check lint type-check import-check test test-fast test-cov custom-checks version-check release inspect inspect-essential inspect-summary clean clean-all

PYTHON := python
UVRUN := uv run

help:
	@echo "Blender MCP - Targets"
	@echo "  make sync            # Sync dev environment with uv"
	@echo "  make check           # Full quality gate"
	@echo "  make check-fast      # Fast quality gate"
	@echo "  make format          # Format source with Ruff formatter"
	@echo "  make lint            # Lint source with Ruff"
	@echo "  make type-check      # MyPy + Pyright"
	@echo "  make import-check    # Import-linter architecture checks"
	@echo "  make test            # Run tests"
	@echo "  make test-cov        # Run tests with coverage"
	@echo "  make inspect         # Show all tools (full format)"
	@echo "  make inspect-essential  # Show ESSENTIAL tier tools (priority 1-9)"
	@echo "  make inspect-summary # Show all tools as compact table"
	@echo "  make clean           # Remove build/test cache artifacts"

install:
	$(PYTHON) -m pip install -e ".[dev]"

sync:
	uv sync --all-extras

check: version-check lint format-check type-check import-check custom-checks test
	@echo "All checks passed."

check-fast: version-check lint custom-checks
	@echo "Fast checks passed."

format:
	$(UVRUN) ruff format blender_mcp scripts tests

format-check:
	$(UVRUN) ruff format --check blender_mcp scripts tests

lint:
	$(UVRUN) ruff check blender_mcp scripts tests --select E9,F63,F7,F82

type-check:
	$(UVRUN) mypy blender_mcp --ignore-missing-imports || true
	$(UVRUN) pyright blender_mcp

import-check:
	$(UVRUN) lint-imports

custom-checks:
	$(UVRUN) python scripts/quality/run_checks.py --fast

version-check:
	$(UVRUN) python scripts/quality/check_version.py

test:
	$(UVRUN) pytest tests -v --tb=short

test-fast:
	$(UVRUN) pytest tests/unit -v --tb=short -q -x

test-cov:
	$(UVRUN) pytest tests -v --cov=blender_mcp --cov-report=term --cov-report=html --cov-report=xml

release: check
	$(PYTHON) create_release_zip.py

inspect:
	$(UVRUN) python scripts/inspect_tools.py

inspect-essential:
	$(UVRUN) python scripts/inspect_tools.py --tier essential

inspect-summary:
	$(UVRUN) python scripts/inspect_tools.py --summary

clean:
	$(PYTHON) -c "import pathlib, shutil; dirs=['build','dist','htmlcov','.pytest_cache','.mypy_cache','.ruff_cache','.importlinter_cache','blender_mcp.egg-info']; [shutil.rmtree(d, ignore_errors=True) for d in dirs if pathlib.Path(d).exists()]; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; [f.unlink() for f in pathlib.Path('.').rglob('*.pyc') if f.exists()]"
	@echo "Cleaned generated artifacts."

clean-all: clean
	$(PYTHON) -c "import pathlib, shutil; dirs=['.venv','venv']; [shutil.rmtree(d, ignore_errors=True) for d in dirs if pathlib.Path(d).exists()]; [f.unlink() for f in pathlib.Path('.').glob('*.zip') if f.exists()]"
	@echo "Cleaned all local environment artifacts."

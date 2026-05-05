# AGENTS.md

## Repo Shape
- Single FastAPI app in `src/`; `src/main.py` creates `app` and includes `src/routes.py`.
- CSV inputs live in `data/`; tests use fixtures under `tests/data/`.
- Generated calendar output comes from `src/utils/ical.py`; address/geocoding logic lives in `src/utils/location.py`.

## Working Rules
- Prefer `nix develop` for local work. The shell sets `PYTHONPATH=.`, links `.venv`, and installs pre-commit hooks.
- If you do not use Nix, run `uv sync` first.
- Keep path-traversal protection in `GET /{name}.ics` intact; do not weaken the name validation or `resolve()` guard.
- Geocoding is optional and can be disabled with `GEOCODE_ENABLED=False`; mock Nominatim in tests instead of hitting the network.

## Commands
- Run the app: `uv run uvicorn src.main:app --reload`
- Run tests: `uv run pytest`
- Run focused tests: `uv run pytest tests/unit/test_server.py` or `uv run pytest tests/unit/test_location.py`
- Ruff check: `nix develop --command ruff check .`
- Ruff format check: `nix develop --command ruff format --check .`
- Ruff autofix / format: `nix develop --command ruff check --fix` and `nix develop --command ruff format`

## CI / Pre-commit
- GitHub Actions test workflow runs Ruff check, Ruff format check, and `pytest` on `main` and pull requests into `main`.
- Pre-commit hooks use the same Nix commands and also run `pytest` on every commit.
- Tag pushes matching `v*` build and publish a multi-arch Docker image.

## Releases
- `scripts/release.py` is the manual release helper.
- It only runs on `main`, expects a clean tree, and bumps `pyproject.toml` plus `uv.lock`.
- Use `python scripts/release.py --dry-run` first; the script does not run tests or lint before tagging.
- It infers the bump from commits since the latest `v*` tag: `feat:` or `feature:` means minor, `BREAKING CHANGE` or `!:` means major, otherwise patch.
- Pushes a `v*` tag trigger `.github/workflows/build.yml`, which publishes the GHCR image.

## Test Notes
- Some tests patch `settings.data_dir`; prefer that pattern over changing global config.
- Cache-sensitive geocoding tests clear `get_coordinates.cache_clear()` before asserting behavior.
- If calendar output changes, update both server tests and iCal/location tests together.

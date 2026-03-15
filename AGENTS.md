# AGENTS.md

## Cursor Cloud specific instructions

### Repository overview

This is **Pachca GitHub Integration** — an integration between [Pachca](https://pachca.com) (team messenger) and GitHub. The project uses Python (inferred from `.gitignore`).

### Current state

The repository is in its initial scaffolding phase with only `README.md`, `.gitignore` (Python template), and `LICENSE` (MIT). There is no application code, no dependency manifest (`requirements.txt`, `pyproject.toml`, etc.), and no test suite yet.

### Development environment

- **Python**: 3.12 is available system-wide at `/usr/bin/python3`.
- **pip**: Available system-wide.
- No virtual environment or dependency files exist yet. When dependency files are added, update the VM update script accordingly.

### Running the project

No services, lint checks, tests, or build steps exist yet. When code is added:
- Check for `requirements.txt` or `pyproject.toml` and install dependencies.
- Check `README.md` for updated run/test/lint instructions.

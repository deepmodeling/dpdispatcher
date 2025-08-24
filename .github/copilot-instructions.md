# DPDispatcher Development Guide

DPDispatcher is a Python package used to generate HPC (High-Performance Computing) scheduler systems (Slurm/PBS/LSF/Bohrium) jobs input scripts, submit them to HPC systems, and poke until they finish.

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Working Effectively

### Bootstrap, Build, and Test

- **Create virtual environment and install:**

  ```bash
  uv venv .venv
  source .venv/bin/activate
  uv pip install .[test] coverage ruff pre-commit
  ```

- **Run the test suite:**

  ```bash
  python -m coverage run -p --source=./dpdispatcher -m unittest -v
  python -m coverage combine
  python -m coverage report
  ```

  - **TIMING: Tests take ~25 seconds. NEVER CANCEL - set timeout to 2+ minutes.**

- **Run linting and formatting:**

  ```bash
  ruff check .
  ruff format --check .
  ```

  - **TIMING: Linting takes <1 second.**

- **Run type checking:**

  ```bash
  pyright
  ```

  - **TIMING: Type checking takes ~2-3 seconds.**

- **Build documentation:**

  ```bash
  uv pip install .[docs]
  cd doc
  make html
  ```

  - **TIMING: Documentation build takes ~14 seconds.**

### CLI Usage

- **Test basic CLI functionality:**

  ```bash
  dpdisp --help
  dpdisp run examples/dpdisp_run.py
  ```

- **Run sample job dispatch script:**
  ```bash
  python examples/dpdisp_run.py
  ```

## Validation

- **ALWAYS run the test suite after making code changes.** Tests execute quickly (~25 seconds) and should never be cancelled.
- **ALWAYS run linting before committing:** `ruff check . && ruff format --check .`
- **ALWAYS run type checking:** `pyright` to catch type-related issues.
- **Test CLI functionality:** Run `dpdisp --help` and test with example scripts to ensure the CLI works correctly.
- **Build documentation:** Run `make html` in the `doc/` directory to verify documentation builds without errors.

## Build and Development Workflow

- **Dependencies:** The project uses `uv` as the package manager for fast dependency resolution.
- **Build system:** Uses `setuptools` with `pyproject.toml` configuration.
- **Python versions:** Supports Python 3.7+ (check `pyproject.toml` for current support matrix).
- **Testing:** Uses `unittest` framework with coverage reporting.
- **Linting:** Uses `ruff` for both linting and formatting.
- **Type checking:** Uses `pyright` for static type analysis (configured in `pyproject.toml`).
- **Documentation:** Uses Sphinx with MyST parser for markdown support.

## Key Components

### Core Modules

- **`dpdispatcher/submission.py`**: Main classes - `Submission`, `Job`, `Task`, `Resources`
- **`dpdispatcher/machine.py`**: Machine configuration and dispatch logic
- **`dpdispatcher/contexts/`**: Context managers for different execution environments (SSH, local, etc.)
- **`dpdispatcher/machines/`**: HPC scheduler implementations (Slurm, PBS, LSF, Shell, etc.)

### Configuration Files

- **`examples/machine/`**: Example machine configurations (JSON format)
- **`examples/resources/`**: Example resource specifications
- **`examples/task/`**: Example task definitions
- **`examples/dpdisp_run.py`**: Complete working example using PEP 723 script metadata

### Important Directories

- **`tests/`**: Comprehensive test suite including unit tests and integration tests
- **`doc/`**: Sphinx documentation source files
- **`ci/`**: CI/CD configuration for Docker-based testing

## Common Tasks

### Running Examples

```bash
# Example with lazy local execution (no HPC needed)
dpdisp run examples/dpdisp_run.py

# Example output files created:
# - log: contains "hello world!" output
# - Various job tracking files (automatically cleaned up)
```

### Testing with Different HPC Systems

- **Local/Shell execution:** Use `LazyLocalContext` with `Shell` batch type (examples/machine/lazy_local.json)
- **SSH remote execution:** Use `SSHContext` (requires SSH setup)
- **HPC schedulers:** Use `Slurm`, `PBS`, `LSF` batch types (require actual HPC environment)

### Debugging Job Execution

- Check job logs in the work directory
- Use `dpdisp submission` commands to inspect job states
- Review machine and resource configurations in JSON files

## Project Structure Reference

```
.
├── README.md
├── pyproject.toml           # Project configuration and dependencies
├── dpdispatcher/            # Main package
│   ├── __init__.py
│   ├── submission.py        # Core submission/job/task classes
│   ├── machine.py          # Machine configuration
│   ├── contexts/           # Execution contexts (SSH, local, etc.)
│   ├── machines/           # HPC scheduler implementations
│   └── utils/              # Utility functions
├── examples/               # Example configurations and scripts
│   ├── machine/           # Example machine configs
│   ├── resources/         # Example resource specs
│   ├── task/             # Example task definitions
│   └── dpdisp_run.py     # Complete working example
├── tests/                # Comprehensive test suite
├── doc/                  # Sphinx documentation
└── ci/                   # CI/CD Docker configurations
```

## Development Notes

- **Always use virtual environments** - The system Python is externally managed
- **Always add type hints** - Include proper type annotations in all Python code for better maintainability
- **Always use conventional commit format** - All commit messages and PR titles must follow the conventional commit specification (e.g., `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)
- **Test artifacts are gitignored** - Job execution creates temporary files that are automatically excluded
- **Pre-commit hooks available** - Use `pre-commit install` to enable automated code quality checks
- **Multiple execution contexts** - Code supports local execution, SSH remote execution, and various HPC schedulers
- **Extensive examples** - Use `examples/` directory as reference for proper configuration formats

## Troubleshooting

- **Virtual environment issues:** Always use `uv venv .venv` and `source .venv/bin/activate`
- **Test failures:** Most tests run locally; some require specific HPC environments and will be skipped
- **Documentation build warnings:** Some warnings about external inventory URLs are expected in sandboxed environments
- **Pre-commit network issues:** If pre-commit fails with network timeouts, run `ruff check` and `ruff format` directly

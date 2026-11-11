# joule

A small framework on top of Prefect for batch jobs over tables of instruments: `stage` wraps a task, `job` wraps a flow.
Each stage takes and returns a PyArrow table with a per-row status (any string you choose), caches its result for the job's retention period,
and records every row's status in a durable, append-only audit log.

**The framework is `src/joule/` and nothing else.** Everything under `examples/` is optional: sample jobs, an audit
dashboard, and a Docker/AWS setup for running them. You don't need any of it to use the library.

    src/joule/       the framework (~8 files)
    examples/
      flows/         sample jobs written with @job / @stage
      dashboard/     audit dashboard (API + page) and the audit-table schema
      deploy/        Docker Compose stack, nginx, Terraform for a throwaway EC2 box

## Using it

    uv venv .venv --python 3.12
    uv pip install --python .venv/bin/python -e .
    source .venv/bin/activate

Set `AUDIT_DATABASE_URL` to a Postgres with the table from `examples/dashboard/init.sql` to enable the audit log
(without it, auditing is a no-op). See `examples/flows/` for jobs.

## Running the examples

    cd examples/deploy
    docker compose up -d        # postgres, prefect server, worker, audit dashboard, nginx
    # Prefect UI:  http://localhost:8080/prefect
    # Dashboard:   http://localhost:8080/audit/

AWS: see `examples/deploy/aws/README.md`.

## Neovim (LSP)

LazyVim with pyright. `pyproject.toml` already points pyright at `.venv`, `src/` and `examples/`, so start from the
project root with the venv active:

    cd ~/Code/prefect-run
    source .venv/bin/activate
    nvim .

One-time: enable the Python extra with `:LazyExtras` -> `lang.python`, restart.
Check with `:LspInfo` that `pyright` is attached. `gd` goes to definition, `gr` to references, `K` shows docs.

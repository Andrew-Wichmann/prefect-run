# joules

**Joules is a library for writing batch jobs on top of Prefect.** A Joules job is a straight pipeline of stages. Each stage takes
a PyArrow table and returns two: the transformed table, and a status table describing what happened to each record.

The transformed table gives Joules two things:

1. **Cached, queryable results.** Joules stores each stage's output as Parquet. That gives a standard result cache, so a job
   can restart from any stage, and it lets external tools query the stored results for analysis.
2. **Schema-checked pipelines.** Each stage declares its input and output PyArrow schemas. Joules checks that the stages chain
   when the job is defined, before anything runs, and enforces the schemas on every table at run time.

The status table gives you a **row-level audit trail**. When a stage completes, Joules appends that table to a durable,
append-only audit log (Postgres), so operators can later trace each record's path through a job. A status is any string you
choose, with an optional note; the library has no list of them.

`stage` wraps a Prefect task and `job` wraps a flow.

**The framework is `src/joules/` and nothing else.** Everything under `examples/` is optional: sample jobs, an audit
dashboard, and a Docker/AWS setup for running them. You don't need any of it to use the library.

    src/joules/       the framework (8 small files)
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

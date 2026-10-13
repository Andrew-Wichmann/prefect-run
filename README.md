# prefect-run

Prefect server, worker and a small `run` package (`stage` = task wrapper, `job` = flow wrapper).

## Stack

    docker compose up -d        # postgres, prefect server, worker, nginx
    # UI: http://localhost:8080/prefect

## Local development

    uv venv .venv --python 3.12
    uv pip install --python .venv/bin/python -e .
    source .venv/bin/activate

Code lives in `src/run/`; flows and the deployment script are in `flows/`.

## Neovim (LSP)

LazyVim with pyright. `pyproject.toml` already points pyright at `.venv`,
`src/` and `flows/`, so all you need is to start from the project root with the
venv active:

    cd ~/Code/prefect-run
    source .venv/bin/activate
    nvim .

One-time: enable the Python extra with `:LazyExtras` -> `lang.python`, restart.
Check with `:LspInfo` that `pyright` is attached. `gd` goes to definition,
`gr` to references, `K` shows docs.

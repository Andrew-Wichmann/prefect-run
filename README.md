# prefect-run

Prefect server, worker and a small `joule` package (`stage` = task wrapper, `job` = flow wrapper).

## Stack

    docker compose up -d        # postgres, prefect server, worker, nginx
    # UI: http://localhost:8080/prefect

## Local development

    uv venv .venv --python 3.12
    uv pip install --python .venv/bin/python -e .
    source .venv/bin/activate

Code lives in `src/joule/`; flows and the deployment script are in `flows/`.

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

## Links on the job card

Two ways to put a link on a run's card in the audit dashboard (http/https only):

```python
from joule import Link, job, link

@job(..., links=[Link("Margin dashboard", "https://grafana.example.com/d/margin?var-cob={cob}")])
def margin(...):
    link("Request trace", f"https://grafana.example.com/explore?trace={trace_id}")  # known only while running
```

`links=` is fixed per job type; `{name}` placeholders are filled per run from the run's parameters and `cob`, `run_id`,
`run_name`, `job` (a link whose placeholder has no value is hidden). `joule.link(label, url)` attaches a link to the
current run: it is a Prefect link artifact (also in Prefect's Artifacts tab), and a later link with the same label replaces the earlier one on the card.

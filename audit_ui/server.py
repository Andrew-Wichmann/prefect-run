"""Read-only HTTP API + static page over the stage_audit table."""

import asyncio
import importlib
import json
import os
import re
import sys
import threading
import time as clock
import urllib.error
import urllib.request
import tempfile
import uuid
import zipfile
from functools import lru_cache
from xml.sax.saxutils import escape
from dataclasses import asdict
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import psycopg
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from psycopg.rows import dict_row

DSN = os.environ["AUDIT_DATABASE_URL"]
PREFECT = os.environ.get("PREFECT_API_URL", "http://prefect-server:4200/api")
HERE = Path(__file__).parent
CACHE = Path(os.environ.get("PREFECT_LOCAL_STORAGE_PATH", "/opt/cache"))
SNAPSHOT_ROWS = 200  # most rows returned per request
PAGES = {"/": "index.html"}
ASSETS = {"/style.css": "text/css; charset=utf-8", **{f"/{n}.js": "text/javascript; charset=utf-8" for n in
          ["live", "tz", "stage-common", "layouts", "stage-data"]}}

sys.path.append("/opt/flows")  # job modules live next to the worker's flows
import deploy  # noqa: E402  (lists the job modules)
from joule.job import JOBS as REGISTRY  # noqa: E402

for module in deploy.JOBS:
    importlib.import_module(module)  # importing a job module registers it

# What the page needs about each job that has delivery and duration SLAs, straight from its @job declaration.
JOBS = {
    name: {
        "sla": asdict(spec.sla),
        "duration_sla": {"max_seconds": spec.duration_sla},
        "iceberg_table": spec.iceberg_table,
        "retention_seconds": spec.retention.total_seconds(),  # how long the job keeps its stage results
    }
    for name, spec in REGISTRY.items()
    if spec.sla and spec.duration_sla
}


class Changes:
    """Counts changes seen by the listeners; SSE handlers wait on it."""

    def __init__(self):
        self.version = 0
        self.cond = threading.Condition()

    def bump(self):
        with self.cond:
            self.version += 1
            self.cond.notify_all()

    def wait(self, seen, timeout):
        with self.cond:
            self.cond.wait_for(lambda: self.version != seen, timeout)
            return self.version


CHANGES = Changes()


def listen_audit():
    """Postgres NOTIFY from the stage_audit insert trigger -> change."""
    while True:
        try:
            with psycopg.connect(DSN, autocommit=True) as conn:
                conn.execute("LISTEN stage_audit")
                CHANGES.bump()  # anything missed while disconnected
                for _ in conn.notifies():
                    CHANGES.bump()
        except psycopg.Error as e:
            print("audit listener:", e, flush=True)
            clock.sleep(2)


def listen_prefect():
    """Prefect flow-run events (new runs, state changes) -> change."""
    from prefect.events.clients import get_events_subscriber
    from prefect.events.filters import EventFilter, EventNameFilter

    async def run():
        flt = EventFilter(event=EventNameFilter(prefix=["prefect.flow-run.", "prefect.task-run."]))
        async with get_events_subscriber(filter=flt) as events:
            async for _ in events:
                CHANGES.bump()

    while True:
        try:
            asyncio.run(run())
        except Exception as e:  # server restarting etc.
            print("prefect listener:", e, flush=True)
        clock.sleep(2)


def job_stages(name):
    """Stage names a job declares in @job(stages=...)."""
    return REGISTRY[name].stages


# Flow runs (jobs) and task runs (stages) show Prefect's own state names, unchanged.
# Instruments have their own, separate vocabulary: joule.Status.
RUN_STATES = ["Scheduled", "Pending", "Running", "Completed", "Failed", "Crashed", "Cancelling", "Cancelled", "Paused"]


def query(sql, params=()):
    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchall()


def prefect(path, body=None):
    req = urllib.request.Request(
        PREFECT + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


PAGE_SIZE = 10


def run_info(run, job):
    """One flow run as a job-history row; SLA is judged against the COB date in the SLA's timezone."""
    sla = JOBS[job]["sla"]
    tz = ZoneInfo(sla["tz"])
    start = datetime.fromisoformat(run["start_time"]) if run["start_time"] else None
    end = datetime.fromisoformat(run["end_time"]) if run["end_time"] else None
    status = run["state"]["name"]
    cob = start.astimezone(tz).date() if start else None
    # Delivery SLA: due at `time` on COB + day_offset (T+1 = the day after the COB date), in the SLA's timezone.
    deadline = None
    sla_met = None
    if cob:
        hour, minute = map(int, sla["time"].split(":"))
        deadline = datetime.combine(cob + timedelta(days=sla.get("day_offset", 0)), time(hour, minute), tz)
        if end and status == "Completed":
            sla_met = end <= deadline
        elif datetime.now(timezone.utc) > deadline:
            sla_met = False  # still not delivered after the deadline
    finish = end or datetime.now(timezone.utc)
    duration_s = (finish - start).total_seconds() if start else None
    # Duration SLA: how long the run may take. Breached as soon as it runs over, even while in flight.
    limit = JOBS[job]["duration_sla"]["max_seconds"]
    duration_sla_met = None if duration_s is None else False if duration_s > limit else True if status == "Completed" else None
    return {
        "run_id": run["id"],
        "run_name": run["name"],
        "job": job,
        "cob": cob.isoformat() if cob else None,
        "status": status,
        "status_type": run["state"]["type"],
        "start_time": run["start_time"],
        "end_time": run["end_time"],
        "duration_s": duration_s,
        "sla_met": sla_met,
        "sla_deadline": deadline.isoformat() if deadline else None,
        "duration_sla_met": duration_sla_met,
        "url": f"/prefect/runs/flow-run/{run['id']}",
        "deployment_id": run.get("deployment_id"),
        "parameters": run.get("parameters") or {},
    }


MAX_SCAN = 1000  # newest runs considered when filtering
SCAN_BATCH = 200  # Prefect's page-size cap


def jobs_history(page, f):
    """Job-history page. Job and status filter in Prefect; the derived columns filter here."""
    flows = {x["id"]: x["name"] for x in prefect("/flows/filter", {"flows": {"name": {"any_": list(JOBS)}}})}
    names = [n for n in [f.get("job")] if n in JOBS] or None
    ids = [i for i, n in flows.items() if names is None or n in names]
    flt = {"flows": {"id": {"any_": ids}}}
    if f.get("status"):
        flt["flow_runs"] = {"state": {"name": {"any_": [f["status"]]}}}

    runs = []
    while len(runs) < MAX_SCAN:
        batch = prefect(
            "/flow_runs/filter", {**flt, "sort": "START_TIME_DESC", "limit": SCAN_BATCH, "offset": len(runs)}
        )
        runs += batch
        if len(batch) < SCAN_BATCH:
            break

    rows = [run_info(r, flows[r["flow_id"]]) for r in runs]
    sla_filter = {"met": True, "missed": False, "pending": None}.get(f.get("sla"), "any")
    dsla_filter = {"met": True, "missed": False, "pending": None}.get(f.get("dsla"), "any")
    min_s = float(f["min_minutes"]) * 60 if f.get("min_minutes") else None
    rows = [
        r
        for r in rows
        if (not f.get("cob") or r["cob"] == f["cob"])
        and (sla_filter == "any" or r["sla_met"] is sla_filter)
        and (dsla_filter == "any" or r["duration_sla_met"] is dsla_filter)
        and (min_s is None or (r["duration_s"] or 0) >= min_s)
    ]
    return {
        "page": page,
        "page_size": PAGE_SIZE,
        "total": len(rows),
        "rows": rows[page * PAGE_SIZE : (page + 1) * PAGE_SIZE],
        "jobs": list(JOBS),
        "statuses": RUN_STATES,
    }


def stage_times(run_id):
    """Start/end/duration of each stage's Prefect task run, keyed by stage name."""
    tasks = prefect("/task_runs/filter", {"flow_runs": {"id": {"any_": [run_id]}}, "limit": 200})
    return {
        t["name"]: {
            "id": t["id"],
            "status": t["state"]["name"],
            "status_type": t["state"]["type"],
            "start_time": t["start_time"],
            "end_time": t["end_time"],
            "duration_s": t["total_run_time"],
        }
        for t in tasks
    }


BASELINE_RUNS = 10  # completed earlier runs of the job averaged into "historical"


def stage_baseline(run):
    """Average start/end (seconds after the run's first stage started) and duration per stage over earlier completed runs."""
    earlier = prefect(
        "/flow_runs/filter",
        {
            "flows": {"id": {"any_": [run["flow_id"]]}},
            "flow_runs": {"id": {"not_any_": [run["id"]]}, "state": {"type": {"any_": ["COMPLETED"]}}},
            "sort": "START_TIME_DESC",
            "limit": BASELINE_RUNS,
        },
    )
    if not earlier:
        return {}
    tasks = prefect("/task_runs/filter", {"flow_runs": {"id": {"any_": [r["id"] for r in earlier]}}, "limit": 200})
    parse = datetime.fromisoformat
    # Offsets are measured from each run's own first stage start, so when the runs happened doesn't matter.
    origin = {}
    for t in tasks:
        if t["start_time"]:
            origin[t["flow_run_id"]] = min(origin.get(t["flow_run_id"], parse(t["start_time"])), parse(t["start_time"]))
    samples = {}
    for t in tasks:
        if t["state"]["name"] == "Completed" and t["start_time"] and t["end_time"]:
            t0 = origin[t["flow_run_id"]]
            samples.setdefault(t["name"], []).append(
                ((parse(t["start_time"]) - t0).total_seconds(), (parse(t["end_time"]) - t0).total_seconds(), t["total_run_time"])
            )
    return {
        stage: {
            "start_s": sum(x[0] for x in xs) / len(xs),
            "end_s": sum(x[1] for x in xs) / len(xs),
            "duration_s": sum(x[2] for x in xs) / len(xs),
            "runs": len(xs),
        }
        for stage, xs in samples.items()
    }


def stage_counts(run_id):
    """How many instruments ended in each status at each stage of a run."""
    counts = {}
    for r in query(
        "SELECT stage_name, status, count(*) AS n FROM stage_audit WHERE flow_run_id = %s GROUP BY 1, 2",
        (run_id,),
    ):
        counts.setdefault(r["stage_name"], {})[r["status"]] = r["n"]
    return counts


def job_detail(run_id):
    run = prefect(f"/flow_runs/{run_id}")
    flow = prefect(f"/flows/{run['flow_id']}")
    name = flow["name"]
    if name not in JOBS:
        raise KeyError(name)
    return {
        **JOBS[name],
        **run_info(run, name),
        "name": name,
        "stages": job_stages(name),
        "stage_times": stage_times(run_id),
        "stage_counts": stage_counts(run_id),
        "stage_baseline": stage_baseline(run),
    }


def stage_history(run_id, stage, offset=0, limit=100, filters=None, sort="key", direction="asc"):
    """What one stage did to each instrument in a single run: one page, filtered and sorted in the database."""
    cols = {"key": "item_key", "status": "status", "detail": "detail", "at": "recorded_at::text"}
    where, params = ["flow_run_id = %s", "stage_name = %s"], [run_id, stage]
    for name, text in (filters or {}).items():
        if name in cols and text:
            like = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            where.append(f"COALESCE({cols[name]}::text, '') ILIKE %s")
            params.append(f"%{like}%")
    where = " AND ".join(where)
    order = f"{cols.get(sort, 'item_key').split('::')[0]} {'DESC' if direction == 'desc' else 'ASC'}, item_key"
    total = query(f"SELECT count(*) AS n FROM stage_audit WHERE {where}", params)[0]["n"]
    rows = query(f"SELECT item_key, status, detail, recorded_at FROM stage_audit WHERE {where} ORDER BY {order} LIMIT %s OFFSET %s",
                 [*params, min(max(limit, 1), 1000), max(offset, 0)])
    return {"total": total, "items": [{"key": r["item_key"], "status": r["status"], "detail": r["detail"], "at": r["recorded_at"]} for r in rows]}


def instrument_history(run_id, key):
    """Every stage's outcome for one instrument in a single run."""
    return {
        "stages": query(
            "SELECT stage_name, status, detail, recorded_at FROM stage_audit "
            "WHERE flow_run_id = %s AND item_key = %s ORDER BY id",
            (run_id, key),
        )
    }


def _cache_file(task_run):
    """The stage output a task run produced or reused: its result file in the cache (raw Parquet)."""
    key = ((task_run.get("state") or {}).get("data") or {}).get("storage_key")
    if not key:
        raise FileNotFoundError("task run has no stored result")
    return CACHE / Path(key).name  # basename only, so a key can't walk out of CACHE


def snapshot_list(run_id, stage):
    """Every task run of this stage within the flow run (a bust or retry adds one) that has a result, oldest first."""
    runs = prefect("/task_runs/filter", {"flow_runs": {"id": {"any_": [str(uuid.UUID(run_id))]}},
                                         "task_runs": {"name": {"any_": [stage]}}, "sort": "EXPECTED_START_TIME_ASC"})
    out = []
    for t in runs:
        try:
            f = _cache_file(t)
            out.append({"task_run_id": t["id"], "rows": pq.ParquetFile(f).metadata.num_rows, "bytes": f.stat().st_size,
                        "at": t["start_time"]})
        except FileNotFoundError:
            continue
    return {"snapshots": out}


def snapshot_rows(run_id, stage, task_run_id, offset):
    """One page of a stage output's rows, with its schema."""
    pf = pq.ParquetFile(_cache_file(prefect(f"/task_runs/{uuid.UUID(task_run_id)}")))  # FileNotFoundError -> 404 below
    offset = max(offset, 0)
    rows, seen = [], 0
    for batch in pf.iter_batches(batch_size=SNAPSHOT_ROWS):
        if seen + batch.num_rows > offset and len(rows) < SNAPSHOT_ROWS:
            rows += batch.to_pylist()[max(offset - seen, 0):][: SNAPSHOT_ROWS - len(rows)]
        seen += batch.num_rows
        if len(rows) >= SNAPSHOT_ROWS:
            break
    # Each row's status is not a column: ParquetSerializer keeps the outcomes in the file's metadata, keyed by primary key.
    meta = (pf.schema_arrow.metadata or {}).get(b"joule.outcomes")
    outcomes = {}
    if meta:
        o = json.loads(meta)
        outcomes = {str(k): {"status": s, "detail": d} for k, s, d in zip(o["key"], o["status"], o["detail"])}
    for row in rows:
        row["__outcome"] = outcomes.get(str(row.get("primary_key")))
    return {
        "columns": [{"name": c.name, "type": str(c.type)} for c in pf.schema_arrow],
        "total": pf.metadata.num_rows, "offset": offset, "rows": rows, "has_outcomes": bool(outcomes),
    }


# --- Stage-output viewer: the wide stress tables (one row per instrument, 700 pricing_scenario_N columns), paged. -----------------

SCENARIO = "pricing_scenario_"


def stage_file(run_id, stage, task_run_id=None):
    """The Parquet result of this stage in the flow run (the latest task run unless one is named)."""
    if not task_run_id:
        snaps = snapshot_list(run_id, stage)["snapshots"]
        if not snaps:
            raise FileNotFoundError("no snapshot")
        task_run_id = snaps[-1]["task_run_id"]
    return _cache_file(prefect(f"/task_runs/{uuid.UUID(task_run_id)}"))


@lru_cache(maxsize=2)
def _load(path, mtime):
    return pq.read_table(path)


def load(path):
    return _load(str(path), Path(path).stat().st_mtime_ns)


def _outcomes(path):
    meta = (pq.read_schema(path).metadata or {}).get(b"joule.outcomes")
    if not meta:
        return {}
    o = json.loads(meta)
    return {str(k): [s, d] for k, s, d in zip(o["key"], o["status"], o["detail"])}


def matrix_chunks(path, row_offset, row_limit, col_offset, col_limit, key=None):
    """JSON for a window of the table, yielded in pieces so a whole-table request never sits in memory as one string."""
    t = load(path)
    scen = [c for c in t.column_names if c.startswith(SCENARIO)]
    if key:
        t = t.filter(pc.equal(t["primary_key"], key))
        row_offset = 0
    rows = t.slice(row_offset, row_limit or None)
    cols = scen[col_offset: col_offset + col_limit if col_limit else None]
    out = _outcomes(path)
    keys = rows["primary_key"].to_pylist()
    head = {
        "total_rows": t.num_rows, "total_cols": len(scen), "row_offset": row_offset, "col_offset": col_offset,
        "columns": [c for c in t.column_names if not c.startswith(SCENARIO)], "scenario_names": cols,
        "keys": keys, "outcomes": [out.get(k) for k in keys],
        "price": rows["price"].to_pylist() if "price" in rows.column_names else None,
        "curve_shift": rows["curve_shift"].to_pylist() if "curve_shift" in rows.column_names else None,
    }
    yield (json.dumps(head)[:-1] + ', "values": [').encode()
    first = True
    for i in range(0, rows.num_rows, 250):
        part = rows.slice(i, 250)
        lists = [part[c].to_pylist() for c in cols]
        body = ",".join(json.dumps(list(r), separators=(",", ":")) for r in zip(*lists)) if lists else ""
        if body:
            yield ((b"" if first else b",") + body.encode())
            first = False
    yield b"]}"


@lru_cache(maxsize=2)
def _stats(path, mtime):
    """Per-instrument summary of its 700 scenario prices, plus status; chunked so the whole table never becomes Python lists."""
    t = load(path)
    scen = [c for c in t.column_names if c.startswith(SCENARIO)]
    out = _outcomes(path)
    keys, price = t["primary_key"].to_pylist(), t["price"].to_pylist()
    rows = []
    for i in range(0, t.num_rows, 500):
        lists = [t[c].slice(i, 500).to_pylist() for c in scen]
        for j, vals in enumerate(zip(*lists)):
            n, v = len(vals), sorted(vals)
            mean = sum(vals) / n
            std = (sum((x - mean) ** 2 for x in vals) / n) ** 0.5
            k, p = keys[i + j], price[i + j]
            rows.append({"key": k, "status": (out.get(k) or [None])[0], "price": p, "min": v[0], "p5": v[int(.05 * (n - 1))],
                         "p50": v[(n - 1) // 2], "p95": v[int(.95 * (n - 1))], "max": v[-1], "mean": mean, "std": std,
                         "worst_pct": (v[0] / p - 1) if p else None, "best_pct": (v[-1] / p - 1) if p else None})
    return rows


def stats_page(path, sort, desc, offset, limit, q):
    rows = _stats(str(path), Path(path).stat().st_mtime_ns)
    if q:
        rows = [r for r in rows if q.lower() in r["key"].lower()]
    if sort in ("key", "status", "price", "min", "p5", "p50", "p95", "max", "mean", "std", "worst_pct", "best_pct"):
        rows = sorted(rows, key=lambda r: (r[sort] is None, r[sort]), reverse=desc)
    return {"total": len(rows), "offset": offset, "rows": rows[offset: offset + limit]}


@lru_cache(maxsize=2)
def _scenarios(path, mtime):
    """Each scenario's move across the instruments: mean, worst and best percentage change against the instrument's price."""
    t = load(path)
    price = t["price"]
    out = []
    for c in (c for c in t.column_names if c.startswith(SCENARIO)):
        pct = pc.subtract(pc.divide(t[c], price), 1.0)
        mm = pc.min_max(pct).as_py()
        out.append({"n": int(c[len(SCENARIO):]), "mean": pc.mean(pct).as_py(), "min": mm["min"], "max": mm["max"]})
    return out


def write_xlsx(path, dest, row_offset, row_limit, col_offset, col_limit):
    """An Excel workbook of a window of the stage output (key, status, price, curve_shift, then the scenario columns).
    An .xlsx is a zip of XML, so this is written straight to disk row by row with the standard library (no extra packages)."""
    t = load(path)
    scen = [c for c in t.column_names if c.startswith(SCENARIO)]
    other = [c for c in t.column_names if c not in scen]
    cols = scen[col_offset: col_offset + col_limit if col_limit else None]
    rows = t.slice(row_offset, row_limit or None)
    out = _outcomes(path)
    text = lambda v: f'<c t="inlineStr"><is><t>{escape(str(v))}</t></is></c>'  # noqa: E731
    num = lambda v: "<c/>" if v is None else f"<c><v>{v!r}</v></c>"  # noqa: E731
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="stage output" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        with z.open("xl/worksheets/sheet1.xml", "w", force_zip64=True) as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane xSplit="2" ySplit="1" topLeftCell="C2" activePane="bottomRight" state="frozen"/></sheetView></sheetViews><sheetData>')
            f.write(("<row>" + "".join(text(h) for h in ["primary_key", "status", *[c for c in other if c != "primary_key"], *cols]) + "</row>").encode())
            for i in range(0, rows.num_rows, 250):
                part = rows.slice(i, 250)
                keys = part["primary_key"].to_pylist()
                extra = [part[c].to_pylist() for c in other if c != "primary_key"]
                lists = [part[c].to_pylist() for c in cols]
                buf = []
                for j, vals in enumerate(zip(*lists) if lists else [()] * part.num_rows):
                    status = (out.get(keys[j]) or [""])[0]
                    buf.append("<row>" + text(keys[j]) + text(status) + "".join(num(e[j]) for e in extra) + "".join(num(v) for v in vals) + "</row>")
                f.write("".join(buf).encode())
            f.write(b"</sheetData></worksheet>")


class Handler(BaseHTTPRequestHandler):
    def _chunks(self, chunks, ctype):
        """Send a body of unknown length; the connection closes at the end (HTTP/1.0), which marks it."""
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        try:
            for c in chunks:
                self.wfile.write(c)
        except OSError:
            pass

    def _send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        seen = CHANGES.version
        try:
            while True:
                version = CHANGES.wait(seen, 15)
                # a change is a data event; a timeout is a keep-alive comment
                self.wfile.write(b"data: changed\n\n" if version != seen else b": keep-alive\n\n")
                self.wfile.flush()
                seen = version
        except OSError:
            pass  # client went away

    def do_GET(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        try:
            if url.path == "/api/stream":
                return self._stream()
            if url.path in PAGES:
                return self._send((HERE / PAGES[url.path]).read_bytes(), "text/html; charset=utf-8")
            if url.path in ASSETS:
                return self._send((HERE / url.path[1:]).read_bytes(), ASSETS[url.path])
            if url.path == "/api/jobs":
                data = jobs_history(max(int(qs.get("page", ["0"])[0]), 0), {k: v[0] for k, v in qs.items() if v[0]})
            elif url.path == "/api/job":
                data = job_detail(qs["run"][0])
            elif url.path == "/api/stage":
                data = stage_history(qs["run"][0], qs["stage"][0], int(qs.get("offset", ["0"])[0]), int(qs.get("limit", ["100"])[0]),
                                     {k: qs[k][0] for k in ("key", "status", "detail", "at") if k in qs}, qs.get("sort", ["key"])[0], qs.get("dir", ["asc"])[0])
            elif url.path == "/api/snapshots":
                data = snapshot_list(qs["run"][0], qs["stage"][0])
            elif url.path == "/api/snapshot":
                data = snapshot_rows(qs["run"][0], qs["stage"][0], qs["task_run"][0], int(qs.get("offset", ["0"])[0]))
            elif url.path in ("/api/matrix", "/api/stats", "/api/scenarios", "/api/parquet", "/api/outcomes", "/api/xlsx"):
                q = {k: v[0] for k, v in qs.items()}
                f = stage_file(q["run"], q["stage"], q.get("task_run"))
                num = lambda k, d=0: max(int(q.get(k, d)), 0)  # noqa: E731
                if url.path == "/api/matrix":
                    return self._chunks(matrix_chunks(f, num("row_offset"), num("row_limit"), num("col_offset"), num("col_limit"),
                                                      q.get("key")), "application/json")
                if url.path == "/api/xlsx":
                    with tempfile.NamedTemporaryFile(suffix=".xlsx") as tmp:
                        write_xlsx(f, tmp.name, num("row_offset"), num("row_limit"), num("col_offset"), num("col_limit"))
                        size = Path(tmp.name).stat().st_size
                        self.send_response(200)
                        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                        self.send_header("Content-Disposition", f'attachment; filename="{re.sub(r"[^A-Za-z0-9_-]", "_", q["stage"])}-{q["run"][:8]}.xlsx"')
                        self.send_header("Content-Length", str(size))
                        self.end_headers()
                        while chunk := tmp.read(1 << 20):
                            self.wfile.write(chunk)
                    return
                if url.path == "/api/parquet":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(f.stat().st_size))
                    self.end_headers()
                    with open(f, "rb") as fh:
                        while chunk := fh.read(1 << 20):
                            self.wfile.write(chunk)
                    return
                if url.path == "/api/outcomes":
                    data = [{"primary_key": k, "status": v[0], "detail": v[1]} for k, v in _outcomes(f).items()]
                elif url.path == "/api/scenarios":
                    data = {"scenarios": _scenarios(str(f), f.stat().st_mtime_ns)}
                else:
                    data = stats_page(f, q.get("sort", "key"), q.get("dir") == "desc", num("offset"), min(num("limit", 50), 500), q.get("q", ""))
            elif url.path == "/api/instrument":
                data = instrument_history(qs["run"][0], qs["key"][0])
            else:
                return self.send_error(404)
            body = json.dumps(data, default=str).encode()
            self._send(body, "application/json")
        except urllib.error.HTTPError as e:
            self.send_error(404 if e.code == 404 else 502, "prefect error")
        except FileNotFoundError:
            self.send_error(404, "no snapshot")
        except OSError:
            self.send_error(502, "prefect unreachable")
        except (KeyError, ValueError, psycopg.Error) as e:
            self.send_error(400 if isinstance(e, (KeyError, ValueError)) else 500, str(e)[:100])


if __name__ == "__main__":
    for target in (listen_audit, listen_prefect):
        threading.Thread(target=target, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()

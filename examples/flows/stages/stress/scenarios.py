import random

import pyarrow as pa
import pyarrow.compute as pc

SCENARIOS = 700
SCENARIO_FIELDS = [pa.field(f"pricing_scenario_{i}", pa.float64()) for i in range(1, SCENARIOS + 1)]
_SHOCKS = (lambda r: [r.gauss(0.0, 0.08) for _ in range(SCENARIOS)])(random.Random(2026))  # one market move per scenario, the same in every job


def add_scenarios(table: pa.Table, base: pa.ChunkedArray | pa.Array) -> pa.Table:
    """Append the 700 ``pricing_scenario_N`` columns: ``base`` repriced under each scenario's market move,
    scaled by a per-instrument sensitivity (stub for the real revaluation)."""
    beta = pa.array([random.uniform(0.4, 1.6) for _ in range(len(base))])
    prices = [pc.round(pc.multiply(base, pc.add(1.0, pc.multiply(beta, shock))), 4) for shock in _SHOCKS]
    columns = [*table.columns, *prices]
    return pa.Table.from_arrays(columns, schema=pa.schema([*table.schema, *SCENARIO_FIELDS]))

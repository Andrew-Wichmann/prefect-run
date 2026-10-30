import random
from enum import Enum

import pyarrow as pa


class InstrumentType(str, Enum):
    BOND_FUTURE = "bond_future"
    FIXED_INCOME_REPO = "fixed_income_repo"
    INTEREST_RATE_SWAP = "interest_rate_swap"
    MORTGAGE_BACKED_SECURITY = "mortgage_backed_security"
    TO_BE_ANNOUNCED = "to_be_announced"
    STOCK = "stock"
    EQUITY_OPTION = "equity_option"
    EQUITY_FUTURE = "equity_future"


# Deployment ("<flow name>/<deployment name>") that stresses each type. Types
# without an entry have no job yet.
JOB_FOR: dict[InstrumentType, str] = {
    InstrumentType.BOND_FUTURE: "stress-bond-futures/stress-bond-futures",
    InstrumentType.FIXED_INCOME_REPO: "stress-fixed-income-repos/stress-fixed-income-repos",
    InstrumentType.INTEREST_RATE_SWAP: "stress-interest-rate-swaps/stress-interest-rate-swaps",
    InstrumentType.MORTGAGE_BACKED_SECURITY: "stress-mortgage-backed-security/stress-mortgage-backed-security",
    InstrumentType.TO_BE_ANNOUNCED: "stress-to-be-announced/stress-to-be-announced",
}


PREFIX = {
    InstrumentType.BOND_FUTURE: "BF",
    InstrumentType.FIXED_INCOME_REPO: "REPO",
    InstrumentType.INTEREST_RATE_SWAP: "IRS",
    InstrumentType.MORTGAGE_BACKED_SECURITY: "MBS",
    InstrumentType.TO_BE_ANNOUNCED: "TBA",
    InstrumentType.STOCK: "STK",
    InstrumentType.EQUITY_OPTION: "OPT",
    InstrumentType.EQUITY_FUTURE: "EQF",
}


def make_instruments(rng: random.Random, n: int, only: InstrumentType | None = None) -> pa.Table:
    """Fake instrument master: ``n`` rows of mixed type (or all of type ``only``) with a random price."""
    types = [only or rng.choice(list(InstrumentType)) for _ in range(n)]
    return pa.table(
        {
            "primary_key": [f"{PREFIX[t]}-{i:04d}" for i, t in enumerate(types)],
            "instrument_type": [t.value for t in types],
            "price": [round(rng.uniform(90, 120), 2) for _ in types],
        }
    )

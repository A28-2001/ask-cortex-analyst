"""Write eval results without ever replacing a good run with a broken one.

The recorded results in eval/ are irreplaceable: the live account behind them
can lapse, and the numbers they back are quoted publicly. An eval script run
while the account is down used to overwrite them with error output. Now, if
any result shows an infrastructure failure (as opposed to a model producing
bad SQL, which is a legitimate recorded outcome), the canonical file is left
alone and the run is written to a timestamped sibling for inspection.

Also writes with yaml.safe_dump, converting Decimal and date values first,
so result files load with yaml.safe_load (earlier runs leaked Python-specific
Decimal tags).
"""

import datetime as dt
import decimal

import yaml

INFRA_FAILURE_MARKERS = (
    "API_ERROR",
    "trial has ended",
    "Failed to connect",
    "has been suspended",
    "cannot be resumed",
    "Max retries exceeded",
    "Connection refused",
)


def _plain(value):
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def infrastructure_failures(results):
    """IDs of results whose recorded output is an infrastructure error."""
    return [
        r.get("id", "?")
        for r in results
        if any(m in str(v) for v in r.values() for m in INFRA_FAILURE_MARKERS)
    ]


def save_results(path, results):
    """Write results to `path`, or to a .failed-<time>.yaml sibling if any
    call hit an infrastructure failure. Returns the path actually written."""
    failed = infrastructure_failures(results)
    target = path
    if failed:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        target = path[: -len(".yaml")] + f".failed-{stamp}.yaml"
    with open(target, "w") as f:
        yaml.safe_dump({"results": _plain(results)}, f, sort_keys=False, width=100, allow_unicode=True)
    if failed:
        print(
            f"\n{len(failed)} of {len(results)} calls hit an infrastructure failure "
            f"({', '.join(failed[:6])}). Left {path} untouched; wrote this run to {target}."
        )
    else:
        print(f"\nWrote results to {path}")
    return target

"""Run PEP 723 script."""

from dpdispatcher.run import run_pep723


def run(*, filename: str, allow_ref: bool = False) -> None:
    with open(filename) as f:
        script = f.read()
    run_pep723(script, allow_ref=allow_ref)

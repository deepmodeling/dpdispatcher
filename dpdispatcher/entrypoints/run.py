"""Run PEP 723 script."""

from dpdispatcher.run import run_pep723


def run(*, filename: str):
    with open(filename) as f:
        script = f.read()
    run_pep723(script)

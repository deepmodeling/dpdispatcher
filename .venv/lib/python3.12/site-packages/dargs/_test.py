from __future__ import annotations

from typing import List

from dargs.dargs import Argument


def test_arguments() -> list[Argument]:
    """Returns a list of arguments."""
    return [
        Argument(name="test1", dtype=int, doc="Argument 1"),
        Argument(name="test2", dtype=[float, None], doc="Argument 2"),
        Argument(
            name="test3",
            dtype=List[str],
            default=["test"],
            optional=True,
            doc="Argument 3",
        ),
    ]


__all__ = [
    "test_arguments",
]

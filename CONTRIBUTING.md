# How to contribute

DPDispatcher welcomes contributions from individuals and organizations under the LGPL-3.0 License.

Open an issue, submit a pull request, join a GitHub discussion, or contact the DeepModeling team. Improvements of every size are welcome, including:

- using, starring, or forking DPDispatcher;
- improving documentation and examples;
- reporting or fixing bugs; and
- requesting, discussing, or implementing features.

## Docstrings and documentation

Public modules, classes, functions, and core API methods must have docstrings.
DPDispatcher uses the NumPy docstring convention enforced by Ruff's `D` rules.
Document behavior, parameters, return values, exceptions, important invariants,
and backend-specific differences when they are not obvious from the signature.
Avoid comments that merely repeat the function name.

User-facing documentation lives in `doc/` and is built with Sphinx and MyST.
Use Sphinx/MyST cross-references to API objects so renamed objects produce a
documentation warning instead of a silent broken link. After documentation or
Python changes, run:

```bash
pre-commit run --all-files
pyright
python -m coverage run -p --source=./dpdispatcher -m unittest -v
python -m coverage combine
python -m coverage report
make -C doc html
```

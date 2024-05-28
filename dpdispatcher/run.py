import os
import re
import sys
from glob import glob
from hashlib import sha1

from dpdispatcher.machine import Machine
from dpdispatcher.submission import Resources, Submission, Task

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
from typing import List, Optional

from dargs import Argument

from dpdispatcher.arginfo import machine_dargs, resources_dargs, task_dargs

REGEX = r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"


def read_pep723(script: str) -> Optional[dict]:
    """Read a PEP 723 script metadata from a script string.

    Parameters
    ----------
    script : str
        Script content.

    Returns
    -------
    dict
        PEP 723 metadata.
    """
    name = "script"
    matches = list(
        filter(lambda m: m.group("type") == name, re.finditer(REGEX, script))
    )
    if len(matches) > 1:
        # TODO: Add tests for scenarios where multiple script blocks are found
        raise ValueError(f"Multiple {name} blocks found")
    elif len(matches) == 1:
        content = "".join(
            line[2:] if line.startswith("# ") else line[1:]
            for line in matches[0].group("content").splitlines(keepends=True)
        )
        return tomllib.loads(content)
    else:
        # TODO: Add tests for scenarios where no metadata is found
        return None


def pep723_args() -> Argument:
    """Return the argument parser for PEP 723 metadata."""
    machine_args = machine_dargs()
    machine_args.fold_subdoc = True
    machine_args.doc = "Machine configuration. See related documentation for details."
    resources_args = resources_dargs(detail_kwargs=False)
    resources_args.fold_subdoc = True
    resources_args.doc = (
        "Resources configuration. See related documentation for details."
    )
    task_args = task_dargs()
    command_arg = task_args["command"]
    command_arg.doc = (
        "Python interpreter or launcher. No need to contain the Python script filename."
    )
    command_arg.default = "python"
    command_arg.optional = True
    task_args["task_work_path"].doc += " Can be a glob pattern."
    task_args.name = "task_list"
    task_args.doc = "List of tasks to execute."
    task_args.repeat = True
    task_args.dtype = (list,)
    return Argument(
        "pep723",
        dtype=dict,
        doc="PEP 723 metadata",
        sub_fields=[
            Argument(
                "work_base",
                dtype=str,
                optional=True,
                default="./",
                doc="Base directory for the work",
            ),
            Argument(
                "forward_common_files",
                dtype=List[str],
                optional=True,
                default=[],
                doc="Common files to forward to the remote machine",
            ),
            Argument(
                "backward_common_files",
                dtype=List[str],
                optional=True,
                default=[],
                doc="Common files to backward from the remote machine",
            ),
            machine_args,
            resources_args,
            task_args,
        ],
    )


def create_submission(metadata: dict, hash: str) -> Submission:
    """Create a Submission instance from a PEP 723 metadata.

    Parameters
    ----------
    metadata : dict
        PEP 723 metadata.
    hash : str
        Submission hash.

    Returns
    -------
    Submission
        Submission instance.
    """
    base = pep723_args()
    metadata = base.normalize_value(metadata, trim_pattern="_*")
    base.check_value(metadata, strict=False)

    tasks = []
    for task in metadata["task_list"]:
        task = task.copy()
        task["command"] += f" $REMOTE_ROOT/script_{hash}.py"
        task_work_path = os.path.join(
            metadata["machine"]["local_root"],
            metadata["work_base"],
            task["task_work_path"],
        )
        if os.path.isdir(task_work_path):
            tasks.append(Task.load_from_dict(task))
        elif glob(task_work_path):
            for file in glob(task_work_path):
                tasks.append(Task.load_from_dict({**task, "task_work_path": file}))
        # TODO: Add tests for scenarios where the task work path is a glob pattern
        else:
            # TODO: Add tests for scenarios where the task work path is not found
            raise FileNotFoundError(f"Task work path {task_work_path} not found.")
    return Submission(
        work_base=metadata["work_base"],
        forward_common_files=metadata["forward_common_files"],
        backward_common_files=metadata["backward_common_files"],
        machine=Machine.load_from_dict(metadata["machine"]),
        resources=Resources.load_from_dict(metadata["resources"]),
        task_list=tasks,
    )


def run_pep723(script: str):
    """Run a PEP 723 script.

    Parameters
    ----------
    script : str
        Script content.
    """
    metadata = read_pep723(script)
    if metadata is None:
        raise ValueError("No PEP 723 metadata found.")
    dpdispatcher_metadata = metadata["tool"]["dpdispatcher"]
    script_hash = sha1(script.encode("utf-8")).hexdigest()
    submission = create_submission(dpdispatcher_metadata, script_hash)
    submission.machine.context.write_file(f"script_{script_hash}.py", script)
    # write script
    submission.run_submission()

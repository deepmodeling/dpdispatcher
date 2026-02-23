"""Submit a submission from JSON file."""

import json
from typing import List

from dargs import Argument

from dpdispatcher.arginfo import machine_dargs, resources_dargs, task_dargs
from dpdispatcher.machine import Machine
from dpdispatcher.submission import Resources, Submission, Task


def submission_args() -> Argument:
    """Return the argument parser for submission JSON.

    Returns
    -------
    Argument
        submission argument
    """
    machine_args = machine_dargs()
    machine_args.fold_subdoc = True
    machine_args.doc = "Machine configuration. See related documentation for details."

    resources_args = resources_dargs(detail_kwargs=False)
    resources_args.fold_subdoc = True
    resources_args.doc = (
        "Resources configuration. See related documentation for details."
    )

    task_args = task_dargs()
    task_args.name = "task_list"
    task_args.doc = "List of tasks to execute."
    task_args.repeat = True
    task_args.dtype = (list,)

    return Argument(
        "submission",
        dtype=dict,
        doc="Submission configuration",
        sub_fields=[
            Argument(
                "work_base",
                dtype=str,
                optional=False,
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


def load_submission_from_json(json_path: str) -> Submission:
    """Load a Submission from a JSON file.

    Parameters
    ----------
    json_path : str
        Path to the JSON file.

    Returns
    -------
    Submission
        Submission instance.
    """
    with open(json_path) as f:
        submission_dict = json.load(f)

    # Normalize and check with arginfo
    base = submission_args()
    submission_dict = base.normalize_value(submission_dict, trim_pattern="_*")
    base.check_value(submission_dict, strict=False)

    # Create Task list
    task_list = [Task.load_from_dict(task) for task in submission_dict["task_list"]]

    # Create Submission
    return Submission(
        work_base=submission_dict["work_base"],
        forward_common_files=submission_dict["forward_common_files"],
        backward_common_files=submission_dict["backward_common_files"],
        machine=Machine.load_from_dict(submission_dict["machine"]),
        resources=Resources.load_from_dict(submission_dict["resources"]),
        task_list=task_list,
    )


def submit(*, filename: str, dry_run: bool = False, exit_on_submit: bool = False) -> None:
    """Submit a submission from a JSON file.

    Parameters
    ----------
    filename : str
        Path to the JSON file.
    dry_run : bool
        If True, only upload files without submitting.
    exit_on_submit : bool
        If True, exit after submitting without waiting for completion.
    """
    submission = load_submission_from_json(filename)
    submission.run_submission(dry_run=dry_run, exit_on_submit=exit_on_submit)

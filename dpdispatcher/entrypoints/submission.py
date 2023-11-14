from pathlib import Path

from dpdispatcher.dlog import dlog
from dpdispatcher.submission import Submission
from dpdispatcher.utils.job_status import JobStatus
from dpdispatcher.utils.record import record


def handle_submission(
    *,
    submission_hash: str,
    download_terminated_log: bool = False,
    download_finished_task: bool = False,
    clean: bool = False,
):
    """Handle terminated submission.

    Parameters
    ----------
    submission_hash : str
        Submission hash to download.
    download_terminated_log : bool, optional
        Download log files of terminated tasks.
    download_finished_task : bool, optional
        Download finished tasks.
    clean : bool, optional
        Clean submission.

    Raises
    ------
    ValueError
        At least one action should be specified.
    """
    if int(download_terminated_log) + int(download_finished_task) + int(clean) == 0:
        raise ValueError("At least one action should be specified.")

    submission_file = record.get_submission(submission_hash)
    submission = Submission.submission_from_json(str(submission_file))
    submission.belonging_tasks = [
        task for job in submission.belonging_jobs for task in job.job_task_list
    ]
    # TODO: for unclear reason, the submission_hash may be changed
    submission.submission_hash = submission_hash
    submission.machine.context.bind_submission(submission)
    submission.update_submission_state()

    terminated_tasks = []
    finished_tasks = []
    for task in submission.belonging_tasks:
        task.get_task_state(submission.machine.context)
        if task.task_state == JobStatus.terminated:
            terminated_tasks.append(task)
        elif task.task_state == JobStatus.finished:
            finished_tasks.append(task)
    submission.belonging_tasks = []

    if download_terminated_log:
        for task in terminated_tasks:
            task.backward_files = [task.outlog, task.errlog]
        submission.belonging_tasks += terminated_tasks
    if download_finished_task:
        submission.belonging_tasks += finished_tasks

    submission.download_jobs()

    if download_terminated_log:
        terminated_log_files = []
        for task in terminated_tasks:
            assert submission.local_root is not None
            terminated_log_files.append(
                Path(submission.local_root) / task.task_work_path / task.outlog
            )
            terminated_log_files.append(
                Path(submission.local_root) / task.task_work_path / task.errlog
            )

        dlog.info(
            "Terminated logs are downloaded into:\n  "
            + "\n  ".join([str(f) for f in terminated_log_files])
        )

    if clean:
        submission.clean_jobs()

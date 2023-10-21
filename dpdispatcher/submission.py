# %%
import asyncio
import copy
import functools
import json
import os
import pathlib
import random
import time
import uuid
from hashlib import sha1
from typing import Optional

from dargs.dargs import Argument, Variant

from dpdispatcher import dlog
from dpdispatcher.JobStatus import JobStatus
from dpdispatcher.machine import Machine

# from dpdispatcher.slurm import SlurmResources
# %%
default_strategy = dict(if_cuda_multi_devices=False, ratio_unfinished=0.0)


class Submission:
    """A submission represents a collection of tasks.
    These tasks usually locate at a common directory.
    And these Tasks may share common files to be uploaded and downloaded.

    Parameters
    ----------
    work_base : Path
        the base directory of the local tasks. It is usually the dir name of project .
    machine : Machine
        machine class object (for example, PBS, Slurm, Shell) to execute the jobs.
        The machine can still be bound after the instantiation with the bind_submission method.
    resources : Resources
        the machine resources (cpu or gpu) used to generate the slurm/pbs script
    forward_common_files : list
        the common files to be uploaded to other computers before the jobs begin
    backward_common_files : list
        the common files to be downloaded from other computers after the jobs finish
    task_list : list of Task
        a list of tasks to be run.
    """

    def __init__(
        self,
        work_base,
        machine=None,
        resources=None,
        forward_common_files=[],
        backward_common_files=[],
        *,
        task_list=[],
    ):
        # self.submission_list = submission_list
        self.local_root = None
        self.work_base = work_base
        self._abs_work_base = os.path.abspath(work_base)

        self.resources = resources
        self.forward_common_files = (
            sorted(forward_common_files)
            if isinstance(forward_common_files, list)
            else forward_common_files
        )
        self.backward_common_files = (
            sorted(backward_common_files)
            if isinstance(backward_common_files, list)
            else backward_common_files
        )

        self.submission_hash = None
        # warning: can not remote .copy() or there will be bugs
        # self.belonging_tasks = task_list
        self.belonging_tasks = task_list.copy()
        self.belonging_jobs = list()

        self.bind_machine(machine)

    def __repr__(self):
        return json.dumps(self.serialize(), indent=4)

    def __eq__(self, other):
        """When check whether the two submission are equal,
        we disregard the runtime infomation(job_state, job_id, fail_count) of the submission.belonging_jobs.
        """
        return json.dumps(self.serialize(if_static=True)) == json.dumps(
            other.serialize(if_static=True)
        )

    def __getitem__(self, key):
        return self.serialize()[key]

    @classmethod
    def deserialize(cls, submission_dict, machine=None):
        """Convert the submission_dict to a Submission class object.

        Parameters
        ----------
        submission_dict : dict
            path-like, the base directory of the local tasks
        machine : Machine
            Machine class Object to execute the jobs

        Returns
        -------
        submission : Submission
            the Submission class instance converted from the submission_dict
        """
        submission = cls(
            work_base=submission_dict["work_base"],
            resources=Resources.deserialize(
                resources_dict=submission_dict["resources"]
            ),
            forward_common_files=submission_dict["forward_common_files"],
            backward_common_files=submission_dict["backward_common_files"],
        )
        submission.belonging_jobs = [
            Job.deserialize(job_dict=job_dict)
            for job_dict in submission_dict["belonging_jobs"]
        ]
        submission.submission_hash = submission.get_hash()
        if machine is not None:
            submission.bind_machine(machine=machine)
        else:
            machine = Machine.deserialize(machine_dict=submission_dict["machine"])
            submission.bind_machine(machine)
        return submission

    def serialize(self, if_static=False):
        """Convert the Submission class instance to a dictionary.

        Parameters
        ----------
        if_static : bool
            whether dump the job runtime infomation (like job_id, job_state, fail_count) to the dictionary.

        Returns
        -------
        submission_dict : dict
            the dictionary converted from the Submission class instance
        """
        assert self.resources is not None
        submission_dict = {}
        # if if_none_local_root:
        #     submission_dict['local_root'] = None
        # else:
        #     submission_dict['local_root'] = self.local_root

        submission_dict["work_base"] = self.work_base
        submission_dict["_abs_work_base"] = self._abs_work_base
        machine = getattr(self, "machine", None)
        if machine is None:
            submission_dict["machine"] = {}
        else:
            submission_dict["machine"] = machine.serialize()
        submission_dict["resources"] = self.resources.serialize()
        submission_dict["forward_common_files"] = self.forward_common_files
        submission_dict["backward_common_files"] = self.backward_common_files
        submission_dict["belonging_jobs"] = [
            job.serialize(if_static=if_static) for job in self.belonging_jobs
        ]
        return submission_dict

    def register_task(self, task):
        if self.belonging_jobs:
            raise RuntimeError(
                "Not allowed to register tasks after generating jobs. "
                f"submission hash error {self}"
            )
        self.belonging_tasks.append(task)

    def register_task_list(self, task_list):
        if self.belonging_jobs:
            raise RuntimeError(
                "Not allowed to register tasks after generating jobs. "
                f"submission hash error {self}"
            )
        self.belonging_tasks.extend(task_list)

    def get_hash(self):
        return sha1(
            json.dumps(self.serialize(if_static=True)).encode("utf-8")
        ).hexdigest()

    def bind_machine(self, machine):
        """Bind this submission to a machine. update the machine's context remote_root and local_root.

        Parameters
        ----------
        machine : Machine
            the machine to bind with
        """
        self.submission_hash = self.get_hash()
        self.machine = machine
        for job in self.belonging_jobs:
            job.machine = machine
        if machine is not None:
            self.machine.context.bind_submission(self)
            self.local_root = machine.context.temp_local_root
        return self

    def run_submission(
        self, *, dry_run=False, exit_on_submit=False, clean=True, check_interval=30
    ):
        """Main method to execute the submission.
        First, check whether old Submission exists on the remote machine, and try to recover from it.
        Second, upload the local files to the remote machine where the tasks to be executed.
        Third, run the submission defined previously.
        Forth, wait until the tasks in the submission finished and download the result file to local directory.
        If dry_run is True, submission will be uploaded but not be executed and exit.
        If exit_on_submit is True, submission will exit.
        """
        assert self.resources is not None
        if not self.belonging_jobs:
            self.generate_jobs()
        self.try_recover_from_json()
        self.update_submission_state()
        if self.check_all_finished():
            dlog.info("info:check_all_finished: True")
        else:
            dlog.info("info:check_all_finished: False")
            self.upload_jobs()
            if dry_run is True:
                dlog.info(f"submission succeeded: {self.submission_hash}")
                dlog.info(f"at {self.machine.context.remote_root}")
                return self.serialize()
            self.handle_unexpected_submission_state()
            self.submission_to_json()
            time.sleep(1)
            self.update_submission_state()
            self.check_all_finished()
            self.handle_unexpected_submission_state()

        ratio_unfinished = self.resources.strategy["ratio_unfinished"]
        while not self.check_all_finished():
            if exit_on_submit is True:
                dlog.info(f"submission succeeded: {self.submission_hash}")
                dlog.info(f"at {self.machine.context.remote_root}")
                return self.serialize()
            if ratio_unfinished > 0.0 and self.check_ratio_unfinished(ratio_unfinished):
                self.remove_unfinished_tasks()
                break

            try:
                time.sleep(check_interval)
            except (Exception, KeyboardInterrupt, SystemExit) as e:
                self.submission_to_json()
                dlog.exception(e)
                dlog.info(f"submission exit: {self.submission_hash}")
                dlog.info(f"at {self.machine.context.remote_root}")
                dlog.debug(self.serialize())
                raise e
            else:
                self.update_submission_state()
                self.handle_unexpected_submission_state()
            finally:
                pass
        self.handle_unexpected_submission_state()
        self.try_download_result()
        self.submission_to_json()
        if clean:
            self.clean_jobs()
        return self.serialize()

    def try_download_result(self):
        start_time = time.time()
        retry_interval = 60  # retry every 1 minute
        success = False
        while not success:
            try:
                self.download_jobs()
                success = True
            except (EOFError, Exception) as e:
                dlog.exception(e)
                elapsed_time = time.time() - start_time
                if elapsed_time < 3600:  # in 1 h
                    dlog.info("Retrying in 1 minute...")
                    time.sleep(retry_interval)
                elif elapsed_time < 86400:  # 1 h ~ 24 h
                    retry_interval = 600  # retry every 10 min
                    dlog.info("Retrying in 10 minutes...")
                    time.sleep(retry_interval)
                else:  # > 24 h
                    dlog.info("Maximum retries time reached. Exiting.")
                    break

    async def async_run_submission(self, **kwargs):
        """Async interface of run_submission.

        Examples
        --------
        >>> import asyncio
        >>> from dpdispacher import Machine, Resource, Submission
        >>> async def run_jobs():
        ...     backgroud_task = set()
        ...     # task1
        ...     task1 = Task(...)
        ...     submission1 = Submission(..., task_list=[task1])
        ...     background_task = asyncio.create_task(
        ...         submission1.async_run_submission(check_interval=2, clean=False)
        ...     )
        ...     # task2
        ...     task2 = Task(...)
        ...     submission2 = Submission(..., task_list=[task1])
        ...     background_task = asyncio.create_task(
        ...         submission2.async_run_submission(check_interval=2, clean=False)
        ...     )
        ...     background_tasks.add(background_task)
        ...     result = await asyncio.gather(*background_tasks)
        ...     return result
        >>> run_jobs()

        May raise Error if pass `clean=True` explicitly when submit to pbs or slurm.
        """
        kwargs = {**{"clean": False}, **kwargs}
        if kwargs["clean"]:
            dlog.warning(
                "Using async submission with `clean=True`, "
                "job may fail in queue system"
            )
        loop = asyncio.get_event_loop()
        wrapped_submission = functools.partial(self.run_submission, **kwargs)
        return await loop.run_in_executor(None, wrapped_submission)

    def update_submission_state(self):
        """Check whether all the jobs in the submission.

        Notes
        -----
        this method will not handle unexpected (like resubmit terminated) job state in the submission.
        """
        for job in self.belonging_jobs:
            if job.job_state == JobStatus.finished:
                # finished job will be finished for ever, skip
                continue
            job.get_job_state()
            dlog.debug(
                f"debug:update_submission_state: job: {job.job_hash}, {job.job_id}, {job.job_state}"
            )
        # self.submission_to_json()

    def handle_unexpected_submission_state(self):
        """Handle unexpected job state of the submission.
        If the job state is unsubmitted, submit the job.
        If the job state is terminated (killed unexpectly), resubmit the job.
        If the job state is unknown, raise an error.
        """
        try:
            for job in self.belonging_jobs:
                job.handle_unexpected_job_state()
        except Exception as e:
            self.submission_to_json()
            raise RuntimeError(
                f"Meet errors will handle unexpected submission state.\n"
                f"Debug information: remote_root=={self.machine.context.remote_root}.\n"
                f"Debug information: submission_hash=={self.submission_hash}.\n"
                f"Please check the dirs and scripts in remote_root. "
                f"The job information mentioned above may help."
            ) from e

    # not used here, submitting job is in handle_unexpected_submission_state.

    # def submit_submission(self):
    #     """submit the job belonging to the submission.
    #     """
    #     for job in self.belonging_jobs:
    #         job.submit_job()
    #     self.get_submission_state()

    # def update_submi

    def check_ratio_unfinished(self, ratio_unfinished: float) -> bool:
        """Calculate the ratio of unfinished tasks in the submission.

        Parameters
        ----------
        ratio_unfinished : float
            the ratio of unfinished tasks in the submission

        Returns
        -------
        bool
            whether the ratio of unfinished tasks in the submission is larger than ratio_unfinished
        """
        assert self.resources is not None
        if self.resources.group_size == 1:
            # if group size is 1, calculate job state is enough and faster
            status_list = [job.job_state for job in self.belonging_jobs]
        else:
            # get task state is more accurate
            status_list = []
            for task in self.belonging_tasks:
                task.get_task_state(self.machine.context)
                status_list.append(task.task_state)
        finished_num = status_list.count(JobStatus.finished)
        return finished_num / len(self.belonging_tasks) >= (1 - ratio_unfinished)

    def remove_unfinished_tasks(self):
        dlog.info("Remove unfinished tasks")
        # kill all jobs and mark them as finished
        for job in self.belonging_jobs:
            if job.job_state != JobStatus.finished:
                self.machine.kill(job)
                job.job_state = JobStatus.finished
        # remove all unfinished tasks
        finished_tasks = []
        for task in self.belonging_tasks:
            if task.task_state == JobStatus.finished:
                finished_tasks.append(task)
            # there is no need to remove actual remote directory
            # as it should be cleaned anyway
        self.belonging_tasks = finished_tasks
        # clean removed tasks in jobs - although this should not be necessary
        for job in self.belonging_jobs:
            job.job_task_list = [
                task
                for task in job.job_task_list
                if task.task_state == JobStatus.finished
            ]

    def check_all_finished(self):
        """Check whether all the jobs in the submission.

        Notes
        -----
        This method will not handle unexpected job state in the submission.
        """
        # self.update_submission_state()
        if any(
            (job.job_state in [JobStatus.terminated, JobStatus.unknown])
            for job in self.belonging_jobs
        ):
            self.submission_to_json()
        if any(
            (
                job.job_state
                in [
                    JobStatus.running,
                    JobStatus.waiting,
                    JobStatus.unsubmitted,
                    JobStatus.completing,
                    JobStatus.terminated,
                    JobStatus.unknown,
                ]
            )
            for job in self.belonging_jobs
        ):
            return False
        else:
            return True

    def generate_jobs(self):
        """After tasks register to the self.belonging_tasks,
        This method generate the jobs and add these jobs to self.belonging_jobs.
        The jobs are generated by the tasks randomly, and there are self.resources.group_size tasks in a task.
        Why we randomly shuffle the tasks is under the consideration of load balance.
        The random seed is a constant (to be concrete, 42). And this insures that the jobs are equal when we re-run the program.
        """
        assert self.resources is not None
        if self.belonging_jobs:
            raise RuntimeError(
                f"Can not generate jobs when submission.belonging_jobs is not empty. debug:{self}"
            )
        group_size = self.resources.group_size
        if (group_size < 0) or (not isinstance(group_size, int)):
            raise RuntimeError("group_size must be a positive number")
        task_num = len(self.belonging_tasks)
        if task_num == 0:
            raise RuntimeError("submission must have at least 1 task")
        if group_size == 0:
            # 0 means infinity
            group_size = task_num
        random.seed(42)
        random_task_index = list(range(task_num))
        random.shuffle(random_task_index)
        random_task_index_ll = [
            random_task_index[ii : ii + group_size]
            for ii in range(0, task_num, group_size)
        ]

        for ii in random_task_index_ll:
            job_task_list = [self.belonging_tasks[jj] for jj in ii]
            job = Job(
                job_task_list=job_task_list,
                machine=self.machine,
                resources=copy.deepcopy(self.resources),
            )
            self.belonging_jobs.append(job)

        if self.machine is not None:
            self.bind_machine(self.machine)

        self.submission_hash = self.get_hash()

    def upload_jobs(self):
        self.machine.context.upload(self)

    def download_jobs(self):
        self.machine.context.download(self)
        # for job in self.belonging_jobs:
        #     job.tag_finished()
        # self.machine.context.write_file(self.machine.finish_tag_name, write_str="")

    def clean_jobs(self):
        self.machine.context.clean()

    def submission_to_json(self):
        # self.update_submission_state()
        write_str = json.dumps(self.serialize(), indent=4, default=str)
        submission_file_name = f"{self.submission_hash}.json"
        self.machine.context.write_file(submission_file_name, write_str=write_str)

    @classmethod
    def submission_from_json(cls, json_file_name="submission.json"):
        with open(json_file_name) as f:
            submission_dict = json.load(f)
        # submission_dict = machine.context.read_file(json_file_name)
        submission = cls.deserialize(submission_dict=submission_dict, machine=None)
        return submission

    # def check_if_recover()

    def try_recover_from_json(self):
        submission_file_name = f"{self.submission_hash}.json"
        if_recover = self.machine.context.check_file_exists(submission_file_name)
        submission = None
        submission_dict = {}
        if if_recover:
            submission_dict_str = self.machine.context.read_file(
                fname=submission_file_name
            )
            submission_dict = json.loads(submission_dict_str)
            submission = Submission.deserialize(submission_dict=submission_dict)
            submission.bind_machine(machine=self.machine)
            if self == submission:
                self.belonging_jobs = submission.belonging_jobs
                self.belonging_tasks = [
                    task for job in self.belonging_jobs for task in job.job_task_list
                ]
                self.bind_machine(machine=self.machine)
                dlog.info(
                    f"Find old submission; recover submission from json file;"
                    f"submission.submission_hash:{submission.submission_hash}; "
                    f"machine.context.remote_root:{self.machine.context.remote_root}; "
                    f"submission.work_base:{submission.work_base};"
                )
                # self = submission.bind_machine(machine=self.machine)
            else:
                print(self.serialize())
                print(submission.serialize())
                raise RuntimeError("Recover failed.")


class Task:
    """A task is a sequential command to be executed,
    as well as the files it depends on to transmit forward and backward.

    Parameters
    ----------
    command : Str
        the command to be executed.
    task_work_path : Path
        the directory of each file where the files are dependent on.
    forward_files : list of Path
        the files to be transmitted to remote machine before the command execute.
    backward_files : list of Path
        the files to be transmitted from remote machine after the comand finished.
    outlog : Str
        the filename to which command redirect stdout
    errlog : Str
        the filename to which command redirect stderr
    """

    def __init__(
        self,
        command,
        task_work_path,
        forward_files=[],
        backward_files=[],
        outlog="log",
        errlog="err",
    ):
        self.command = command
        self.task_work_path = task_work_path
        self.forward_files = forward_files
        self.backward_files = backward_files
        self.outlog = outlog
        self.errlog = errlog

        # self.task_need_resources = task_need_resources

        self.task_hash = self.get_hash()
        # self.task_need_resources="<to be completed in the future>"
        # self.uuid =
        self.task_state = JobStatus.unsubmitted

    def __repr__(self):
        return str(self.serialize())

    def __eq__(self, other):
        return json.dumps(self.serialize()) == json.dumps(other.serialize())

    def __getitem__(self, key):
        return self.serialize()[key]

    def get_hash(self):
        return sha1(json.dumps(self.serialize()).encode("utf-8")).hexdigest()

    @classmethod
    def load_from_json(cls, json_file):
        with open(json_file) as f:
            task_dict = json.load(f)
        return cls.load_from_dict(task_dict)

    @classmethod
    def load_from_dict(cls, task_dict: dict) -> "Task":
        # check dict
        base = cls.arginfo()
        task_dict = base.normalize_value(task_dict, trim_pattern="_*")
        base.check_value(task_dict, strict=False)

        task = cls.deserialize(task_dict=task_dict)
        return task

    @classmethod
    def deserialize(cls, task_dict):
        """Convert the task_dict to a Task class object.

        Parameters
        ----------
        task_dict : dict
            the dictionary which contains the task information

        Returns
        -------
        task : Task
            the Task class instance converted from the task_dict
        """
        task = cls(**task_dict)
        return task

    def serialize(self):
        task_dict = {}
        task_dict["command"] = self.command
        task_dict["task_work_path"] = self.task_work_path
        task_dict["forward_files"] = self.forward_files
        task_dict["backward_files"] = self.backward_files
        task_dict["outlog"] = self.outlog
        task_dict["errlog"] = self.errlog
        # task_dict['task_need_resources'] = self.task_need_resources
        return task_dict

    @staticmethod
    def arginfo():
        doc_command = (
            "A command to be executed of this task. The expected return code is 0."
        )
        doc_task_work_path = "The dir where the command to be executed."
        doc_forward_files = (
            "The files to be uploaded in task_work_path before the task exectued."
        )
        doc_backward_files = "The files to be download to local_root in task_work_path after the task finished"
        doc_outlog = "The out log file name. redirect from stdout"
        doc_errlog = "The err log file name. redirect from stderr"

        task_args = [
            Argument("command", str, optional=False, doc=doc_command),
            Argument("task_work_path", str, optional=False, doc=doc_task_work_path),
            Argument(
                "forward_files", list, optional=False, doc=doc_forward_files, default=[]
            ),
            Argument(
                "backward_files",
                list,
                optional=False,
                doc=doc_backward_files,
                default=[],
            ),
            Argument(
                "outlog",
                [type(None), str],
                optional=False,
                doc=doc_outlog,
                default="log",
            ),
            Argument(
                "errlog",
                [type(None), str],
                optional=False,
                doc=doc_errlog,
                default="err",
            ),
        ]
        task_format = Argument("task", dict, task_args)
        return task_format

    def get_task_state(self, context):
        """Get the task state by checking the tag file.

        Parameters
        ----------
        context : Context
            the context of the task
        """
        if self.task_state in (JobStatus.finished, JobStatus.unsubmitted):
            # finished task should always be finished
            # unsubmitted task do not need to check tag
            return
        # check tag
        task_tag_finished = (
            pathlib.PurePath(self.task_work_path)
            / (self.task_hash + "_task_tag_finished")
        ).as_posix()
        result = context.check_file_exists(task_tag_finished)
        if result:
            self.task_state = JobStatus.finished


class Job:
    """Job is generated by Submission automatically.
    A job ususally has many tasks and it may request computing resources from job scheduler systems.
    Each Job can generate a script file to be submitted to the job scheduler system or executed locally.

    Parameters
    ----------
    job_task_list : list of Task
        the tasks belonging to the job
    resources : Resources
        the machine resources. Passed from Submission when it constructs jobs.
    machine : machine
        machine object to execute the job. Passed from Submission when it constructs jobs.
    """

    def __init__(
        self,
        job_task_list,
        *,
        resources,
        machine=None,
    ):
        self.job_task_list = job_task_list
        # self.job_work_base = job_work_base
        self.resources = resources
        self.machine = machine
        self.job_state = None  # JobStatus.unsubmitted
        self.job_id = ""
        self.fail_count = 0
        self.job_uuid = uuid.uuid4()

        # self.job_hash = self.get_hash()
        self.job_hash = self.get_hash()
        self.script_file_name = self.job_hash + ".sub"

    def __repr__(self):
        return str(self.serialize())

    def __eq__(self, other):
        """When check whether the two jobs are equal,
        we disregard the runtime infomation(job_state, job_id, fail_count) of the jobs.
        """
        return json.dumps(self.serialize(if_static=True)) == json.dumps(
            other.serialize(if_static=True)
        )

    @classmethod
    def deserialize(cls, job_dict, machine=None):
        """Convert the  job_dict to a Submission class object.

        Parameters
        ----------
        job_dict : dict
            the dictionary which contains the job information
        machine : Machine
            the machine object to execute the job

        Returns
        -------
        submission : Job
            the Job class instance converted from the job_dict
        """
        if len(job_dict.keys()) != 1:
            raise RuntimeError(
                f"json file may be broken, len(job_dict.keys()) must be 1. {job_dict}"
            )
        job_hash = list(job_dict.keys())[0]

        job_task_list = [
            Task.deserialize(task_dict)
            for task_dict in job_dict[job_hash]["job_task_list"]
        ]
        job = Job(
            job_task_list=job_task_list,
            resources=Resources.deserialize(
                resources_dict=job_dict[job_hash]["resources"]
            ),
            machine=machine,
        )

        # job.job_runtime_info=job_dict[job_hash]['job_runtime_info']
        job.job_state = job_dict[job_hash]["job_state"]
        job.job_id = job_dict[job_hash]["job_id"]
        job.fail_count = job_dict[job_hash]["fail_count"]
        # job.job_uuid = job_dict[job_hash]['job_uuid']
        for task in job.job_task_list:
            task.task_state = job.job_state
        return job

    def get_job_state(self):
        """Get the jobs. Usually, this method will query the database of slurm or pbs job scheduler system and get the results.

        Notes
        -----
        this method will not submit or resubmit the jobs if the job is unsubmitted.
        """
        dlog.debug(
            f"debug:query database; self.job_hash:{self.job_hash}; self.job_id:{self.job_id}"
        )
        assert self.machine is not None
        job_state = self.machine.check_status(self)
        self.job_state = job_state
        # update general task_state, which should be faster than checking tags
        for task in self.job_task_list:
            # only update if the task is not finished
            if task.task_state != JobStatus.finished:
                task.task_state = job_state

    def handle_unexpected_job_state(self):
        job_state = self.job_state

        if job_state == JobStatus.unknown:
            raise RuntimeError(f"job_state for job {self} is unknown")

        if job_state == JobStatus.terminated:
            self.fail_count += 1
            dlog.info(
                f"job: {self.job_hash} {self.job_id} terminated;"
                f"fail_cout is {self.fail_count}; resubmitting job"
            )
            retry_count = 3
            assert self.machine is not None
            if hasattr(self.machine, "retry_count") and self.machine.retry_count > 0:
                retry_count = self.machine.retry_count + 1
            if (self.fail_count) > 0 and (self.fail_count % retry_count == 0):
                last_error_message = self.get_last_error_message()
                err_msg = f"job:{self.job_hash} {self.job_id} failed {self.fail_count} times. job_detail:{self}"
                if last_error_message is not None:
                    err_msg += f"\nPossible remote error message: {last_error_message}"
                raise RuntimeError(err_msg)
            self.submit_job()
            if self.job_state != JobStatus.unsubmitted:
                dlog.info(
                    "job:{job_hash} re-submit after terminated; new job_id is {job_id}".format(
                        job_hash=self.job_hash, job_id=self.job_id
                    )
                )
                time.sleep(0.2)
                self.get_job_state()
                dlog.info(
                    f"job:{self.job_hash} job_id:{self.job_id} after re-submitting; the state now is {repr(self.job_state)}"
                )
                self.handle_unexpected_job_state()
            if self.resources.wait_time != 0:
                time.sleep(self.resources.wait_time)

        if job_state == JobStatus.unsubmitted:
            dlog.debug(f"job: {self.job_hash} unsubmitted; submit it")
            # if self.fail_count > 3:
            #     raise RuntimeError("job:job {job} failed 3 times".format(job=self))
            self.submit_job()
            if self.job_state != JobStatus.unsubmitted:
                dlog.info(f"job: {self.job_hash} submit; job_id is {self.job_id}")
            if self.resources.wait_time != 0:
                time.sleep(self.resources.wait_time)
            # self.get_job_state()

    def get_hash(self):
        return str(list(self.serialize(if_static=True).keys())[0])

    def serialize(self, if_static=False):
        """Convert the Task class instance to a dictionary.

        Parameters
        ----------
        if_static : bool
            whether dump the job runtime infomation (job_id, job_state, fail_count, job_uuid etc.) to the dictionary.

        Returns
        -------
        task_dict : dict
            the dictionary converted from the Task class instance
        """
        job_content_dict = {}
        # for task in self.job_task_list:
        job_content_dict["job_task_list"] = [
            task.serialize() for task in self.job_task_list
        ]
        job_content_dict["resources"] = self.resources.serialize()
        # job_content_dict['job_work_base'] = self.job_work_base
        job_hash = sha1(json.dumps(job_content_dict).encode("utf-8")).hexdigest()
        if not if_static:
            job_content_dict["job_state"] = self.job_state
            job_content_dict["job_id"] = self.job_id
            job_content_dict["fail_count"] = self.fail_count
            # job_content_dict['job_uuid'] = self.job_uuid
        return {job_hash: job_content_dict}

    def register_job_id(self, job_id):
        self.job_id = job_id

    def submit_job(self):
        assert self.machine is not None
        job_id = self.machine.do_submit(self)
        self.register_job_id(job_id)
        if job_id:
            self.job_state = JobStatus.waiting
        else:
            self.job_state = JobStatus.unsubmitted

    def job_to_json(self):
        write_str = json.dumps(self.serialize(), indent=2, default=str)
        assert self.machine is not None
        self.machine.context.write_file(
            self.job_hash + "_job.json", write_str=write_str
        )

    def get_last_error_message(self) -> Optional[str]:
        """Get last error message when the job is terminated."""
        assert self.machine is not None
        last_err_file = self.job_hash + "_last_err_file"
        if self.machine.context.check_file_exists(last_err_file):
            last_error_message = self.machine.context.read_file(last_err_file)
            # red color
            last_error_message = "\033[31m" + last_error_message + "\033[0m"
            return last_error_message


class Resources:
    """Resources is used to describe the machine resources we need to do calculations.

    Parameters
    ----------
    number_node : int
        The number of node need for each `job`.
    cpu_per_node : int
        cpu numbers of each node.
    gpu_per_node : int
        gpu numbers of each node.
    queue_name : str
        The queue name of batch job scheduler system.
    group_size : int
        The number of `tasks` in a `job`.
    custom_flags : list of Str
        The extra lines pass to job submitting script header
    strategy : dict
        strategies we use to generation job submitting scripts.
        if_cuda_multi_devices : bool
            If there are multiple nvidia GPUS on the node, and we want to assign the tasks to different GPUS.
            If true, dpdispatcher will manually export environment variable CUDA_VISIBLE_DEVICES to different task.
            Usually, this option will be used with Task.task_need_resources variable simultaneously.
        ratio_unfinished : float
            The ratio of `task` that can be unfinished.
        customized_script_header_template_file : str
            The customized template file to generate job submitting script header,
            which overrides the default file.
    para_deg : int
        Decide how many tasks will be run in parallel.
        Usually run with `strategy['if_cuda_multi_devices']`
    source_list : list of Path
        The env file to be sourced before the command execution.
    wait_time : int
        The waitting time in second after a single task submitted. Default: 0.
    """

    def __init__(
        self,
        number_node,
        cpu_per_node,
        gpu_per_node,
        queue_name,
        group_size,
        *,
        custom_flags=[],
        strategy=default_strategy,
        para_deg=1,
        module_unload_list=[],
        module_purge=False,
        module_list=[],
        source_list=[],
        envs={},
        prepend_script=[],
        append_script=[],
        wait_time=0,
        **kwargs,
    ):
        self.number_node = number_node
        self.cpu_per_node = cpu_per_node
        self.gpu_per_node = gpu_per_node
        self.queue_name = queue_name
        self.group_size = group_size

        # self.extra_specification = extra_specification
        self.custom_flags = custom_flags
        self.strategy = strategy
        self.para_deg = para_deg
        self.module_purge = module_purge
        self.module_unload_list = module_unload_list
        self.module_list = module_list
        self.source_list = source_list
        self.envs = envs
        self.prepend_script = prepend_script
        self.append_script = append_script
        self.wait_time = wait_time
        # self.if_cuda_multi_devices = if_cuda_multi_devices

        self.kwargs = kwargs.get("kwargs", kwargs)

        self.gpu_in_use = 0
        self.task_in_para = 0
        # self. = 0
        # if self.gpu_per_node > 1:
        # self.in_para_task_num = 0

        for kk, value in default_strategy.items():
            self.strategy.setdefault(kk, value)
        if self.strategy["if_cuda_multi_devices"] is True:
            if gpu_per_node < 1:
                raise RuntimeError(
                    "gpu_per_node can not be smaller than 1 when if_cuda_multi_devices is True"
                )
            if number_node != 1:
                raise RuntimeError(
                    "number_node must be 1 when if_cuda_multi_devices is True"
                )
        if self.strategy["ratio_unfinished"] >= 1.0:
            raise RuntimeError("ratio_unfinished must be smaller than 1.0")

    def __eq__(self, other):
        return json.dumps(self.serialize()) == json.dumps(other.serialize())

    def serialize(self):
        resources_dict = {}
        resources_dict["number_node"] = self.number_node
        resources_dict["cpu_per_node"] = self.cpu_per_node
        resources_dict["gpu_per_node"] = self.gpu_per_node
        resources_dict["queue_name"] = self.queue_name
        resources_dict["group_size"] = self.group_size

        resources_dict["custom_flags"] = self.custom_flags
        resources_dict["strategy"] = self.strategy
        resources_dict["para_deg"] = self.para_deg
        resources_dict["module_purge"] = self.module_purge
        resources_dict["module_unload_list"] = self.module_unload_list
        resources_dict["module_list"] = self.module_list
        resources_dict["source_list"] = self.source_list
        resources_dict["envs"] = self.envs
        resources_dict["prepend_script"] = self.prepend_script
        resources_dict["append_script"] = self.append_script
        resources_dict["wait_time"] = self.wait_time
        resources_dict["kwargs"] = self.kwargs
        return resources_dict

    @classmethod
    def deserialize(cls, resources_dict):
        resources = cls(
            number_node=resources_dict.get("number_node", 1),
            cpu_per_node=resources_dict.get("cpu_per_node", 1),
            gpu_per_node=resources_dict.get("gpu_per_node", 0),
            queue_name=resources_dict.get("queue_name", ""),
            group_size=resources_dict["group_size"],
            custom_flags=resources_dict.get("custom_flags", []),
            strategy=resources_dict.get("strategy", default_strategy),
            para_deg=resources_dict.get("para_deg", 1),
            module_purge=resources_dict.get("module_purge", False),
            module_unload_list=resources_dict.get("module_unload_list", []),
            module_list=resources_dict.get("module_list", []),
            source_list=resources_dict.get("source_list", []),
            envs=resources_dict.get("envs", {}),
            prepend_script=resources_dict.get("prepend_script", []),
            append_script=resources_dict.get("append_script", []),
            wait_time=resources_dict.get("wait_time", 0),
            **resources_dict.get("kwargs", {}),
        )
        return resources

    def __getitem__(self, key):
        return self.serialize()[key]

    @classmethod
    def load_from_json(cls, json_file):
        with open(json_file) as f:
            resources_dict = json.load(f)
        resources = cls.deserialize(resources_dict=resources_dict)
        return resources

    @classmethod
    def load_from_dict(cls, resources_dict):
        # check dict
        base = cls.arginfo(detail_kwargs="batch_type" in resources_dict)
        resources_dict = base.normalize_value(resources_dict, trim_pattern="_*")
        base.check_value(resources_dict, strict=False)

        return cls.deserialize(resources_dict=resources_dict)

    @staticmethod
    def arginfo(detail_kwargs=True):
        doc_number_node = "The number of node need for each `job`"
        doc_cpu_per_node = "cpu numbers of each node assigned to each job."
        doc_gpu_per_node = "gpu numbers of each node assigned to each job."
        doc_queue_name = "The queue name of batch job scheduler system."
        doc_group_size = "The number of `tasks` in a `job`. 0 means infinity."
        doc_custom_flags = "The extra lines pass to job submitting script header"
        doc_para_deg = "Decide how many tasks will be run in parallel."
        doc_source_list = "The env file to be sourced before the command execution."
        doc_module_purge = (
            "Remove all modules on HPC system before module load (module_list)"
        )
        doc_module_unload_list = (
            "The modules to be unloaded on HPC system before submitting jobs"
        )
        doc_module_list = (
            "The modules to be loaded on HPC system before submitting jobs"
        )
        doc_envs = "The environment variables to be exported on before submitting jobs"
        doc_prepend_script = "Optional script run before jobs submitted."
        doc_append_script = "Optional script run after jobs submitted."
        doc_wait_time = "The waitting time in second after a single `task` submitted"
        doc_if_cuda_multi_devices = (
            "If there are multiple nvidia GPUS on the node, and we want to assign the tasks to different GPUS."
            "If true, dpdispatcher will manually export environment variable CUDA_VISIBLE_DEVICES to different task."
            "Usually, this option will be used with Task.task_need_resources variable simultaneously."
        )
        doc_ratio_unfinished = "The ratio of `tasks` that can be unfinished."
        doc_customized_script_header_template_file = (
            "The customized template file to generate job submitting script header, "
            "which overrides the default file."
        )

        strategy_args = [
            Argument(
                "if_cuda_multi_devices",
                bool,
                optional=True,
                default=False,
                doc=doc_if_cuda_multi_devices,
            ),
            Argument(
                "ratio_unfinished",
                float,
                optional=True,
                default=0.0,
                doc=doc_ratio_unfinished,
            ),
            Argument(
                "customized_script_header_template_file",
                str,
                optional=True,
                doc=doc_customized_script_header_template_file,
            ),
        ]
        doc_strategy = "strategies we use to generation job submitting scripts."
        strategy_format = Argument(
            "strategy", dict, strategy_args, optional=True, doc=doc_strategy
        )

        resources_args = [
            Argument("number_node", int, optional=True, doc=doc_number_node, default=1),
            Argument(
                "cpu_per_node", int, optional=True, doc=doc_cpu_per_node, default=1
            ),
            Argument(
                "gpu_per_node", int, optional=True, doc=doc_gpu_per_node, default=0
            ),
            Argument("queue_name", str, optional=True, doc=doc_queue_name, default=""),
            Argument("group_size", int, optional=False, doc=doc_group_size),
            Argument("custom_flags", list, optional=True, doc=doc_custom_flags),
            # Argument("strategy", dict, optional=True, doc=doc_strategy,default=default_strategy),
            strategy_format,
            Argument("para_deg", int, optional=True, doc=doc_para_deg, default=1),
            Argument(
                "source_list", list, optional=True, doc=doc_source_list, default=[]
            ),
            Argument(
                "module_purge", bool, optional=True, doc=doc_module_purge, default=False
            ),
            Argument(
                "module_unload_list",
                list,
                optional=True,
                doc=doc_module_unload_list,
                default=[],
            ),
            Argument(
                "module_list", list, optional=True, doc=doc_module_list, default=[]
            ),
            Argument("envs", dict, optional=True, doc=doc_envs, default={}),
            Argument(
                "prepend_script",
                list,
                optional=True,
                doc=doc_prepend_script,
                default=[],
            ),
            Argument(
                "append_script", list, optional=True, doc=doc_append_script, default=[]
            ),
            Argument(
                "wait_time", [int, float], optional=True, doc=doc_wait_time, default=0
            ),
        ]

        if detail_kwargs:
            batch_variant = Variant(
                "batch_type",
                [
                    machine.resources_arginfo()
                    for machine in set(Machine.subclasses_dict.values())
                ],
                optional=False,
                doc="The batch job system type loaded from machine/batch_type.",
            )

            resources_format = Argument(
                "resources", dict, resources_args, [batch_variant]
            )
        else:
            resources_args.append(
                Argument(
                    "kwargs", dict, optional=True, doc="Vary by different machines."
                )
            )
            resources_args.append(
                Argument(
                    "batch_type",
                    str,
                    optional=True,
                    doc="Allow this key when strict checking.",
                )
            )
            resources_format = Argument("resources", dict, resources_args)
        return resources_format


# %%

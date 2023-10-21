import math
import pathlib
import shlex
from typing import List

from dargs import Argument

from dpdispatcher import dlog
from dpdispatcher.JobStatus import JobStatus
from dpdispatcher.machine import Machine, script_command_template
from dpdispatcher.utils import RetrySignal, customized_script_header_template, retry

# from dpdispatcher.submission import Resources

slurm_script_header_template = """\
#!/bin/bash -l
#SBATCH --parsable
{slurm_nodes_line}
{slurm_ntasks_per_node_line}
{slurm_number_gpu_line}
{slurm_partition_line}"""


class Slurm(Machine):
    def gen_script(self, job):
        slurm_script = super().gen_script(job)
        return slurm_script

    def gen_script_header(self, job):
        resources = job.resources
        script_header_dict = {}
        script_header_dict["slurm_nodes_line"] = "#SBATCH --nodes {number_node}".format(
            number_node=resources.number_node
        )
        script_header_dict[
            "slurm_ntasks_per_node_line"
        ] = f"#SBATCH --ntasks-per-node {resources.cpu_per_node}"
        custom_gpu_line = resources.kwargs.get("custom_gpu_line", None)
        if not custom_gpu_line:
            script_header_dict[
                "slurm_number_gpu_line"
            ] = f"#SBATCH --gres=gpu:{resources.gpu_per_node}"
        else:
            script_header_dict["slurm_number_gpu_line"] = custom_gpu_line
        if resources.queue_name != "":
            script_header_dict[
                "slurm_partition_line"
            ] = f"#SBATCH --partition {resources.queue_name}"
        else:
            script_header_dict["slurm_partition_line"] = ""
        if (
            resources["strategy"].get("customized_script_header_template_file")
            is not None
        ):
            slurm_script_header = customized_script_header_template(
                resources["strategy"]["customized_script_header_template_file"],
                resources,
            )
        else:
            slurm_script_header = slurm_script_header_template.format(
                **script_header_dict
            )
        return slurm_script_header

    @retry()
    def do_submit(self, job):
        script_file_name = job.script_file_name
        script_str = self.gen_script(job)
        job_id_name = job.job_hash + "_job_id"
        # script_str = self.sub_script(job_dirs, cmd, args=args, resources=resources, outlog=outlog, errlog=errlog)
        self.context.write_file(fname=script_file_name, write_str=script_str)
        script_run_str = self.gen_script_command(job)
        script_run_file_name = f"{job.script_file_name}.run"
        self.context.write_file(fname=script_run_file_name, write_str=script_run_str)
        # self.context.write_file(fname=os.path.join(self.context.submission.work_base, script_file_name), write_str=script_str)
        ret, stdin, stdout, stderr = self.context.block_call(
            "cd {} && {} {}".format(
                shlex.quote(self.context.remote_root),
                "sbatch",
                shlex.quote(script_file_name),
            )
        )
        if ret != 0:
            err_str = stderr.read().decode("utf-8")
            if (
                "Socket timed out on send/recv operation" in err_str
                or "Unable to contact slurm controller" in err_str
            ):
                # server network error, retry 3 times
                raise RetrySignal(
                    "Get error code %d in submitting through ssh with job: %s . message: %s"
                    % (ret, job.job_hash, err_str)
                )
            elif (
                "Job violates accounting/QOS policy" in err_str
                # the number of jobs exceeds DEFAULT_MAX_JOB_COUNT (by default 10000)
                or "Slurm temporarily unable to accept job, sleeping and retrying"
                in err_str
            ):
                # job number exceeds, skip the submitting
                return ""
            raise RuntimeError(
                "status command squeue fails to execute\nerror message:%s\nreturn code %d\n"
                % (err_str, ret)
            )
        subret = stdout.readlines()
        # --parsable
        # Outputs only the job id number and the cluster name if present.
        # The values are separated by a semicolon. Errors will still be displayed.
        job_id = subret[0].split(";")[0].strip()
        self.context.write_file(job_id_name, job_id)
        return job_id

    def default_resources(self, resources):
        pass

    @retry()
    def check_status(self, job):
        job_id = job.job_id
        if job_id == "":
            return JobStatus.unsubmitted
        ret, stdin, stdout, stderr = self.context.block_call(
            'squeue -o "%.18i %.2t" -j ' + job_id
        )
        if ret != 0:
            err_str = stderr.read().decode("utf-8")
            if "Invalid job id specified" in err_str:
                if self.check_finish_tag(job):
                    dlog.info(f"job: {job.job_hash} {job.job_id} finished")
                    return JobStatus.finished
                else:
                    return JobStatus.terminated
            elif (
                "Socket timed out on send/recv operation" in err_str
                or "Unable to contact slurm controller" in err_str
                or "Invalid user for SlurmUser" in err_str
            ):
                # retry 3 times
                raise RetrySignal(
                    "Get error code %d in checking status through ssh with job: %s . message: %s"
                    % (ret, job.job_hash, err_str)
                )
            raise RuntimeError(
                "status command squeue fails to execute."
                "job_id:%s \n error message:%s\n return code %d\n"
                % (job_id, err_str, ret)
            )
        status_line = stdout.read().decode("utf-8").split("\n")[-2]
        status_word = status_line.split()[-1]
        if not (len(status_line.split()) == 2 and status_word.isupper()):
            raise RuntimeError(
                "Error in getting job status, "
                + f"status_line = {status_line}, "
                + f"parsed status_word = {status_word}"
            )
        if status_word in ["PD", "CF", "S"]:
            return JobStatus.waiting
        elif status_word in ["R"]:
            return JobStatus.running
        elif status_word in ["CG"]:
            return JobStatus.completing
        elif status_word in [
            "C",
            "E",
            "K",
            "BF",
            "CA",
            "CD",
            "F",
            "NF",
            "PR",
            "SE",
            "ST",
            "TO",
        ]:
            if self.check_finish_tag(job):
                dlog.info(f"job: {job.job_hash} {job.job_id} finished")
                return JobStatus.finished
            else:
                return JobStatus.terminated
        else:
            return JobStatus.unknown

    def check_finish_tag(self, job):
        job_tag_finished = job.job_hash + "_job_tag_finished"
        return self.context.check_file_exists(job_tag_finished)

    @classmethod
    def resources_subfields(cls) -> List[Argument]:
        """Generate the resources subfields.

        Returns
        -------
        list[Argument]
            resources subfields
        """
        doc_custom_gpu_line = "Custom GPU configuration, starting with #SBATCH"
        return [
            Argument(
                "kwargs",
                dict,
                [
                    Argument(
                        "custom_gpu_line",
                        str,
                        optional=True,
                        default=None,
                        doc=doc_custom_gpu_line,
                    )
                ],
                optional=True,
                doc="Extra arguments.",
            )
        ]

    def kill(self, job):
        """Kill the job.

        Parameters
        ----------
        job : Job
            job
        """
        job_id = job.job_id
        # -Q Do not report an error if the specified job is already completed.
        ret, stdin, stdout, stderr = self.context.block_call(
            "scancel -Q " + str(job_id)
        )
        # we do not need to stop here if scancel failed; just continue


class SlurmJobArray(Slurm):
    """Slurm with job array enabled for multiple tasks in a job."""

    def gen_script_header(self, job):
        slurm_job_size = job.resources.kwargs.get("slurm_job_size", 1)
        if job.fail_count > 0:
            # resubmit jobs, check if some of tasks have been finished
            job_array = set()
            for ii, task in enumerate(job.job_task_list):
                task_tag_finished = (
                    pathlib.PurePath(task.task_work_path)
                    / (task.task_hash + "_task_tag_finished")
                ).as_posix()
                if not self.context.check_file_exists(task_tag_finished):
                    job_array.add(ii // slurm_job_size)
            return super().gen_script_header(job) + "\n#SBATCH --array=%s" % (
                ",".join(map(str, job_array))
            )
        return super().gen_script_header(job) + "\n#SBATCH --array=0-%d" % (
            math.ceil(len(job.job_task_list) / slurm_job_size) - 1
        )

    def gen_script_command(self, job):
        resources = job.resources
        slurm_job_size = resources.kwargs.get("slurm_job_size", 1)
        # SLURM_ARRAY_TASK_ID: 0 ~ n_jobs-1
        script_command = "case $SLURM_ARRAY_TASK_ID in\n"
        for ii, task in enumerate(job.job_task_list):
            command_env = ""
            command_env += self.gen_command_env_cuda_devices(resources=resources)

            task_tag_finished = task.task_hash + "_task_tag_finished"

            log_err_part = ""
            if task.outlog is not None:
                log_err_part += f"1>>{shlex.quote(task.outlog)} "
            if task.errlog is not None:
                log_err_part += f"2>>{shlex.quote(task.errlog)} "

            flag_if_job_task_fail = job.job_hash + "_flag_if_job_task_fail"
            last_err_file = job.job_hash + "_last_err_file"
            single_script_command = script_command_template.format(
                flag_if_job_task_fail=flag_if_job_task_fail,
                command_env=command_env,
                task_work_path=shlex.quote(
                    pathlib.PurePath(task.task_work_path).as_posix()
                ),
                command=task.command,
                task_tag_finished=task_tag_finished,
                log_err_part=log_err_part,
                err_file=shlex.quote(task.errlog),
                last_err_file=shlex.quote(last_err_file),
            )
            if ii % slurm_job_size == 0:
                script_command += f"{ii // slurm_job_size})\n"
            script_command += single_script_command
            script_command += self.gen_script_wait(resources=resources)
            script_command += "\n"
            if (
                ii % slurm_job_size == slurm_job_size - 1
                or ii == len(job.job_task_list) - 1
            ):
                script_command += ";;\n"
        script_command += "*)\nexit 1\n;;\nesac\n"
        return script_command

    def gen_script_end(self, job):
        # We cannot have a end script for job array
        # we may check task tag instead
        return ""

    @retry()
    def check_status(self, job):
        job_id = job.job_id
        if job_id == "":
            return JobStatus.unsubmitted
        ret, stdin, stdout, stderr = self.context.block_call(
            'squeue -h -o "%.18i %.2t" -j ' + job_id
        )
        if ret != 0:
            err_str = stderr.read().decode("utf-8")
            if "Invalid job id specified" in err_str:
                if self.check_finish_tag(job):
                    dlog.info(f"job: {job.job_hash} {job.job_id} finished")
                    return JobStatus.finished
                else:
                    return JobStatus.terminated
            elif (
                "Socket timed out on send/recv operation" in err_str
                or "Unable to contact slurm controller" in err_str
            ):
                # retry 3 times
                raise RetrySignal(
                    "Get error code %d in checking status through ssh with job: %s . message: %s"
                    % (ret, job.job_hash, err_str)
                )
            raise RuntimeError(
                "status command squeue fails to execute."
                "job_id:%s \n error message:%s\n return code %d\n"
                % (job_id, err_str, ret)
            )
        status_lines = stdout.read().decode("utf-8").split("\n")[:-1]
        status = []
        for status_line in status_lines:
            status_word = status_line.split()[-1]
            if not (len(status_line.split()) == 2 and status_word.isupper()):
                raise RuntimeError(
                    "Error in getting job status, "
                    + f"status_line = {status_line}, "
                    + f"parsed status_word = {status_word}"
                )
            if status_word in ["PD", "CF", "S"]:
                status.append(JobStatus.waiting)
            elif status_word in ["R"]:
                status.append(JobStatus.running)
            elif status_word in ["CG"]:
                status.append(JobStatus.completing)
            elif status_word in [
                "C",
                "E",
                "K",
                "BF",
                "CA",
                "CD",
                "F",
                "NF",
                "PR",
                "SE",
                "ST",
                "TO",
            ]:
                status.append(JobStatus.finished)
            else:
                status.append(JobStatus.unknown)
        # running if any job is running
        if JobStatus.running in status:
            return JobStatus.running
        elif JobStatus.waiting in status:
            return JobStatus.waiting
        elif JobStatus.completing in status:
            return JobStatus.completing
        elif JobStatus.unknown in status:
            return JobStatus.unknown
        else:
            if self.check_finish_tag(job):
                dlog.info(f"job: {job.job_hash} {job.job_id} finished")
                return JobStatus.finished
            else:
                return JobStatus.terminated

    def check_finish_tag(self, job):
        results = []
        for task in job.job_task_list:
            task.get_task_state(self.context)
            results.append(task.task_state == JobStatus.finished)
        return all(results)

    @classmethod
    def resources_subfields(cls) -> List[Argument]:
        """Generate the resources subfields.

        Returns
        -------
        list[Argument]
            resources subfields
        """
        doc_slurm_job_size = "Number of tasks in a Slurm job"
        arg = super().resources_subfields()[0]
        arg.extend_subfields(
            [
                Argument(
                    "slurm_job_size",
                    int,
                    optional=True,
                    default=1,
                    doc=doc_slurm_job_size,
                ),
            ]
        )
        return [arg]

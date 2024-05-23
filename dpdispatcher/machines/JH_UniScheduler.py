import shlex
from typing import List

from dargs import Argument

from dpdispatcher.dlog import dlog
from dpdispatcher.machine import Machine
from dpdispatcher.utils.job_status import JobStatus
from dpdispatcher.utils.utils import (
    RetrySignal,
    customized_script_header_template,
    retry,
)

JH_UniScheduler_script_header_template = """\
#!/bin/bash -l
#JSUB -e %J.err
#JSUB -o %J.out
{JH_UniScheduler_nodes_line}
{JH_UniScheduler_ptile_line}
{JH_UniScheduler_partition_line}
{JH_UniScheduler_number_gpu_line}"""


class JH_UniScheduler(Machine):
    """JH_UniScheduler batch."""

    def gen_script(self, job):
        JH_UniScheduler_script = super().gen_script(job)
        return JH_UniScheduler_script

    def gen_script_header(self, job):
        resources = job.resources
        script_header_dict = {
            "JH_UniScheduler_nodes_line": f"#JSUB -n {resources.number_node * resources.cpu_per_node}",
            "JH_UniScheduler_ptile_line": f"#JSUB -R 'span[ptile={resources.cpu_per_node}]'",
            "JH_UniScheduler_partition_line": f"#JSUB -q {resources.queue_name}",
        }
        custom_gpu_line = resources.kwargs.get("custom_gpu_line", None)
        if not custom_gpu_line:
            script_header_dict["JH_UniScheduler_number_gpu_line"] = (
                "" f"#JSUB -gpgpu {resources.gpu_per_node}"
            )
        else:
            script_header_dict["JH_UniScheduler_number_gpu_line"] = custom_gpu_line
        if (
            resources["strategy"].get("customized_script_header_template_file")
            is not None
        ):
            JH_UniScheduler_script_header = customized_script_header_template(
                resources["strategy"]["customized_script_header_template_file"],
                resources,
            )
        else:
            JH_UniScheduler_script_header = (
                JH_UniScheduler_script_header_template.format(**script_header_dict)
            )

        return JH_UniScheduler_script_header

    @retry()
    def do_submit(self, job):
        script_file_name = job.script_file_name
        script_str = self.gen_script(job)
        job_id_name = job.job_hash + "_job_id"
        self.context.write_file(fname=script_file_name, write_str=script_str)
        script_run_str = self.gen_script_command(job)
        script_run_file_name = f"{job.script_file_name}.run"
        self.context.write_file(fname=script_run_file_name, write_str=script_run_str)

        try:
            stdin, stdout, stderr = self.context.block_checkcall(
                "cd {} && {} {}".format(
                    shlex.quote(self.context.remote_root),
                    "jsub < ",
                    shlex.quote(script_file_name),
                )
            )
        except RuntimeError as err:
            raise RetrySignal(err) from err

        subret = stdout.readlines()
        job_id = subret[0].split()[1][1:-1]
        self.context.write_file(job_id_name, job_id)
        return job_id

    def default_resources(self, resources):
        pass

    @retry()
    def check_status(self, job):
        try:
            job_id = job.job_id
        except AttributeError:
            return JobStatus.terminated
        if job_id == "":
            return JobStatus.unsubmitted
        ret, stdin, stdout, stderr = self.context.block_call("jjobs " + job_id)
        err_str = stderr.read().decode("utf-8")
        if (f"Job <{job_id}> is not found") in err_str:
            if self.check_finish_tag(job):
                return JobStatus.finished
            else:
                return JobStatus.terminated
        elif ret != 0:
            # just retry when any unknown error raised.
            raise RetrySignal(
                "Get error code %d in checking status through ssh with job: %s . message: %s"
                % (ret, job.job_hash, err_str)
            )
        status_out = stdout.read().decode("utf-8").split("\n")
        if len(status_out) < 2:
            return JobStatus.unknown
        else:
            status_line = status_out[1]
            status_word = status_line.split()[2]

        if status_word in ["PEND"]:
            return JobStatus.waiting
        elif status_word in ["RUN", "PSUSP", "SSUSP", "USUSP"]:
            return JobStatus.running
        elif status_word in ["DONE", "EXIT"]:
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
        doc_custom_gpu_line = "Custom GPU configuration, starting with #JSUB"

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
                    ),
                ],
                optional=False,
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
        ret, stdin, stdout, stderr = self.context.block_call(
            "jctrl kill " + str(job_id)
        )

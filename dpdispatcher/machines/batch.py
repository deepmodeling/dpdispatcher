import os
import shlex
from subprocess import PIPE, Popen

from dpdispatcher.dlog import dlog
from dpdispatcher.machine import Machine
from dpdispatcher.utils.job_status import JobStatus
from dpdispatcher.utils.utils import customized_script_header_template

shell_script_header_template = """@echo off\n"""


class Batch(Machine):
    def gen_script(self, job):
        shell_script = super().gen_script(job)
        return shell_script

    def gen_script_header(self, job):
        resources = job.resources
        if (
            resources["strategy"].get("customized_script_header_template_file")
            is not None
        ):
            shell_script_header = customized_script_header_template(
                resources["strategy"]["customized_script_header_template_file"],
                resources,
            )
        else:
            shell_script_header = shell_script_header_template
        return shell_script_header

    def do_submit(self, job):
        script_str = self.gen_script(job)
        script_file_name = job.script_file_name
        job_id_name = job.job_hash + "_job_id"
        output_name = job.job_hash + ".out"
        self.context.write_file(fname=script_file_name, write_str=script_str)
        script_run_str = self.gen_script_command(job)
        script_run_file_name = f"{job.script_file_name}.run"
        self.context.write_file(fname=script_run_file_name, write_str=script_run_str)

        cmd = f"start /B cmd /C {shlex.quote(script_file_name)} > {output_name} 2>&1 && echo %!PID!"
        process = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            err_str = stderr.decode("utf-8")
            raise RuntimeError(
                f"Failed to execute command: {cmd}\nError: {err_str}\nReturn code: {process.returncode}"
            )

        job_id = stdout.decode("utf-8").strip()
        self.context.write_file(job_id_name, job_id)
        return job_id

    def default_resources(self, resources):
        pass

    def check_status(self, job):
        job_id = job.job_id

        if not job_id:
            return JobStatus.unsubmitted

        cmd = f'tasklist /FI "PID eq {job_id}"'
        process = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            err_str = stderr.decode("utf-8")
            raise RuntimeError(
                f"Failed to execute command: {cmd}\nError: {err_str}\nReturn code: {process.returncode}"
            )

        output = stdout.decode("utf-8")
        if str(job_id) in output:
            if self.check_finish_tag(job):
                dlog.info(f"job: {job.job_hash} {job.job_id} finished")
                return JobStatus.finished
            return JobStatus.running
        else:
            return JobStatus.terminated

    def check_finish_tag(self, job):
        job_tag_finished = job.job_hash + "_job_tag_finished"
        return self.context.check_file_exists(job_tag_finished)

    def kill(self, job):
        job_id = job.job_id
        cmd = f"taskkill /PID {job_id} /F"
        process = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            err_str = stderr.decode("utf-8")
            raise RuntimeError(
                f"Failed to kill job {job_id}: {err_str}\nReturn code: {process.returncode}"
            )

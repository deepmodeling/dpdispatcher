import os
import shlex
import subprocess

from dpdispatcher.dlog import dlog
from dpdispatcher.machine import Machine
from dpdispatcher.utils.job_status import JobStatus
from dpdispatcher.utils.utils import customized_script_header_template

shell_script_header_template = """@echo off"""


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
        cmd = f"cd {shlex.quote(self.context.remote_root)} && {script_file_name} > {output_name} 2>&1"
        ret, stdin, stdout, stderr = self.context.block_call(cmd)

        print("ret:", ret)
        print("stdin:", stdin.read().decode("utf-8"))
        print("stdout:", stdout.read().decode("utf-8"))
        print("stderr:", stderr.read().decode("utf-8"))

        if ret != 0:
            err_str = stderr.read().decode("utf-8")
            raise RuntimeError(
                f"status command {cmd} fails to execute\nerror message:{err_str}\nreturn code {ret}\n"
            )
        job_id = int(stdout.read().decode("utf-8").strip())

        self.context.write_file(job_id_name, job_id)
        return job_id

    def default_resources(self, resources):
        pass

    def check_status(self, job):
        job_id = job.job_id

        if not job_id:
            return JobStatus.unsubmitted

        cmd = f'tasklist /FI "PID eq {job_id}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to execute command: {cmd}\nError: {result.stderr}\nReturn code: {result.returncode}"
            )

        if str(job_id) in result.stdout:
            if self.check_finish_tag(job):
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
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to kill job {job_id}: {result.stderr}\nReturn code: {result.returncode}"
            )

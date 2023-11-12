import os
import shutil
import time

from dpdispatcher.utils.utils import customized_script_header_template

try:
    from bohriumsdk.client import Client
    from bohriumsdk.job import Job
    from bohriumsdk.storage import Storage
    from bohriumsdk.util import Util
except ModuleNotFoundError:
    found_bohriumsdk = False
else:
    found_bohriumsdk = True

from dpdispatcher.dlog import dlog
from dpdispatcher.machine import Machine
from dpdispatcher.utils.job_status import JobStatus

shell_script_header_template = """
#!/bin/bash -l
"""


class OpenAPI(Machine):
    def __init__(self, context):
        if not found_bohriumsdk:
            raise ModuleNotFoundError(
                "bohriumsdk not installed. Install dpdispatcher with `pip install dpdispatcher[bohrium]`"
            )
        self.context = context
        self.remote_profile = context.remote_profile.copy()

        self.grouped = self.remote_profile.get("grouped", True)
        self.retry_count = self.remote_profile.get("retry_count", 3)
        self.ignore_exit_code = context.remote_profile.get("ignore_exit_code", True)
        self.client = Client()
        self.job = Job(client=self.client)
        self.storage = Storage(client=self.client)
        self.group_id = None

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

    def gen_local_script(self, job):
        script_str = self.gen_script(job)
        script_file_name = job.script_file_name
        self.context.write_local_file(fname=script_file_name, write_str=script_str)
        script_run_str = self.gen_script_command(job)
        script_run_file_name = f"{job.script_file_name}.run"
        self.context.write_local_file(
            fname=script_run_file_name, write_str=script_run_str
        )
        return script_file_name

    def _gen_backward_files_list(self, job):
        result_file_list = []
        # result_file_list.extend(job.backward_common_files)
        for task in job.job_task_list:
            result_file_list.extend(
                [os.path.join(task.task_work_path, b_f) for b_f in task.backward_files]
            )
        result_file_list = list(set(result_file_list))
        return result_file_list

    def do_submit(self, job):
        self.gen_local_script(job)

        project_id = self.remote_profile.get("project_id", 0)

        openapi_params = {
            "oss_path": job.upload_path,
            "input_file_type": 3,
            "input_file_method": 1,
            "job_type": "container",
            "job_name": self.remote_profile.get("job_name", "DP-GEN"),
            "project_id": project_id,
            "scass_type": self.remote_profile.get("machine_type", ""),
            "cmd": f"bash {job.script_file_name}",
            "log_files": os.path.join(
                job.job_task_list[0].task_work_path, job.job_task_list[0].outlog
            ),
            "out_files": self._gen_backward_files_list(job),
            "platform": self.remote_profile.get("platform", "ali"),
            "image_address": self.remote_profile.get("image_address", ""),
        }
        if job.job_state == JobStatus.unsubmitted:
            openapi_params["job_id"] = job.job_id

        data = self.job.insert(**openapi_params)

        job.job_id = data.get("jobId", 0)  # type: ignore
        # self.job_group_id = data.get("jobGroupId")
        job.job_state = JobStatus.waiting
        return job.job_id

    def _get_job_detail(self, job_id, group_id):
        check_return = self.job.detail(job_id)
        assert check_return is not None, (
            f"Failed to retrieve tasks information. To resubmit this job, please "
            f"try again, if this problem still exists please delete the submission "
            f"file and try again.\nYou can check submission.submission_hash in the "
            f'previous log or type `grep -rl "{job_id}:job_group_id:{group_id}" '
            f"~/.dpdispatcher/dp_cloud_server/` to find corresponding file. "
            f"You can try with command:\n    "
            f'rm $(grep -rl "{job_id}:job_group_id:{group_id}" ~/.dpdispatcher/dp_cloud_server/)'
        )
        return check_return

    def check_status(self, job):
        if job.job_id == "":
            return JobStatus.unsubmitted
        job_id = job.job_id
        group_id = None
        if hasattr(job, "jgid"):
            group_id = job.jgid
        check_return = self._get_job_detail(job_id, group_id)
        try:
            dp_job_status = check_return["status"]  # type: ignore
        except IndexError as e:
            dlog.error(
                f"cannot find job information in bohrium for job {job.job_id}. check_return:{check_return}; retry one more time after 60 seconds"
            )
            time.sleep(60)
            retry_return = self._get_job_detail(job_id, group_id)
            try:
                dp_job_status = retry_return["status"]  # type: ignore
            except IndexError as e:
                raise RuntimeError(
                    f"cannot find job information in bohrium for job {job.job_id} {check_return} {retry_return}"
                )

        job_state = self.map_dp_job_state(
            dp_job_status,
            check_return.get("exitCode", 0),  # type: ignore
            self.ignore_exit_code,
        )
        if job_state == JobStatus.finished:
            job_log = self.job.log(job_id)
            if self.remote_profile.get("output_log"):
                print(job_log, end="")
            self._download_job(job)
        elif self.remote_profile.get("output_log") and job_state == JobStatus.running:
            job_log = self.job.log(job_id)
            print(job_log, end="")
        return job_state

    def _download_job(self, job):
        data = self.job.detail(job.job_id)
        job_url = data["jobFiles"]["outFiles"][0]["url"]  # type: ignore
        if not job_url:
            return
        job_hash = job.job_hash
        result_filename = job_hash + "_back.zip"
        target_result_zip = os.path.join(self.context.local_root, result_filename)
        self.storage.download_from_url(job_url, target_result_zip)
        Util.unzip_file(target_result_zip, out_dir=self.context.local_root)
        try:
            os.makedirs(os.path.join(self.context.local_root, "backup"), exist_ok=True)
            shutil.move(
                target_result_zip,
                os.path.join(
                    self.context.local_root,
                    "backup",
                    os.path.split(target_result_zip)[1],
                ),
            )
        except (OSError, shutil.Error) as e:
            dlog.exception("unable to backup file, " + str(e))

    def check_finish_tag(self, job):
        job_tag_finished = job.job_hash + "_job_tag_finished"
        dlog.info("check if job finished: ", job.job_id, job_tag_finished)
        return self.context.check_file_exists(job_tag_finished)
        # return
        # pass

    def check_if_recover(self, submission):
        return False
        # pass

    @staticmethod
    def map_dp_job_state(status, exit_code, ignore_exit_code=True):
        if isinstance(status, JobStatus):
            return status
        map_dict = {
            -1: JobStatus.terminated,
            0: JobStatus.waiting,
            1: JobStatus.running,
            2: JobStatus.finished,
            3: JobStatus.waiting,
            4: JobStatus.running,
            5: JobStatus.terminated,
            6: JobStatus.running,
            9: JobStatus.waiting,
        }
        if status not in map_dict:
            dlog.error(f"unknown job status {status}")
            return JobStatus.unknown
        if status == -1 and exit_code != 0 and ignore_exit_code:
            return JobStatus.finished
        return map_dict[status]

    def kill(self, job):
        """Kill the job.

        Parameters
        ----------
        job : Job
            job
        """
        job_id = job.job_id
        self.job.kill(job_id)

    def get_exit_code(self, job):
        """Get exit code of the job.

        Parameters
        ----------
        job : Job
            job

        Returns
        -------
        int
            exit code
        """
        check_return = self.job.detail(job.job_id)
        return check_return.get("exitCode", -999)  # type: ignore

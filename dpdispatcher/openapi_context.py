import os
import shutil
import uuid

import tqdm

try:
    from bohriumsdk.client import Client
    from bohriumsdk.job import Job
    from bohriumsdk.storage import Storage
    from bohriumsdk.util import Util
except ModuleNotFoundError:
    found_bohriumsdk = False
else:
    found_bohriumsdk = True

from dpdispatcher import dlog
from dpdispatcher.base_context import BaseContext
from dpdispatcher.JobStatus import JobStatus

DP_CLOUD_SERVER_HOME_DIR = os.path.join(
    os.path.expanduser("~"), ".dpdispatcher/", "dp_cloud_server/"
)


class OpenAPIContext(BaseContext):
    def __init__(
        self,
        local_root,
        remote_root=None,
        remote_profile={},
        *args,
        **kwargs,
    ):
        if not found_bohriumsdk:
            raise ModuleNotFoundError(
                "bohriumsdk not installed. Install dpdispatcher with `pip install dpdispatcher[bohrium]`"
            )
        self.init_local_root = local_root
        self.init_remote_root = remote_root
        self.temp_local_root = os.path.abspath(local_root)
        self.remote_profile = remote_profile
        self.client = Client()
        self.storage = Storage(client=self.client)
        self.job = Job(client=self.client)
        self.util = Util()
        self.jgid = None

    @classmethod
    def load_from_dict(cls, context_dict):
        local_root = context_dict.get("local_root", "./")
        remote_root = context_dict.get("remote_root", None)
        remote_profile = context_dict.get("remote_profile", {})

        bohrium_context = cls(
            local_root=local_root,
            remote_root=remote_root,
            remote_profile=remote_profile,
        )
        return bohrium_context

    def bind_submission(self, submission):
        self.submission = submission
        self.local_root = os.path.join(self.temp_local_root, submission.work_base)
        self.remote_root = "."

        self.submission_hash = submission.submission_hash

        self.machine = submission.machine

    def _gen_object_key(self, job, zip_filename):
        if hasattr(job, "upload_path") and job.upload_path:
            return job.upload_path
        else:
            project_id = self.remote_profile.get("project_id")

            uid = uuid.uuid4()
            path = os.path.join(str(project_id), str(uid), zip_filename)
            setattr(job, "upload_path", path)
            return path

    def upload_job(self, job, common_files=None):
        if common_files is None:
            common_files = []
        self.machine.gen_local_script(job)
        zip_filename = job.job_hash + ".zip"
        zip_task_file = os.path.join(self.local_root, zip_filename)

        upload_file_list = [
            job.script_file_name,
        ]

        upload_file_list.extend(common_files)

        for task in job.job_task_list:
            for file in task.forward_files:
                upload_file_list.append(os.path.join(task.task_work_path, file))

        upload_zip = Util.zip_file_list(
            self.local_root, zip_task_file, file_list=upload_file_list
        )
        project_id = self.remote_profile.get("project_id", 0)

        data = self.job.create(
            project_id=project_id,
            name=self.remote_profile.get("job_name", "DP-GEN"),
            group_id=self.jgid,  # type: ignore
        )
        self.jgid = data.get("jobGroupId", "")  # type: ignore
        token = data.get("token", "")  # type: ignore

        object_key = os.path.join(data["storePath"], zip_filename)  # type: ignore
        job.upload_path = object_key
        job.job_id = data["jobId"]  # type: ignore
        job.jgid = data["jobGroupId"]  # type: ignore
        self.storage.upload_From_file_multi_part(
            object_key=object_key, file_path=upload_zip, token=token
        )

        # self._backup(self.local_root, upload_zip)

    def upload(self, submission):
        # oss_task_dir = os.path.join('%s/%s/%s.zip' % ('indicate', file_uuid, file_uuid))
        # zip_filename = submission.submission_hash + '.zip'
        # oss_task_zip = 'indicate/' + submission.submission_hash + '/' + zip_filename

        # zip_path = "/home/felix/workplace/22_dpdispatcher/dpdispatcher-yfb/dpdispatcher/dpcloudserver/t.txt"
        # zip_path = self.local_root
        bar_format = "{l_bar}{bar}| {n:.02f}/{total:.02f} %  [{elapsed}<{remaining}, {rate_fmt}{postfix}]"
        job_to_be_uploaded = []
        result = None
        dlog.info("checking all job has been uploaded")
        for job in submission.belonging_jobs:
            if job.job_state == JobStatus.unsubmitted:
                job_to_be_uploaded.append(job)
        if len(job_to_be_uploaded) == 0:
            dlog.info("all job has been uploaded, continue")
            return result
        for job in tqdm.tqdm(
            job_to_be_uploaded,
            desc="Uploading to tiefblue",
            bar_format=bar_format,
            leave=False,
            disable=None,
        ):
            self.upload_job(job, submission.forward_common_files)
        return result
        # return oss_task_zip
        # api.upload(self.oss_task_dir, zip_task_file)

    def download(self, submission):
        jobs = submission.belonging_jobs
        job_hashs = {}
        job_infos = {}
        job_result = []
        for job in jobs:
            jid = job.job_id
            job_hashs[jid] = job.job_hash
            jobinfo = self.job.detail(jid)
            # jobinfo = self.api.get_job_detail(jid)
            job_result.append(jobinfo)
        # if group_id is not None:
        #     job_result = self.api.get_tasks_list(group_id)
        for each in job_result:
            if "resultUrl" in each and each["resultUrl"] != "" and each["status"] == 2:
                job_hash = ""
                if each["id"] not in job_hashs:
                    dlog.info(
                        f"find unexpect job_hash, but task {each['id']} still been download."
                    )
                    dlog.debug(str(job_hashs))
                    job_hash = str(each["id"])
                else:
                    job_hash = job_hashs[each["id"]]
                job_infos[job_hash] = each
        bar_format = "{l_bar}{bar}| {n:.02f}/{total:.02f} %  [{elapsed}<{remaining}, {rate_fmt}{postfix}]"
        for job_hash, info in tqdm.tqdm(
            job_infos.items(),
            desc="Validating download file from Lebesgue",
            bar_format=bar_format,
            leave=False,
            disable=None,
        ):
            result_filename = job_hash + "_back.zip"
            target_result_zip = os.path.join(self.local_root, result_filename)
            if self._check_if_job_has_already_downloaded(
                target_result_zip, self.local_root
            ):
                continue
            self.storage.download_from_url(info["resultUrl"], target_result_zip)
            Util.unzip_file(target_result_zip, out_dir=self.local_root)
            self._backup(self.local_root, target_result_zip)
        self._clean_backup(
            self.local_root, keep_backup=self.remote_profile.get("keep_backup", True)
        )
        return True

    def write_file(self, fname, write_str):
        result = self.write_home_file(fname, write_str)
        return result

    def write_local_file(self, fname, write_str):
        local_filename = os.path.join(self.local_root, fname)
        with open(local_filename, "w") as f:
            f.write(write_str)
        return local_filename

    def read_file(self, fname):
        result = self.read_home_file(fname)
        return result

    def write_home_file(self, fname, write_str):
        # os.makedirs(self.remote_root, exist_ok = True)
        with open(os.path.join(DP_CLOUD_SERVER_HOME_DIR, fname), "w") as fp:
            fp.write(write_str)
        return True

    def read_home_file(self, fname):
        with open(os.path.join(DP_CLOUD_SERVER_HOME_DIR, fname)) as fp:
            ret = fp.read()
        return ret

    def check_file_exists(self, fname):
        result = self.check_home_file_exits(fname)
        return result

    def check_home_file_exits(self, fname):
        return os.path.isfile(os.path.join(DP_CLOUD_SERVER_HOME_DIR, fname))

    def clean(self):
        submission_file_name = f"{self.submission.submission_hash}.json"
        submission_json = os.path.join(DP_CLOUD_SERVER_HOME_DIR, submission_file_name)
        os.remove(submission_json)
        return True

    def _check_if_job_has_already_downloaded(self, target, local_root):
        backup_file_location = os.path.join(
            local_root, "backup", os.path.split(target)[1]
        )
        if os.path.exists(backup_file_location):
            return True
        else:
            return False

    def _backup(self, local_root, target):
        try:
            # move to backup directory
            os.makedirs(os.path.join(local_root, "backup"), exist_ok=True)
            shutil.move(
                target, os.path.join(local_root, "backup", os.path.split(target)[1])
            )
        except (OSError, shutil.Error) as e:
            dlog.exception("unable to backup file, " + str(e))

    def _clean_backup(self, local_root, keep_backup=True):
        if not keep_backup:
            dir_to_be_removed = os.path.join(local_root, "backup")
            if os.path.exists(dir_to_be_removed):
                shutil.rmtree(dir_to_be_removed)

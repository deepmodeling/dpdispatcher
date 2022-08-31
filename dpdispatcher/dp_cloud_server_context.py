#!/usr/bin/env python
# coding: utf-8
# %%
import time
import uuid

from dargs.dargs import Argument
from dpdispatcher.base_context import BaseContext
from typing import List
import os
from dpdispatcher import dlog
# from dpdispatcher.submission import Machine
# from . import dlog
from .dpcloudserver.api import API
from .dpcloudserver import zip_file
import shutil
import tqdm

# from zip_file import zip_files
from .dpcloudserver.config import ALI_OSS_BUCKET_URL

DP_CLOUD_SERVER_HOME_DIR = os.path.join(
    os.path.expanduser('~'),
    '.dpdispatcher/',
    'dp_cloud_server/'
)
ENDPOINT = 'http://oss-cn-shenzhen.aliyuncs.com'
BUCKET_NAME = 'dpcloudserver'


class DpCloudServerContext(BaseContext):
    def __init__(self,
                 local_root,
                 remote_root=None,
                 remote_profile={},
                 *args,
                 **kwargs,
                 ):
        self.init_local_root = local_root
        self.init_remote_root = remote_root
        self.temp_local_root = os.path.abspath(local_root)
        self.remote_profile = remote_profile
        email = remote_profile.get("email", None)
        password = remote_profile.get('password')
        if email is None:
            raise ValueError("can not find email in remote_profile, please check your machine file.")
        if password is None:
            raise ValueError("can not find password in remote_profile, please check your machine file.")
        self.api = API(email, password)

        os.makedirs(DP_CLOUD_SERVER_HOME_DIR, exist_ok=True)

    @classmethod
    def load_from_dict(cls, context_dict):
        local_root = context_dict['local_root']
        remote_root = context_dict.get('remote_root', None)
        remote_profile = context_dict.get('remote_profile', {})

        dp_cloud_server_context = cls(
            local_root=local_root,
            remote_root=remote_root,
            remote_profile=remote_profile
        )
        return dp_cloud_server_context

    def bind_submission(self, submission):
        self.submission = submission
        self.local_root = os.path.join(self.temp_local_root, submission.work_base)
        self.remote_root = '$(pwd)'

        self.submission_hash = submission.submission_hash

        self.machine = submission.machine

        # def zip_files(self, submission):
        #     file_uuid = uuid.uuid1().hex
        # oss_task_dir = os.path.join()

    def _gen_oss_path(self, job, zip_filename):
        if hasattr(job, 'upload_path') and job.upload_path:
            return job.upload_path
        else:
            program_id = self.remote_profile.get('program_id')
            program_id = self.remote_profile.get('project_id', program_id)
            if program_id is None:
                program_id = 0
            uid = uuid.uuid4()
            path = os.path.join("program", str(program_id), str(uid), zip_filename)
            setattr(job, 'upload_path', path)
            return path

    def upload_job(self, job, common_files=None):
        MAX_RETRY = 3
        if common_files is None:
            common_files = []
        self.machine.gen_local_script(job)
        zip_filename = job.job_hash + '.zip'
        oss_task_zip = self._gen_oss_path(job, zip_filename)
        zip_task_file = os.path.join(self.local_root, zip_filename)

        upload_file_list = [job.script_file_name, ]
        upload_file_list.extend(common_files)

        for task in job.job_task_list:
            for file in task.forward_files:
                upload_file_list.append(
                    os.path.join(
                        task.task_work_path, file
                    )
                )

        upload_zip = zip_file.zip_file_list(
            self.local_root,
            zip_task_file,
            file_list=upload_file_list
        )
        result = self.api.upload(oss_task_zip, upload_zip, ENDPOINT, BUCKET_NAME)
        retry_count = 0
        while True:
            if self.api.check_file_has_uploaded(ALI_OSS_BUCKET_URL + oss_task_zip):
                self._backup(self.local_root, upload_zip)
                break
            elif retry_count < MAX_RETRY:
                time.sleep(1 + retry_count)
                retry_count += 1
            else:
                raise ValueError(f"upload retried excess {MAX_RETRY} terminate.")

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
            if not self.api.check_job_has_uploaded(job.job_id):
                job_to_be_uploaded.append(job)
        if len(job_to_be_uploaded) == 0:
            dlog.info("all job has been uploaded, continue")
            return result
        for job in tqdm.tqdm(job_to_be_uploaded, desc="Uploading to Lebesgue", bar_format=bar_format, leave=False):
            self.upload_job(job, submission.forward_common_files)
        return result
        # return oss_task_zip
        # api.upload(self.oss_task_dir, zip_task_file)

    def download(self, submission):
        jobs = submission.belonging_jobs
        job_hashs = {}
        group_id = None
        job_infos = {}
        for job in jobs:
            ids = job.job_id.split(":job_group_id:")
            jid, gid = int(ids[0]), int(ids[1])
            job_hashs[jid] = job.job_hash
            group_id = gid
        if group_id is not None:
            job_result = self.api.get_tasks_list(group_id)
            for each in job_result:
                if 'result_url' in each and each['result_url'] != '' and each['status'] == 2:
                    job_hash = ''
                    if each['task_id'] not in job_hashs:
                        dlog.info(f"find unexpect job_hash, but task {each['task_id']} still been download.")
                        dlog.debug(str(job_hashs))
                        job_hash = str(each['task_id'])
                    else:
                        job_hash = job_hashs[each['task_id']]
                    job_infos[job_hash] = each
        bar_format = "{l_bar}{bar}| {n:.02f}/{total:.02f} %  [{elapsed}<{remaining}, {rate_fmt}{postfix}]"
        for job_hash, info in tqdm.tqdm(job_infos.items(), desc="Validating download file from Lebesgue",
                                        bar_format=bar_format, leave=False):
            result_filename = job_hash + '_back.zip'
            target_result_zip = os.path.join(self.local_root, result_filename)
            if self._check_if_job_has_already_downloaded(target_result_zip, self.local_root):
                continue
            self.api.download_from_url(info['result_url'], target_result_zip)
            zip_file.unzip_file(target_result_zip, out_dir=self.local_root)
            self._backup(self.local_root, target_result_zip)
        self._clean_backup(self.local_root, keep_backup=self.remote_profile.get('keep_backup', True))
        return True

    def _check_if_job_has_already_downloaded(self, target, local_root):
        backup_file_location = os.path.join(local_root, 'backup', os.path.split(target)[1])
        if os.path.exists(backup_file_location):
            return True
        else:
            return False

    def _backup(self, local_root, target):
        try:
            # move to backup directory
            os.makedirs(os.path.join(local_root, 'backup'), exist_ok=True)
            shutil.move(target,
                        os.path.join(local_root, 'backup', os.path.split(target)[1]))
        except (OSError, shutil.Error) as e:
            dlog.exception("unable to backup file, " + str(e))

    def _clean_backup(self, local_root, keep_backup=True):
        if not keep_backup:
            dir_to_be_removed = os.path.join(local_root, 'backup')
            if os.path.exists(dir_to_be_removed):
                shutil.rmtree(dir_to_be_removed)

    def write_file(self, fname, write_str):
        result = self.write_home_file(fname, write_str)
        return result

    def write_local_file(self, fname, write_str):
        local_filename = os.path.join(self.local_root, fname)
        with open(local_filename, 'w') as f:
            f.write(write_str)
        return local_filename

    def read_file(self, fname):
        result = self.read_home_file(fname)
        return result

    def write_home_file(self, fname, write_str):
        # os.makedirs(self.remote_root, exist_ok = True)
        with open(os.path.join(DP_CLOUD_SERVER_HOME_DIR, fname), 'w') as fp:
            fp.write(write_str)
        return True

    def read_home_file(self, fname):
        with open(os.path.join(DP_CLOUD_SERVER_HOME_DIR, fname), 'r') as fp:
            ret = fp.read()
        return ret

    def check_file_exists(self, fname):
        result = self.check_home_file_exits(fname)
        return result

    def check_home_file_exits(self, fname):
        return os.path.isfile(os.path.join(DP_CLOUD_SERVER_HOME_DIR, fname))

    def clean(self):
        submission_file_name = "{submission_hash}.json".format(
            submission_hash=self.submission.submission_hash
        )
        submission_json = os.path.join(
            DP_CLOUD_SERVER_HOME_DIR,
            submission_file_name
        )
        os.remove(submission_json)
        return True

    # def get_return(self, cmd_pipes):
    #     if not self.check_finish(cmd_pipes):
    #         return None, None, None
    #     else :
    #         retcode = cmd_pipes['stdout'].channel.recv_exit_status()
    #         return retcode, cmd_pipes['stdout'], cmd_pipes['stderr']

    def kill(self, cmd_pipes):
        pass

    @classmethod
    def machine_subfields(cls) -> List[Argument]:
        """Generate the machine subfields.
        
        Returns
        -------
        list[Argument]
            machine subfields
        """
        doc_remote_profile = "The information used to maintain the connection with remote machine."
        return [Argument("remote_profile", dict, [
            Argument("email", str, optional=False, doc="Email"),
            Argument("password", str, optional=False, doc="Password"),
            Argument("program_id", int, optional=False, alias=['project_id'], doc="Program ID"),
            Argument("keep_backup", bool, optional=True, doc="keep download and upload zip"),
            Argument("input_data", dict, optional=False, doc="Configuration of job"),
        ], doc=doc_remote_profile)]


class LebesgueContext(DpCloudServerContext):
    pass

# %%

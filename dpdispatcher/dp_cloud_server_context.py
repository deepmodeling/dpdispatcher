#!/usr/bin/env python
# coding: utf-8
#%%
from dpdispatcher import dp_cloud_server
from dpdispatcher.base_context import BaseContext
import os, sys, paramiko, json, uuid, tarfile, time, stat, shutil
from glob import glob
# from dpdispatcher import dlog
# from dpdispatcher.submission import Machine
from .dpcloudserver import api
from .dpcloudserver import zip_file
# from zip_file import zip_files
DP_CLOUD_SERVER_HOME_DIR = os.path.join(
    os.path.expanduser('~'),
    '.dpdispatcher/',
    'dp_cloud_server/'
)
ENDPOINT = 'http://oss-cn-shenzhen.aliyuncs.com'
BUCKET_NAME = 'dpcloudserver'

class DpCloudServerContext(BaseContext):
    def __init__ (self,
        local_root,
        remote_root=None,
        remote_profile={},
    ):
        self.temp_local_root = os.path.abspath(local_root)
        self.remote_profile = remote_profile
        username = remote_profile['username']
        password = remote_profile['password']

        api.login(username=username, password=password)

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

    def upload(self, submission):
        # oss_task_dir = os.path.join('%s/%s/%s.zip' % ('indicate', file_uuid, file_uuid))
        # zip_filename = submission.submission_hash + '.zip'
        # oss_task_zip = 'indicate/' + submission.submission_hash + '/' + zip_filename

        # zip_path = "/home/felix/workplace/22_dpdispatcher/dpdispatcher-yfb/dpdispatcher/dpcloudserver/t.txt"
        # zip_path = self.local_root

        for job in submission.belonging_jobs:
            self.machine.gen_local_script(job)
            zip_filename = job.job_hash + '.zip'
            oss_task_zip = 'indicate/' + job.job_hash + '/' + zip_filename
            zip_task_file = os.path.join(self.local_root, zip_filename)

            upload_file_list = [job.script_file_name, ]
            upload_file_list.extend(submission.forward_common_files)

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

            result = api.upload(oss_task_zip, upload_zip, ENDPOINT, BUCKET_NAME)
        return result
        # return oss_task_zip
        # api.upload(self.oss_task_dir, zip_task_file)

    def download(self, submission):
        for job in submission.belonging_jobs:
            result_filename = job.job_hash + '_back.zip'
            oss_result_zip = 'indicate/' + job.job_hash + '/' + result_filename
            target_result_zip = os.path.join(self.local_root, result_filename)
            api.download(oss_result_zip, target_result_zip, ENDPOINT, BUCKET_NAME)
            zip_file.unzip_file(target_result_zip, out_dir=self.local_root)
        return True

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

    def kill(self, cmd_pipes) :
        pass
#%%

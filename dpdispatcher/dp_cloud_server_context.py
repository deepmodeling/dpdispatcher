#!/usr/bin/env python
# coding: utf-8
# %%
from dargs.dargs import Argument
from dpdispatcher.base_context import BaseContext
from typing import List
import os
# from dpdispatcher import dlog
# from dpdispatcher.submission import Machine
from .dpcloudserver.api import API
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
            result = self.api.upload(oss_task_zip, upload_zip, ENDPOINT, BUCKET_NAME)
        return result
        # return oss_task_zip
        # api.upload(self.oss_task_dir, zip_task_file)

    def download(self, submission):
        jobs = submission.belonging_jobs
        job_hashs = {}
        group_id = None
        job_infos = {}
        for job in jobs:
            if isinstance(job.job_id, str) and ':job_group_id:' in job.job_id:
                ids = job.job_id.split(":job_group_id:")
                jid, gid = int(ids[0]), int(ids[1])
                job_hashs[jid] = job.job_hash 
                group_id = gid
            else:
                job_infos[job.job_hash] = self.get_tasks(job.job_id)[0]
        if group_id is not None:
            job_result = self.api.get_tasks_v2_list(group_id)
            for each in job_result:
                if 'result_url' in each and each['result_url'] != '' and each['status'] == 2:
                    job_hash = job_hashs[each['task_id']]
                    job_infos[job_hash] = each
        for hash, info in job_infos.items():
            result_filename = hash + '_back.zip'
            target_result_zip = os.path.join(self.local_root, result_filename)
            self.api.download_from_url(info['result_url'], target_result_zip)
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
            Argument("program_id", int, optional=False, doc="Program ID"),
            Argument("input_data", dict, [
                Argument("job_name", str, optional=True, doc="Job name"),
                Argument("image_name", str, optional=True, doc="Name of the image which run the job, optional "
                                                               "when platform is not ali/oss."),
                Argument("disk_size", str, optional=True, doc="disk size (GB), optional "
                                                              "when platform is not ali/oss."),
                Argument("scass_type", str, optional=False, doc="machine configuration."),
                Argument("platform", str, optional=False, doc="Job run in which platform."),
                Argument("log_file", str, optional=True, doc="location of log file."),
                Argument('checkpoint_files', [str, list], optional=True, doc="location of checkpoint files when "
                                                                                  "it is list type. record file "
                                                                                  "changes when it is string value "
                                                                                  "'sync_files'"),
                Argument('checkpoint_time', int, optional=True, default=15, doc='interval of checkpoint data been '
                                                                                'stored minimum 15.'),
                Argument('backward_files', list, optional=True, doc='which files to be uploaded to remote '
                                                                         'resources. Upload all the files when it is '
                                                                         'None or empty.')
            ], optional=False, doc="Configuration of job"),
        ], doc=doc_remote_profile)]
#%%

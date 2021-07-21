from dpdispatcher.JobStatus import JobStatus
from dpdispatcher import dlog
from dpdispatcher.machine import Machine
from dpdispatcher.dpcloudserver import api
from dpdispatcher.dpcloudserver.config import ALI_OSS_BUCKET_URL
import time

shell_script_header_template="""
#!/bin/bash -l
"""

class DpCloudServer(Machine):
    def __init__(self, context):
        self.context = context
        self.input_data = context.remote_profile['input_data'].copy()

    def gen_script(self, job):
        shell_script = super(DpCloudServer, self).gen_script(job)
        return shell_script

    def gen_script_header(self, job):
        shell_script_header = shell_script_header_template
        return shell_script_header

    def gen_local_script(self, job):
        script_str = self.gen_script(job) 
        script_file_name = job.script_file_name
        self.context.write_local_file(
            fname=script_file_name, 
            write_str=script_str
        )
        return script_file_name

    def do_submit(self, job):
        self.gen_local_script(job)
        zip_filename = job.job_hash + '.zip'
        oss_task_zip = 'indicate/' + job.job_hash + '/' + zip_filename
        job_resources = ALI_OSS_BUCKET_URL + oss_task_zip

        input_data = self.input_data.copy()

        input_data['job_resources'] = job_resources
        input_data['command'] = f"bash {job.script_file_name}"


        job_id = api.job_create(
            job_type=input_data['job_type'],
            oss_path=input_data['job_resources'],
            input_data=input_data,
            program_id=self.context.remote_profile.get('program_id', None)
        )

        job.job_id = job_id
        job.job_state = JobStatus.waiting
        return job_id

    def check_status(self, job):
        if job.job_id == '':
            return JobStatus.unsubmitted
        dlog.debug(f"debug: check_status; job.job_id:{job.job_id}; job.job_hash:{job.job_hash}")

        check_return = api.get_tasks(job.job_id)
        try:
            dp_job_status = check_return[0]["status"]
        except IndexError as e:
            dlog.error(f"cannot find job information in check_return. job {job.job_id}. check_return:{check_return}; retry one more time after 60 seconds")
            time.sleep(60)
            retry_return = api.get_tasks(job.job_id)
            try:
                dp_job_status = retry_return[0]["status"]
            except IndexError as e:
                raise RuntimeError(f"cannot find job information in dpcloudserver's database for job {job.job_id} {check_return} {retry_return}")

        job_state = self.map_dp_job_state(dp_job_status)
        return job_state

    def check_finish_tag(self, job):
        job_tag_finished = job.job_hash + '_job_tag_finished'
        dlog.info('check if job finished: ',job.job_id, job_tag_finished)
        return self.context.check_file_exists(job_tag_finished)
        # return
        # pass

    def check_if_recover(self, submission):
        return False
        # pass

    @staticmethod
    def map_dp_job_state(status):
        map_dict = {
            -1:JobStatus.terminated,
            0:JobStatus.waiting,
            1:JobStatus.running,
            2:JobStatus.finished
        }
        return map_dict[status]


    # def check_finish_tag(self, job):
    #     job_tag_finished = job.job_hash + '_job_tag_finished'
    #     return self.context.check_file_exists(job_tag_finished)




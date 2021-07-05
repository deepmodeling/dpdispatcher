#import psutil

from dpdispatcher.JobStatus import JobStatus
from dpdispatcher import dlog
from dpdispatcher.machine import Machine

shell_script_header_template="""
#!/bin/bash -l
"""

class Shell(Machine):
    def gen_script(self, job):
        shell_script = super(Shell, self).gen_script(job)
        return shell_script

    def gen_script_header(self, job):
        shell_script_header = shell_script_header_template
        return shell_script_header

    def do_submit(self, job):
        script_str = self.gen_script(job) 
        script_file_name = job.script_file_name
        job_id_name = job.job_hash + '_job_id'
        output_name = job.job_hash + '.out'
        self.context.write_file(fname=script_file_name, write_str=script_str)
        ret, stdin, stdout, stderr = self.context.block_call('cd %s && { nohup bash %s 1>>%s 2>>%s & } && echo $!' % (self.context.remote_root, script_file_name, output_name, output_name) )
        if ret != 0:
            err_str = stderr.read().decode('utf-8')
            raise RuntimeError\
                    ("status command squeue fails to execute\nerror message:%s\nreturn code %d\n" % (err_str, ret))
        job_id = int(stdout.read().decode('utf-8').strip())
        self.context.write_file(job_id_name, str(job_id))
        return job_id

        # script_file_name = job.script_file_name
        # script_str = self.gen_script(job)
        # job_id_name = job.job_hash + '_job_id'
        # script_str = self.sub_script(job_dirs, cmd, args=args, resources=resources, outlog=outlog, errlog=errlog)
        # self.context.write_file(fname=script_file_name, write_str=script_str)
        # stdin, stdout, stderr = self.context.block_checkcall('cd %s && %s %s' % (self.context.remote_root, 'qsub', script_file_name))
        # subret = (stdout.readlines())
        # job_id = subret[0].split()[0]
        # self.context.write_file(job_id_name, job_id)        
        # return job_id


    def default_resources(self, resources) :
        pass
    
    def check_status(self, job):
        job_id = job.job_id
        # print('shell.check_status.job_id', job_id)
        # job_state = JobStatus.unknown
        if job_id == "" :
            return JobStatus.unsubmitted

        ret, stdin, stdout, stderr = self.context.block_call(f"if ps -p {job_id} > /dev/null; then echo 1; fi")
        if ret != 0:
            err_str = stderr.read().decode('utf-8')
            raise RuntimeError\
                    ("status command squeue fails to execute\nerror message:%s\nreturn code %d\n" % (err_str, ret))
        
        if_job_exists = bool(stdout.read().decode('utf-8').strip())
        if self.check_finish_tag(job=job):
            dlog.info(f"job: {job.job_hash} {job.job_id} finished")
            return JobStatus.finished

        if if_job_exists:
            return JobStatus.running
        else:
            return JobStatus.terminated
        # return job_state
    
    # def check_status(self, job):
    #     job_id = job.job_id
    #     uuid_names = job.job_hash
    #     cnt = 0
    #     ret, stdin, stdout, stderr = self.context.block_call("ps aux | grep %s"%uuid_names)
    #     response_list = stdout.read().decode('utf-8').split("\n")
    #     for response in response_list:
    #         if  uuid_names + ".sub" in response:
    #             return True
    #     return False

    def check_finish_tag(self, job):
        job_tag_finished = job.job_hash + '_job_tag_finished'
        # print('job finished: ',job.job_id, job_tag_finished)
        return self.context.check_file_exists(job_tag_finished)

import os,sys,time,random,uuid
import psutil

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
        self.context.write_file(fname=script_file_name, write_str=script_str)
        proc = self.context.call('cd %s && exec bash %s' % (self.context.remote_root, script_file_name))

        job_id = int(proc.pid)
        # print('shell.do_submit.job_id', job_id)
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
        job_state = JobStatus.unknown
        if job_id == "" :
            return JobStatus.unsubmitted

        if_job_exists = psutil.pid_exists(pid=job_id)
        if self.check_finish_tag(job=job):
            dlog.info(f"job: {job.job_hash} {job.job_id} finished")
            return JobStatus.finished

        if if_job_exists:
            return JobStatus.running
        else:
            return JobStatus.terminated
        return job_state
    
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

    def check_status_(self, job):
        job_id = job.job_id
        if job_id == "" :
            return JobStatus.unsubmitted
        ret, stdin, stdout, stderr\
            = self.context.block_call ("qstat -x " + job_id)
        err_str = stderr.read().decode('utf-8')
        if (ret != 0) :
            if str("qstat: Unknown Job Id") in err_str :
                if self.check_finish_tag() :
                    return JobStatus.finished
                else :
                    return JobStatus.terminated
            else :
                raise RuntimeError ("status command qstat fails to execute. erro info: %s return code %d"
                                    % (err_str, ret))
        status_line = stdout.read().decode('utf-8').split ('\n')[-2]
        status_word = status_line.split ()[-2]        
        # dlog.info (status_word)
        if status_word in ["Q","H"] :
            return JobStatus.waiting
        elif    status_word in ["R"] :
            return JobStatus.running
        elif    status_word in ["C", "E", "K", "F"] :
            if self.check_finish_tag(job) :
                return JobStatus.finished
            else :
                return JobStatus.terminated
        else :
            return JobStatus.unknown

    def check_finish_tag(self, job):
        job_tag_finished = job.job_hash + '_job_tag_finished'
        # print('job finished: ',job.job_id, job_tag_finished)
        return self.context.check_file_exists(job_tag_finished)

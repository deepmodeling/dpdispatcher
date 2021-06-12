import os,sys,time,random,uuid

from dpdispatcher.JobStatus import JobStatus
from dpdispatcher import dlog
from dpdispatcher.machine import Machine


pbs_script_header_template="""
#!/bin/bash -l
{select_node_line}
#PBS -j oe
{queue_name_line}
"""

class PBS(Machine):
    def gen_script(self, job):
        pbs_script = super(PBS, self).gen_script(job)
        return pbs_script

    def gen_script_header(self, job):
        resources = job.resources
        pbs_script_header_dict= {}
        pbs_script_header_dict['select_node_line']="#PBS -l select={number_node}:ncpus={cpu_per_node}:ngpus={gpu_per_node}".format(
            number_node=resources.number_node, cpu_per_node=resources.cpu_per_node, gpu_per_node=resources.gpu_per_node
        )
        pbs_script_header_dict['queue_name_line']="#PBS -q {queue_name}".format(queue_name=resources.queue_name)
        pbs_script_header = pbs_script_header_template.format(**pbs_script_header_dict)
        return pbs_script_header

    def do_submit(self, job):
        script_file_name = job.script_file_name
        script_str = self.gen_script(job)
        job_id_name = job.job_hash + '_job_id'
        # script_str = self.sub_script(job_dirs, cmd, args=args, resources=resources, outlog=outlog, errlog=errlog)
        self.context.write_file(fname=script_file_name, write_str=script_str)
        # self.context.write_file(fname=os.path.join(self.context.submission.work_base, script_file_name), write_str=script_str)
        # script_file_dir = os.path.join(self.context.submission.work_base)
        script_file_dir = self.context.remote_root
        # stdin, stdout, stderr = self.context.block_checkcall('cd %s && %s %s' % (self.context.remote_root, 'qsub', script_file_name))
        stdin, stdout, stderr = self.context.block_checkcall('cd %s && %s %s' % (script_file_dir, 'qsub', script_file_name))
        subret = (stdout.readlines())
        job_id = subret[0].split()[0]
        self.context.write_file(job_id_name, job_id)        
        return job_id


    def default_resources(self, resources) :
        pass
    
    def check_status(self, job):
        job_id = job.job_id
        if job_id == "" :
            return JobStatus.unsubmitted
        ret, stdin, stdout, stderr\
            = self.context.block_call ("qstat -x " + job_id)
        err_str = stderr.read().decode('utf-8')
        if (ret != 0) :
            if str("qstat: Unknown Job Id") in err_str or str("Job has finished") in err_str:
                if self.check_finish_tag(job=job) :
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
            if self.check_finish_tag(job):
                dlog.info(f"job: {job.job_hash} {job.job_id} finished")
                return JobStatus.finished
            else :
                return JobStatus.terminated
        else :
            return JobStatus.unknown

    def check_finish_tag(self, job):
        job_tag_finished = job.job_hash + '_job_tag_finished'
        return self.context.check_file_exists(job_tag_finished)




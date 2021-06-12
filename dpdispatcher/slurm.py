from dpdispatcher.machine import Machine
import os,sys,time,random,uuid
from collections import defaultdict

from dpdispatcher.JobStatus import JobStatus
from dpdispatcher import dlog
# from dpdispatcher.submission import Resources

slurm_script_header_template="""\
#!/bin/bash -l
{slurm_nodes_line}
{slurm_ntasks_per_node_line}
{slurm_number_gpu_line}
{slurm_partition_line}"""

class Slurm(Machine):
    def gen_script(self, job):
        slurm_script = super(Slurm, self).gen_script(job)
        return slurm_script

    def gen_script_header(self, job):
        resources = job.resources
        script_header_dict = {}
        script_header_dict['slurm_nodes_line']="#SBATCH --nodes {number_node}".format(number_node=resources.number_node)
        script_header_dict['slurm_ntasks_per_node_line']="#SBATCH --ntasks-per-node {cpu_per_node}".format(cpu_per_node=resources.cpu_per_node)
        script_header_dict['slurm_number_gpu_line']="#SBATCH --gres=gpu:{gpu_per_node}".format(gpu_per_node=resources.gpu_per_node)
        script_header_dict['slurm_partition_line']="#SBATCH --partition {queue_name}".format(queue_name=resources.queue_name)
        slurm_script_header = slurm_script_header_template.format(**script_header_dict)
        return slurm_script_header

    def do_submit(self, job, retry=0, max_retry=3):
        script_file_name = job.script_file_name
        script_str = self.gen_script(job)
        job_id_name = job.job_hash + '_job_id'
        # script_str = self.sub_script(job_dirs, cmd, args=args, resources=resources, outlog=outlog, errlog=errlog)
        self.context.write_file(fname=script_file_name, write_str=script_str)
        # self.context.write_file(fname=os.path.join(self.context.submission.work_base, script_file_name), write_str=script_str)
        ret, stdin, stdout, stderr = self.context.block_call('cd %s && %s %s' % (self.context.remote_root, 'sbatch', script_file_name))
        if ret != 0:
            err_str = stderr.read().decode('utf-8')
            if "Socket timed out on send/recv operation" in err_str:
                # server network error, retry 3 times
                if retry < max_retry:
                    dlog.warning("Get error code %d in submitting through ssh with job: %s . message: %s" %
                        (ret, job.job_hash, err_str))
                    dlog.warning("Sleep 60 s and retry submitting...")
                    # rest 60s
                    time.sleep(60)
                    return self.do_submit(job, retry=retry+1, max_retry=max_retry)
            elif "Job violates accounting/QOS policy" in err_str:
                # job number exceeds, skip the submitting
                return ''
            else:
                raise RuntimeError\
                    ("status command squeue fails to execute\nerror message:%s\nreturn code %d\n" % (err_str, ret))
        subret = (stdout.readlines())
        # Submitted batch job 293859
        assert subret[0].startswith('Submitted'), f"Error when submiitting job to slurm system.subret:{subret}"
        job_id = subret[0].split()[-1]
        self.context.write_file(job_id_name, job_id)        
        return job_id

    def default_resources(self, resources) :
        pass
    
    def check_status(self, job, retry=0, max_retry=3):
        job_id = job.job_id
        if job_id == '' :
            return JobStatus.unsubmitted
        ret, stdin, stdout, stderr \
            = self.context.block_call ('squeue -o "%.18i %.2t" -j ' + job_id)
        if (ret != 0) :
            err_str = stderr.read().decode('utf-8')
            if str("Invalid job id specified") in err_str :
                if self.check_finish_tag(job) :
                    return JobStatus.finished
                else :
                    return JobStatus.terminated
            elif "Socket timed out on send/recv operation" in err_str:
                # retry 3 times
                if retry < max_retry:
                    dlog.warning("Get error code %d in checking status through ssh with job: %s . message: %s" %
                        (ret, job.job_hash, err_str))
                    dlog.warning("Sleep 60 s and retry checking...")
                    # rest 60s
                    time.sleep(60)
                    return self.check_status(job_id, retry=retry+1, max_retry=max_retry)
            else:
                raise RuntimeError("status command squeue fails to execute."
                    "job_id:%s \n error message:%s\n return code %d\n" % (job_id, err_str, ret))
        status_line = stdout.read().decode('utf-8').split ('\n')[-2]
        status_word = status_line.split ()[-1]
        if not (len(status_line.split()) == 2 and status_word.isupper()): 
            raise RuntimeError("Error in getting job status, " +
                              f"status_line = {status_line}, " + 
                              f"parsed status_word = {status_word}")
        if status_word in ["PD","CF","S"] :
            return JobStatus.waiting
        elif status_word in ["R"] :
            return JobStatus.running
        elif status_word in ["CG"] :
            return JobStatus.completing
        elif status_word in ["C","E","K","BF","CA","CD","F","NF","PR","SE","ST","TO"] :
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

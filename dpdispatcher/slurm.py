import os,sys,time,random,uuid
from collections import defaultdict

from dpdispatcher.JobStatus import JobStatus
from dpdispatcher import dlog
# from dpdispatcher.submission import Resources
from dpdispatcher.batch import Batch

slurm_script_template="""\
{slurm_script_header}
{slurm_script_env}
{slurm_script_command}
{slurm_script_end}
"""

slurm_script_header_template="""\
#!/bin/bash -l
{slurm_nodes_line}
{slurm_ntasks_per_node_line}
{slurm_number_gpu_line}
{slurm_partition_line}
"""

slurm_script_env_template="""
export REMOTE_ROOT={remote_root}
test $? -ne 0 && exit 1
"""

slurm_script_command_template="""
cd $REMOTE_ROOT
cd {task_work_path}
test $? -ne 0 && exit 1
if [ ! -f {task_tag_finished} ] ;then
  {command_env} {command}  1>> {outlog} 2>> {errlog} 
  if test $? -ne 0; then touch {task_tag_finished}; fi
  touch {task_tag_finished}
fi &
"""

slurm_script_end_template="""

cd $REMOTE_ROOT
test $? -ne 0 && exit 1

wait

touch {job_tag_finished}
"""

slurm_script_wait="""
wait
"""

default_slurm_sbatch_dict={
#     'nodes': 1,
#     'tasks_per_node':4,
#     'gpus_per_node':0,
#     'partition': 'GPUV100',
    'cpus_per_task':1,
    'time': "120:0:0",
    'mem': "8G",
    'exclude':[]
}

# class SlurmResources(object):
#     def __init__(self,
#                 resources,
#                 slurm_sbatch_dict):
#         self.resources = resources
#         self.group_size = resources.group_size
#         self.slurm_sbatch_dict = slurm_sbatch_dict

#     def serialize(self):
#         slurm_resources_dict={}
#         slurm_resources_dict['resources'] = self.resources.serialize()
#         slurm_resources_dict['slurm_sbatch_dict'] = self.slurm_sbatch_dict
#         return slurm_resources_dict

#     @classmethod
#     def deserialize(cls, slurm_resources_dict):
#         resources =  Resources.deserialize(slurm_resources_dict['resources'])
#         slurm_sbatch_dict = slurm_resources_dict['slurm_sbatch_dict']
#         slurm_resources = cls(resources=resources, slurm_sbatch_dict=slurm_sbatch_dict)
#         return slurm_resources

class Slurm(Batch):
    def gen_script(self, job):
        # if type(job.resources) is SlurmResources:
        #     resources = job.resources.resources
        #     slurm_sbatch_dict = job.resources.slurm_sbatch_dict
        # elif type(job.resources) is Resources:
        #     resources = job.resources
        #     slurm_sbatch_dict = {}
        # else:
        #     raise RuntimeError('type job.resource error')
        resources = job.resources
        slurm_sbatch_dict = resources.kwargs.get('slurm_sbatch_dict', {})
        
        script_header_dict = {}
        script_header_dict['slurm_nodes_line']="#SBATCH --nodes {number_node}".format(number_node=resources.number_node)
        script_header_dict['slurm_ntasks_per_node_line']="#SBATCH --ntasks-per-node {cpu_per_node}".format(cpu_per_node=resources.cpu_per_node)
        script_header_dict['slurm_number_gpu_line']="#SBATCH --gres=gpu:{gpu_per_node}".format(gpu_per_node=resources.gpu_per_node)
        script_header_dict['slurm_partition_line']="#SBATCH --partition {queue_name}".format(queue_name=resources.queue_name)
        slurm_script_header = slurm_script_header_template.format(**script_header_dict) 

        for k,v in slurm_sbatch_dict.items():
            line = "#SBATCH --{key} {value}\n".format(key=k.replace('_', '-'), value=str(v))
            slurm_script_header += line

        script_env_dict = {}
        script_env_dict['remote_root'] = self.context.remote_root

        slurm_script_env = slurm_script_env_template.format(**script_env_dict)

        slurm_script_command = ""
        
        for task in job.job_task_list:
            command_env = ""     
            task_need_resources = task.task_need_resources
            if resources.in_use+task_need_resources > 1:
                slurm_script_command += slurm_script_wait
                resources.in_use = 0

            command_env += self.get_command_env_cuda_devices(resources=resources, task=task)

            command_env += "export DP_TASK_NEED_RESOURCES={task_need_resources} ;".format(task_need_resources=task.task_need_resources)

            task_tag_finished = task.task_hash + '_task_tag_finished'

            temp_slurm_script_command = slurm_script_command_template.format(command_env=command_env, 
                task_work_path=task.task_work_path, command=task.command, task_tag_finished=task_tag_finished,
                outlog=task.outlog, errlog=task.errlog)

            slurm_script_command+=temp_slurm_script_command
            

        job_tag_finished = job.job_hash + '_job_tag_finished'
        slurm_script_end = slurm_script_end_template.format(job_tag_finished=job_tag_finished)

        slurm_script = slurm_script_template.format(
                          slurm_script_header=slurm_script_header,
                          slurm_script_env=slurm_script_env,
                          slurm_script_command=slurm_script_command,
                          slurm_script_end=slurm_script_end)
        return slurm_script
    
    def do_submit(self, job):
        script_file_name = job.script_file_name
        script_str = self.gen_script(job)
        job_id_name = job.job_hash + '_job_id'
        # script_str = self.sub_script(job_dirs, cmd, args=args, resources=resources, outlog=outlog, errlog=errlog)
        self.context.write_file(fname=script_file_name, write_str=script_str)
        # self.context.write_file(fname=os.path.join(self.context.submission.work_base, script_file_name), write_str=script_str)
        stdin, stdout, stderr = self.context.block_checkcall('cd %s && %s %s' % (self.context.remote_root, 'sbatch', script_file_name))
        subret = (stdout.readlines())
        job_id = subret[0].split()[-1]
        self.context.write_file(job_id_name, job_id)        
        return job_id

    def default_resources(self, resources) :
        pass
    
    def check_status(self, job):
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
            else :
                raise RuntimeError\
                    ("status command squeue fails to execute\nerror message:%s\nreturn code %d\n" % (err_str, ret))
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
            if self.check_finish_tag(job) :
                return JobStatus.finished
            else :
                return JobStatus.terminated
        else :
            return JobStatus.unknown                    
        
    def check_finish_tag(self, job):
        job_tag_finished = job.job_hash + '_job_tag_finished'
        print('job finished: ',job.job_id, job_tag_finished)
        return self.context.check_file_exists(job_tag_finished)

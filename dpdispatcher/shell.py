import os,sys,time,random,uuid
import psutil

from dpdispatcher.JobStatus import JobStatus
from dpdispatcher import dlog
from dpdispatcher.batch import Batch

shell_script_template="""
{shell_script_header}
{shell_script_env}
{shell_script_command}
{shell_script_end}

"""

shell_script_header_template="""
#!/bin/bash -l
export REMOTE_ROOT={remote_root}
"""

shell_script_env_template="""
cd $REMOTE_ROOT
test $? -ne 0 && exit 1
"""

shell_script_command_template="""
cd $REMOTE_ROOT
cd {task_work_path}
test $? -ne 0 && exit 1
if [ ! -f {task_tag_finished} ] ;then
  {command_env} {command}  1>> {outlog} 2>> {errlog} 
  if test $? -ne 0; then touch {task_tag_finished}; fi
  touch {task_tag_finished}
fi &
"""

shell_script_end_template="""
cd $REMOTE_ROOT

test $? -ne 0 && exit 1

wait

touch {job_tag_finished}
"""

shell_script_wait="""
wait
"""

class Shell(Batch):
    def gen_script(self, job):
        resources = job.resources
        script_header_dict= {}
        script_header_dict['remote_root']=self.context.remote_root
        # script_header_dict['select_node_line']="#PBS -l select={number_node}:ncpus={cpu_per_node}:ngpus={gpu_per_node}".format(
        #     number_node=resources.number_node, cpu_per_node=resources.cpu_per_node, gpu_per_node=resources.gpu_per_node)
        # script_header_dict['walltime_line']="#PBS -l walltime=120:0:0"
        # script_header_dict['queue_name_line']="#PBS -q {queue_name}".format(queue_name=resources.queue_name)

        shell_script_header = shell_script_header_template.format(**script_header_dict) 

        shell_script_env = shell_script_env_template.format()
      
        shell_script_command = ""
        
        resources_in_use=0
        for task in job.job_task_list:
            command_env = ""     
            task_need_resources_mod = task.task_need_resources
            if resources_in_use+task_need_resources_mod > 1:
               shell_script_command += shell_script_wait
               resources_in_use = 0

            command_env += self.get_command_env_cuda_devices(resources=resources, task=task)

            command_env = "export {str_CUDA_VISIBLE_DEVICES} ;".format(str_CUDA_VISIBLE_DEVICES=str_CUDA_VISIBLE_DEVICES)
               
            command_env += "export DP_TASK_NEED_RESOURCES={task_need_resources} ;".format(task_need_resources=task.task_need_resources)

            task_tag_finished = task.task_hash + '_task_tag_finished'

            temp_shell_script_command = shell_script_command_template.format(command_env=command_env, 
                 task_work_path=task.task_work_path, command=task.command, task_tag_finished=task_tag_finished,
                 outlog=task.outlog, errlog=task.errlog)

            shell_script_command+=temp_shell_script_command
        
        job_tag_finished = job.job_hash + '_job_tag_finished'
        shell_script_end = shell_script_end_template.format(job_tag_finished=job_tag_finished)

        shell_script = shell_script_template.format(
                          shell_script_header=shell_script_header,
                          shell_script_env=shell_script_env,
                          shell_script_command=shell_script_command,
                          shell_script_end=shell_script_end)
        return shell_script
    
    def do_submit(self, job):
        script_str = self.gen_script(job) 
        script_file_name = job.script_file_name
        job_id_name = job.job_hash + '_job_id'
        self.context.write_file(fname=script_file_name, write_str=script_str)
        proc = self.context.call('cd %s && exec bash %s' % (self.context.remote_root, script_file_name))

        job_id = int(proc.pid)
        print('shell.do_submit.job_id', job_id)
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
        print('shell.check_status.job_id', job_id)
        job_state = JobStatus.unknown
        if job_id == "" :
            return JobStatus.unsubmitted

        if_job_exists = psutil.pid_exists(pid=job_id)
        if self.check_finish_tag(job=job):
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
        print('job finished: ',job.job_id, job_tag_finished)
        return self.context.check_file_exists(job_tag_finished)

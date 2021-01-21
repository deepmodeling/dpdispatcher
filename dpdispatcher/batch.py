
import os,sys,time,random,uuid

from dpdispatcher.JobStatus import JobStatus
from dpdispatcher import dlog
class Batch(object) :
    def __init__ (self,
                  context):
        self.context = context
        # self.uuid_names = uuid_names
        self.upload_tag_name = '%s_job_tag_upload' % self.context.job_uuid
        self.finish_tag_name = '%s_job_tag_finished' % self.context.job_uuid
        self.sub_script_name = '%s.sub' % self.context.job_uuid
        self.job_id_name = '%s_job_id' % self.context.job_uuid

    def check_status(self, job) :
        raise NotImplementedError('abstract method check_status should be implemented by derived class')        
        
    def default_resources(self, res) :
        raise NotImplementedError('abstract method sub_script_head should be implemented by derived class')        

    def sub_script_head(self, res) :
        raise NotImplementedError('abstract method sub_script_head should be implemented by derived class')        

    def sub_script_cmd(self, res):
        raise NotImplementedError('abstract method sub_script_cmd should be implemented by derived class')        

    def do_submit(self, job):
        '''
        submit a single job, assuming that no job is running there.
        '''
        raise NotImplementedError('abstract method do_submit should be implemented by derived class')        

    def gen_script(self, **kwargs):
        raise NotImplementedError('abstract method gen_script should be implemented by derived class')        

    def check_finish_tag(self, **kwargs):
        raise NotImplementedError('abstract method check_finish_tag should be implemented by derived class')        

    def get_command_env_cuda_devices(self, resources, task):
        task_need_resources = task.task_need_resources
        command_env=""
        if resources.if_cuda_multi_devices is True:
            min_CUDA_VISIBLE_DEVICES = int(resources.in_use*resources.gpu_per_node)
            max_CUDA_VISIBLE_DEVICES = int((resources.in_use + task_need_resources)*resources.gpu_per_node-0.000000001)
            list_CUDA_VISIBLE_DEVICES  = list(range(min_CUDA_VISIBLE_DEVICES, max_CUDA_VISIBLE_DEVICES+1))
            if len(list_CUDA_VISIBLE_DEVICES) == 0:
                raise RuntimeError("list_CUDA_VISIBLE_DEVICES can not be empty")

            command_env+="export CUDA_VISIBLE_DEVICES="
            for ii in list_CUDA_VISIBLE_DEVICES:
                command_env+="{ii},".format(ii=ii) 
            command_env+=" ;"
        return command_env




import os,sys,time,random,uuid

from dpdispatcher.JobStatus import JobStatus
from dpdispatcher import dlog
class Batch(object) :
    def __init__ (self,
                  context):
        self.context = context
        # self.uuid_names = uuid_names
        self.upload_tag_name = '%s_tag_upload' % self.context.job_uuid
        self.finish_tag_name = '%s_tag_finished' % self.context.job_uuid
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

    def gen_script(self):
        raise NotImplementedError('abstract method gen_script should be implemented by derived class')        

    def check_finish_tag(self) :
        raise NotImplementedError('abstract method check_finish_tag should be implemented by derived class')        

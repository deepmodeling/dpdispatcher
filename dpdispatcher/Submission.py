
import os,sys,time,random,uuid,json

from dpdispatcher.JobStatus import JobStatus
from dpdispatcher import dlog

class Submission(object):
    def __init__(self,
                work_base,
                resources,
                forward_common_files,
                backward_common_files,
                context,
                batch):
        # self.submission_list = submission_list
        self.work_base = work_base
        self.resources = resources
        self.forward_common_files= forward_common_files
        self.backward_common_files = backward_common_files
        self.context = context
        self.batch = batch


        self.uuid = "<to be implemented>"
        self.belonging_tasks = []
        self.belonging_jobs = []

    def register_tasks(self, task):
        self.belonging_tasks.append(task)

    def register_task_list(self, task_list):
        self.belonging_tasks.extend(task_list)
            
    def run_jobs(self):
        self.submit_jobs()
        while not self.check_all_finished():
            time.sleep(20)
        return True

    def submit_jobs(self):
        for job in self.belonging_jobs:        
            job.submit()

    def check_all_finished(self):
        if all(job.state == JobStatus.finished for job in self.belonging_jobs):
            return True
        else:
            return False

    def generate_jobs(self):
        group_size = self.resources.get('group_size', 1)
        if group_size < 1 or type(group_size) is not int:
            raise RuntimeError('group_size must be a positive number')   
        task_num = len(self.belonging_tasks)
        if task_num == 0:
            raise RuntimeError("submission must have at least 1 task")
        random.seed(str(self.work_base))
        random_task_index = list(range(task_num))
        random.shuffle(random_task_index)
        random_task_index_ll = [random_task_index[ii:ii+group_size] for ii in range(0,task_num,group_size)]
        
        for ii in random_task_index_ll:
            task_list = [ self.belonging_tasks[jj] for jj in ii ]
            job = Job(task_list=task_list, batch=self.batch)
            self.belonging_jobs.append(job)
    
    def dump_fo_file(self, record_file_path):
        pass

    def recover_jobs_from_file(self, record_file_path):
        for ii in json.load(record_file_path):
            job = Job.deserialize(ii)
            self.belonging_jobs.append(job)
            self.register_task_list(job.task_list)

class Task(object):
    def __init__(self,
                command,
                task_work_path,
                forward_files,
                backward_files,
                outlog='log',
                errlog='err'):

        self.command = command
        self.task_work_path = task_work_path
        self.forward_files = forward_files
        self.backward_files = backward_files
        self.outlog = outlog
        self.errlog = errlog

        self.uuid = "<to be implemented>"
        # self.uuid = 

    @classmethod
    def deserialize(cls, task_dict):
        task=Task(**task_dict)
        return task

    def serialize(self):
        task_dict={}
        task_dict['command'] = str(self.command)
        return task_dict


class Job(object):
    def __init__(self,
                task_list,
                batch=None):
        self.task_list = task_list
        # self.script_file_name = script_file_name
        self.script_file_name = uuid.uuid4() + '.sub'

        self.fail_count = 0
        self.uuid = "<to be implemented>"

    @classmethod
    def deserialize(cls, job_dict, batch=None):
        task_list = []
        job = Job(task_list=task_list, batch=batch)
        return job
     
    def serialize(self):
        job_dict = {}
        job_dict['job_state'] = 1
        job_dict['fail_count'] = 0
        return job_dict

    def register_job_id(self, job_id):
        self.job_id = job_id
    
    def submit(self):
        job_id = self.batch.do_submit(self)
        self.register_job_id(job_id)

    def check_state(self):
        return self.batch.check(self)


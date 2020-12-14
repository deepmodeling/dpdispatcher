
import os,sys,time,random,uuid,json
from dpdispatcher.JobStatus import JobStatus
from dpdispatcher import dlog

class Submission(object):
    """submission represents the whole workplace, all the tasks to be calculated
    Parameters
    ----------
    work_base : str
        path-like, the base directory of the local tasks
    resources : Resources
        the machine resources (cpu or gpu) used to generate the slurm/pbs script
    forward_common_files: list
        the common files to be uploaded to other computers before the jobs begin
    backward_common_files: list 
        the common files to be downloaded from other computers after the jobs finish
    batch : Batch
        Batch object to execute the jobs
    """
    def __init__(self,
                work_base,
                resources,
                forward_common_files,
                backward_common_files,
                batch=None):
        # self.submission_list = submission_list
        self.work_base = work_base
        self.resources = resources
        self.forward_common_files= forward_common_files
        self.backward_common_files = backward_common_files
        self.batch = batch


        self.uuid = "<to be implemented>"
        self.belonging_tasks = []
        self.belonging_jobs = []

    def register_task(self, task):
        self.belonging_tasks.append(task)

    def register_task_list(self, task_list):
        self.belonging_tasks.extend(task_list)
    
    def band_batch(self,batch):
        self.batch = batch
            
    def run_submission(self):
        self.upload_jobs()
        self.submit_submission()
        while not self.check_all_finished():
            # print(job, job.state)
            time.sleep(20)
        return True

    def submit_submission(self):
        for job in self.belonging_jobs:        
            job.submit_job()

    def check_all_finished(self):
        if all(job.state == JobStatus.finished for job in self.belonging_jobs):
            return True
        else:
            return False

    def generate_jobs(self):
        """after the the tasks register to the self.belonging_tasks, this method generate the
        jobs and add these jobs to self.beloinging_jobs
        """
        group_size = self.resources.group_size
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
            job_task_list = [ self.belonging_tasks[jj] for jj in ii ]
            job = Job(job_task_list=job_task_list, job_work_base=self.work_base, batch=self.batch, resources=self.resources)
            self.belonging_jobs.append(job)

    def upload_jobs(self):
        self.batch.context.upload(self)
    
    def download_jobs(self):
        pass
    
    def dump_fo_file(self, record_file_path):
        pass

    def recover_jobs_from_file(self, record_file_path):
        for ii in json.load(record_file_path):
            job = Job.deserialize(ii)
            self.belonging_jobs.append(job)
            self.register_task_list(job.job_task_list)

class Task(object):
    def __init__(self,
                command,
                task_work_path,
                forward_files,
                backward_files,
                outlog='log',
                errlog='err',
                task_need_resources=None):

        self.command = command
        self.task_work_path = task_work_path
        self.forward_files = forward_files
        self.backward_files = backward_files
        self.outlog = outlog
        self.errlog = errlog

        self.uuid = "<to be implemented>"
        self.task_need_resources="<to be completed in the future>"
        # self.uuid = 

    def __repr__(self):
        return str(self.serialize())

    @classmethod
    def deserialize(cls, task_dict):
        task=Task(**task_dict)
        return task

    def serialize(self):
        task_dict={}
        task_dict['command'] = str(self.command)
        task_dict['task_work_path'] = str(self.task_work_path)
        task_dict['forward_files'] = str(self.forward_files)
        task_dict['backward_files'] = str(self.backward_files)
        task_dict['outlog'] = str(self.outlog)
        task_dict['errlog'] = str(self.errlog)
        return task_dict


class Job(object):
    def __init__(self,
                job_task_list,
                job_work_base,
                resources,
                batch=None):
        self.job_task_list = job_task_list
        self.job_work_base = job_work_base
        self.resources = resources
        self.batch = batch
        # self.script_file_name = script_file_name
        self.job_uuid = str(uuid.uuid4()) 
        self.script_file_name = self.job_uuid + '.sub'

        self.fail_count = 0
        # self.uuid = "<to be implemented>"

    def __repr__(self):
        return str(self.serialize())

    @classmethod
    def deserialize(cls, job_dict, batch=None):
        task_list = []
        job = Job(task_list=task_list, batch=batch)
        return job

    @property
    def state(self):
        state=self.batch.check_status(self)
        return state
     
    def serialize(self):
        job_dict = {}
        job_dict['job_state'] = 1
        job_dict['fail_count'] = 0
        job_dict['resources'] = self.resources
        job_dict['job_task_list'] = []
        job_dict['job_work_base'] = self.job_work_base
        for task in self.job_task_list:
            job_dict['job_task_list'].append(task.serialize())
        return {self.script_file_name:job_dict}

    def register_job_id(self, job_id):
        self.job_id = job_id
    
    def submit_job(self):
        job_id = self.batch.do_submit(self)
        self.register_job_id(job_id)

    # def check_state(self):
    #     return self.batch.check_status(self)

class Resources(object):
    def __init__(self,
                 number_node,
                 cpu_per_node,
                 gpu_per_node,
                 queue_name,
                 group_size=1):
        self.number_node = number_node
        self.cpu_per_node = cpu_per_node
        self.gpu_per_node = gpu_per_node
        self.queue_name = queue_name
        self.group_size = group_size
        
    def serialize(self):
        resources_dict = {}
        resources_dict['number_node'] = self.numbder_node
        resources_dict['cpu_per_node'] = self.cpu_per_node
        resources_dict['gpu_per_node'] = self.gpu_per_node
        resources_dict['queue_name'] = self.queue_name
        resources_dict['group_size'] = self.group_size
        return resources_dict



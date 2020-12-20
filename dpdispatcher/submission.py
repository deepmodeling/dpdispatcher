
import os,sys,time,random,uuid,json
from dpdispatcher.JobStatus import JobStatus
from dpdispatcher import dlog
from hashlib import sha1

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
                forward_common_files=[],
                backward_common_files=[],
                batch=None):
        # self.submission_list = submission_list
        self.work_base = work_base
        self.resources = resources
        self.forward_common_files= forward_common_files
        self.backward_common_files = backward_common_files


        self.submission_hash = None
        self.uuid = "<to be implemented>"
        self.belonging_tasks = []
        self.belonging_jobs = []
    
        self.bind_batch(batch)

    def __repr__(self):
        return str(self.serialize())

    def __eq__(self, other):
       #  print('submission.__eq__() self', self.serialize(), )
       #  print('submission.__eq__() other', other.serialize())
        return self.serialize(if_static=True) == other.serialize(if_static=True)    
    
    @classmethod
    def deserialize(cls, submission_dict, batch=None):
        submission = cls(work_base=submission_dict['work_base'],
            resources=Resources.deserialize(resources_dict=submission_dict['resources']),
            forward_common_files=submission_dict['forward_common_files'],
            backward_common_files=submission_dict['backward_common_files'])
        submission.belonging_jobs = [Job.deserialize(job_dict=job_dict) for job_dict in submission_dict['belonging_jobs']]
        submission.submission_hash = submission.get_hash()
        submission.bind_batch(batch=batch)
        return submission

    def serialize(self, if_static=False):
        submission_dict = {}
        submission_dict['work_base'] = self.work_base
        submission_dict['resources'] = self.resources.serialize()
        submission_dict['forward_common_files'] = self.forward_common_files
        submission_dict['backward_common_files'] = self.backward_common_files
        submission_dict['belonging_jobs'] = [ job.serialize(if_static=if_static) for job in self.belonging_jobs]
        # print('&&&&&&&&', submission_dict['belonging_jobs'] )
        return submission_dict
    
    # @property
    def get_hash(self):
        return sha1(str(self.serialize(if_static=True)).encode('utf-8')).hexdigest() 
        # return self.sha1(str(self.serialize(if_static=True)).encode('utf-8')).hexdigest() 

    def register_task(self, task):
        self.belonging_tasks.append(task)

    def register_task_list(self, task_list):
        self.belonging_tasks.extend(task_list)
    
    def bind_batch(self, batch):
        self.submission_hash = self.get_hash()
        self.batch = batch
        for job in self.belonging_jobs:
            job.batch = batch
        if batch is not None:
            self.batch.context.bind_submission(self)
        return self

            
    def run_submission(self):
        """main method the 
        """
        self.try_recover_from_json()
        # print('submission.run_submission:self', self)
        if self.check_all_finished():
            pass
            # print('recover success submission.run_submission: recover all finished 1', self)
        else:
            # self.update_submission_state()
            self.upload_jobs()
            self.update_submission_state()
            self.submission_to_json
        #     self.submit_submission()
        
        while not self.check_all_finished():
            # if_dump_to_json = self.update_submission_state()
            #     self.submission_to_json()
            try: 
                time.sleep(10)
            except KeyboardInterrupt as e:
                self.submission_to_json()
                print('<<<<<<dpdispatcher<<<<<<KeyboardInterrupt<<<<<<exit<<<<<<')
                print(self.serialize())
                print('>>>>>>dpdispatcher>>>>>>KeyboardInterrupt>>>>>>exit>>>>>>')
                exit(1)
            except SystemExit as e:
                self.submission_to_json()
                print('<<<<<<dpdispatcher<<<<<<SystemExit<<<<<<exit<<<<<<')
                print(self.serialize())
                print('>>>>>>dpdispatcher>>>>>>SystemExit>>>>>>exit>>>>>>')
                exit(2)
            except Exception as e:
                self.submission_to_json()
                print('<<<<<<dpdispatcher<<<<<<{e}<<<<<<exit<<<<<<'.format(e=e))
                print(self.serialize())
                print('>>>>>>dpdispatcher>>>>>>{e}>>>>>>exit>>>>>>'.format(e=e))
                exit(3)
            finally:
                pass
      
        self.update_submission_state()
        self.submission_to_json()
        self.download_jobs()
        return True
    
    def get_submission_state(self):
        for job in self.belonging_jobs:
            job.get_job_state()
        # self.submission_to_json()

    def update_submission_state(self):
        for job in self.belonging_jobs:
            job.update_job_state()

    def submit_submission(self):
        for job in self.belonging_jobs:        
            job.submit_job()
        self.get_submission_state()

    def check_all_finished(self):
        self.get_submission_state()
        # print('debug:***', [job.job_state for job in self.belonging_jobs])
        # print('debug:***', [job for job in self.belonging_jobs])
        if any( (job.job_state in  [JobStatus.terminated, JobStatus.unknown] ) for job in self.belonging_jobs):
            self.submission_to_json()
        if any( (job.job_state in  [JobStatus.running, JobStatus.waiting, JobStatus.unsubmitted, JobStatus.completing, JobStatus.terminated, JobStatus.unknown] ) for job in self.belonging_jobs):
            return False
        else:
            return True

    def generate_jobs(self):
        """
        after the the tasks register to the self.belonging_tasks, this method generate the
        jobs and add these jobs to self.belonging_jobs
        """
        group_size = self.resources.group_size
        if group_size < 1 or type(group_size) is not int:
            raise RuntimeError('group_size must be a positive number')   
        task_num = len(self.belonging_tasks)
        if task_num == 0:
            raise RuntimeError("submission must have at least 1 task")
        random.seed(42)
        random_task_index = list(range(task_num))
        random.shuffle(random_task_index)
        random_task_index_ll = [random_task_index[ii:ii+group_size] for ii in range(0,task_num,group_size)]
        
        for ii in random_task_index_ll:
            job_task_list = [ self.belonging_tasks[jj] for jj in ii ]
            job = Job(job_task_list=job_task_list, batch=self.batch, resources=self.resources)
            self.belonging_jobs.append(job)

        self.submission_hash = self.get_hash()
        

    def upload_jobs(self):
        self.batch.context.upload(self)
    
    def download_jobs(self):
        self.batch.context.download(self)
        # for job in self.belonging_jobs:
        #     job.tag_finished()
        # self.batch.context.write_file(self.batch.finish_tag_name, write_str="")
    
    def submission_to_json(self):
        # print('~~~~,~~~', self.serialize())
        self.get_submission_state()
        write_str = json.dumps(self.serialize(), indent=2, default=str)
        self.batch.context.write_file('submission.json', write_str=write_str)
    
    @classmethod
    def submission_from_json(cls, json_file_name='submission.json'):
        with open(json_file_name, 'r') as f:
            submission_dict = json.load(f)
        # submission_dict = batch.context.read_file(json_file_name)
        submission = cls.deserialize(submission_dict=submission_dict, batch=None) 
        return submission
   
    def try_recover_from_json(self):
        if_recover = self.batch.context.check_file_exists('submission.json')
        # print('submission.try_recover_from_json if_recover', if_recover)
        submission = None
        submission_dict = {}
        if if_recover :
            submission_dict_str = self.batch.context.read_file(fname='submission.json')
            submission_dict = json.loads(submission_dict_str)
            # print('submission.try_recover_from_json submission_dict', submission_dict)
            submission = Submission.deserialize(submission_dict=submission_dict)
            # print('-------submission.try_recover_from_json submission', submission)
            if self == submission:
                self.belonging_jobs = submission.belonging_jobs
                self.bind_batch(batch=self.batch)
                self = submission.bind_batch(batch=self.batch)
                # print('!!!!!!!!!submission.try_recover_from_json submission', self)
                # self.submission_hash = self.get_hash()
            else:
                raise RuntimeError("recover fail")
        # return submission

class Task(object):
    """a task is a sequential command to be executed, as well as its files to transmit forward and backward.
    Parameters
    ----------
    command : str
        the command to be executed.
    task_work_path : path-like
        the directory of each file where the files are dependent on.
    forward_files : list of path-like 
        the files to be transmitted to other location before the calculation begins
    backward_files : list of path-like 
        the files to be transmitted from other location after the calculation finished
    log : str
        the files to be transmitted from other location after the calculation finished
    err : str
        the files to be transmitted from other location after the calculation finished
    task_need_resources : float number, between 0 to 1.
        the reources need to execute the task. For example, if task_need_resources==0.33, then 3 tasks will run in parallel
    """
    def __init__(self,
                command,
                task_work_path,
                forward_files=[],
                backward_files=[],
                outlog='log',
                errlog='err',
                *,
                task_need_resources=1):

        self.command = command
        self.task_work_path = task_work_path
        self.forward_files = forward_files
        self.backward_files = backward_files
        self.outlog = outlog
        self.errlog = errlog

        self.task_need_resources = task_need_resources

        self.uuid = "<to be implemented>"
        # self.task_need_resources="<to be completed in the future>"
        # self.uuid = 

    def __repr__(self):
        return str(self.serialize())
    
    def __eq__(self, other):
        return self.serialize() == other.serialize()

    @classmethod
    def deserialize(cls, task_dict):
        task=cls(**task_dict)
        return task

    def serialize(self):
        task_dict={}
        task_dict['command'] = self.command
        task_dict['task_work_path'] = self.task_work_path
        task_dict['forward_files'] = self.forward_files
        task_dict['backward_files'] = self.backward_files
        task_dict['outlog'] = self.outlog
        task_dict['errlog'] = self.errlog
        task_dict['task_need_resources'] = self.task_need_resources
        return task_dict

class Job(object):
    """Job is generated by Submission represnting a serials of command. 
    Each Job can generate a HPC script to submit the job in PBS or Slurm job scheduler system. 
    Parameters
    ----------
    job_task_liste : list of Task
        the tasks belong to the job
    resources : Resources
        the machine resources. Passed from Submission when instantiating.
    batch : Batch
        Batch object to execute the job. Passed from Submission when instantiating.
    """
    def __init__(self,
                job_task_list,
                # job_work_base,
                *,
                resources,
                batch=None,
                ):
        self.job_task_list = job_task_list
        # self.job_work_base = job_work_base
        self.resources = resources
        self.batch = batch
        
        self.job_state = None # JobStatus.unsubmitted
        self.job_id = ""
        self.fail_count = -1

        # self.job_hash = self.get_hash()
        self.job_hash = self.get_hash()
        self.script_file_name = self.job_hash+ '.sub'


    def __repr__(self):
        return str(self.serialize())
    
    def __eq__(self, other):
        return self.serialize(if_static=True) == other.serialize(if_static=True)

    @classmethod
    def deserialize(cls, job_dict, batch=None):
        job_hash = list(job_dict.keys())[0]
        job_task_list = [Task.deserialize(task_dict) for task_dict in job_dict[job_hash]['job_task_list']]
        job = Job(job_task_list=job_task_list, 
           #  job_work_base=job_dict[job_hash]['job_work_base'],
            resources=Resources.deserialize(resources_dict=job_dict[job_hash]['resources']),
            batch=batch)

        # job.job_runtime_info=job_dict[job_hash]['job_runtime_info'] 
        job.job_state = job_dict[job_hash]['job_state']
        job.job_id = job_dict[job_hash]['job_id']
        job.fail_count = job_dict[job_hash]['fail_count']
        return job

    def get_job_state(self):
        job_state = self.batch.check_status(self)
        self.job_state = job_state

    def update_job_state(self):
        job_state = self.job_state

        if job_state == JobStatus.unknown:
            raise RuntimeError("job_state for job {job} is unknown".format(job=self))

        if job_state == JobStatus.terminated:
            print("job: {job_hash} terminated; restarting job".format(job_hash=self.job_hash))
            if self.fail_count > 5:
                raise RuntimeError("job:job {job} failed 5 times".format(job=self))
            self.fail_count += 1
            self.submit_job()
            self.get_job_state()

        if job_state == JobStatus.unsubmitted:
            if self.fail_count > 5:
                raise RuntimeError("job:job {job} failed 5 times".format(job=self))
            self.fail_count += 1
            self.submit_job()
            print("job: {job_hash} submit; job_id is {job_id}".format(job_hash=self.job_hash, job_id=self.job_id))
            self.get_job_state()
    
    def get_hash(self):
        return str(list(self.serialize(if_static=True).keys())[0])

    def serialize(self, if_static=False):
        job_content_dict = {}
        # for task in self.job_task_list:
        job_content_dict['job_task_list'] = [ task.serialize() for task in self.job_task_list ] 
        job_content_dict['resources'] = self.resources.serialize()
        # job_content_dict['job_work_base'] = self.job_work_base
        job_hash = sha1(str(job_content_dict).encode('utf-8')).hexdigest() 
        if not if_static:
            job_content_dict['job_state'] = self.job_state
            job_content_dict['job_id'] = self.job_id
            job_content_dict['fail_count'] = self.fail_count
         
        return {job_hash: job_content_dict}

    def register_job_id(self, job_id):
        self.job_id = job_id
    
    def submit_job(self):
        job_id = self.batch.do_submit(self)
        self.register_job_id(job_id)

    def job_to_json(self):
        # print('~~~~,~~~', self.serialize())
        write_str = json.dumps(self.serialize(), indent=2, default=str)
        self.batch.context.write_file(self.job_hash + '_job.json', write_str=write_str)
    


class Resources(object):
    """Resources is used to describe the machine resources we need to do calculations.
    Parameters
    ----------
    number_node : int
        the number of node we need to do the calculation.
    cpu_per_node : int
        cpu numbers of each node.
    gpu_per_node : int
        gpu numbers of each node.
    queue_name : str
        the job queue name of slurm or pbs job scheduler system.
    """
    def __init__(self,
                 number_node,
                 cpu_per_node,
                 gpu_per_node,
                 queue_name,
                 group_size=1,
                 *,
                 if_cuda_multi_devices=False):
        self.number_node = number_node
        self.cpu_per_node = cpu_per_node
        self.gpu_per_node = gpu_per_node
        self.queue_name = queue_name
        self.group_size = group_size
        
        self.if_cuda_multi_devices = if_cuda_multi_devices
        # if self.gpu_per_node > 1:
            
        if self.if_cuda_multi_devices is True:
            if gpu_per_node < 1:
                raise RuntimeError("gpu_per_node can not be smaller than 1 when if_cuda_multi_devices is True")
            if number_node != 1:
                raise RuntimeError("number_node must be 1 when if_cuda_multi_devices is True")

    def __eq__(self, other):
        return self.serialize() == other.serialize()
        
    def serialize(self):
        resources_dict = {}
        resources_dict['number_node'] = self.number_node
        resources_dict['cpu_per_node'] = self.cpu_per_node
        resources_dict['gpu_per_node'] = self.gpu_per_node
        resources_dict['queue_name'] = self.queue_name
        resources_dict['group_size'] = self.group_size
        resources_dict['if_cuda_multi_devices'] = self.if_cuda_multi_devices
        return resources_dict
     
    @classmethod
    def deserialize(cls, resources_dict):
        resources = cls(**resources_dict)
        return resources


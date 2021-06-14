
from dpdispatcher.ssh_context import SSHSession
import os,sys,time,random,uuid,json
from typing import Optional
import dargs
from dargs import dargs, Argument

from dpdispatcher.JobStatus import JobStatus
from dpdispatcher import dlog
from dpdispatcher.base_context import BaseContext

script_template="""\
{script_header}
{script_custom_flags}
{script_env}
{script_command}
{script_end}
"""

script_env_template="""
export REMOTE_ROOT={remote_root}
test $? -ne 0 && exit 1

{module_unload_part}
{module_load_part}
{source_files_part}
{export_envs_part}
"""

script_command_template="""
cd $REMOTE_ROOT
cd {task_work_path}
test $? -ne 0 && exit 1
if [ ! -f {task_tag_finished} ] ;then
  {command_env} ( {command} ) {log_err_part}
  if test $? -eq 0; then touch {task_tag_finished}; fi
fi &
"""

script_end_template="""
cd $REMOTE_ROOT
test $? -ne 0 && exit 1

wait

touch {job_tag_finished}
"""

class Machine(object):
    """A machine is used to handle the connection with remote machines.

    Parameters
    ----------
    context : SubClass derived from BaseContext
        The context is used to mainatin the connection with remote machine.
    """

    subclasses_dict = {}

    # def __new__(cls, batch_type, context_type, local_root='./', remote_root=None, remote_profile={}):
    #     if cls is Machine:
    #         # instance = object.__new__(batch_type, context_type, local_root, remote_root, remote_profile)
    #         subcls = cls.subclasses_dict[cls.__name__]
    #         instance = subcls.__new__(batch_type, context_type, local_root, remote_root, remote_profile)
    #     else:
    #         instance = object.__new__(cls)
    #     return instance

    # def __init__(self, batch_type, context_type, local_root='./', remote_root=None, remote_profile={}):
    #     pass

    def __init__ (self,
                context):
        self.context = context
        # self.uuid_names = uuid_names
        # self.upload_tag_name = '%s_job_tag_upload' % self.context.job_uuid
        # self.finish_tag_name = '%s_job_tag_finished' % self.context.job_uuid
        # self.sub_script_name = '%s.sub' % self.context.job_uuid
        # self.job_id_name = '%s_job_id' % self.context.job_uuid

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.subclasses_dict[cls.__name__]=cls
        # cls.subclasses.append(cls)

    @classmethod
    def load_from_json(cls, json_path):
        with open(json_path, 'r') as f:
            machine_dict = json.load(f)
        machine = cls.load_from_dict(machine_dict=machine_dict)
        return machine

    @classmethod
    def load_from_dict(cls, machine_dict):
        batch_type = machine_dict['batch_type']
        try:
            machine_class = cls.subclasses_dict[batch_type]
        except KeyError as e:
            dlong.error(f"KeyError:batch_type; cls.subclasses_dict:{cls.subclasses_dict}; batch_type:{batch_type};")
            raise e
        context = BaseContext.load_from_dict(machine_dict)
        machine = machine_class(context=context)
        return machine

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

    def gen_script(self, job):
        script_header = self.gen_script_header(job)
        script_custom_flags = self.gen_script_custom_flags_lines(job)
        script_env = self.gen_script_env(job)
        script_command = self.gen_script_command(job)
        script_end = self.gen_script_end(job)
        script = script_template.format(
            script_header=script_header,
            script_custom_flags=script_custom_flags,
            script_env=script_env,
            script_command=script_command,
            script_end=script_end
        )
        return script

    def check_if_recover(self, submission):
        submission_hash = submission.submission_hash
        submission_file_name = "{submission_hash}.json".format(submission_hash=submission_hash)
        if_recover = self.context.check_file_exists(submission_file_name)
        return if_recover

    def check_finish_tag(self, **kwargs):
        raise NotImplementedError('abstract method check_finish_tag should be implemented by derived class')        

    def gen_script_header(self, job):
        raise NotImplementedError('abstract method gen_script_header should be implemented by derived class')

    def gen_script_custom_flags_lines(self, job):
        custom_flags_lines = ""
        custom_flags = job.resources.custom_flags
        for ii in custom_flags:
            line = ii + '\n'
            custom_flags_lines += line 
        return custom_flags_lines

    def gen_script_env(self, job):
        source_files_part = ""

        module_unload_part = ""
        module_unload_list = job.resources.module_unload_list
        for ii in module_unload_list:
            module_unload_part += f"module unload {ii}\n"

        module_load_part = ""
        module_list = job.resources.module_list
        for ii in module_list:
            module_load_part += f"module load {ii}\n"
        
        source_list = job.resources.source_list
        for ii in source_list:
            line = "{ source %s; } \n" % ii
            source_files_part += line

        export_envs_part = ""
        envs = job.resources.envs
        for k,v in envs.items():
            export_envs_part += f"export {k}={v}\n"

        script_env = script_env_template.format(
            remote_root=self.context.remote_root,
            module_unload_part=module_unload_part,
            module_load_part=module_load_part,
            source_files_part=source_files_part,
            export_envs_part=export_envs_part,
        )
        return script_env

    def gen_script_command(self, job):
        script_command = ""
        resources = job.resources
        # in_para_task_num = 0
        for task in job.job_task_list:
            command_env = ""
            command_env += self.gen_command_env_cuda_devices(resources=resources)

            task_tag_finished = task.task_hash + '_task_tag_finished'

            log_err_part = ""
            if task.outlog is not None:
                log_err_part += f"1>>{task.outlog} "
            if task.errlog is not None:
                log_err_part += f"2>>{task.errlog} "

            single_script_command = script_command_template.format(command_env=command_env, 
                task_work_path=task.task_work_path, command=task.command, task_tag_finished=task_tag_finished,
                log_err_part=log_err_part)
            script_command += single_script_command

            script_command += self.gen_script_wait(resources=resources)
        return script_command

    def gen_script_end(self, job):
        job_tag_finished = job.job_hash + '_job_tag_finished'
        script_end = script_end_template.format(job_tag_finished=job_tag_finished)
        return script_end

    def gen_script_wait(self, resources):
        # if not resources.strategy.get('if_cuda_multi_devices', None):
        #     return "wait \n"
        para_deg = resources.para_deg
        resources.task_in_para += 1
        # task_need_gpus = task.task_need_gpus
        if resources.task_in_para >= para_deg:
            # pbs_script_command += pbs_script_wait
            resources.task_in_para = 0
            if resources.strategy['if_cuda_multi_devices'] is True:
                resources.gpu_in_use += 1
                if resources.gpu_in_use % resources.gpu_per_node == 0:
                    return "wait \n"
                else:
                    return ""
            return "wait \n"
        return ""

    def gen_command_env_cuda_devices(self, resources):
        # task_need_resources = task.task_need_resources
        # task_need_gpus = task_need_resources.get('task_need_gpus', 1)
        command_env = ""
        # gpu_number = resources.gpu_per_node
        # resources.gpu_in_use = 0

        if resources.strategy['if_cuda_multi_devices'] is True:
            if resources.gpu_per_node == 0:
                raise RuntimeError("resources.gpu_per_node can not be 0")
            gpu_index = resources.gpu_in_use % resources.gpu_per_node
            command_env+=f"export CUDA_VISIBLE_DEVICES={gpu_index};"
            # for ii in list_CUDA_VISIBLE_DEVICES:
            #     command_env+="{ii},".format(ii=ii) 
        return command_env

    @staticmethod
    def arginfo():
        # TODO: change the possible value of batch and context types after we refactor the code
        doc_batch_type = 'The batch job system type. Option: Slurm, PBS, LSF, Shell, DpCloudServer'
        doc_context_type = 'The connection used to remote machine. Option: LocalContext, LazyLocalContext, SSHContext， DpCloudServerContext'
        doc_local_root = 'The dir where the tasks and relating files locate. Typically the project dir.'
        doc_remote_root = 'The dir where the tasks are executed on the remote machine. Only needed when context is not lazy-local.'
        doc_remote_profile = 'The information used to maintain the connection with remote machine. Only needed when context is ssh.'
        doc_clean_asynchronously = 'Clean the remote directory asynchronously after the job finishes.'

        remote_profile_format = SSHSession.arginfo()
        remote_profile_format.name = "remote_profile"
        remote_profile_format.doc = doc_remote_profile
        machine_args = [
            Argument("batch_type", str, optional=False, doc=doc_batch_type),
            Argument("context_type", str, optional=False, doc=doc_context_type),
            # TODO: add default to local_root and remote_root after refactor the code
            Argument("local_root", str, optional=False, doc=doc_local_root),
            Argument("remote_root", str, optional=True, doc=doc_remote_root),
            remote_profile_format,
            Argument("clean_asynchronously", bool, optional=True, default=False, doc=doc_clean_asynchronously),
        ]

        machine_format = Argument("machine", dict, machine_args)
        return machine_format

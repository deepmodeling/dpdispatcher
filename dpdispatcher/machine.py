
from dpdispatcher.ssh_context import SSHSession
import json
from dargs import Argument, Variant
from typing import List
import pathlib
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
REMOTE_ROOT={remote_root}
echo 0 > $REMOTE_ROOT/{flag_if_job_task_fail}
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
  if test $? -eq 0; then touch {task_tag_finished}; else echo 1 > $REMOTE_ROOT/{flag_if_job_task_fail};fi
fi &
"""

script_end_template="""
cd $REMOTE_ROOT
test $? -ne 0 && exit 1

wait
FLAG_IF_JOB_TASK_FAIL=$(cat {flag_if_job_task_fail})
if test $FLAG_IF_JOB_TASK_FAIL -eq 0; then touch {job_tag_finished}; else exit 1;fi
"""

class Machine(object):
    """A machine is used to handle the connection with remote machines.

    Parameters
    ----------
    context : SubClass derived from BaseContext
        The context is used to mainatin the connection with remote machine.
    """

    subclasses_dict = {}
    options = set()

    def __new__(cls, *args, **kwargs):
        if cls is Machine:
            subcls = cls.subclasses_dict[kwargs['batch_type']]
            instance = subcls.__new__(subcls, *args, **kwargs)
        else:
            instance = object.__new__(cls)
        return instance

    def __init__(self,
        batch_type=None,
        context_type=None,
        local_root=None,
        remote_root=None,
        remote_profile={},
        *,
        context=None
    ):
        if context is None:
            assert isinstance(self, self.__class__.subclasses_dict[batch_type])
            context = BaseContext(
                context_type=context_type,
                local_root=local_root,
                remote_root=remote_root,
                remote_profile=remote_profile
            )
        else:
            pass
        self.bind_context(context=context)

    def bind_context(self, context):
        self.context = context

    # def __init__ (self,
    #             context):
    #     self.context = context
        # self.uuid_names = uuid_names
        # self.upload_tag_name = '%s_job_tag_upload' % self.context.job_uuid
        # self.finish_tag_name = '%s_job_tag_finished' % self.context.job_uuid
        # self.sub_script_name = '%s.sub' % self.context.job_uuid
        # self.job_id_name = '%s_job_id' % self.context.job_uuid

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.subclasses_dict[cls.__name__]=cls
        cls.subclasses_dict[cls.__name__.lower()]=cls
        cls.options.add(cls.__name__)
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
            dlog.error(f"KeyError:batch_type; cls.subclasses_dict:{cls.subclasses_dict}; batch_type:{batch_type};")
            raise e
        context = BaseContext.load_from_dict(machine_dict)
        machine = machine_class(context=context)
        return machine

    def serialize(self, if_empty_remote_profile=False):
        machine_dict = {}
        machine_dict['batch_type'] = self.__class__.__name__
        machine_dict['context_type'] = self.context.__class__.__name__
        machine_dict['local_root'] = self.context.init_local_root
        machine_dict['remote_root'] = self.context.init_remote_root
        if not if_empty_remote_profile:
            machine_dict['remote_profile'] = self.context.remote_profile
        else:
            machine_dict['remote_profile'] = {}
        return machine_dict

    def __eq__(self, other):
        return self.serialize() == other.serialize()

    @classmethod
    def deserialize(cls, machine_dict):
        machine = cls.load_from_dict(machine_dict=machine_dict)
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
        module_purge = job.resources.module_purge
        if module_purge:
            module_unload_part += "module purge\n"
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
            if isinstance(v, list):
                for each_value in v:
                    export_envs_part += f"export {k}={each_value}\n"
            else:
                export_envs_part += f"export {k}={v}\n"

        flag_if_job_task_fail = job.job_hash + '_flag_if_job_task_fail'

        script_env = script_env_template.format(
            flag_if_job_task_fail=flag_if_job_task_fail,
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

            flag_if_job_task_fail = job.job_hash + '_flag_if_job_task_fail'
            single_script_command = script_command_template.format(
                flag_if_job_task_fail=flag_if_job_task_fail,
                command_env=command_env,
                task_work_path=pathlib.PurePath(task.task_work_path).as_posix(),
                command=task.command,
                task_tag_finished=task_tag_finished,
                log_err_part=log_err_part)
            script_command += single_script_command

            script_command += self.gen_script_wait(resources=resources)
        return script_command

    def gen_script_end(self, job):
        job_tag_finished = job.job_hash + '_job_tag_finished'
        flag_if_job_task_fail = job.job_hash + '_flag_if_job_task_fail'
        script_end = script_end_template.format(
            job_tag_finished=job_tag_finished,
            flag_if_job_task_fail=flag_if_job_task_fail
        )
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

    @classmethod
    def arginfo(cls):
        # TODO: change the possible value of batch and context types after we refactor the code
        doc_batch_type = 'The batch job system type. Option: ' + ', '.join(cls.options)
        doc_context_type = 'The connection used to remote machine. Option: ' + ', '.join(BaseContext.options)
        doc_local_root = 'The dir where the tasks and relating files locate. Typically the project dir.'
        doc_remote_root = 'The dir where the tasks are executed on the remote machine. Only needed when context is not lazy-local.'
        doc_clean_asynchronously = 'Clean the remote directory asynchronously after the job finishes.'

        machine_args = [
            Argument("batch_type", str, optional=False, doc=doc_batch_type),
            # TODO: add default to local_root and remote_root after refactor the code
            Argument("local_root", str, optional=False, doc=doc_local_root),
            Argument("remote_root", str, optional=True, doc=doc_remote_root),
            Argument("clean_asynchronously", bool, optional=True, default=False, doc=doc_clean_asynchronously),
        ]

        context_variant = Variant(
            "context_type",
            [context.machine_arginfo() for context in set(BaseContext.subclasses_dict.values())],
            optional=False,
            doc=doc_context_type,
        )

        machine_format = Argument("machine", dict, machine_args, [context_variant])
        return machine_format

    @classmethod
    def resources_arginfo(cls) -> Argument:
        """Generate the resources arginfo.

        Returns
        -------
        Argument
            resources arginfo
        """
        return Argument(
            cls.__name__, dict, sub_fields=cls.resources_subfields(),
            alias=[cls.__name__.lower()]
        )

    @classmethod
    def resources_subfields(cls) -> List[Argument]:
        """Generate the resources subfields.
        
        Returns
        -------
        list[Argument]
            resources subfields
        """
        return [Argument("kwargs", dict, optional=True, doc="This field is empty for this batch.")]
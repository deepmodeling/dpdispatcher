import json
import pathlib
import shlex
from abc import ABCMeta, abstractmethod
from typing import List, Tuple

from dargs import Argument, Variant

from dpdispatcher import dlog
from dpdispatcher.base_context import BaseContext

script_template = """\
{script_header}
{script_custom_flags}
{script_env}
{script_command}
{script_end}
"""

script_env_template = """
REMOTE_ROOT=$(readlink -f {remote_root})
echo 0 > $REMOTE_ROOT/{flag_if_job_task_fail}
test $? -ne 0 && exit 1

{module_unload_part}
{module_load_part}
{source_files_part}
{export_envs_part}
{prepend_script_part}
"""

script_command_template = """
cd $REMOTE_ROOT
cd {task_work_path}
test $? -ne 0 && exit 1
if [ ! -f {task_tag_finished} ] ;then
  {command_env} ( {command} ) {log_err_part}
  if test $? -eq 0; then touch {task_tag_finished}; else echo 1 > $REMOTE_ROOT/{flag_if_job_task_fail};tail -v -c 1000 $REMOTE_ROOT/{task_work_path}/{err_file} > $REMOTE_ROOT/{last_err_file};fi
fi &
"""

script_end_template = """
cd $REMOTE_ROOT
test $? -ne 0 && exit 1

wait
FLAG_IF_JOB_TASK_FAIL=$(cat {flag_if_job_task_fail})
if test $FLAG_IF_JOB_TASK_FAIL -eq 0; then touch {job_tag_finished}; else exit 1;fi

{append_script_part}
"""


class Machine(metaclass=ABCMeta):
    """A machine is used to handle the connection with remote machines.

    Parameters
    ----------
    context : SubClass derived from BaseContext
        The context is used to mainatin the connection with remote machine.
    """

    subclasses_dict = {}
    options = set()
    # alias: for subclasses_dict key
    # notes: this attribute can be inherited
    alias: Tuple[str, ...] = tuple()

    def __new__(cls, *args, **kwargs):
        if cls is Machine:
            subcls = cls.subclasses_dict[kwargs["batch_type"]]
            instance = subcls.__new__(subcls, *args, **kwargs)
        else:
            instance = object.__new__(cls)
        return instance

    def __init__(
        self,
        batch_type=None,
        context_type=None,
        local_root=None,
        remote_root=None,
        remote_profile={},
        *,
        context=None,
    ):
        if context is None:
            assert isinstance(self, self.__class__.subclasses_dict[batch_type])
            context = BaseContext(  # type: ignore
                context_type=context_type,
                local_root=local_root,
                remote_root=remote_root,
                remote_profile=remote_profile,
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
        alias = [cls.__name__, *cls.alias]
        for aa in alias:
            cls.subclasses_dict[aa] = cls
            cls.subclasses_dict[aa.lower()] = cls
        cls.options.add(cls.__name__)
        # cls.subclasses.append(cls)

    @classmethod
    def load_from_json(cls, json_path):
        with open(json_path) as f:
            machine_dict = json.load(f)
        machine = cls.load_from_dict(machine_dict=machine_dict)
        return machine

    @classmethod
    def load_from_dict(cls, machine_dict):
        batch_type = machine_dict["batch_type"]
        try:
            machine_class = cls.subclasses_dict[batch_type]
        except KeyError as e:
            dlog.error(
                f"KeyError:batch_type; cls.subclasses_dict:{cls.subclasses_dict}; batch_type:{batch_type};"
            )
            raise e
        # check dict
        base = cls.arginfo()
        machine_dict = base.normalize_value(machine_dict, trim_pattern="_*")
        base.check_value(machine_dict, strict=False)

        context = BaseContext.load_from_dict(machine_dict)
        machine = machine_class(context=context)
        return machine

    def serialize(self, if_empty_remote_profile=False):
        machine_dict = {}
        machine_dict["batch_type"] = self.__class__.__name__
        machine_dict["context_type"] = self.context.__class__.__name__
        machine_dict["local_root"] = self.context.init_local_root
        machine_dict["remote_root"] = self.context.init_remote_root
        if not if_empty_remote_profile:
            machine_dict["remote_profile"] = self.context.remote_profile
        else:
            machine_dict["remote_profile"] = {}
        return machine_dict

    def __eq__(self, other):
        return self.serialize() == other.serialize()

    @classmethod
    def deserialize(cls, machine_dict):
        machine = cls.load_from_dict(machine_dict=machine_dict)
        return machine

    @abstractmethod
    def check_status(self, job):
        raise NotImplementedError(
            "abstract method check_status should be implemented by derived class"
        )

    def default_resources(self, res):
        raise NotImplementedError(
            "abstract method default_resources should be implemented by derived class"
        )

    def sub_script_head(self, res):
        raise NotImplementedError(
            "abstract method sub_script_head should be implemented by derived class"
        )

    def sub_script_cmd(self, res):
        raise NotImplementedError(
            "abstract method sub_script_cmd should be implemented by derived class"
        )

    @abstractmethod
    def do_submit(self, job):
        """Submit a single job, assuming that no job is running there."""
        raise NotImplementedError(
            "abstract method do_submit should be implemented by derived class"
        )

    def gen_script_run_command(self, job):
        return f"source $REMOTE_ROOT/{job.script_file_name}.run"

    def gen_script(self, job):
        script_header = self.gen_script_header(job)
        script_custom_flags = self.gen_script_custom_flags_lines(job)
        script_env = self.gen_script_env(job)
        script_run_command = self.gen_script_run_command(job)
        script_end = self.gen_script_end(job)
        script = script_template.format(
            script_header=script_header,
            script_custom_flags=script_custom_flags,
            script_env=script_env,
            script_command=script_run_command,
            script_end=script_end,
        )
        return script

    def check_if_recover(self, submission):
        submission_hash = submission.submission_hash
        submission_file_name = f"{submission_hash}.json"
        if_recover = self.context.check_file_exists(submission_file_name)
        return if_recover

    @abstractmethod
    def check_finish_tag(self, **kwargs):
        raise NotImplementedError(
            "abstract method check_finish_tag should be implemented by derived class"
        )

    @abstractmethod
    def gen_script_header(self, job):
        raise NotImplementedError(
            "abstract method gen_script_header should be implemented by derived class"
        )

    def gen_script_custom_flags_lines(self, job):
        custom_flags_lines = ""
        custom_flags = job.resources.custom_flags
        for ii in custom_flags:
            line = ii + "\n"
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
        for k, v in envs.items():
            if isinstance(v, list):
                for each_value in v:
                    export_envs_part += f"export {k}={each_value}\n"
            else:
                export_envs_part += f"export {k}={v}\n"

        prepend_script = job.resources.prepend_script
        prepend_script_part = "\n".join(prepend_script)

        flag_if_job_task_fail = job.job_hash + "_flag_if_job_task_fail"

        script_env = script_env_template.format(
            flag_if_job_task_fail=flag_if_job_task_fail,
            remote_root=shlex.quote(self.context.remote_root),
            module_unload_part=module_unload_part,
            module_load_part=module_load_part,
            source_files_part=source_files_part,
            export_envs_part=export_envs_part,
            prepend_script_part=prepend_script_part,
        )
        return script_env

    def gen_script_command(self, job):
        script_command = ""
        resources = job.resources
        # in_para_task_num = 0
        for task in job.job_task_list:
            command_env = ""
            command_env += self.gen_command_env_cuda_devices(resources=resources)

            task_tag_finished = task.task_hash + "_task_tag_finished"

            log_err_part = ""
            if task.outlog is not None:
                log_err_part += f"1>>{shlex.quote(task.outlog)} "
            if task.errlog is not None:
                log_err_part += f"2>>{shlex.quote(task.errlog)} "

            flag_if_job_task_fail = job.job_hash + "_flag_if_job_task_fail"
            last_err_file = job.job_hash + "_last_err_file"
            single_script_command = script_command_template.format(
                flag_if_job_task_fail=flag_if_job_task_fail,
                command_env=command_env,
                task_work_path=shlex.quote(
                    pathlib.PurePath(task.task_work_path).as_posix()
                ),
                command=task.command,
                task_tag_finished=task_tag_finished,
                log_err_part=log_err_part,
                err_file=shlex.quote(task.errlog),
                last_err_file=shlex.quote(last_err_file),
            )
            script_command += single_script_command

            script_command += self.gen_script_wait(resources=resources)
        return script_command

    def gen_script_end(self, job):
        job_tag_finished = job.job_hash + "_job_tag_finished"
        flag_if_job_task_fail = job.job_hash + "_flag_if_job_task_fail"

        append_script = job.resources.append_script
        append_script_part = "\n".join(append_script)

        script_end = script_end_template.format(
            job_tag_finished=job_tag_finished,
            flag_if_job_task_fail=flag_if_job_task_fail,
            append_script_part=append_script_part,
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
            if resources.strategy["if_cuda_multi_devices"] is True:
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

        if resources.strategy["if_cuda_multi_devices"] is True:
            if resources.gpu_per_node == 0:
                raise RuntimeError("resources.gpu_per_node can not be 0")
            gpu_index = resources.gpu_in_use % resources.gpu_per_node
            command_env += f"export CUDA_VISIBLE_DEVICES={gpu_index};"
            # for ii in list_CUDA_VISIBLE_DEVICES:
            #     command_env+="{ii},".format(ii=ii)
        return command_env

    @classmethod
    def arginfo(cls):
        # TODO: change the possible value of batch and context types after we refactor the code
        doc_batch_type = "The batch job system type. Option: " + ", ".join(cls.options)
        doc_context_type = (
            "The connection used to remote machine. Option: "
            + ", ".join(BaseContext.options)
        )
        doc_local_root = "The dir where the tasks and relating files locate. Typically the project dir."
        doc_remote_root = "The dir where the tasks are executed on the remote machine. Only needed when context is not lazy-local."
        doc_clean_asynchronously = (
            "Clean the remote directory asynchronously after the job finishes."
        )

        machine_args = [
            Argument("batch_type", str, optional=False, doc=doc_batch_type),
            # TODO: add default to local_root and remote_root after refactor the code
            Argument(
                "local_root", [str, type(None)], optional=False, doc=doc_local_root
            ),
            Argument(
                "remote_root", [str, type(None)], optional=True, doc=doc_remote_root
            ),
            Argument(
                "clean_asynchronously",
                bool,
                optional=True,
                default=False,
                doc=doc_clean_asynchronously,
            ),
        ]

        context_variant = Variant(
            "context_type",
            [
                context.machine_arginfo()
                for context in set(BaseContext.subclasses_dict.values())
            ],
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
        alias = []
        for aa in cls.alias:
            alias.extend(
                (
                    aa,
                    aa.lower(),
                )
            )
        return Argument(
            cls.__name__,
            dict,
            sub_fields=cls.resources_subfields(),
            alias=[cls.__name__.lower(), *alias],
        )

    @classmethod
    def resources_subfields(cls) -> List[Argument]:
        """Generate the resources subfields.

        Returns
        -------
        list[Argument]
            resources subfields
        """
        return [
            Argument(
                "kwargs", dict, optional=True, doc="This field is empty for this batch."
            )
        ]

    def kill(self, job):
        """Kill the job.

        If not implemented, pass and let the user manually kill it.

        Parameters
        ----------
        job : Job
            job
        """
        dlog.warning("Job %s should be manually killed" % job.job_id)

    def get_exit_code(self, job):
        """Get exit code of the job.

        Parameters
        ----------
        job : Job
            job
        """
        raise NotImplementedError(
            "abstract method get_exit_code should be implemented by derived class"
        )

import os, getpass, time
from abc import ABC

from dpdispatcher.machine import Machine
from dpdispatcher.JobStatus import JobStatus
from dpdispatcher.submission import Resources


lsf_script_template = """\
{lsf_script_header}
{lsf_script_env}
{lsf_script_command}
{lsf_script_end}
"""

lsf_script_header_template = """\
#!/bin/bash -l
#BSUB -e %J.err
#BSUB -o %J.out
{lsf_nodes_line}
{lsf_ptile_line}
{lsf_partition_line}
{lsf_walltime_line}
{lsf_number_gpu_line}
"""

lsf_script_env_template = """
{prepend_text}
export REMOTE_ROOT={remote_root}
test $? -ne 0 && exit 1
"""

lsf_script_command_template = """
cd $REMOTE_ROOT
cd {task_work_path}
test $? -ne 0 && exit 1
if [ ! -f {task_tag_finished} ] ;then
  {command_env} {command}  1>> {outlog} 2>> {errlog} 
  if test $? -ne 0; then touch {task_tag_finished}; fi
  touch {task_tag_finished}
fi 
"""

lsf_script_end_template = """

cd $REMOTE_ROOT
test $? -ne 0 && exit 1

wait

{append_text}
touch {job_tag_finished}
"""

lsf_script_wait = """
wait
"""

default_lsf_bsub_dict = {
    'm': "8G"
}


# class LSFResources(Resources):
#     """
#     LSF resources
#     """
#     def __init__(
#             self,
#             number_node,
#             cpu_per_node,
#             gpu_per_node,
#             queue_name,
#             walltime="120:00:00",
#             prepend_text="",
#             append_text="",
#             gpu_usage=True,
#             gpu_new_syntax=True,
#             lsf_bsub_dict=None,
#             group_size=1
#     ):
#         """define LSF resources
#
#         Parameters
#         ----------
#         number_node: nodes to be used
#         cpu_per_node: CPU cores used on each node
#         gpu_per_node: GPU
#         queue_name: the name of queue
#         walltime: max time of task
#         prepend_text: prepend scripts, code executed before the task run
#         append_text: append scripts, code executed after the task run
#         gpu_usage: choose if GPU line is used
#         lsf_bsub_dict: other bsub parameters.
#         group_size: tasks contained by each group
#         """
#         super().__init__(number_node, cpu_per_node, gpu_per_node, queue_name, group_size)
#         if lsf_bsub_dict is None:
#             lsf_bsub_dict = {}
#         self.walltime = walltime
#         self.gpu_new_syntax = gpu_new_syntax
#         self.gpu_usage = gpu_usage
#         self.prepend_text = prepend_text
#         self.append_text = append_text
#         self.lsf_bsub_dict = lsf_bsub_dict


class LSF(Machine):
    """
    LSF batch
    """
    def gen_script(self, job):
        # if type(job.resources) is LSFResources:
        #     resources = job.resources
        #     lsf_bsub_dict = job.resources.lsf_bsub_dict
        #     if lsf_bsub_dict is None:
        #         lsf_bsub_dict = {}
        # elif type(job.resources) is Resources:
        #     resources = LSFResources(**job.resources.__dict__)
        #     lsf_bsub_dict = {}
        # else:
        #     raise RuntimeError('type job.resource error')

        resources = job.resources
        lsf_bsub_dict = resources.extra_specification.copy()

        # headers
        script_header_dict = {
            'lsf_nodes_line': "#BSUB -n {number_cores}".format(
                number_cores=resources.number_node * resources.cpu_per_node),
            'lsf_ptile_line': "#BSUB -R 'span[ptile={cpu_per_node}]'".format(
                cpu_per_node=resources.cpu_per_node),
            'lsf_partition_line': "#BSUB -q {queue_name}".format(
                queue_name=resources.queue_name),
            'lsf_walltime_line': "#BSUB -W {walltime}".format(
                walltime=resources.kwargs.get('walltime', '12:00'))
        }
        gpu_usage_flag = resources.kwargs.get('gpu_usage', False)
        gpu_new_syntax_flag = resources.kwargs.get('gpu_new_syntax', False)
        if gpu_usage_flag is True:
            if gpu_new_syntax_flag is True:
                script_header_dict['lsf_number_gpu_line'] = "#BSUB -gpu 'num={gpu_per_node}:mode=shared:" \
                                                            "j_exclusive=yes'".format(
                    gpu_per_node=resources.gpu_per_node)
            else:
                script_header_dict['lsf_number_gpu_line'] = '#BSUB -R "select[ngpus >0] rusage[' \
                                                            'ngpus_excl_p={gpu_per_node}]"'.format(
                    gpu_per_node=resources.gpu_per_node)
        else:
            script_header_dict['lsf_number_gpu_line'] = ""
        lsf_script_header = lsf_script_header_template.format(**script_header_dict)

        for k, v in lsf_bsub_dict.items():
            line = "#BSUB -{key} {value}\n".format(key=k, value=str(v))
            lsf_script_header += line

        # envs
        script_env_dict = {
            'prepend_text': resources.kwargs.get('prepend_text', ""),
            'remote_root': self.context.remote_root
        }
        lsf_script_env = lsf_script_env_template.format(**script_env_dict)

        # commands
        lsf_script_command = ""

        for task in job.job_task_list:
            command_env = ""
            lsf_script_command += self.get_script_wait(resources=resources, task=task)
            command_env += self.get_command_env_cuda_devices(resources=resources, task=task)

            task_tag_finished = task.task_hash + '_task_tag_finished'

            temp_lsf_script_command = lsf_script_command_template.format(
                command_env=command_env,
                task_work_path=task.task_work_path,
                command=task.command,
                task_tag_finished=task_tag_finished,
                outlog=task.outlog, errlog=task.errlog
            )

            lsf_script_command += temp_lsf_script_command

        # end
        job_tag_finished = job.job_hash + '_job_tag_finished'
        lsf_script_end = lsf_script_end_template.format(
            append_text=resources.kwargs.get('append_text', ""),
            job_tag_finished=job_tag_finished
        )

        # join the whole script
        lsf_script = lsf_script_template.format(
            lsf_script_header=lsf_script_header,
            lsf_script_env=lsf_script_env,
            lsf_script_command=lsf_script_command,
            lsf_script_end=lsf_script_end)
        return lsf_script

    def do_submit(self, job):
        script_file_name = job.script_file_name
        script_str = self.gen_script(job)
        job_id_name = job.job_hash + '_job_id'
        self.context.write_file(fname=script_file_name, write_str=script_str)
        stdin, stdout, stderr = self.context.block_checkcall(
            'cd %s && %s %s' % (self.context.remote_root, 'bsub < ', script_file_name)
        )
        subret = (stdout.readlines())
        job_id = subret[0].split()[1][1:-1]
        self.context.write_file(job_id_name, job_id)
        return job_id

    # TODO: add default resources
    def default_resources(self, resources):
        pass

    def check_status(self, job):
        try:
            job_id = job.job_id
        except AttributeError:
            return JobStatus.terminated
        if job_id == "":
            return JobStatus.unsubmitted
        ret, stdin, stdout, stderr \
            = self.context.block_call("bjobs " + job_id)
        err_str = stderr.read().decode('utf-8')
        if ("Job <%s> is not found" % job_id) in err_str:
            if self.check_finish_tag(job):
                return JobStatus.finished
            else:
                return JobStatus.terminated
        elif ret != 0:
            raise RuntimeError("status command bjobs fails to execute.\n error info: %s \nreturn code %d\n"
                               % (err_str, ret))
        status_out = stdout.read().decode('utf-8').split('\n')
        if len(status_out) < 2:
            return JobStatus.unknown
        else:
            status_line = status_out[1]
            status_word = status_line.split()[2]

        # ref: https://www.ibm.com/support/knowledgecenter/en/SSETD4_9.1.2/lsf_command_ref/bjobs.1.html
        if status_word in ["PEND", "WAIT", "PSUSP"]:
            return JobStatus.waiting
        elif status_word in ["RUN", "USUSP"]:
            return JobStatus.running
        elif status_word in ["DONE", "EXIT"]:
            if self.check_finish_tag(job):
                dlog.info(f"job: {job.job_hash} {job.job_id} finished")
                return JobStatus.finished
            else:
                return JobStatus.terminated
        else:
            return JobStatus.unknown

    def check_finish_tag(self, job):
        job_tag_finished = job.job_hash + '_job_tag_finished'
        print('job finished: ', job.job_id, job_tag_finished)
        return self.context.check_file_exists(job_tag_finished)

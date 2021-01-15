import os, getpass, time
from dpdispatcher.batch import Batch
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
{lsf_nodes_line}
{lsf_ptile_line}
{lsf_number_gpu_line}
{lsf_partition_line}
"""

lsf_script_env_template = """
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
fi &
"""

lsf_script_end_template = """

cd $REMOTE_ROOT
test $? -ne 0 && exit 1

wait

touch {job_tag_finished}
"""

lsf_script_wait = """
wait
"""

default_lsf_bsub_dict = {
    'w': "120:00:00",
    'm': "8G"
}


class LSFResources(Resources):
    """
    LSF resources
    """
    def __init__(
            self,
            number_node,
            cpu_per_node,
            gpu_per_node,
            queue_name,
            prepend_text=None,
            append_text=None,
            gpu_usage=True,
            gpu_new_syntax=True
    ):
        """define LSF resources

        Parameters
        ----------
        number_node: nodes to be used
        cpu_per_node: CPU cores uesd on each node
        gpu_per_node: GPU
        queue_name:
        prepend_text: prepend scripts, code executed before the task run
        append_text: append scripts, code executed after the task run
        gpu_usage: choose if GPU line is used
        """
        super().__init__(number_node, cpu_per_node, gpu_per_node, queue_name)
        self.gpu_new_syntax = gpu_new_syntax
        self.gpu_usage = gpu_usage
        self.prepend_text = prepend_text
        self.append_text = append_text


class LSF(Batch):
    """
    LSF batch
    """
    def gen_script(self, job):
        if type(job.resources) is LSFResources:
            resources = job.resources
            lsf_bsub_dict = {}
        elif type(job.resources) is Resources:
            job.resources
            resources = LSFResources()
            lsf_bsub_dict = {}
        else:
            raise RuntimeError('type job.resource error')

        # headers
        script_header_dict = {
            'lsf_nodes_line': "#BSUB -n {number_cores}".format(
                number_cores=resources.number_node * resources.cpu_per_node),
            'lsf_ptile_line': "#BSUB -R 'span[ptile={cpu_per_node}]'".format(
                cpu_per_node=resources.cpu_per_node),
            'lsf_partition_line': "#BSUB -q {queue_name}".format(
                queue_name=resources.queue_name)
        }
        if resources.gpu
        'lsf_number_gpu_line': "#BSUB -gpu 'num=%d:mode=shared:j_exclusive=yes'".format(
            gpu_per_node=resources.gpu_per_node),
        lsf_script_header = lsf_script_header_template.format(**script_header_dict)

        for k, v in lsf_bsub_dict.items():
            line = "#BSUB -{key} {value}\n".format(key=k, value=str(v))
            lsf_script_header += line

        # envs
        script_env_dict = {
            'remote_root': self.context.remote_root
        }
        lsf_script_env = lsf_script_env_template.format(**script_env_dict)

        # commands
        lsf_script_command = ""

        for task in job.job_task_list:
            command_env = ""
            task_need_resources = task.task_need_resources
            if resources.in_use + task_need_resources > 1:
                lsf_script_command += lsf_script_wait
                resources.in_use = 0

            command_env += self.get_command_env_cuda_devices(resources=resources, task=task)

            command_env += "export DP_TASK_NEED_RESOURCES={task_need_resources} ;".format(
                task_need_resources=task.task_need_resources)

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
        lsf_script_end = lsf_script_end_template.format(job_tag_finished=job_tag_finished)

        # join the whole script
        lsf_script = lsf_script_template.format(
            lsf_script_header=lsf_script_header,
            lsf_script_env=lsf_script_env,
            lsf_script_command=lsf_script_command,
            lsf_script_end=lsf_script_end)
        return lsf_script

    def check_status(self):
        try:
            job_id = self._get_job_id()
        except:
            return JobStatus.terminated
        if job_id == "":
            raise RuntimeError("job %s is has not been submitted" % self.remote_root)
        ret, stdin, stdout, stderr \
            = self.context.block_call("bjobs " + job_id)
        err_str = stderr.read().decode('utf-8')
        if ("Job <%s> is not found" % job_id) in err_str:
            if self.check_finish_tag():
                return JobStatus.finished
            else:
                return JobStatus.terminated
        elif ret != 0:
            raise RuntimeError("status command bjobs fails to execute. erro info: %s return code %d"
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
            if self.check_finish_tag():
                return JobStatus.finished
            else:
                return JobStatus.terminated
        else:
            return JobStatus.unknown

    def do_submit(self, job):
        if res == None:
            res = self.default_resources(res)
        if 'task_max' in res and res['task_max'] > 0:
            while self._check_sub_limit(task_max=res['task_max']):
                time.sleep(60)
        script_str = self.sub_script(job_dirs, cmd, args=args, res=res, outlog=outlog, errlog=errlog)
        self.context.write_file(self.sub_script_name, script_str)
        stdin, stdout, stderr = self.context.block_checkcall(
            'cd %s && %s < %s' % (self.context.remote_root, 'bsub', self.sub_script_name))
        subret = (stdout.readlines())
        job_id = subret[0].split()[1][1:-1]
        self.context.write_file(self.job_id_name, job_id)

    def default_resources(self, res_):
        """
        set default value if a key in res_ is not fhound
        """
        if res_ == None:
            res = {}
        else:
            res = res_
        _default_item(res, 'node_cpu', 1)
        _default_item(res, 'numb_node', 1)
        _default_item(res, 'task_per_node', 1)
        _default_item(res, 'cpus_per_task', -1)
        _default_item(res, 'numb_gpu', 0)
        _default_item(res, 'time_limit', '1:0:0')
        _default_item(res, 'mem_limit', -1)
        _default_item(res, 'partition', '')
        _default_item(res, 'account', '')
        _default_item(res, 'qos', '')
        _default_item(res, 'constraint_list', [])
        _default_item(res, 'license_list', [])
        _default_item(res, 'exclude_list', [])
        _default_item(res, 'module_unload_list', [])
        _default_item(res, 'module_list', [])
        _default_item(res, 'source_list', [])
        _default_item(res, 'envs', None)
        _default_item(res, 'with_mpi', False)
        _default_item(res, 'cuda_multi_tasks', False)
        _default_item(res, 'allow_failure', False)
        _default_item(res, 'cvasp', False)
        return res

    def sub_script_head(self, res):
        ret = ''
        ret += "#!/bin/bash -l\n#BSUB -e %J.err\n#BSUB -o %J.out\n"
        if res['numb_gpu'] == 0:
            ret += '#BSUB -n %d\n#BSUB -R span[ptile=%d]\n' % (
                res['numb_node'] * res['task_per_node'], res['node_cpu'])
        else:
            if res['node_cpu']:
                ret += '#BSUB -R span[ptile=%d]\n' % res['node_cpu']
            if res.get('new_lsf_gpu', False):
                # supportted in LSF >= 10.1.0 SP6
                # ref: https://www.ibm.com/support/knowledgecenter/en/SSWRJV_10.1.0/lsf_resource_sharing/use_gpu_res_reqs.html
                ret += '#BSUB -n %d\n#BSUB -gpu "num=%d:mode=shared:j_exclusive=yes"\n' % (
                    res['numb_gpu'], res['task_per_node'])
            else:
                ret += '#BSUB -n %d\n#BSUB -R "select[ngpus >0] rusage[ngpus_excl_p=%d]"\n' % (
                    res['numb_gpu'], res['task_per_node'])
        if res['time_limit']:
            ret += '#BSUB -W %s\n' % (res['time_limit'].split(':')[
                                          0] + ':' + res['time_limit'].split(':')[1])
        if res['mem_limit'] > 0:
            ret += "#BSUB -M %d \n" % (res['mem_limit'])
        ret += '#BSUB -J %s\n' % (res['job_name'] if 'job_name' in res else 'dpdisp')
        if len(res['partition']) > 0:
            ret += '#BSUB -q %s\n' % res['partition']
        ret += "\n"
        for ii in res['module_unload_list']:
            ret += "module unload %s\n" % ii
        for ii in res['module_list']:
            ret += "module load %s\n" % ii
        ret += "\n"
        for ii in res['source_list']:
            ret += "source %s\n" % ii
        ret += "\n"
        envs = res['envs']
        if envs != None:
            for key in envs.keys():
                ret += 'export %s=%s\n' % (key, envs[key])
            ret += '\n'
        return ret

    def sub_script_cmd(self,
                       cmd,
                       arg,
                       res):
        if res['with_mpi']:
            ret = 'mpirun -machinefile $LSB_DJOB_HOSTFILE -n %d %s %s' % (
                res['numb_node'] * res['task_per_node'], cmd, arg)
        else:
            ret = '%s %s' % (cmd, arg)
        return ret

    def _get_job_id(self):
        if self.context.check_file_exists(self.job_id_name):
            return self.context.read_file(self.job_id_name)
        else:
            return ""

    def _check_sub_limit(self, task_max, **kwarg):
        stdin_run, stdout_run, stderr_run = self.context.block_checkcall("bjobs | grep RUN | wc -l")
        njobs_run = int(stdout_run.read().decode('utf-8').split('\n')[0])
        stdin_pend, stdout_pend, stderr_pend = self.context.block_checkcall("bjobs | grep PEND | wc -l")
        njobs_pend = int(stdout_pend.read().decode('utf-8').split('\n')[0])
        if (njobs_pend + njobs_run) < task_max:
            return False
        else:
            return True

    def _make_squeue(self, mdata1, res):
        ret = ''
        ret += 'bjobs -u %s ' % mdata1['username']
        ret += '-q %s ' % res['partition']
        ret += '| grep PEND '
        return ret

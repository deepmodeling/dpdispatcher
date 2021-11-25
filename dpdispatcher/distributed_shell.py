from dpdispatcher.JobStatus import JobStatus
from dpdispatcher import dlog
from dpdispatcher.machine import Machine
from dpdispatcher.utils import run_cmd_with_all_output
import subprocess as sp


shell_script_header_template="""
#!/bin/bash -l
set -x
"""

script_env_template="""
{module_unload_part}
{module_load_part}
{source_files_part}
{export_envs_part}

REMOTE_ROOT=`pwd`
echo 0 > {flag_if_job_task_fail}
test $? -ne 0 && exit 1

if ! ls {submission_hash}_upload.tgz 1>/dev/null 2>&1; then
    hadoop fs -get {remote_root}/*.tgz .
fi
for TGZ in `ls *.tgz`; do tar xvf $TGZ; done

"""
script_end_template="""
cd $REMOTE_ROOT
test $? -ne 0 && exit 1

wait
FLAG_IF_JOB_TASK_FAIL=$(cat {flag_if_job_task_fail})
if test $FLAG_IF_JOB_TASK_FAIL -eq 0; then
    tar czf {submission_hash}_{job_hash}_download.tar.gz {all_task_dirs}
    hadoop fs -put -f {submission_hash}_{job_hash}_download.tar.gz {remote_root}
    hadoop fs -touchz {remote_root}/{job_tag_finished}
else
    exit 1
fi
"""

class DistributedShell(Machine):
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

        flag_if_job_task_fail = job.job_hash + '_flag_if_job_task_fail'

        script_env = script_env_template.format(
            flag_if_job_task_fail=flag_if_job_task_fail,
            module_unload_part=module_unload_part,
            module_load_part=module_load_part,
            source_files_part=source_files_part,
            export_envs_part=export_envs_part,
            remote_root=self.context.remote_root,
            submission_hash=self.context.submission.submission_hash,
        )
        return script_env

    def gen_script_end(self, job):
        all_task_dirs = ""
        for task in job.job_task_list:
            all_task_dirs += "%s " % task.task_work_path
        job_tag_finished = job.job_hash + '_job_tag_finished'
        flag_if_job_task_fail = job.job_hash + '_flag_if_job_task_fail'
        script_end = script_end_template.format(
            job_tag_finished=job_tag_finished,
            flag_if_job_task_fail=flag_if_job_task_fail,
            all_task_dirs=all_task_dirs,
            remote_root=self.context.remote_root,
            submission_hash=self.context.submission.submission_hash,
            job_hash=job.job_hash
        )
        return script_end

    def gen_script_header(self, job):
        shell_script_header = shell_script_header_template
        return shell_script_header

    def do_submit(self, job):
        """ submit th job to yarn using distributed shell

        Parameters
        ----------
        job : Job class instance
            job to be submitted

        Returns
        -------
        job_id: string
            submit process id
        """

        script_str = self.gen_script(job)
        script_file_name = job.script_file_name
        job_id_name = job.job_hash + '_job_id'
        output_name = job.job_hash + '.out'
        self.context.write_file(fname=script_file_name, write_str=script_str)

        resources = job.resources
        submit_command = 'hadoop jar %s/hadoop-yarn-applications-distributedshell-*.jar ' \
                         'org.apache.hadoop.yarn.applications.distributedshell.Client ' \
                         '-jar %s/hadoop-yarn-applications-distributedshell-*.jar ' \
                         '-queue %s -appname "distributedshell_dpgen_%s" ' \
                         '-shell_env YARN_CONTAINER_RUNTIME_TYPE=docker ' \
                         '-shell_env YARN_CONTAINER_RUNTIME_DOCKER_IMAGE=%s ' \
                         '-shell_env ENV_DOCKER_CONTAINER_SHM_SIZE=\'600m\' '\
                         '-master_memory 1024 -master_vcores 2 -num_containers 1 ' \
                         '-container_resources memory-mb=%s,vcores=%s ' \
                         '-shell_script /tmp/%s' % (resource.kwargs.get('yarn_path',''),
                                        resource.kwargs.get('yarn_path',''), resources.queue_name, job.job_hash,
                                        resources.kwargs.get('img_name',''),resources.kwargs.get('mem_limit', 1)*1024,
                                        resources.cpu_per_node, script_file_name)

        cmd = '{ nohup %s 1>%s 2>%s & } && echo $!' % (submit_command, output_name, output_name)
        ret, stdout, stderr = run_cmd_with_all_output(cmd)

        if ret != 0:
            err_str = stderr.decode('utf-8')
            raise RuntimeError\
                    ("Command squeue fails to execute, error message:%s\nreturn code %d\n" % (err_str, ret))
        job_id = int(stdout.decode('utf-8').strip())

        self.context.write_file(job_id_name, str(job_id))
        return job_id

    def check_status(self, job):
        job_id = job.job_id
        if job_id == '' :
            return JobStatus.unsubmitted

        ret, stdout, stderr = run_cmd_with_all_output(f"if ps -p {job_id} > /dev/null; then echo 1; fi")
        if ret != 0:
            err_str = stderr.decode('utf-8')
            raise RuntimeError \
                ("Command fails to execute, error message:%s\nreturn code %d\n" % (err_str, ret))

        if_job_exists = bool(stdout.decode('utf-8').strip())
        if self.check_finish_tag(job=job):
            dlog.info(f"job: {job.job_hash} {job.job_id} finished")
            return JobStatus.finished

        if if_job_exists:
            return JobStatus.running
        else:
            return JobStatus.terminated

    def check_finish_tag(self, job):
        job_tag_finished = job.job_hash + '_job_tag_finished'
        return self.context.check_file_exists(job_tag_finished)

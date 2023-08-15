import shlex

from dpdispatcher import dlog
from dpdispatcher.JobStatus import JobStatus
from dpdispatcher.machine import Machine

fugaku_script_header_template = """\
{queue_name_line}
{fugaku_node_number_line}
{fugaku_ntasks_per_node_line}
"""


class Fugaku(Machine):
    def gen_script(self, job):
        fugaku_script = super().gen_script(job)
        return fugaku_script

    def gen_script_header(self, job):
        resources = job.resources
        fugaku_script_header_dict = {}
        fugaku_script_header_dict[
            "fugaku_node_number_line"
        ] = f'#PJM -L "node={resources.number_node}" '
        fugaku_script_header_dict[
            "fugaku_ntasks_per_node_line"
        ] = f'#PJM --mpi "max-proc-per-node={resources.cpu_per_node}"'
        fugaku_script_header_dict[
            "queue_name_line"
        ] = f'#PJM -L "rscgrp={resources.queue_name}"'
        fugaku_script_header = fugaku_script_header_template.format(
            **fugaku_script_header_dict
        )
        return fugaku_script_header

    def do_submit(self, job):
        script_file_name = job.script_file_name
        script_str = self.gen_script(job)
        job_id_name = job.job_hash + "_job_id"
        # script_str = self.sub_script(job_dirs, cmd, args=args, resources=resources, outlog=outlog, errlog=errlog)
        self.context.write_file(fname=script_file_name, write_str=script_str)
        # self.context.write_file(fname=os.path.join(self.context.submission.work_base, script_file_name), write_str=script_str)
        # script_file_dir = os.path.join(self.context.submission.work_base)
        script_file_dir = self.context.remote_root
        # stdin, stdout, stderr = self.context.block_checkcall('cd %s && %s %s' % (self.context.remote_root, 'pjsub', script_file_name))

        stdin, stdout, stderr = self.context.block_checkcall(
            "cd {} && {} {}".format(
                shlex.quote(script_file_dir), "pjsub", shlex.quote(script_file_name)
            )
        )
        subret = stdout.readlines()
        job_id = subret[0].split()[5]
        self.context.write_file(job_id_name, job_id)
        return job_id

    def default_resources(self, resources):
        pass

    def check_status(self, job):
        job_id = job.job_id
        if job_id == "":
            return JobStatus.unsubmitted
        ret, stdin, stdout, stderr = self.context.block_call("pjstat " + job_id)
        err_str = stderr.read().decode("utf-8")
        try:
            status_line = stdout.read().decode("utf-8").split("\n")[-2]
        # pjstat only retrun 0 if the job is not waiting or running
        except Exception:
            ret, stdin, stdout, stderr = self.context.block_call("pjstat -H  " + job_id)
            status_line = stdout.read().decode("utf-8").split("\n")[-2]
            status_word = status_line.split()[3]
            if status_word in ["EXT", "CCL", "ERR"]:
                if self.check_finish_tag(job):
                    dlog.info(f"job: {job.job_hash} {job.job_id} finished")
                    return JobStatus.finished
                else:
                    return JobStatus.terminated
            else:
                return JobStatus.unknown
        status_word = status_line.split()[3]
        # dlog.info (status_word)
        if status_word in ["QUE", "HLD", "RNA", "SPD"]:
            return JobStatus.waiting
        elif status_word in ["RUN", "RNE"]:
            return JobStatus.running
        else:
            return JobStatus.unknown

    def check_finish_tag(self, job):
        job_tag_finished = job.job_hash + "_job_tag_finished"
        return self.context.check_file_exists(job_tag_finished)

import shlex

from dpdispatcher.dlog import dlog
from dpdispatcher.machine import Machine
from dpdispatcher.utils.job_status import JobStatus
from dpdispatcher.utils.utils import customized_script_header_template

pbs_script_header_template = """
#!/bin/bash -l
{select_node_line}
#PBS -j oe
{queue_name_line}
"""


class PBS(Machine):
    def gen_script(self, job):
        pbs_script = super().gen_script(job)
        return pbs_script

    def gen_script_header(self, job):
        resources = job.resources
        pbs_script_header_dict = {}
        pbs_script_header_dict["select_node_line"] = (
            f"#PBS -l select={resources.number_node}:ncpus={resources.cpu_per_node}"
        )
        if resources.gpu_per_node != 0:
            pbs_script_header_dict["select_node_line"] += (
                f":ngpus={resources.gpu_per_node}"
            )
        pbs_script_header_dict["queue_name_line"] = f"#PBS -q {resources.queue_name}"
        if (
            resources["strategy"].get("customized_script_header_template_file")
            is not None
        ):
            pbs_script_header = customized_script_header_template(
                resources["strategy"]["customized_script_header_template_file"],
                resources,
            )
        else:
            pbs_script_header = pbs_script_header_template.format(
                **pbs_script_header_dict
            )
        return pbs_script_header

    def do_submit(self, job):
        script_file_name = job.script_file_name
        script_str = self.gen_script(job)
        job_id_name = job.job_hash + "_job_id"
        # script_str = self.sub_script(job_dirs, cmd, args=args, resources=resources, outlog=outlog, errlog=errlog)
        self.context.write_file(fname=script_file_name, write_str=script_str)
        script_run_str = self.gen_script_command(job)
        script_run_file_name = f"{job.script_file_name}.run"
        self.context.write_file(fname=script_run_file_name, write_str=script_run_str)
        # self.context.write_file(fname=os.path.join(self.context.submission.work_base, script_file_name), write_str=script_str)
        # script_file_dir = os.path.join(self.context.submission.work_base)
        script_file_dir = self.context.remote_root
        # stdin, stdout, stderr = self.context.block_checkcall('cd %s && %s %s' % (self.context.remote_root, 'qsub', script_file_name))
        stdin, stdout, stderr = self.context.block_checkcall(
            "cd {} && {} {}".format(
                shlex.quote(script_file_dir), "qsub", shlex.quote(script_file_name)
            )
        )
        subret = stdout.readlines()
        job_id = subret[0].split()[0]
        self.context.write_file(job_id_name, job_id)
        return job_id

    def default_resources(self, resources):
        pass

    def check_status(self, job):
        job_id = job.job_id
        if job_id == "":
            return JobStatus.unsubmitted
        ret, stdin, stdout, stderr = self.context.block_call("qstat -x " + job_id)
        err_str = stderr.read().decode("utf-8")
        if ret != 0:
            if "qstat: Unknown Job Id" in err_str or "Job has finished" in err_str:
                if self.check_finish_tag(job=job):
                    return JobStatus.finished
                else:
                    return JobStatus.terminated
            else:
                raise RuntimeError(
                    "status command qstat fails to execute. erro info: %s return code %d"
                    % (err_str, ret)
                )
        status_line = stdout.read().decode("utf-8").split("\n")[-2]
        status_word = status_line.split()[-2]
        # dlog.info (status_word)
        if status_word in ["Q", "H"]:
            return JobStatus.waiting
        elif status_word in ["R"]:
            return JobStatus.running
        elif status_word in ["C", "E", "K", "F"]:
            if self.check_finish_tag(job):
                dlog.info(f"job: {job.job_hash} {job.job_id} finished")
                return JobStatus.finished
            else:
                return JobStatus.terminated
        else:
            return JobStatus.unknown

    def check_finish_tag(self, job):
        job_tag_finished = job.job_hash + "_job_tag_finished"
        return self.context.check_file_exists(job_tag_finished)

    def kill(self, job):
        """Kill the job.

        Parameters
        ----------
        job : Job
            job
        """
        job_id = job.job_id
        ret, stdin, stdout, stderr = self.context.block_call("qdel " + str(job_id))


class Torque(PBS):
    def check_status(self, job):
        job_id = job.job_id
        if job_id == "":
            return JobStatus.unsubmitted
        ret, stdin, stdout, stderr = self.context.block_call("qstat -l " + job_id)
        err_str = stderr.read().decode("utf-8")
        if ret != 0:
            if "qstat: Unknown Job Id" in err_str or "Job has finished" in err_str:
                if self.check_finish_tag(job=job):
                    return JobStatus.finished
                else:
                    return JobStatus.terminated
            else:
                raise RuntimeError(
                    "status command qstat fails to execute. erro info: %s return code %d"
                    % (err_str, ret)
                )
        status_line = stdout.read().decode("utf-8").split("\n")[-2]
        status_word = status_line.split()[-2]
        # dlog.info (status_word)
        if status_word in ["Q", "H"]:
            return JobStatus.waiting
        elif status_word in ["R"]:
            return JobStatus.running
        elif status_word in ["C", "E", "K", "F"]:
            if self.check_finish_tag(job):
                dlog.info(f"job: {job.job_hash} {job.job_id} finished")
                return JobStatus.finished
            else:
                return JobStatus.terminated
        else:
            return JobStatus.unknown

    def gen_script_header(self, job):
        # ref: https://support.adaptivecomputing.com/wp-content/uploads/2021/02/torque/torque.htm#topics/torque/2-jobs/requestingRes.htm
        resources = job.resources
        pbs_script_header_dict = {}
        pbs_script_header_dict["select_node_line"] = (
            f"#PBS -l nodes={resources.number_node}:ppn={resources.cpu_per_node}"
        )
        if resources.gpu_per_node != 0:
            pbs_script_header_dict["select_node_line"] += (
                f":gpus={resources.gpu_per_node}"
            )
        pbs_script_header_dict["queue_name_line"] = f"#PBS -q {resources.queue_name}"
        if (
            resources["strategy"].get("customized_script_header_template_file")
            is not None
        ):
            pbs_script_header = customized_script_header_template(
                resources["strategy"]["customized_script_header_template_file"],
                resources,
            )
        else:
            pbs_script_header = pbs_script_header_template.format(
                **pbs_script_header_dict
            )
        return pbs_script_header


sge_script_header_template = """
#!/bin/bash
#$ -N dpdispatcher_submit
{select_node_line}
#$ -cwd

"""


class SGE(PBS):
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
        super(PBS, self).__init__(
            batch_type,
            context_type,
            local_root,
            remote_root,
            remote_profile,
            context=context,
        )

    def gen_script_header(self, job):
        resources = job.resources
        sge_script_header_dict = {}
        # resources.number_node is not used
        sge_script_header_dict["select_node_line"] = (
            f"#$ -pe mpi {resources.cpu_per_node} "
        )
        # resources.queue_name is not necessary
        sge_script_header = sge_script_header_template.format(**sge_script_header_dict)
        return sge_script_header

    def do_submit(self, job):
        script_file_name = job.script_file_name
        script_str = self.gen_script(job)
        job_id_name = job.job_hash + "_job_id"
        self.context.write_file(fname=script_file_name, write_str=script_str)
        script_file_dir = self.context.remote_root
        stdin, stdout, stderr = self.context.block_checkcall(
            "cd {} && {} {}".format(script_file_dir, "qsub", script_file_name)
        )
        subret = stdout.readlines()
        job_id = subret[0].split()[2]
        self.context.write_file(job_id_name, job_id)
        return job_id

    def default_resources(self, resources):
        pass

    def check_status(self, job):
        job_id = job.job_id
        status_line = None
        if job_id == "":
            return JobStatus.unsubmitted
        ret, stdin, stdout, stderr = self.context.block_call("qstat")
        err_str = stderr.read().decode("utf-8")
        if ret != 0:
            raise RuntimeError(
                "status command qstat fails to execute. erro info: %s return code %d"
                % (err_str, ret)
            )
        status_text_list = stdout.read().decode("utf-8").split("\n")
        for txt in status_text_list:
            if job_id in txt:
                status_line = txt

        if status_line is None:
            count = 0
            while count <= 6:
                if self.check_finish_tag(job=job):
                    return JobStatus.finished
                dlog.info(
                    "not tag_finished detected, execute sync command and wait. count "
                    + str(count)
                )
                self.context.block_call("sync")
                import time

                time.sleep(10)
                count += 1
            return JobStatus.terminated
        else:
            status_word = status_line.split()[4]
            # dlog.info (status_word)
            if status_word in ["qw"]:
                return JobStatus.waiting
            elif status_word in ["r"]:
                return JobStatus.running
            else:
                return JobStatus.unknown

    def check_finish_tag(self, job):
        job_tag_finished = job.job_hash + "_job_tag_finished"
        return self.context.check_file_exists(job_tag_finished)

from dpdispatcher.machine import Machine
from dpdispatcher import dlog
from dpdispatcher.JobStatus import JobStatus
from typing import List
from dargs import Argument


lsf_script_header_template = """\
#!/bin/bash -l
#BSUB -e %J.err
#BSUB -o %J.out
{lsf_nodes_line}
{lsf_ptile_line}
{lsf_partition_line}
{lsf_number_gpu_line}
"""


class LSF(Machine):
    """
    LSF batch
    """

    def gen_script(self, job):
        lsf_script = super(LSF, self).gen_script(job)
        return lsf_script

    def gen_script_header(self, job):
        resources = job.resources
        script_header_dict = {
            'lsf_nodes_line': "#BSUB -n {number_cores}".format(
                number_cores=resources.number_node * resources.cpu_per_node),
            'lsf_ptile_line': "#BSUB -R 'span[ptile={cpu_per_node}]'".format(
                cpu_per_node=resources.cpu_per_node),
            'lsf_partition_line': "#BSUB -q {queue_name}".format(
                queue_name=resources.queue_name)
        }
        gpu_usage_flag = resources.kwargs.get('gpu_usage', False)
        gpu_new_syntax_flag = resources.kwargs.get('gpu_new_syntax', False)
        gpu_exclusive_flag = resources.kwargs.get('gpu_exclusive', True)
        custom_gpu_line = resources.kwargs.get("custom_gpu_line", None)
        if not custom_gpu_line:
            if gpu_usage_flag is True:
                if gpu_new_syntax_flag is True:
                    if gpu_exclusive_flag is True:
                        script_header_dict['lsf_number_gpu_line'] = "#BSUB -gpu 'num={gpu_per_node}:mode=shared:" \
                                                                    "j_exclusive=yes'".format(
                            gpu_per_node=resources.gpu_per_node)
                    else:
                        script_header_dict['lsf_number_gpu_line'] = "#BSUB -gpu 'num={gpu_per_node}:mode=shared:" \
                                                                    "j_exclusive=no'".format(
                            gpu_per_node=resources.gpu_per_node)
                else:
                    script_header_dict['lsf_number_gpu_line'] = '#BSUB -R "select[ngpus >0] rusage[' \
                                                                'ngpus_excl_p={gpu_per_node}]"'.format(
                        gpu_per_node=resources.gpu_per_node)
            else:
                script_header_dict['lsf_number_gpu_line'] = ""
        else:
            script_header_dict['lsf_number_gpu_line'] = custom_gpu_line
        lsf_script_header = lsf_script_header_template.format(**script_header_dict)

        return lsf_script_header

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

    # TODO: derive abstract methods
    def default_resources(self, resources):
        pass

    def sub_script_cmd(self, res):
        pass

    def sub_script_head(self, res):
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
        return self.context.check_file_exists(job_tag_finished)

    @classmethod
    def resources_subfields(cls) -> List[Argument]:
        """Generate the resources subfields.
        
        Returns
        -------
        list[Argument]
            resources subfields
        """
        doc_custom_gpu_line = "Custom GPU configuration, starting with #BSUB"
        doc_gpu_usage = "Choosing if GPU is used in the calculation step. "
        doc_gpu_new_syntax = "For LFS >= 10.1.0.3, new option -gpu for #BSUB could be used. " \
            "If False, and old syntax would be used."
        doc_gpu_exclusive = "Only take effect when new syntax enabled. " \
            "Control whether submit tasks in exclusive way for GPU."
        return [Argument("kwargs", dict, [
            Argument("gpu_usage", bool, optional=True, default=False, doc=doc_gpu_usage),
            Argument("gpu_new_syntax", bool, optional=True, default=False, doc=doc_gpu_new_syntax),
            Argument("gpu_exclusive", bool, optional=True, default=True, doc=doc_gpu_exclusive),
            Argument("custom_gpu_line", str, optional=True, default=None, doc=doc_custom_gpu_line)
        ], optional=False, doc="Extra arguments.")]
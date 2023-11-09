import os
import subprocess as sp

from dpdispatcher.base_context import BaseContext


class SPRetObj:
    def __init__(self, ret):
        self.data = ret

    def read(self):
        return self.data

    def readlines(self):
        lines = self.data.decode("utf-8").splitlines()
        ret = []
        for aa in lines:
            ret.append(aa + "\n")
        return ret


class LazyLocalContext(BaseContext):
    """Run jobs in the local server and local directory.

    Parameters
    ----------
    local_root : str
        The local directory to store the jobs.
    remote_root : str, optional
        The argument takes no effect.
    remote_profile : dict, optional
        The remote profile. The default is {}.
    *args
        The arguments.
    **kwargs
        The keyword arguments.
    """

    def __init__(
        self,
        local_root,
        remote_root=None,
        remote_profile={},
        *args,
        **kwargs,
    ):
        assert isinstance(local_root, str)
        self.init_local_root = local_root
        self.init_remote_root = remote_root
        self.temp_local_root = os.path.abspath(local_root)
        self.temp_remote_root = os.path.abspath(local_root)
        self.remote_profile = remote_profile
        # self.job_uuid = None
        # self.submission = None
        # if job_uuid:
        #    self.job_uuid=job_uuid
        # else:
        #    self.job_uuid = str(uuid.uuid4())

    @classmethod
    def load_from_dict(cls, context_dict):
        local_root = context_dict["local_root"]
        remote_root = context_dict.get("remote_root", None)
        remote_profile = context_dict.get("remote_profile", {})
        instance = cls(
            local_root=local_root,
            remote_root=remote_root,
            remote_profile=remote_profile,
        )
        return instance

    def bind_submission(self, submission):
        self.submission = submission
        self.local_root = os.path.join(self.temp_local_root, submission.work_base)
        self.remote_root = os.path.join(self.temp_local_root, submission.work_base)
        # dlog.debug("debug:LazyLocalContext.bind_submission;"
        #     "submission.submission_hash:{submission.submission_hash};"
        #     "self.local_root:{self.local_root};"
        #     "self.remote_root:{self.remote_root}")

    def get_job_root(self):
        return self.local_root

    def upload(
        self,
        jobs,
        # local_up_files,
        dereference=True,
    ):
        pass

    def download(
        self,
        jobs,
        # remote_down_files,
        check_exists=False,
        mark_failure=True,
        back_error=False,
    ):
        pass

    #    for ii in job_dirs :
    #        for jj in remote_down_files :
    #            fname = os.path.join(self.local_root, ii, jj)
    #            exists = os.path.exists(fname)
    #            if not exists:
    #                if check_exists:
    #                    if mark_failure:
    #                        with open(os.path.join(self.local_root, ii, 'tag_failure_download_%s' % jj), 'w') as fp: pass
    #                    else:
    #                        pass
    #                else:
    #                    raise RuntimeError('do not find download file ' + fname)

    def block_checkcall(self, cmd):
        # script_dir = os.path.join(self.local_root, self.submission.work_base)
        # os.chdir(script_dir)
        proc = sp.Popen(
            cmd, cwd=self.local_root, shell=True, stdout=sp.PIPE, stderr=sp.PIPE
        )
        o, e = proc.communicate()
        stdout = SPRetObj(o)
        stderr = SPRetObj(e)
        code = proc.returncode
        if code != 0:
            raise RuntimeError(
                "Get error code %d in locally calling %s with job: %s ",
                (code, cmd, self.submission.submission_hash),
            )
        return None, stdout, stderr

    def block_call(self, cmd):
        proc = sp.Popen(
            cmd, cwd=self.local_root, shell=True, stdout=sp.PIPE, stderr=sp.PIPE
        )
        o, e = proc.communicate()
        stdout = SPRetObj(o)
        stderr = SPRetObj(e)
        code = proc.returncode
        return code, None, stdout, stderr

    def clean(self):
        pass

    def write_file(self, fname, write_str):
        os.makedirs(self.remote_root, exist_ok=True)
        with open(os.path.join(self.remote_root, fname), "w") as fp:
            fp.write(write_str)

    def read_file(self, fname):
        with open(os.path.join(self.remote_root, fname)) as fp:
            ret = fp.read()
        return ret

    def check_file_exists(self, fname):
        # submission_work_base = os.path.join(self.local_root, self.submission.work_base)
        # file_to_be_checked = os.path.join(submission_work_base, fname)
        # print('debug:dpdispatcher.LazyLocalContext().check_file_exists:file_to_be_checked', file_to_be_checked)
        # return os.path.isfile(file_to_be_checked)
        return os.path.isfile(os.path.join(self.remote_root, fname))

    def call(self, cmd):
        cwd = os.getcwd()
        proc = sp.Popen(
            cmd, cwd=self.local_root, shell=True, stdout=sp.PIPE, stderr=sp.PIPE
        )
        return proc

    def check_finish(self, proc):
        return proc.poll() is not None

    def get_return(self, proc):
        ret = proc.poll()
        if ret is None:
            return None, None, None
        else:
            try:
                o, e = proc.communicate()
                stdout = SPRetObj(o)
                stderr = SPRetObj(e)
            except sp.SubprocessError:
                stdout = None
                stderr = None
        return ret, stdout, stderr

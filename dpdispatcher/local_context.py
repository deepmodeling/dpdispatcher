import hashlib
import os
import shutil
import signal
import subprocess as sp
from glob import glob
from subprocess import TimeoutExpired

from dpdispatcher import dlog
from dpdispatcher.base_context import BaseContext


class SPRetObj(object):
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


def _check_file_path(fname):
    dirname = os.path.dirname(fname)
    if dirname != "":
        os.makedirs(dirname, exist_ok=True)


def _identical_files(fname0, fname1):
    with open(fname0) as fp:
        code0 = hashlib.sha1(fp.read().encode("utf-8")).hexdigest()
    with open(fname1) as fp:
        code1 = hashlib.sha1(fp.read().encode("utf-8")).hexdigest()
    return code0 == code1


class LocalContext(BaseContext):
    def __init__(
        self,
        local_root,
        remote_root,
        remote_profile={},
        *args,
        **kwargs,
    ):
        """
        local_root:
        remote_root:
        remote_profile:
        """
        assert type(local_root) == str
        self.init_local_root = local_root
        self.init_remote_root = remote_root
        self.temp_local_root = os.path.abspath(local_root)
        self.temp_remote_root = os.path.abspath(remote_root)
        self.remote_profile = remote_profile

    @classmethod
    def load_from_dict(cls, context_dict):
        local_root = context_dict["local_root"]
        remote_root = context_dict["remote_root"]
        remote_profile = context_dict.get("remote_profile", {})
        instance = cls(
            local_root=local_root,
            remote_root=remote_root,
            remote_profile=remote_profile,
        )
        return instance

    def get_job_root(self):
        return self.remote_root

    def bind_submission(self, submission):
        self.submission = submission
        self.local_root = os.path.join(self.temp_local_root, submission.work_base)
        self.remote_root = os.path.join(
            self.temp_remote_root, submission.submission_hash
        )

    def upload(self, submission):
        os.makedirs(self.remote_root, exist_ok=True)
        for ii in submission.belonging_tasks:
            local_job = os.path.join(self.local_root, ii.task_work_path)
            remote_job = os.path.join(self.remote_root, ii.task_work_path)
            os.makedirs(remote_job, exist_ok=True)

            file_list = []
            for kk in ii.forward_files:
                abs_file_list = glob(os.path.join(local_job, kk))
                if not abs_file_list:
                    raise RuntimeError(
                        "cannot find upload file " + os.path.join(local_job, kk)
                    )
                rel_file_list = [
                    os.path.relpath(ii, start=local_job) for ii in abs_file_list
                ]
                file_list.extend(rel_file_list)

            for jj in file_list:
                if not os.path.exists(os.path.join(local_job, jj)):
                    raise RuntimeError(
                        "cannot find upload file " + os.path.join(local_job, jj)
                    )
                if os.path.exists(os.path.join(remote_job, jj)):
                    os.remove(os.path.join(remote_job, jj))
                _check_file_path(os.path.join(remote_job, jj))
                os.symlink(os.path.join(local_job, jj), os.path.join(remote_job, jj))

        local_job = self.local_root
        remote_job = self.remote_root

        file_list = []
        for kk in submission.forward_common_files:
            abs_file_list = glob(os.path.join(local_job, kk))
            if not abs_file_list:
                raise RuntimeError(
                    "cannot find upload file " + os.path.join(local_job, kk)
                )
            rel_file_list = [
                os.path.relpath(ii, start=local_job) for ii in abs_file_list
            ]
            file_list.extend(rel_file_list)

        for jj in file_list:
            if not os.path.exists(os.path.join(local_job, jj)):
                raise RuntimeError(
                    "cannot find upload file " + os.path.join(local_job, jj)
                )
            if os.path.exists(os.path.join(remote_job, jj)):
                os.remove(os.path.join(remote_job, jj))
            _check_file_path(os.path.join(remote_job, jj))
            os.symlink(os.path.join(local_job, jj), os.path.join(remote_job, jj))

    def download(
        self, submission, check_exists=False, mark_failure=True, back_error=False
    ):
        for ii in submission.belonging_tasks:
            local_job = os.path.join(self.local_root, ii.task_work_path)
            remote_job = os.path.join(self.remote_root, ii.task_work_path)
            flist = ii.backward_files
            if back_error:
                flist += glob(os.path.join(remote_job, "error*"))
            for jj in flist:
                rfile = os.path.join(remote_job, jj)
                lfile = os.path.join(local_job, jj)
                if not os.path.realpath(rfile) == os.path.realpath(lfile):
                    if (not os.path.exists(rfile)) and (not os.path.exists(lfile)):
                        if check_exists:
                            if mark_failure:
                                tag_file_path = os.path.join(
                                    self.local_root,
                                    ii.task_work_path,
                                    "tag_failure_download_%s" % jj,
                                )
                                with open(tag_file_path, "w") as fp:
                                    pass
                            else:
                                pass
                        else:
                            raise RuntimeError("do not find download file " + rfile)
                    elif (not os.path.exists(rfile)) and (os.path.exists(lfile)):
                        # already downloaded
                        pass
                    elif (os.path.exists(rfile)) and (not os.path.exists(lfile)):
                        # trivial case, download happily
                        # for links, copy instead of moving (default behavior of copyfile is following symlinks)
                        if not os.path.islink(rfile):
                            shutil.move(rfile, lfile)
                        else:
                            shutil.copyfile(rfile, lfile)
                    elif (os.path.exists(rfile)) and (os.path.exists(lfile)):
                        # both exists, replace!
                        dlog.info("find existing %s, replacing by %s" % (lfile, rfile))
                        if os.path.isdir(lfile):
                            shutil.rmtree(lfile, ignore_errors=True)
                        elif os.path.isfile(lfile) or os.path.islink(lfile):
                            os.remove(lfile)
                        shutil.copyfile(rfile, lfile)
                    else:
                        raise RuntimeError("should not reach here!")
                else:
                    # no nothing in the case of linked files
                    pass
        local_job = self.local_root
        remote_job = self.remote_root
        flist = submission.backward_common_files
        if back_error:
            flist += glob(os.path.join(remote_job, "error*"))
        for jj in flist:
            rfile = os.path.join(remote_job, jj)
            lfile = os.path.join(local_job, jj)
            if not os.path.realpath(rfile) == os.path.realpath(lfile):
                if (not os.path.exists(rfile)) and (not os.path.exists(lfile)):
                    if check_exists:
                        if mark_failure:
                            with open(
                                os.path.join(
                                    self.local_root, "tag_failure_download_%s" % jj
                                ),
                                "w",
                            ) as fp:
                                pass
                        else:
                            pass
                    else:
                        raise RuntimeError("do not find download file " + rfile)
                elif (not os.path.exists(rfile)) and (os.path.exists(lfile)):
                    # already downloaded
                    pass
                elif (os.path.exists(rfile)) and (not os.path.exists(lfile)):
                    # trivial case, download happily
                    if not os.path.islink(rfile):
                        shutil.move(rfile, lfile)
                    else:
                        shutil.copyfile(rfile, lfile)
                elif (os.path.exists(rfile)) and (os.path.exists(lfile)):
                    dlog.info(f"both exist rfile:{rfile}; lfile:{lfile}")
                    # both exists, replace!
                    dlog.info("find existing %s, replacing by %s" % (lfile, rfile))
                    if os.path.isdir(lfile):
                        shutil.rmtree(lfile, ignore_errors=True)
                    elif os.path.isfile(lfile) or os.path.islink(lfile):
                        os.remove(lfile)
                    shutil.copyfile(rfile, lfile)
                else:
                    raise RuntimeError("should not reach here!")
            else:
                # no nothing in the case of linked files
                pass

    def block_checkcall(self, cmd):
        proc = sp.Popen(
            cmd, cwd=self.remote_root, shell=True, stdout=sp.PIPE, stderr=sp.PIPE
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
            cmd, cwd=self.remote_root, shell=True, stdout=sp.PIPE, stderr=sp.PIPE
        )
        o, e = proc.communicate()
        stdout = SPRetObj(o)
        stderr = SPRetObj(e)
        code = proc.returncode
        return code, None, stdout, stderr

    def clean(self):
        shutil.rmtree(self.remote_root, ignore_errors=True)

    def write_file(self, fname, write_str):
        os.makedirs(self.remote_root, exist_ok=True)
        with open(os.path.join(self.remote_root, fname), "w") as fp:
            fp.write(write_str)

    def read_file(self, fname):
        with open(os.path.join(self.remote_root, fname), "r") as fp:
            ret = fp.read()
        return ret

    def check_file_exists(self, fname):
        return os.path.isfile(os.path.join(self.remote_root, fname))

    def call(self, cmd):
        proc = sp.Popen(
            cmd, cwd=self.remote_root, shell=True, stdout=sp.PIPE, stderr=sp.PIPE
        )
        return proc

    def kill(self, job_id):
        os.kill(job_id, signal.SIGTERM)

    def check_finish(self, proc):
        return proc.poll() != None

    def get_return(self, proc):
        ret = proc.poll()
        if ret is None:
            return None, None, None
        else:
            try:
                o, e = proc.communicate()
                stdout = SPRetObj(o)
                stderr = SPRetObj(e)
            except TimeoutExpired:
                stdout = None
                stderr = None
        return ret, stdout, stderr

from dpdispatcher.base_context import BaseContext
import os,shutil,uuid
import subprocess as sp
from glob import glob
from dpdispatcher import dlog

class SPRetObj(object) :
    def __init__ (self,
                ret) :
        self.data = ret

    def read(self) :
        return self.data

    def readlines(self) :
        lines = self.data.decode('utf-8').splitlines()
        ret = []
        for aa in lines:
            ret.append(aa+'\n')
        return ret

class LazyLocalContext(BaseContext) :
    def __init__ (self,
                local_root,
                remote_root=None,
                remote_profile={}
                ):
        """
        local_root:
        remote_root:
        remote_profile:
        """
        assert(type(local_root) == str)
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
        local_root = context_dict['local_root']
        remote_root = context_dict.get('remote_root', None)
        remote_profile = context_dict.get('remote_profile', {})
        instance = cls(
            local_root=local_root,
            remote_root=remote_root,
            remote_profile=remote_profile
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

    def get_job_root(self) :
        return self.local_root

    def upload(self,
               jobs,
               # local_up_files,
               dereference = True) :
        pass

    def download(self, 
                 jobs,
                 # remote_down_files,
                 check_exists = False,
                 mark_failure = True,
                 back_error=False) :
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


    def block_checkcall(self,
                        cmd) :
        cwd = os.getcwd()
        # script_dir = os.path.join(self.local_root, self.submission.work_base)
        os.chdir(self.local_root)
        # os.chdir(script_dir)
        proc = sp.Popen(cmd, shell=True, stdout = sp.PIPE, stderr = sp.PIPE)
        o, e = proc.communicate()
        stdout = SPRetObj(o)
        stderr = SPRetObj(e)
        code = proc.returncode
        if code != 0:
            os.chdir(cwd)        
            raise RuntimeError("Get error code %d in locally calling %s with job: %s ", (code, cmd, self.submission.submission_hash))
        os.chdir(cwd)        
        return None, stdout, stderr
        
    def block_call(self, cmd) :
        cwd = os.getcwd()
        os.chdir(self.local_root)
        proc = sp.Popen(cmd, shell=True, stdout = sp.PIPE, stderr = sp.PIPE)
        o, e = proc.communicate()
        stdout = SPRetObj(o)
        stderr = SPRetObj(e)
        code = proc.returncode
        os.chdir(cwd)        
        return code, None, stdout, stderr

    def clean(self) :
        pass

    def write_file(self, fname, write_str):
        os.makedirs(self.remote_root, exist_ok = True)
        with open(os.path.join(self.remote_root, fname), 'w') as fp :
            fp.write(write_str)

    def read_file(self, fname):
        with open(os.path.join(self.remote_root, fname), 'r') as fp:
            ret = fp.read()
        return ret

    def check_file_exists(self, fname):
        # submission_work_base = os.path.join(self.local_root, self.submission.work_base)
        # file_to_be_checked = os.path.join(submission_work_base, fname)
        # print('debug:dpdispatcher.LazyLocalContext().check_file_exists:file_to_be_checked', file_to_be_checked)
        # return os.path.isfile(file_to_be_checked)
        return os.path.isfile(os.path.join(self.remote_root, fname))
        
    def call(self, cmd) :
        cwd = os.getcwd()
        os.chdir(self.local_root)
        proc = sp.Popen(cmd, shell=True, stdout = sp.PIPE, stderr = sp.PIPE)
        os.chdir(cwd)        
        return proc

    def kill(self, proc):
        proc.kill()

    def check_finish(self, proc):
        return (proc.poll() != None)

    def get_return(self, proc):
        ret = proc.poll()
        if ret is None:
            return None, None, None
        else :
            try:
                o, e = proc.communicate()
                stdout = SPRetObj(o)
                stderr = SPRetObj(e)
            except:
                stdout = None
                stderr = None
        return ret, stdout, stderr
    
    

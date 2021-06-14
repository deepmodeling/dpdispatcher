#!/usr/bin/env python
# coding: utf-8

from dpdispatcher.base_context import BaseContext
import os, sys, paramiko, json, uuid, tarfile, time, stat, shutil
from glob import glob
from dpdispatcher import dlog
from dargs.dargs import Argument
# from dpdispatcher.submission import Machine

class SSHSession (object):
    def __init__(self,
                hostname,
                username,
                password=None,
                port=22,
                key_filename=None,
                passphrase=None,
                timeout=10):

        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.key_filename = key_filename
        self.passphrase = passphrase
        self.timeout = timeout
        self.ssh = None
        self._setup_ssh()

    # @classmethod
    # def deserialize(cls, jdata):
    #     instance = cls(**jdata)
    #     return instance
        
    # def bk_ensure_alive(self,
    #                  max_check = 10,
    #                  sleep_time = 10):
    #     count = 1
    #     while not self._check_alive():
    #         if count == max_check:
    #             raise RuntimeError('cannot connect ssh after %d failures at interval %d s' %
    #                                (max_check, sleep_time))
    #         dlog.info('connection check failed, try to reconnect to ' + self.remote_host)
    #         self._setup_ssh(hostname=self.remote_host,
    #                         port=self.remote_port,
    #                         username=self.remote_uname,
    #                         password=self.remote_password,
    #                         key_filename=self.local_key_filename,
    #                         timeout=self.remote_timeout,
    #                         passphrase=self.local_key_passphrase)
    #         count += 1
    #         time.sleep(sleep_time)

    def ensure_alive(self,
                    max_check = 10,
                    sleep_time = 10):
        count = 1
        while not self._check_alive():
            if count == max_check:
                raise RuntimeError('cannot connect ssh after %d failures at interval %d s' %
                                    (max_check, sleep_time))
            dlog.info('connection check failed, try to reconnect to ' + self.remote_root)
            self._setup_ssh()
            count += 1
            time.sleep(sleep_time)

    def _check_alive(self):
        if self.ssh == None:
            return False
        try :
            transport = self.ssh.get_transport()
            transport.send_ignore()
            return True
        except EOFError:
            return False        

    # def bk_setup_ssh(self,
    #                hostname,
    #                port=22,
    #                username=None,
    #                password=None,
    #                key_filename=None,
    #                timeout=None,
    #                passphrase=None):
    #     self.ssh = paramiko.SSHClient()
    #     # ssh_client.load_system_host_keys()
    #     self.ssh.set_missing_host_key_policy(paramiko.WarningPolicy)
    #     self.ssh.connect(hostname=hostname, port=port,
    #                      username=username, password=password,
    #                      key_filename=key_filename, timeout=timeout, passphrase=passphrase)
    #     assert(self.ssh.get_transport().is_active())
    #     transport = self.ssh.get_transport()
    #     transport.set_keepalive(60)
    
    def _setup_ssh(self):
        # machine = self.machine
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.WarningPolicy)
        self.ssh.connect(hostname=self.hostname, port=self.port,
                        username=self.username, password=self.password,
                        key_filename=self.key_filename, timeout=self.timeout,passphrase=self.passphrase)
        assert(self.ssh.get_transport().is_active())
        transport = self.ssh.get_transport()
        transport.set_keepalive(60)
        # reset sftp
        self._sftp = None
                        

    def get_ssh_client(self) :
        return self.ssh

    # def get_session_root(self) :
    #     return self.remote_root

    def close(self) :
        self.ssh.close()

    def exec_command(self, cmd, retry = 0):
        """Calling self.ssh.exec_command but has an exception check."""
        try:
            return self.ssh.exec_command(cmd)
        except paramiko.ssh_exception.SSHException:
            # SSH session not active
            # retry for up to 3 times
            if retry < 3:
                dlog.warning("SSH session not active in calling %s, retry the command..." % cmd)
                # ensure alive
                self.ensure_alive()
                return self.exec_command(cmd, retry = retry+1)
            raise RuntimeError("SSH session not active")

    @property
    def sftp(self):
        """Returns sftp. Open a new one if not existing."""
        if self._sftp is None:
            self.ensure_alive()
            self._sftp = self.ssh.open_sftp()
        return self._sftp

    @staticmethod
    def arginfo():
        doc_hostname = 'hostname or ip of ssh connection.'
        doc_username = 'username of target linux system'
        doc_password = 'password of linux system'
        doc_port = 'ssh connection port.'
        doc_key_filename = 'key_filename used by ssh connection'
        doc_passphrase = 'passphrase used by ssh connection'
        doc_timeout = 'timeout of ssh connection'

        ssh_remote_profile_args = [
            Argument("hostname", str, optional=False, doc=doc_hostname),
            Argument("username", str, optional=False, doc=doc_username),
            Argument("password", str, optional=True, doc=doc_password),
            Argument("port", int, optional=True, default=22, doc=doc_port),
            Argument("key_filename", [str, None], optional=True, default=None, doc=doc_key_filename),
            Argument("passphrase", [str, None], optional=True, default=None, doc=doc_passphrase),
            Argument("timeout", int, optional=True, default=10, doc=doc_timeout)
        ]
        ssh_remote_profile_format = Argument("ssh_session", dict, ssh_remote_profile_args)
        return ssh_remote_profile_format
        

class SSHContext(BaseContext):
    def __init__ (self,
                local_root,
                remote_root,
                remote_profile,
                clean_asynchronously=False,
                ):
        assert(type(local_root) == str)
        self.temp_local_root = os.path.abspath(local_root)
        # self.job_uuid = None
        self.clean_asynchronously = clean_asynchronously
        # self.job_uuid = job_uuid
        # if job_uuid:
        #    self.job_uuid=job_uuid
        # else:
        #    self.job_uuid = str(uuid.uuid4())
        self.ssh_session = SSHSession(**remote_profile)
        # self.temp_remote_root = os.path.join(self.ssh_session.get_session_root())
        self.temp_remote_root = remote_root
        self.ssh_session.ensure_alive()
        try:
            self.sftp.mkdir(self.temp_remote_root)
        except OSError: 
            pass

    @classmethod
    def load_from_dict(cls, context_dict):
        # instance = cls()
        # input = dict(
        #     hostname = jdata['hostname'],
        #     remote_root = jdata['remote_root'],
        #     username = jdata['username'],
        #     password = jdata.get('password', None),
        #     port = jdata.get('port', 22),
        #     key_filename = jdata.get('key_filename', None),
        #     passphrase = jdata.get('passphrase', None),
        #     timeout = jdata.get('timeout', 10),
        # )
        local_root = context_dict['local_root']
        remote_root = context_dict['remote_root']
        remote_profile = context_dict['remote_profile']
        clean_asynchronously = context_dict.get('clean_asynchronously', False)

        ssh_context = cls(
            local_root=local_root,
            remote_root=remote_root,
            remote_profile=remote_profile,
            clean_asynchronously=clean_asynchronously
        )
        # local_root = jdata['local_root']
        # ssh_session = SSHSession(**input)
        # ssh_context = SSHContext(
        #     local_root=local_root,
        #     ssh_session=ssh_session,
        #     clean_asynchronously=jdata.get('clean_asynchronously', False),
        #     )
        return ssh_context

    @property
    def ssh(self):
        return self.ssh_session.get_ssh_client()  

    @property
    def sftp(self):
        return self.ssh_session.sftp

    def close(self):
        self.ssh_session.close()

    def get_job_root(self) :
        return self.remote_root

    def bind_submission(self, submission):
        self.submission = submission
        self.local_root = os.path.join(self.temp_local_root, submission.work_base)
        # self.remote_root = os.path.join(self.temp_remote_root, self.submission.submission_hash, self.submission.work_base )
        self.remote_root = os.path.join(self.temp_remote_root, self.submission.submission_hash)

        # self.job_uuid = submission.submission_hash
        # dlog.debug("debug:SSHContext.bind_submission"
        #     "{submission.submission_hash}; {self.local_root}; {self.remote_root")

        # try:
        # print('self.remote_root', self.remote_root)
        # sftp = self.ssh_session.ssh.open_sftp() 
        # sftp.mkdir(self.remote_root)
        # sftp.close()
        # except:
        #     pass
        
    def upload(self,
               # job_dirs,
               submission,
               # local_up_files,
               dereference = True) :
        self.ssh_session.ensure_alive()
        cwd = os.getcwd()
        os.chdir(self.local_root) 
        file_list = []
        
      #   for ii in job_dirs :
        for task in submission.belonging_tasks :
            for jj in task.forward_files :
                # file_list.append(os.path.join(ii, jj))        
                file_list.append(os.path.join(task.task_work_path, jj))        
        # for ii in submission.forward_common_files:
        #     file_list.append(ii)
        file_list.extend(submission.forward_common_files)

        self._put_files(file_list, dereference = dereference)
        os.chdir(cwd)

    def download(self, 
                 submission,
                 # job_dirs,
                 # remote_down_files,
                 check_exists = False,
                 mark_failure = True,
                 back_error=False) :
        self.ssh_session.ensure_alive()
        cwd = os.getcwd()
        os.chdir(self.local_root) 
        file_list = []
        # for ii in job_dirs :
        for task in submission.belonging_tasks :
            for jj in task.backward_files:
                file_name = os.path.join(task.task_work_path, jj)                
                if check_exists:
                    if self.check_file_exists(file_name):
                        file_list.append(file_name)
                    elif mark_failure :
                        with open(os.path.join(self.local_root, task.task_work_path, 'tag_failure_download_%s' % jj), 'w') as fp: pass
                    else:
                        pass
                else:
                    file_list.append(file_name)
            if back_error:
                errors=glob(os.path.join(task.task_work_path, 'error*'))
                file_list.extend(errors)
        file_list.extend(submission.backward_common_files)
        if len(file_list) > 0:
            self._get_files(file_list)
        os.chdir(cwd)
        
    def block_checkcall(self, 
                        cmd,
                        asynchronously=False,
                        stderr_whitelist=None) :
        """Run command with arguments. Wait for command to complete. If the return code
        was zero then return, otherwise raise RuntimeError.

        Parameters
        ----------
        cmd: str
            The command to run.
        asynchronously: bool, optional, default=False
            Run command asynchronously. If True, `nohup` will be used to run the command.
        """
        self.ssh_session.ensure_alive()
        if asynchronously:
            cmd = "nohup %s >/dev/null &" % cmd
        stdin, stdout, stderr = self.ssh_session.exec_command(('cd %s ;' % self.remote_root) + cmd)
        exit_status = stdout.channel.recv_exit_status() 
        if exit_status != 0:
            raise RuntimeError("Get error code %d in calling %s through ssh with job: %s . message: %s" %
                              (exit_status, cmd, self.submission.submission_hash, stderr.read().decode('utf-8')))
        return stdin, stdout, stderr    

    def block_call(self, 
                   cmd) :
        self.ssh_session.ensure_alive()
        stdin, stdout, stderr = self.ssh_session.exec_command(('cd %s ;' % self.remote_root) + cmd)
        exit_status = stdout.channel.recv_exit_status() 
        return exit_status, stdin, stdout, stderr

    def clean(self) :        
        self.ssh_session.ensure_alive()
        self._rmtree(self.remote_root)

    def write_file(self, fname, write_str):
        self.ssh_session.ensure_alive()
        with self.sftp.open(os.path.join(self.remote_root, fname), 'w') as fp :
            fp.write(write_str)

    def read_file(self, fname):
        self.ssh_session.ensure_alive()
        with self.sftp.open(os.path.join(self.remote_root, fname), 'r') as fp:
            ret = fp.read().decode('utf-8')
        return ret

    def check_file_exists(self, fname):
        self.ssh_session.ensure_alive()
        try:
            self.sftp.stat(os.path.join(self.remote_root, fname)) 
            ret = True
        except IOError:
            ret = False
        return ret        
        
    def call(self, cmd):
        stdin, stdout, stderr = self.ssh_session.exec_command(cmd)
        # stdin, stdout, stderr = self.ssh.exec_command('echo $$; exec ' + cmd)
        # pid = stdout.readline().strip()
        # print(pid)
        return {'stdin':stdin, 'stdout':stdout, 'stderr':stderr}
    
    def check_finish(self, cmd_pipes):
        return cmd_pipes['stdout'].channel.exit_status_ready()


    def get_return(self, cmd_pipes):
        if not self.check_finish(cmd_pipes):
            return None, None, None
        else :
            retcode = cmd_pipes['stdout'].channel.recv_exit_status()
            return retcode, cmd_pipes['stdout'], cmd_pipes['stderr']

    def kill(self, cmd_pipes) :
        raise RuntimeError('dose not work! we do not know how to kill proc through paramiko.SSHClient')
        self.block_checkcall('kill -15 %s' % cmd_pipes['pid'])


    def _rmtree(self, remotepath, verbose = False):
        """Remove the remote path."""
        # The original implementation method removes files one by one using sftp.
        # If the latency of the remote server is high, it is very slow.
        # Thus, it's better to use system's `rm` to remove a directory, which may
        # save a lot of time.
        if verbose:
            dlog.info('removing %s' % remotepath)
        # In some supercomputers, it's very slow to remove large numbers of files
        # (e.g. directory containing trajectory) due to bad I/O performance.
        # So an asynchronously option is provided.
        self.block_checkcall('rm -rf %s' % remotepath, asynchronously=self.clean_asynchronously)

    def _put_files(self,
                   files,
                   dereference = True) :
        of = self.submission.submission_hash + '.tgz'
        # local tar
        cwd = os.getcwd()
        os.chdir(self.local_root)
        if os.path.isfile(of) :
            os.remove(of)
        with tarfile.open(of, "w:gz", dereference = dereference) as tar:
            for ii in files :
                tar.add(ii)
        os.chdir(cwd)

        try:
            self.sftp.mkdir(self.remote_root)
        except OSError: 
            pass
        # trans
        from_f = os.path.join(self.local_root, of)
        to_f = os.path.join(self.remote_root, of)
        try:
           self.sftp.put(from_f, to_f)
        except FileNotFoundError:
           raise FileNotFoundError("from %s to %s @ %s : %s Error!"%(from_f, self.ssh_session.username, self.ssh_session.hostname, to_f))
        # remote extract
        self.block_checkcall('tar xf %s' % of)
        # clean up
        os.remove(from_f)
        self.sftp.remove(to_f)

    def _get_files(self, 
                   files) :
        of = self.submission.submission_hash + '.tar.gz'
        # remote tar
        # If the number of files are large, we may get "Argument list too long" error.
        # Thus, we may run tar commands for serveral times and tar only 100 files for
        # each time.
        per_nfile = 100
        ntar = len(files) // per_nfile + 1
        if ntar <= 1:
            self.block_checkcall('tar czf %s %s' % (of, " ".join(files)))
        else:
            of_tar = self.submission.submission_hash + '.tar'
            for ii in range(ntar):
                ff = files[per_nfile * ii : per_nfile * (ii+1)]
                if ii == 0:
                    # tar cf for the first time
                    self.block_checkcall('tar cf %s %s' % (of_tar, " ".join(ff)))
                else:
                    # append using tar rf
                    # -r, --append append files to the end of an archive
                    self.block_checkcall('tar rf %s %s' % (of_tar, " ".join(ff)))
            # compress the tar file using gzip, and will get a tar.gz file
            # overwrite considering dpgen may stop and restart
            # -f, --force force overwrite of output file and compress links
            self.block_checkcall('gzip -f %s' % of_tar)
        # trans
        from_f = os.path.join(self.remote_root, of)
        to_f = os.path.join(self.local_root, of)
        if os.path.isfile(to_f) :
            os.remove(to_f)
        self.sftp.get(from_f, to_f)
        # extract
        cwd = os.getcwd()
        os.chdir(self.local_root)
        with tarfile.open(of, "r:gz") as tar:
            tar.extractall()
        os.chdir(cwd)        
        # cleanup
        os.remove(to_f)
        self.sftp.remove(from_f)

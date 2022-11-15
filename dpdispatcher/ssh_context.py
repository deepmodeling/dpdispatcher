#!/usr/bin/env python
# coding: utf-8

from dpdispatcher.base_context import BaseContext
import os, paramiko, tarfile, time
import uuid
import shutil
from functools import lru_cache
from glob import glob
from dpdispatcher import dlog
from dargs.dargs import Argument
from typing import List
import pathlib
import socket
# from dpdispatcher.submission import Machine
from dpdispatcher.utils import (
    get_sha256, generate_totp, rsync,
    retry, RetrySignal,
)

class SSHSession (object):
    def __init__(self,
                hostname,
                username,
                password=None,
                port=22,
                key_filename=None,
                passphrase=None,
                timeout=10,
                totp_secret=None,
                tar_compress=True
                ):

        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.key_filename = key_filename
        self.passphrase = passphrase
        self.timeout = timeout
        self.totp_secret = totp_secret
        self.ssh = None
        self.tar_compress = tar_compress
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
        if self.ssh is None:
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
    
    @retry(max_retry=3, sleep=1)
    def _setup_ssh(self):
        # machine = self.machine
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy)
        # if self.totp_secret and self.password is None:
        #     self.password = generate_totp(self.totp_secret)
        # self.ssh.connect(hostname=self.hostname, port=self.port,
        #                 username=self.username, password=self.password,
        #                 key_filename=self.key_filename, timeout=self.timeout,passphrase=self.passphrase,
        #                 compress=True,
        #                 )
        # assert(self.ssh.get_transport().is_active())
        # transport = self.ssh.get_transport()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect((self.hostname, self.port))

        #Make a Paramiko Transport object using the socket
        ts = paramiko.Transport(sock)
        ts.banner_timeout = 60
        ts.use_compression(compress=True)

        #Tell Paramiko that the Transport is going to be used as a client
        ts.start_client(timeout=self.timeout)

        #Begin authentication; note that the username and callback are passed
        key_path = os.path.join(os.path.expanduser("~"), ".ssh", "id_rsa")
        if self.key_filename:
            key_path = os.path.abspath(self.key_filename)
        key = None
        key_ok = False
        key_error = None
        if os.path.exists(key_path):
            try:
                key = paramiko.RSAKey.from_private_key_file(key_path)
            except paramiko.PasswordRequiredException:
                key = paramiko.RSAKey.from_private_key_file(key_path, self.passphrase)
        if key is not None:
            try:
                ts.auth_publickey(self.username, key)
            except paramiko.ssh_exception.AuthenticationException as e:
                key_error = e
            else:
                key_ok = True
        if self.totp_secret is not None:
            try:
                ts.auth_interactive(self.username, self.inter_handler)
            except paramiko.ssh_exception.AuthenticationException:
                # since the asynchrony of interactive authentication, one addtional try is added
                # retry for up to 3 times
                raise RetrySignal("Authentication failed")
        elif key_ok:
            pass
        elif self.password is not None:
            ts.auth_password(self.username, self.password)
        elif key_error is not None:
            raise RuntimeError("Authentication failed, try to provide password") from key_error
        else:
            raise RuntimeError("Please provide at least one form of authentication")
        assert(ts.is_active())
        #Opening a session creates a channel along the socket to the server
        ts.open_session(timeout=self.timeout)
        ts.set_keepalive(60)
        self.ssh._transport = ts
        # reset sftp
        self._sftp = None
                        
    def inter_handler(self, title, instructions, prompt_list):
        """
        inter_handler: the callback for paramiko.transport.auth_interactive

        The prototype for this function is defined by Paramiko, so all of the
        arguments need to be there, even though we don't use 'title' or
        'instructions'.

        The function is expected to return a tuple of data containing the
        responses to the provided prompts. Experimental results suggests that
        there will be one call of this function per prompt, but the mechanism
        allows for multiple prompts to be sent at once, so it's best to assume
        that that can happen.

        Since tuples can't really be built on the fly, the responses are 
        collected in a list which is then converted to a tuple when it's time
        to return a value.

        Experiments suggest that the username prompt never happens. This makes
        sense, but the Username prompt is included here just in case.
        """

        resp = []  #Initialize the response container

        #Walk the list of prompts that the server sent that we need to answer
        for pr in prompt_list:
            #str() used to to make sure that we're dealing with a string rather than a unicode string
            #strip() used to get rid of any padding spaces sent by the server
            pr_str = str(pr[0]).strip().lower()
            if "username" in pr_str:
                resp.append(self.username)
            elif "password" in pr_str:
                resp.append(self.password)
            elif "verification" in pr_str or "token" in pr_str and self.totp_secret:
                resp.append(generate_totp(self.totp_secret))

        return tuple(resp)  #Convert the response list to a tuple and return it

    def get_ssh_client(self) :
        return self.ssh

    # def get_session_root(self):
    #     return self.remote_root

    def close(self) :
        self.ssh.close()

    @retry(sleep=1)
    def exec_command(self, cmd):
        """Calling self.ssh.exec_command but has an exception check."""
        try:
            return self.ssh.exec_command(cmd)
        except (paramiko.ssh_exception.SSHException, socket.timeout) as e:
            # SSH session not active
            # retry for up to 3 times
            # ensure alive
            self.ensure_alive()
            raise RetrySignal("SSH session not active in calling %s" % cmd) from e

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
        doc_password = ('(deprecated) password of linux system. Please use '
                        '`SSH keys <https://www.ssh.com/academy/ssh/key>`_ instead to improve security.')
        doc_port = 'ssh connection port.'
        doc_key_filename = 'key filename used by ssh connection. If left None, find key in ~/.ssh or ' \
                           'use password for login'
        doc_passphrase = 'passphrase of key used by ssh connection'
        doc_timeout = 'timeout of ssh connection'
        doc_totp_secret = 'Time-based one time password secret. It should be a base32-encoded string' \
                          ' extracted from the 2D code.'
        doc_tar_compress = 'The archive will be compressed in upload and download if it is True. If not, compression will be skipped.'

        ssh_remote_profile_args = [
            Argument("hostname", str, optional=False, doc=doc_hostname),
            Argument("username", str, optional=False, doc=doc_username),
            Argument("password", str, optional=True, doc=doc_password),
            Argument("port", int, optional=True, default=22, doc=doc_port),
            Argument("key_filename", [str, None], optional=True, default=None, doc=doc_key_filename),
            Argument("passphrase", [str, None], optional=True, default=None, doc=doc_passphrase),
            Argument("timeout", int, optional=True, default=10, doc=doc_timeout),
            Argument("totp_secret", str, optional=True, default=None, doc=doc_totp_secret),
            Argument("tar_compress", bool, optional=True, default=True, doc = doc_tar_compress),
        ]
        ssh_remote_profile_format = Argument("ssh_session", dict, ssh_remote_profile_args)
        return ssh_remote_profile_format
        
    def put(self, from_f, to_f):
        if self.rsync_available:
            return rsync(from_f, self.remote + ":" + to_f, port=self.port, key_filename=self.key_filename, timeout=self.timeout)
        return self.sftp.put(from_f, to_f)

    def get(self, from_f, to_f):
        if self.rsync_available:
            return rsync(self.remote + ":" + from_f, to_f, port=self.port, key_filename=self.key_filename, timeout=self.timeout)
        return self.sftp.get(from_f, to_f)

    @property
    @lru_cache(maxsize=None)
    def rsync_available(self) -> bool:
        return (shutil.which("rsync") is not None and self.password is None
            and self.exec_command("rsync --version")[1].channel.recv_exit_status() == 0
            and self.totp_secret is None
            and self.passphrase is None)

    @property
    def remote(self) -> str:
        return "%s@%s" % (self.username, self.hostname)


class SSHContext(BaseContext):
    def __init__ (self,
                local_root,
                remote_root,
                remote_profile,
                clean_asynchronously=False,
                *args,
                **kwargs,
                ):
        assert(type(local_root) == str)
        self.init_local_root = local_root
        self.init_remote_root = remote_root
        self.temp_local_root = os.path.abspath(local_root)
        assert os.path.isabs(remote_root), f"remote_root must be a abspath"
        self.temp_remote_root = remote_root
        self.remote_profile = remote_profile
        self.remote_root = None

        # self.job_uuid = None
        self.clean_asynchronously = clean_asynchronously
        # self.job_uuid = job_uuid
        # if job_uuid:
        #    self.job_uuid=job_uuid
        # else:
        #    self.job_uuid = str(uuid.uuid4())
        self.ssh_session = SSHSession(**remote_profile)
        # self.temp_remote_root = os.path.join(self.ssh_session.get_session_root())
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
        #     tar_compress = jdata.get('tar_compress', True)
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
        self.local_root = pathlib.PurePath(os.path.join(self.temp_local_root, submission.work_base)).as_posix()
        old_remote_root = self.remote_root
        # self.remote_root = os.path.join(self.temp_remote_root, self.submission.submission_hash, self.submission.work_base )
        self.remote_root = pathlib.PurePath(os.path.join(self.temp_remote_root, self.submission.submission_hash)).as_posix()
        # move the working directory if remote_root changes
        if old_remote_root is not None and old_remote_root != self.remote_root \
            and self.check_file_exists(old_remote_root) \
            and not self.check_file_exists(self.remote_root):
            self.block_checkcall(f"mv {old_remote_root} {self.remote_root}")

        sftp = self.ssh_session.ssh.open_sftp()
        try:
            sftp.mkdir(self.remote_root)
        except OSError:
            pass

        # self.job_uuid = submission.submission_hash
        # dlog.debug("debug:SSHContext.bind_submission"
        #     "{submission.submission_hash}; {self.local_root}; {self.remote_root")

        # try:
        # print('self.remote_root', self.remote_root)
        # sftp = self.ssh_session.ssh.open_sftp() 
        # sftp.mkdir(self.remote_root)
        # sftp.close()
        # except Exception:
        #     pass

    def _walk_directory(self, files, work_path, file_list, directory_list):
        """Convert input path to list of files and directories."""
        for jj in files :
            file_name = os.path.join(work_path, jj)
            if os.path.isfile(file_name):
                file_list.append(file_name)
            elif os.path.isdir(file_name):
                for root, dirs, files in os.walk(file_name, topdown=False, followlinks=True):
                    if not files:
                        directory_list.append(root)
                    for name in files:
                        file_list.append(os.path.join(root, name))
            elif glob(file_name):
                # If the file name contains a wildcard, os.path functions will fail to identify it. Use glob to get the complete list of filenames which match the wildcard.
                abs_file_list = glob(file_name)
                rel_file_list = [os.path.relpath(ii, start=work_path) for ii in abs_file_list]
                self._walk_directory(rel_file_list, work_path, file_list, directory_list)
            else:
                raise RuntimeError(f'cannot find upload file {work_path} {jj}')

    def upload(self,
               # job_dirs,
               submission,
               # local_up_files,
               dereference = True) :
        dlog.info(f'remote path: {self.remote_root}')
        # remote_cwd = 
        self.ssh_session.sftp.chdir(self.temp_remote_root)
        recover = False
        try:
            self.ssh_session.sftp.mkdir(os.path.basename(self.remote_root))
        except OSError:
            # mkdir failed meaning it exists
            if len(self.ssh_session.sftp.listdir(os.path.basename(self.remote_root))):
                recover = True
        self.ssh_session.sftp.chdir(None)

        cwd = os.getcwd()
        os.chdir(self.local_root) 
        file_list = []
        directory_list = []
        for task in submission.belonging_tasks:
            directory_list.append(task.task_work_path)
        #     file_list.append(ii)
            self._walk_directory(task.forward_files, task.task_work_path, file_list, directory_list)
        self._walk_directory(submission.forward_common_files, self.local_root, file_list, directory_list)

        # check if the same file exists on the remote file
        # only check sha256 when the job is recovered
        if recover:
            # generate local sha256 file
            sha256_list = []
            for jj in file_list:
                sha256 = get_sha256(jj)
                jj_rel = pathlib.PurePath(os.path.relpath(jj, self.local_root)).as_posix()
                sha256_list.append(f"{sha256}  {jj_rel}")
            # write to remote
            sha256_file = os.path.join(self.remote_root, ".tmp.sha256." + str(uuid.uuid4()))
            self.write_file(sha256_file, "\n".join(sha256_list))
            # check sha256
            # `:` means pass: https://stackoverflow.com/a/2421592/9567349
            _, stdout, _ = self.block_checkcall("sha256sum -c %s --quiet >.sha256sum_stdout 2>/dev/null || :" % sha256_file)
            self.sftp.remove(sha256_file)
            # regenerate file list
            file_list = []

            for ii in self.read_file(".sha256sum_stdout").split("\n"):
                if ii:
                    file_list.append(ii.split(":")[0])
        else:
            # convert to relative path to local_root
            file_list = [os.path.relpath(jj, self.local_root) for jj in file_list] 

        self._put_files(file_list, dereference = dereference, directories=directory_list, tar_compress = self.remote_profile.get('tar_compress', None))
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
                file_name = pathlib.PurePath(os.path.join(task.task_work_path, jj)).as_posix()
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
            self._get_files(file_list, tar_compress = self.remote_profile.get('tar_compress', None))
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
        fname = pathlib.PurePath(os.path.join(self.remote_root, fname)).as_posix()
        # to prevent old file from being overwritten but cancelled, create a temporary file first
        # when it is fully written, rename it to the original file name
        with self.sftp.open(fname + "~", 'w') as fp :
            fp.write(write_str)
        # sftp.rename may throw OSError
        self.block_checkcall("mv %s %s" % (fname + "~", fname))

    def read_file(self, fname):
        self.ssh_session.ensure_alive()
        with self.sftp.open(pathlib.PurePath(os.path.join(self.remote_root, fname)).as_posix(), 'r') as fp:
            ret = fp.read().decode('utf-8')
        return ret

    def check_file_exists(self, fname):
        self.ssh_session.ensure_alive()
        try:
            self.sftp.stat(pathlib.PurePath(os.path.join(self.remote_root, fname)).as_posix())
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
        #self.block_checkcall('kill -15 %s' % cmd_pipes['pid'])


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
                   dereference = True,
                   directories = None,
                   tar_compress = True,
                   ) :
        """Upload files to server.

        Parameters
        ----------
        files: list
            uploaded files
        dereference: bool, default: True
            If dereference is False, add symbolic and hard links to the archive.
            If it is True, add the content of the target files to the archive.
            This has no effect on systems that do not support symbolic links.
        directories: list, default: None
            uploaded directories non-recursively. Use `files` for uploading
            recursively
        tar_compress: bool, default: True
            If tar_compress is True, compress the archive using gzip
            It it is False, then it is uncompressed
        """
        of_suffix = '.tgz'
        tarfile_mode = "w:gz"
        kwargs = {'compresslevel': 6}
        if not tar_compress :
            of_suffix = '.tar'
            tarfile_mode = "w"
            kwargs = {}
                    
        of = self.submission.submission_hash + of_suffix
        # local tar
        cwd = os.getcwd()
        os.chdir(self.local_root)
        if os.path.isfile(of) :
            os.remove(of)
        with tarfile.open(of, tarfile_mode, dereference = dereference, **kwargs) as tar:
            for ii in files :
                tar.add(ii)
            if directories is not None:
                for ii in directories:
                    tar.add(ii, recursive=False)
        os.chdir(cwd)
        self.ssh_session.ensure_alive()
        try:
            self.sftp.mkdir(self.remote_root)
        except OSError: 
            pass
        # trans
        from_f = pathlib.PurePath(os.path.join(self.local_root, of)).as_posix()
        to_f = pathlib.PurePath(os.path.join(self.remote_root, of)).as_posix()
        try:
           self.ssh_session.put(from_f, to_f)
        except FileNotFoundError:
           raise FileNotFoundError("from %s to %s @ %s : %s Error!"%(from_f, self.ssh_session.username, self.ssh_session.hostname, to_f))
        # remote extract
        self.block_checkcall('tar xf %s' % of)
        # clean up
        os.remove(from_f)
        self.sftp.remove(to_f)

    def _get_files(self, 
                   files,
                   tar_compress = True) :
        
        of_suffix = '.tar.gz'
        tarfile_mode = "r:gz"
        tar_command = 'czfh'
        if not tar_compress :
            of_suffix = '.tar'
            tarfile_mode = "r"
            tar_command = 'cfh'

        of = self.submission.submission_hash + of_suffix
        # remote tar
        # If the number of files are large, we may get "Argument list too long" error.
        # Thus, "-T" accepts a file containing the list of files
        per_nfile = 100
        ntar = len(files) // per_nfile + 1
        if ntar <= 1:
            self.block_checkcall('tar %s %s %s' % (tar_command, of, " ".join(files)))
        else:
            file_list_file = os.path.join(self.remote_root, ".tmp.tar." + str(uuid.uuid4()))
            self.write_file(file_list_file, "\n".join(files))
            self.block_checkcall('tar %s %s -T %s' % (tar_command, of, file_list_file))
        # trans
        from_f = pathlib.PurePath(os.path.join(self.remote_root, of)).as_posix()
        to_f = pathlib.PurePath(os.path.join(self.local_root, of)).as_posix()
        if os.path.isfile(to_f) :
            os.remove(to_f)
        self.ssh_session.get(from_f, to_f)
        # extract
        cwd = os.getcwd()
        os.chdir(self.local_root)
        with tarfile.open(of, mode = tarfile_mode) as tar:
            tar.extractall()
        os.chdir(cwd)    
        # cleanup
        os.remove(to_f)
        self.sftp.remove(from_f)

    @classmethod
    def machine_subfields(cls) -> List[Argument]:
        """Generate the machine subfields.
        
        Returns
        -------
        list[Argument]
            machine subfields
        """
        doc_remote_profile = 'The information used to maintain the connection with remote machine.'
        remote_profile_format = SSHSession.arginfo()
        remote_profile_format.name = "remote_profile"
        remote_profile_format.doc = doc_remote_profile
        return [remote_profile_format]

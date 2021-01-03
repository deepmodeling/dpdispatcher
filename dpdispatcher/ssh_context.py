#!/usr/bin/env python
# coding: utf-8

import os, sys, paramiko, json, uuid, tarfile, time, stat, shutil
from glob import glob
from dpdispatcher import dlog
from dpdispatcher.submission import Machine

class SSHSession (object) :
    # def bk__init__ (self, jdata) :
    #     self.remote_profile = jdata
    #     # with open(remote_profile) as fp :
    #     #     self.remote_profile = json.load(fp)
    #     self.remote_host = self.remote_profile['hostname']
    #     self.remote_uname = self.remote_profile['username']
    #     self.remote_port = self.remote_profile.get('port', 22)
    #     self.remote_password = self.remote_profile.get('password', None)
    #     self.local_key_filename = self.remote_profile.get('key_filename', None)
    #     self.remote_timeout = self.remote_profile.get('timeout', None)
    #     self.local_key_passphrase = self.remote_profile.get('passphrase', None)
    #     self.remote_workpath = self.remote_profile['work_path']
    #     self.ssh = None
    #     self._setup_ssh(hostname=self.remote_host,
    #                     port=self.remote_port,
    #                     username=self.remote_uname,
    #                     password=self.remote_password,
    #                     key_filename=self.local_key_filename,
    #                     timeout=self.remote_timeout,
    #                     passphrase=self.local_key_passphrase)
    
    def __init__(self, machine):
        self.machine = machine
        self.ssh=None
        self._setup_ssh()

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
            dlog.info('connection check failed, try to reconnect to ' + self.machine.remote_root)
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

    def bk_setup_ssh(self,
                   hostname,
                   port=22,
                   username=None,
                   password=None,
                   key_filename=None,
                   timeout=None,
                   passphrase=None):
        self.ssh = paramiko.SSHClient()
        # ssh_client.load_system_host_keys()
        self.ssh.set_missing_host_key_policy(paramiko.WarningPolicy)
        self.ssh.connect(hostname=hostname, port=port,
                         username=username, password=password,
                         key_filename=key_filename, timeout=timeout, passphrase=passphrase)
        assert(self.ssh.get_transport().is_active())
        transport = self.ssh.get_transport()
        transport.set_keepalive(60)
    
    def _setup_ssh(self):
        machine = self.machine
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.WarningPolicy)
        self.ssh.connect(hostname=machine.hostname, port=machine.port,
                        username=machine.username, password=machine.password)
        assert(self.ssh.get_transport().is_active())
        transport = self.ssh.get_transport()
        transport.set_keepalive(60)
                        

    def get_ssh_client(self) :
        return self.ssh

    def get_session_root(self) :
        return self.machine.remote_root

    def close(self) :
        self.ssh.close()


class SSHContext (object):
    def __init__ (self,
                  local_root,
                  ssh_session,
                  job_uuid=None):
        assert(type(local_root) == str)
        self.temp_local_root = os.path.abspath(local_root)
        self.job_uuid = job_uuid
        # if job_uuid:
        #    self.job_uuid=job_uuid
        # else:
        #    self.job_uuid = str(uuid.uuid4())
        self.temp_remote_root = os.path.join(ssh_session.get_session_root())
        self.ssh_session = ssh_session
        self.ssh_session.ensure_alive()
        try:
           sftp = self.ssh_session.ssh.open_sftp() 
           sftp.mkdir(self.temp_remote_root)
           sftp.close()
        except: 
           pass
    
    @property
    def ssh(self):
        return self.ssh_session.get_ssh_client()  

    def close(self):
        self.ssh_session.close()

    def get_job_root(self) :
        return self.remote_root

    def bind_submission(self, submission):
        self.submission = submission
        self.local_root = os.path.join(self.temp_local_root, submission.work_base)
        # self.remote_root = os.path.join(self.temp_remote_root, self.submission.submission_hash, self.submission.work_base )
        self.remote_root = os.path.join(self.temp_remote_root, self.submission.submission_hash)
           
        self.job_uuid = submission.submission_hash
        # try:
        print('self.remote_root', self.remote_root)
        sftp = self.ssh_session.ssh.open_sftp() 
        sftp.mkdir(self.remote_root)
        sftp.close()
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
            for jj in task.forward_files  :
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
                        cmd) :
        self.ssh_session.ensure_alive()
        stdin, stdout, stderr = self.ssh.exec_command(('cd %s ;' % self.remote_root) + cmd)
        exit_status = stdout.channel.recv_exit_status() 
        if exit_status != 0:
            raise RuntimeError("Get error code %d in calling %s through ssh with job: %s . message: %s" %
                               (exit_status, cmd, self.job_uuid, stderr.read().decode('utf-8')))
        return stdin, stdout, stderr    

    def block_call(self, 
                   cmd) :
        self.ssh_session.ensure_alive()
        stdin, stdout, stderr = self.ssh.exec_command(('cd %s ;' % self.remote_root) + cmd)
        exit_status = stdout.channel.recv_exit_status() 
        return exit_status, stdin, stdout, stderr

    def clean(self) :        
        self.ssh_session.ensure_alive()
        sftp = self.ssh.open_sftp()        
        self._rmtree(sftp, self.remote_root)
        sftp.close()

    def write_file(self, fname, write_str):
        self.ssh_session.ensure_alive()
        sftp = self.ssh.open_sftp()
        with sftp.open(os.path.join(self.remote_root, fname), 'w') as fp :
            fp.write(write_str)
        sftp.close()

    def read_file(self, fname):
        self.ssh_session.ensure_alive()
        sftp = self.ssh.open_sftp()
        with sftp.open(os.path.join(self.remote_root, fname), 'r') as fp:
            ret = fp.read().decode('utf-8')
        sftp.close()
        return ret

    def check_file_exists(self, fname):
        self.ssh_session.ensure_alive()
        sftp = self.ssh.open_sftp()
        try:
            sftp.stat(os.path.join(self.remote_root, fname)) 
            ret = True
        except IOError:
            ret = False
        sftp.close()
        return ret        
        
    def call(self, cmd):
        stdin, stdout, stderr = self.ssh.exec_command(cmd)
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


    def _rmtree(self, sftp, remotepath, level=0, verbose = False):
        for f in sftp.listdir_attr(remotepath):
            rpath = os.path.join(remotepath, f.filename)
            if stat.S_ISDIR(f.st_mode):
                self._rmtree(sftp, rpath, level=(level + 1))
            else:
                rpath = os.path.join(remotepath, f.filename)
                if verbose: dlog.info('removing %s%s' % ('    ' * level, rpath))
                sftp.remove(rpath)
        if verbose: dlog.info('removing %s%s' % ('    ' * level, remotepath))
        sftp.rmdir(remotepath)

    def _put_files(self,
                   files,
                   dereference = True) :
        of = self.job_uuid + '.tgz'
        # local tar
        cwd = os.getcwd()
        os.chdir(self.local_root)
        if os.path.isfile(of) :
            os.remove(of)
        with tarfile.open(of, "w:gz", dereference = dereference) as tar:
            for ii in files :
                tar.add(ii)
        os.chdir(cwd)
        # trans
        from_f = os.path.join(self.local_root, of)
        to_f = os.path.join(self.remote_root, of)
        sftp = self.ssh.open_sftp()
        try:
           sftp.put(from_f, to_f)
        except FileNotFoundError:
           raise FileNotFoundError("from %s to %s Error!"%(from_f,to_f))
        # remote extract
        self.block_checkcall('tar xf %s' % of)
        # clean up
        os.remove(from_f)
        sftp.remove(to_f)
        sftp.close()

    def _get_files(self, 
                   files) :
        of = self.job_uuid + '.tgz'
        flist = ""
        for ii in files :
            flist += " " + ii
        # remote tar
        self.block_checkcall('tar czf %s %s' % (of, flist))
        # trans
        from_f = os.path.join(self.remote_root, of)
        to_f = os.path.join(self.local_root, of)
        if os.path.isfile(to_f) :
            os.remove(to_f)
        sftp = self.ssh.open_sftp()
        sftp.get(from_f, to_f)
        # extract
        cwd = os.getcwd()
        os.chdir(self.local_root)
        with tarfile.open(of, "r:gz") as tar:
            tar.extractall()
        os.chdir(cwd)        
        # cleanup
        os.remove(to_f)
        sftp.remove(from_f)
        sftp.close()

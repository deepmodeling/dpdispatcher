#!/usr/bin/env python
# coding: utf-8

import os, sys, paramiko, json, uuid, tarfile, time, stat, shutil
from glob import glob
from dpdispatcher import dlog
# from dpdispatcher.submission import Machine


class HttpContext (object):
    def __init__ (self,
        remote_root):
        self.remote_root = remote_root
    def upload(self,local_upload_files) :
        pass
    def download(self,remote_down_files):
        pass
    def block_call(self, 
                    cmd):
        exit_status, stdin, stdout, stderr = (0, 'foo', 'bar', 'baz')
        return exit_status, stdin, stdout, stderr
    def write_file(self, fname, write_str):
        file_path = os.path.join(self.remote_root, fname)
        pass
    def read_file(self, fname):
        file_path = os.path.join(self.remote_root, fname)
        ret = ''
        return ret
    def check_file_exists(self, fname):
        return False
    def call(self, cmd):
        pass
        stdin, stdout, stderr = self.ssh.exec_command(cmd)
    def get_return(self, cmd_pipes):
        if not self.check_finish(cmd_pipes):
            return None, None, None
        else :
            retcode = cmd_pipes['stdout'].channel.recv_exit_status()
            return retcode, cmd_pipes['stdout'], cmd_pipes['stderr']
    def kill(self, cmd_pipes) :
        pass

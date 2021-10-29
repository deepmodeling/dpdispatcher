# /usr/bin/python
# -*- encoding=utf-8 -*-

import os
import sys
from dpdispatcher.utils import run_cmd_with_all_output

class HDFS(object):
    '''Fundamental class for HDFS basic manipulation
    '''

    @staticmethod
    def exists(uri):
        '''Check existence of hdfs uri
        Returns: True on exists
        Raises: RuntimeError
        '''
        cmd = 'hadoop fs -test -e {uri}'.format(uri=uri)
        try:
            ret, out, err = run_cmd_with_all_output(cmd)
            if ret == 0:
                return True
            elif ret == 1:
                return False
            else:
                raise RuntimeError('Cannot check existence of hdfs uri[{}] '
                                   'with cmd[{}]; ret[{}] stdout[{}] stderr[{}]'.format(
                                    uri, cmd, ret, out, err))
        except Exception as e:
            raise RuntimeError('Cannot check existence of hdfs uri[{}] '
                               'with cmd[{}]'.format(uri, cmd)) from e

    @staticmethod
    def remove(uri):
        '''Check existence of hdfs uri
        Returns: True on exists
        Raises: RuntimeError
        '''

        cmd = 'hadoop fs -rm -r {uri}'.format(uri=uri)
        try:
            ret, out, err = run_cmd_with_all_output(cmd)
            if ret == 0:
                return True
            else:
                raise RuntimeError('Cannot remove hdfs uri[{}] '
                                   'with cmd[{}]; ret[{}] output[{}] stderr[{}]'.format(
                                    uri, cmd, ret, out, err))
        except Exception as e:
            raise RuntimeError('Cannot remove hdfs uri[{}] '
                               'with cmd[{}]'.format(uri, cmd)) from e

    @staticmethod
    def mkdir(uri):
        '''Make new hdfs directory
        Returns: True on success
        Raises: RuntimeError
        '''
        cmd = 'hadoop fs -mkdir -p {uri}'.format(uri=uri)
        try:
            ret, out, err = run_cmd_with_all_output(cmd)
            if ret == 0:
                return True
            else:
                raise RuntimeError('Cannot mkdir of hdfs uri[{}] '
                                   'with cmd[{}]; ret[{}] output[{}] stderr[{}]'.format(
                                    uri, cmd, ret, out, err))
        except Exception as e:
            raise RuntimeError('Cannot mkdir of hdfs uri[{}] '
                               'with cmd[{}]'.format(uri, cmd)) from e



    @staticmethod
    def copy_from_local(local_path, to_uri):
        '''
        Returns: True on success
        Raises: on unexpected error
        '''
        # Make sure local_path is accessible
        if not os.path.exists(local_path) or not os.access(local_path, os.R_OK):
            raise RuntimeError('try to access local_path[{}] '
                               'but failed'.format(local_path))
        cmd = 'hadoop fs -copyFromLocal -f {local} {remote}'.format(local=local_path,
                                                                    remote=to_uri)
        try:
            ret, out, err = run_cmd_with_all_output(cmd)
            if ret == 0:
                return True, out
            else:
                raise RuntimeError('Cannot copy local[{}] to remote[{}] with cmd[{}]; '
                                   'ret[{}] output[{}] stderr[{}]'.format(local_path, to_uri,
                                                                          cmd, ret, out, err))
        except Exception as e:
            raise RuntimeError('Cannot copy local[{}] to remote[{}] with cmd[{}]'
                               .format(local_path, to_uri, cmd)) from e

    @staticmethod
    def copy_to_local(from_uri, local_path):
        remote = ''
        if isinstance(from_uri, string_types):
            remote = from_uri
        elif isinstance(from_uri, list) or \
                isinstance(from_uri, tuple):
            remote = ' '.join(from_uri)
        cmd = 'hadoop fs -copyToLocal {remote} {local}'.format(remote=remote, local=local_path)

        try:
            ret, out, err = run_cmd_with_all_output(cmd)
            if ret == 0:
                return True
            else:
                raise RuntimeError('Cannot copy remote[{}] to local[{}] with cmd[{}]; '
                                   'ret[{}] output[{}] stderr[{}]'.format(from_uri, local_path,
                                                                          cmd, ret, out, err))
        except Exception as e:
            raise RuntimeError('Cannot copy remote[{}] to local[{}] with cmd[{}]'
                               .format(from_uri, local_path, cmd)) from e



    @staticmethod
    def read_hdfs_file(uri):
        cmd = 'hadoop fs -text {uri}'.format(uri=uri)
        try:
            ret, out, err = run_cmd_with_all_output(cmd)
            if ret == 0:
                return out
            else:
                raise RuntimeError('Cannot read text from uri[{}]'
                                   'cmd [{}] ret[{}] output[{}] stderr[{}]'.format(uri, cmd, ret, out, err))
        except Exception as e:
            raise RuntimeError('Cannot read text from uri[{}]'
                               'cmd [{}]'.format(uri, cmd)) from e

    @staticmethod
    def move(from_uri, to_uri):
        cmd = 'hadoop fs -mv {furi} {turi}'.format(furi=from_uri, turi=to_uri)
        try:
            ret, out, err = run_cmd_with_all_output(cmd)
            if ret == 0:
                return True
            else:
                raise RuntimeError('Cannot move from_uri[{}] to '
                                   'to_uri[{}] with cmd[{}]; '
                                   'ret[{}] output[{}] stderr[{}]'.format(from_uri, to_uri,
                                                                          cmd, ret, out, err))
        except Exception as e:
            raise RuntimeError('Cannot move from_uri[{}] to '
                               'to_uri[{}] with cmd[{}]'.format(from_uri, to_uri, cmd)) from e

import os,sys,json,glob,shutil,uuid,time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import LazyLocalContext
from .context import setUpModule
class TestLazyLocalContext(unittest.TestCase):
    def setUp(self) :
        # os.makedirs('loc', exist_ok = True)
        # os.makedirs('loc/task0', exist_ok = True)
        # os.makedirs('loc/task1', exist_ok = True)
        shutil.copytree(
            src='test_context_dir/',
            dst='tmp_lazy_local_context_dir/')

        self.lazy_local_context = LazyLocalContext(
            local_root='tmp_lazy_local_context_dir/'
        )
        submission = MagicMock(work_base='0_md/')
        self.lazy_local_context.bind_submission(submission)

    def tearDown(self):
        shutil.rmtree('tmp_lazy_local_context_dir/')

    def test_upload(self):
        pass

    def test_download(self):        
        pass

    def test_block_call(self):
        code, stdin, stdout, stderr = self.lazy_local_context.block_call('ls')
        self.assertEqual(stdout.readlines(), ['bct-1\n',
            'bct-2\n', 'bct-3\n', 'bct-4\n', 'graph.pb\n'])
        self.assertEqual(code, 0)

        code, stdin, stdout, stderr = self.lazy_local_context.block_call('ls a')
        self.assertEqual(code, 2)
        # self.assertEqual(stderr.read().decode('utf-8'), "ls: cannot access 'a': No such file or directory\n")
        err_msg = stderr.read().decode('utf-8')
        self.assertTrue('ls: cannot access' in err_msg)
        self.assertTrue('No such file or directory\n' in err_msg)

    # def test_block_checkcall(self) :
    #     self.job  = LazyLocalContext('loc', None)
    #     tasks = ['task0', 'task1']
    #     files = ['test0', 'test1']
    #     self.job.upload(tasks, files)
    #     # ls
    #     stdin, stdout, stderr = self.job.block_checkcall('ls')
    #     self.assertEqual(stdout.read().decode('utf-8'), 'task0\ntask1\n')
    #     self.assertEqual(stdout.readlines(), ['task0\n','task1\n'])
    #     with self.assertRaises(RuntimeError):
    #         stdin, stdout, stderr = self.job.block_checkcall('ls a')
            
    # def test_file(self) :
    #     self.job = LazyLocalContext('loc', None)
    #     self.assertFalse(self.job.check_file_exists('aaa'))
    #     tmp = str(uuid.uuid4())
    #     self.job.write_file('aaa', tmp)
    #     self.assertTrue(self.job.check_file_exists('aaa'))
    #     tmp1 = self.job.read_file('aaa')
    #     self.assertEqual(tmp, tmp1)
        

    # def test_call(self) :
    #     self.job = LazyLocalContext('loc', None)
    #     proc = self.job.call('sleep 3')
    #     self.assertFalse(self.job.check_finish(proc))
    #     time.sleep(1)
    #     self.assertFalse(self.job.check_finish(proc))
    #     time.sleep(2.5)
    #     self.assertTrue(self.job.check_finish(proc))
    #     r,o,e=self.job.get_return(proc)
    #     self.assertEqual(r, 0)
    #     self.assertEqual(o.read(), b'')
    #     self.assertEqual(e.read(), b'')
    #     r,o,e=self.job.get_return(proc)
    #     self.assertEqual(r, 0)
    #     self.assertEqual(o, None)
    #     self.assertEqual(e, None)


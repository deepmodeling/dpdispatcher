#%%
import os
import sys
import uuid
import unittest

from dpdispatcher.dpcloudserver import api
from dpdispatcher.dpcloudserver.zip_file import zip_files
# import api
# from zip_file import zip_files


#%%
class DPTest(unittest.TestCase):

    test_data = {
        'job_type': 'indicate',
        'log_file': 'mylog',
        'command': '( echo aa && lmp -i input.lammps && sleep 900 ) > dp.log 2>&1',
        'backward_files': [],
        'job_name': 'dpdispatcher_lammps_test',
        'machine': {
            'platform': 'ali',
            'resources': {
                'gpu_type': '1 * NVIDIA P100',
                'cpu_num': 4,
                'mem_limit': 28,
                'time_limit': '2:00:00',
                'image_name': 'yfb-deepmd-kit-1.2.4-cuda10'
            }
        },
        'job_resources': 'http://dpcloudserver.oss-cn-shenzhen.aliyuncs.com/dpcloudserver/indicate/a657ff49722839f1ee54edeb3e9b1beb0ee5cc0e/a657ff49722839f1ee54edeb3e9b1beb0ee5cc0e.zip'
    }

    username = ''
    password = ''

    ENDPOINT = 'http://oss-cn-shenzhen.aliyuncs.com'
    BUCKET_NAME = 'dpcloudserver'

    @classmethod
    def setUpClass(cls):
        print('execute', sys._getframe().f_code.co_name)
       
    @classmethod
    def tearDownClass(cls):
        print('execute', sys._getframe().f_code.co_name)

    def setUp(self):
        print('execute', sys._getframe().f_code.co_name)
        api.login(self.username, self.password)

    def test_commit_job(self):
        print('----------', sys._getframe().f_code.co_name)
        file_uuid = uuid.uuid1().hex
        oss_task_zip = os.path.join('%s/%s/%s.zip' % ('indicate', file_uuid, file_uuid))
        zip_path = "/home/felix/workplace/22_dpdispatcher/dpdispatcher-yfb/dpdispatcher/dpcloudserver/t.txt"
        zip_task_file = zip_path + '.zip'
        zip_files(zip_path, zip_task_file, [])
        api.upload(oss_task_zip, zip_task_file, self.ENDPOINT, self.BUCKET_NAME)
        job_id = api.job_create(
            self.test_data['job_type'],
            self.test_data['job_resources'],
            self.test_data
            )
        tasks = api.get_tasks(job_id)
        print(tasks)

    def test_get_tasks(self):
        print('----------', sys._getframe().f_code.co_name)
        jobs = api.get_jobs()
        for j in jobs:
            tasks = api.get_tasks(j['id'])
            print(tasks)

    # def test_download(self):
    #     print('----------', sys._getframe().f_code.co_name)
    #     oss_path = 'dpcloudserver/indicate/abe0febc92ce11eb990800163e094dc5/abe0febc92ce11eb990800163e094dc5.zip'
    #     api.download(oss_path, "out.zip", self.ENDPOINT, self.BUCKET_NAME)

if __name__ == '__main__':
    suite = unittest.TestSuite()

    suite.addTest(DPTest("test_commit_job"))
    # suite.addTest(DPTest("test_get_tasks"))
    # suite.addTest(DPTest("test_download"))

    runner = unittest.TextTestRunner()
    runner.run(suite)


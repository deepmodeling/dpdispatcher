import os,sys,json,glob,shutil,uuid,getpass,tarfile
import unittest
import pathlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import HDFSContext
from .context import HDFS
from .context import Machine
from .sample_class import SampleClass
from glob import glob

@unittest.skipIf(not shutil.which("hadoop"), "requires hadoop")
class TestHDFSContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open('jsons/machine_yarn.json', 'r') as f:
            mdata = json.load(f)
        cls.machine = Machine.load_from_dict(mdata['machine'])
        cls.submission = SampleClass.get_sample_submission()
        cls.submission.bind_machine(cls.machine)
        cls.submission_hash = cls.submission.submission_hash
    
    def setUp(self):
        self.context = self.__class__.machine.context

    def test_0_hdfs_context(self):
        self.assertIsInstance(self.context, HDFSContext)

    def test_1_upload(self):
        self.context.upload(self.__class__.submission)

    def test_2_fake_run(self):
        rfile_tgz = self.context.remote_root + '/' + self.context.submission.submission_hash + '_upload.tgz'
        tmp_dir = "./tmp_fake_run"
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        os.mkdir(tmp_dir)
        self.assertTrue(HDFS.copy_to_local(rfile_tgz, tmp_dir))

        cwd = os.getcwd()
        os.chdir(tmp_dir)
        tgz_file_list = glob("*_upload.tgz")
        for tgz in tgz_file_list:
            with tarfile.open(tgz, "r:gz") as tar:
                tar.extractall()
            os.remove(tgz)

        file_list = ['bct-1/log.lammps', 'bct-2/log.lammps', 'bct-3/log.lammps', 'bct-4/log.lammps']
        for fname in file_list:
            with open(fname, 'w') as fp:
                fp.write('# mock log') 

        file_list = glob("./*")
        download_tgz = self.context.submission.submission_hash + '_1_download.tar.gz'
        with tarfile.open(download_tgz, "w:gz", dereference=True) as tar:
            for ii in file_list :
                tar.add(ii)
        ret, _ = HDFS.copy_from_local(download_tgz, self.context.remote_root)
        self.assertTrue(ret)
        os.chdir(cwd)
        shutil.rmtree(tmp_dir)

    def test_3_download(self):
        self.context.download(self.__class__.submission)
        file_list = ['bct-1/log.lammps', 'bct-2/log.lammps', 'bct-3/log.lammps', 'bct-4/log.lammps']
        for fname in file_list:
            self.assertTrue(os.path.isfile(os.path.join(self.context.local_root, fname)))        
            os.remove(os.path.join(self.context.local_root, fname))

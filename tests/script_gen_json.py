#!/usr/bin/env python3
import os,sys,json,glob,shutil,uuid,time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
# from .context import LocalContext
from dpdispatcher.local_context import LocalContext
from .context import JobStatus
from .context import Submission, Job, Task, Resources

from .sample_class import SampleClass

task_dict = SampleClass.get_sample_task_dict()
assert os.path.isfile('jsons/task.json') is False
with open('jsons/task.json', 'w') as f:
    json.dump(task_dict, f, indent=4)

resources_dict = SampleClass.get_sample_resources_dict()
assert os.path.isfile('jsons/resources.json') is False
with open('jsons/resources.json', 'w') as f:
    json.dump(resources_dict, f, indent=4)

submission_dict = SampleClass.get_sample_submission_dict()
assert os.path.isfile('jsons/submission.json') is False
with open('jsons/submission.json', 'w') as f:
    json.dump(submission_dict, f, indent=4)

job_dict = SampleClass.get_sample_job_dict()
assert os.path.isfile('jsons/job.json') is False
with open('jsons/job.json', 'w') as f:
    json.dump(job_dict, f, indent=4)



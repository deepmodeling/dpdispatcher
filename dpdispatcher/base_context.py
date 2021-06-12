import os,shutil,uuid,hashlib
import subprocess as sp
from glob import glob
from dpdispatcher import dlog

class BaseContext(object):
    subclasses_dict = {}
    def __init__(self):
        raise NotImplementedError('abstract method')

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.subclasses_dict[cls.__name__]=cls

    @classmethod
    def load_from_dict(cls, context_dict):
        context_type = context_dict['context_type']
        # print("debug778:context_type", cls.subclasses_dict, context_type)
        try:
            context_class = cls.subclasses_dict[context_type]
        except KeyError as e:
            dlog.error(f"KeyError:context_type; context_type:{context_type}; cls.subclasses_dict:{cls.subclasses_dict}")
            raise e
        context = context_class.load_from_dict(context_dict)
        return context

    def bind_submission(self, submission):
        self.submission = submission

    def upload(self, submission):
        raise NotImplementedError('abstract method')

    def download(self, 
                submission,
                check_exists = False,
                mark_failure = True,
                back_error=False):
        raise NotImplementedError('abstract method')

    def clean(self):
        raise NotImplementedError('abstract method')

    def write_file(self, fname, write_str):
        raise NotImplementedError('abstract method')

    def read_file(self, fname):
        raise NotImplementedError('abstract method')

    def kill(self, proc):
        raise NotImplementedError('abstract method')

    def check_finish(self, proc):
        raise NotImplementedError('abstract method')


from dargs import Argument
from typing import List

from dpdispatcher import dlog

class BaseContext(object):
    subclasses_dict = {}
    options = set()
    def __new__(cls, *args, **kwargs):
        if cls is BaseContext:
            subcls = cls.subclasses_dict[kwargs['context_type']]
            instance = subcls.__new__(subcls, *args, **kwargs)
        else:
            instance = object.__new__(cls)
        return instance

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.subclasses_dict[cls.__name__]=cls
        cls.subclasses_dict[cls.__name__.lower()]=cls
        cls.subclasses_dict[cls.__name__.replace("Context", "")]=cls
        cls.subclasses_dict[cls.__name__.lower().replace("context", "")]=cls
        cls.options.add(cls.__name__)

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

    @classmethod
    def machine_arginfo(cls) -> Argument:
        """Generate the machine arginfo.

        Returns
        -------
        Argument
            machine arginfo
        """
        return Argument(
            cls.__name__, dict, sub_fields=cls.machine_subfields(),
            alias=[
                cls.__name__.lower(),
                cls.__name__.replace("Context", ""),
                cls.__name__.lower().replace("context", "")
            ])

    @classmethod
    def machine_subfields(cls) -> List[Argument]:
        """Generate the machine subfields.
        
        Returns
        -------
        list[Argument]
            machine subfields
        """
        doc_remote_profile = "The information used to maintain the connection with remote machine. This field is empty for this context."
        return [Argument("remote_profile", dict, optional=True, doc=doc_remote_profile)]
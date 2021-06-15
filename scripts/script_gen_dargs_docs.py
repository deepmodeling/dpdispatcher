
#%%
# import sys, os
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..' )))
# import dpdispatcher
from dpdispatcher.submission import Resources, Task
from dpdispatcher.machine import Machine


# %%
resources_dargs_doc = Resources.arginfo().gen_doc()
with open('../doc/resources-auto.rst', 'w') as f:
    # print(resources_dargs_doc)
    f.write(resources_dargs_doc)

machine_dargs_doc = Machine.arginfo().gen_doc()
with open('../doc/machine-auto.rst', 'w') as f:
    f.write(machine_dargs_doc)

task_dargs_doc = Task.arginfo().gen_doc()
with open('../doc/task-auto.rst', 'w') as f:
    f.write(task_dargs_doc)


# %%

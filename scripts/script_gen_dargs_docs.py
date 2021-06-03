
#%%
# import sys, os
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..' )))
# import dpdispatcher
from dpdispatcher.submission import Resources
from dpdispatcher.machine import Machine


# %%
resources_dargs_doc = Resources.dargs_check(if_gen_docs=True)
with open('../doc/resources-auto.rst', 'w') as f:
    f.write(resources_dargs_doc)

machine_dargs_doc = Machine.dargs_check(if_gen_docs=True)
with open('../doc/machine-auto.rst', 'w') as f:
    f.write(machine_dargs_doc)
# %%

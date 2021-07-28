from dpdispatcher import Resources, Task, Machine
from dargs import ArgumentEncoder
import json

resources_dargs = Resources.arginfo()
with open('dpdispatcher-resources.json', 'w') as f:
    json.dump(resources_dargs, f, cls=ArgumentEncoder)

machine_dargs = Machine.arginfo()
with open('dpdispatcher-machine.json', 'w') as f:
    json.dump(machine_dargs, f, cls=ArgumentEncoder)

task_dargs = Task.arginfo()
with open('dpdispatcher-task.json', 'w') as f:
    json.dump(task_dargs, f, cls=ArgumentEncoder)


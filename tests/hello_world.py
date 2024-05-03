# /// script
# # dpdispatcher doesn't use `requires-python` and `dependencies`
# requires-python = ">=3"
# dependencies = [
# ]
# [tool.dpdispatcher]
# work_base = "./"
# forward_common_files=[]
# backward_common_files=[]
# [tool.dpdispatcher.machine]
# batch_type = "Shell"
# local_root = "./"
# context_type = "LazyLocalContext"
# [tool.dpdispatcher.resources]
# number_node = 1
# cpu_per_node = 1
# gpu_per_node = 0
# group_size = 0
# [[tool.dpdispatcher.task_list]]
# # no need to contain the script filename
# command = "python"
# # can be a glob pattern
# task_work_path = "./"
# forward_files = []
# backward_files = ["log"]
# ///

print("hello world!")

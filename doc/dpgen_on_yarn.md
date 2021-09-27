# DPGen on Yarn 支持
## 背景
目前 DPGen 运行支持 Slurm、PBS、LSF、Aliyun、DpCloudServer 等系统平台，连接远程机器的方式支持 SSH、Local、DpCloudServerContext 等。为了在字节内部跑通 DPGen 的大数据量计算任务，我们需要和内部 Yarn 资源平台进行对接，实现一套相关接口。Hadoop/Yarn 生态是目前业界普遍使用的大数据处理平台，我们在对接内部平台时发现可以实现一套不依赖公司内部组件的通用接口，因此为了使 DPGen 能在更广泛的场景下使用，我们将此功能回馈至开源社区。<br/>
DPGen 目前已将提交任务相关的代码剥离至单独的 DPDispatcher 模块，因此我们的接口也基于该模块实现，作为一个公共模块，后续也可供DeePKS-kit、Rid-kit 等其他软件使用。<br/>
## 方案
通过使用 DistributedShell + HDFS 的方式运行任务，状态流程图如下：
![image](https://github.com/shazj99/dpdispatcher/blob/yarn/doc/dpgen_yarn.jpg?raw=true)
- 通过 HDFS 做输入输出文件的中转、中间状态文件的保存。任务实际运行前后会需要或产生很多小文件，为了避免频繁传输小文件降低运行速度，我们将所有文件进行压缩打包后再进行传输。Upload时将forward和forward common文件打包上传至 HDFS Job 目录，任务执行完后再将所有task输出目录整体打包并存放在 HDFS 上，Download时将整个压缩包拉取下来，再根据backward文件列表选取需要的文件存放至本地工作目录。
- 以 DistributedShell 方式向 Yarn 提交单 Container 计算任务。Submit操作主要包含以下几个工作:
  - 生成 container shell script，该脚本在 yarn 上执行，主要完成forward文件的下载、计算、输出文件上传等工作。
  - 根据 Resource 资源配置生成 yarn 提交命令并进行提交。
  <br/>
## 实现
主要在 DpDispatcher 中实现 HDFSContext 和 DistributedShell 两个类即可，以下为需要完成的关键函数：<br/>

```
class HDFSContext(BaseContext) :
    def upload(self, job_dirs, local_up_files):
    """ upload forward files and forward command files to HDFS root dir

    Parameters
    ----------
    job_dirs : list
        the dictionary which contains the upload files
    local_up_files: list
        the file names which will be uploaded
    Returns
    -------
    none
    """
        pass
    
    def download(self, submission):
    """ download backward files from HDFS root dir

    Parameters
    ----------
    submission : Submission class instance
        represents a collection of tasks, such as backward file names
    Returns
    -------
    none
    """
        pass
        
   def check_file_exists(self, fname):
   """ check whether the given file exists, often used in checking whether the belonging job has finished

    Parameters
    ----------
    fname : string
        file name to be checked
    Returns
    -------
    status: boolean
    """
        pass
```

```
class DistributedShell(Machine):
    def do_submit(self, job):
    """ submit th job to yarn using distributed shell
    Parameters
    ----------
    job : Job class instance
        job to be submitted
    Returns
    -------
    job_id: string
        usually a yarn application id
    """
        pass
        
    def check_status(self, job):
    """ check the yarn job status
    Parameters
    ----------
    job : Job class instance
        the submitted job
    Returns
    -------
    status: JobStatus
    """        
        pass
    
    def gen_script_command(self, job):
    """ Generate the shell script to be executed in DistibutedShell container
    Parameters
    ----------
    job : Job class instance
        the submitted job
    Returns
    -------
    script: string
        script command string
    """          
        pass
```

生成的shell script 样例如下，该脚本会在 DistributedShell container 中执行：<br/>

```
#!/bin/bash

## 设置容器内环境变量等
source /opt/intel/oneapi/setvars.sh

## 从HDFS目录里拉取已上传的 forward 和 forward common 文件压缩包
if ! ls uuid_upload_*.tgz 1>/dev/null 2>&1; then
    hadoop fs -get /root/uuid/uuid_upload_*.tgz .
fi
for tgz_file in `ls *.tgz`; do tar xvf $tgz_file; done

## 判断该task是否已经计算成功过
hadoop fs -test -e /root/uuid/sys-0001-0015/tag_0_finished
{ if [ ! $? -eq 0 ] ;then
  cur_dir=`pwd`
  cd t sys-0001-0015
  test $? -ne 0 && exit 1
  
  ## 执行计算
  mpirun -n 32 vasp_std  1>> log 2>> err
  
  if test $? -ne 0; then
      exit 1
  else
      hadoop fs -touchz /root/uuid/sys-0001-0015/tag_0_finished
  fi 
  cd $cur_dir
  test $? -ne 0 && exit 1
fi }&

wait

## 所有工作都执行完后将目录下所有文件打包并上传至HDFS目录，以备下载
tar czf uuid_download.tar.gz sys-0001-0015
hadoop fs -put -f uuid_download.tar.gz /root/uuid/sys-0001-0015

## 标记该job顺利执行成功
hadoop fs -touchz /root/uuid/uuid_tag_finished
```
machine.json中 fp 配置样例如下，需要声明 batch_type 为 `DistributedShell`，context_type 为 `HDFSContext`:

```
  "fp": [
    {
      "command": "mpirun -n 32 vasp_std",
      "machine": {
        "batch_type": "DistributedShell",
        "context_type": "HDFSContext",
        "local_root": "./",
        "remote_root": "hdfs://path/to/remote/root"
      },
      "resources": {
        "number_node": 1,
        "cpu_per_node": 32,
        "gpu_per_node": 0,
        "queue_name": "root.oryx_bigbang",
        "group_size": 1,
        "source_list": ["/opt/intel/oneapi/setvars.sh"],
        "kwargs": {
          "img_name": "",
          "mem_limit": 32,
          "yarn_path": "/path/to/yarn/jars"
        },
        "envs" : {
          "HADOOP_HOME" : "${HADOOP_HOME:/path/to/hadoop/bin}",
          "CLASSPATH": "`${HADOOP_HOME}/bin/hadoop classpath --glob`",
          "PATH": "${HADOOP_HOME}/bin:${PATH}"}
        }
      }
    }
  ]
```
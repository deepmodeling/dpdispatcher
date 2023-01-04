import json
import os
import re
import time
import urllib.parse
import requests
from .retcode import RETCODE
from .config import HTTP_TIME_OUT, API_HOST, API_LOGGER_STACK_INFO
from urllib.parse import urljoin

from dpdispatcher import dlog

try:
    import oss2
    from oss2 import SizedFileAdapter, determine_part_size
    from oss2.models import PartInfo
except ImportError:
    pass
ENABLE_STACK = True if API_LOGGER_STACK_INFO else False


class RequestInfoException(Exception):
    pass


class Client:
    def __init__(self, email=None, password=None, debug=False,
                 base_url=API_HOST):
        self.debug = debug
        self.debug = os.getenv('LBG_CLI_DEBUG_PRINT', debug)
        self.config = {}
        self.token = ''
        self.user_id = None
        self.config['email'] = email
        self.config['password'] = password
        self.base_url = base_url
        self.last_log_offset = 0

    def post(self, url, data=None, header=None, params=None, retry=5):
        self.refresh_token()
        return self._req('POST', url, data=data, header=header, params=params, retry=retry)

    def get(self, url, header=None, params=None, retry=5):
        self.refresh_token()
        return self._req('GET', url, header=header, params=params, retry=retry)

    def _req(self, method, url, data=None, header=None, params=None, retry=5):
        short_url = url
        url = urllib.parse.urljoin(self.base_url, url)
        if header is None:
            header = {}
        if self.token:
            header['Authorization'] = f'jwt {self.token}'
        resp_code = None
        err = None
        for i in range(retry):
            resp = None
            if method == 'GET':
                resp = requests.get(url, params=params, headers=header)
            else:
                if self.debug:
                    print(data)
                resp = requests.post(url, json=data, params=params, headers=header)
            if self.debug:
                print(resp.text)
            resp_code = resp.status_code
            if not resp.ok:
                if self.debug:
                    print(f"retry: {i},statusCode: {resp.status_code}")
                try:
                    result = resp.json()
                    err = result.get("error")
                except:
                    pass
                time.sleep(0.1 * i)
                continue
            result = resp.json()
            if result['code'] == '0000' or result['code'] == 0:
                return result.get('data', {})
            else:
                err = result.get('message') or result.get('error')
                break
        raise RequestInfoException(resp_code, short_url, err)

    def _login(self):
        if self.config['email'] is None or self.config['password'] is None:
            raise RequestInfoException('can not find login information, please check your config')
        post_data = {
            'email': self.config['email'],
            'password': self.config['password']
        }
        resp = self.post('/account/login', post_data)
        self.token = resp['token']
        # print(self.token)
        self.user_id = resp['user_id']

    def refresh_token(self):
        url = '/account/login'
        post_data = {
            'email': self.config['email'],
            'password': self.config['password']
        }
        ret = requests.post(
            urljoin(API_HOST, url),
            json=post_data,
            timeout=HTTP_TIME_OUT,
        )
        ret = json.loads(ret.text)
        if ret['code'] == RETCODE.OK or ret['code'] == 0:
            self.token = ret['data']['token']
            return
        raise ValueError(f"{url} Error: {ret['code']} {ret.get('message', ret.get('error'))} ")

    def _get_oss_bucket(self, endpoint, bucket_name):
        #  res = get("/tools/sts_token", {})
        res = self.get("/data/get_sts_token", {})
        # print('debug>>>>>>>>>>>>>', res)
        dlog.debug(f"debug: _get_oss_bucket: res:{res}")
        auth = oss2.StsAuth(
            res['AccessKeyId'],
            res['AccessKeySecret'],
            res['SecurityToken']
        )
        return oss2.Bucket(auth, endpoint, bucket_name)

    def download(self, oss_file, save_file, endpoint, bucket_name):
        bucket = self._get_oss_bucket(endpoint, bucket_name)
        dlog.debug(f"debug: download: oss_file:{oss_file}; save_file:{save_file}")
        bucket.get_object_to_file(oss_file, save_file)
        return save_file

    def download_from_url(self, url, save_file):
        ret = None
        for retry_count in range(3):
            try:
                ret = requests.get(
                    url,
                    headers={'Authorization': "jwt " + self.token},
                    stream=True
                )
            except Exception as e:
                dlog.error(f"request error {e}", stack_info=ENABLE_STACK)
                continue
            if ret.ok:
                break
            else:
                dlog.error(f"request error status_code:{ret.status_code} reason: {ret.reason} body: \n{ret.text}")
                time.sleep(retry_count)
                ret = None
        if ret is not None:
            ret.raise_for_status()
            with open(save_file, 'wb') as f:
                for chunk in ret.iter_content(chunk_size=8192):
                    f.write(chunk)
            ret.close()

    def upload(self, oss_task_zip, zip_task_file, endpoint, bucket_name):
        dlog.debug(f"debug: upload: oss_task_zip:{oss_task_zip}; zip_task_file:{zip_task_file}")
        bucket = self._get_oss_bucket(endpoint, bucket_name)
        total_size = os.path.getsize(zip_task_file)
        part_size = determine_part_size(total_size, preferred_size=1000 * 1024)
        upload_id = bucket.init_multipart_upload(oss_task_zip).upload_id
        parts = []
        with open(zip_task_file, 'rb') as fileobj:
            part_number = 1
            offset = 0
            while offset < total_size:
                num_to_upload = min(part_size, total_size - offset)
                result = bucket.upload_part(oss_task_zip, upload_id, part_number,
                                            SizedFileAdapter(fileobj, num_to_upload))
                parts.append(PartInfo(part_number, result.etag))
                offset += num_to_upload
                part_number += 1
        # result = bucket.complete_multipart_upload(oss_task_zip, upload_id, parts)
        result = bucket.complete_multipart_upload(oss_task_zip, upload_id, parts)
        # print('debug:upload_result:', result, dir())
        return result

    def job_create(self, job_type, oss_path, input_data, program_id=None, group_id=None):
        post_data = {
            'job_type': job_type,
            'oss_path': [oss_path],
        }
        if program_id is not None:
            post_data["project_id"] = program_id
        if group_id is not None:
            post_data["job_group_id"] = group_id
        for k, v in input_data.items():
            post_data[k] = v
        if input_data.get('backward_files'):
            post_data["out_files"] = input_data.get('backward_files')
        if input_data.get('command'):
            post_data["cmd"] = input_data.get('command')
        if input_data.get('machine_type'):
            post_data['scass_type'] = input_data.get('machine_type')
        log = input_data.get('logFiles', input_data.get('log_files', input_data.get('log_file')))
        if log:
            if isinstance(log, str):
                post_data['log_files'] = [log]
        if 'checkpoint_files' in post_data and post_data['checkpoint_files'] == 'sync_files':
            post_data['checkpoint_files'] = ['*']
        camel_data = {self._camelize(k): v for k, v in post_data.items()}
        ret = self.post('/brm/v2/job/add', camel_data)
        group_id = ret.get('jobGroupId')
        return ret['jobId'], group_id

    def _camelize(self, str_or_iter):
        # code reference from https://pypi.org/project/pyhumps/
        regex = re.compile(r"(?<=[^\-_\s])[\-_\s]+[^\-_\s]")

        def _is_none(_in):
            return "" if _in is None else _in

        s = str(_is_none(str_or_iter))
        if s.isupper() or s.isnumeric():
            return str_or_iter

        if len(s) != 0 and not s[:2].isupper():
            s = s[0].lower() + s[1:]
        return regex.sub(lambda m: m.group(0)[-1].upper(), s)

    def get_tasks(self, job_id, group_id, page=1, per_page=10):
        ret = self.get(
            f'brm/v1/job/{job_id}',
        )
        return ret

    def get_log(self, job_id):
        url, size = self._get_job_log(job_id)
        if not url:
            return ''
        if self.last_log_offset >= size:
            return ''
        resp = requests.get(url, headers={
            'Range': f'bytes={self.last_log_offset}-'
        })
        self.last_log_offset += len(resp.content)
        return resp.content.decode('utf-8')

    def _get_job_log(self, job_id):
        ret = self.get(
            f'/brm/v1/job/{job_id}/log',
            params={
                'pageSize': 1,
            }
        )
        d = ret.get('logFiles')
        if d and len(d) != 0:
            return d[0]['url'], d[0]['size']
        return None, 0

    def get_tasks_list(self, group_id, per_page=30):
        result = []
        page = 0
        while True:
            ret = self.get(
                f'/brm/v1/job/list',
                params={
                    'groupId': group_id,
                    'page': page,
                    'pageSize': per_page,
                }
            )
            if len(ret['items']) == 0:
                break
            for each in ret['items']:
                result.append(each)
            page += 1
        return result

    def get_job_result_url(self, job_id):
        try:
            if not job_id:
                return None
            if 'job_group_id' in job_id:
                ids = job_id.split(":job_group_id:")
                job_id, _ = int(ids[0]), int(ids[1])
            ret = self.get(f'/brm/v1/job/{job_id}', {})
            if 'resultUrl' in ret and len(ret['resultUrl']) != 0:
                return ret.get('resultUrl')
            else:
                return None
        except ValueError as e:
            dlog.error(e, stack_info=ENABLE_STACK)
            return None

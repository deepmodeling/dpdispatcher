import os
import json
import time

try:
    import oss2
    from oss2 import SizedFileAdapter, determine_part_size
    from oss2.models import PartInfo
except ImportError:
    pass
import requests
from urllib.parse import urljoin
from dpdispatcher import dlog

from .retcode import RETCODE
from .config import HTTP_TIME_OUT, API_HOST


class API:
    def __init__(self, email, password):
        self._login_data = {"password": password, 'email': email}
        self._token = None
        self.refresh_token()
        return

    def get(self, url, params, retry=0):
        headers = {'Authorization': "jwt " + self._token}
        ret = None
        for retry_count in range(3):
            try:
                ret = requests.get(
                    urljoin(API_HOST, url),
                    params=params,
                    timeout=HTTP_TIME_OUT,
                    headers=headers
                )
            except Exception as e:
                dlog.error(f"request error {e}")
                continue
            if ret.ok:
                break
            else:
                dlog.error(f"request error status_code:{ret.status_code} reason: {ret.reason} body: \n{ret.text}")
                time.sleep(retry_count * 10)
        if ret is None:
            raise ConnectionError("request fail")
        # print(url,'>>>', params, '<<<', ret.text)
        ret.raise_for_status()
        ret = json.loads(ret.text)
        if ret['code'] == RETCODE.TOKENINVALID and retry <= 3:
            dlog.info("debug: token expire, refresh token")
            if self._login_data is not None:
                self.refresh_token()
                ret = self.get(url, params, retry=retry + 1)
                return ret
        if ret['code'] != RETCODE.OK:
            raise ValueError(f"{url} Error: {ret['code']} {ret['message']}")
        return ret['data']

    def post(self, url, params, retry=0):
        headers = {'Authorization': "jwt " + self._token}
        ret = None
        for retry_count in range(3):
            try:
                ret = requests.post(
                    urljoin(API_HOST, url),
                    json=params,
                    timeout=HTTP_TIME_OUT,
                    headers=headers
                )
            except Exception as e:
                dlog.error(f"request error {e}")
                continue
            if ret.ok:
                break
            else:
                dlog.error(f"request error status_code:{ret.status_code} reason: {ret.reason} body: \n{ret.text}")
                time.sleep(retry_count)
        if ret is None:
            raise ConnectionError("request fail")
        ret.raise_for_status()
        ret = json.loads(ret.text)
        # print(url,'>>>', params, '<<<', ret.text)
        if ret['code'] == RETCODE.TOKENINVALID and retry <= 3:
            dlog.info("debug: token expire, refresh token")
            if self._login_data is not None:
                self.refresh_token()
                ret = self.post(url, params, retry=retry + 1)
                return ret
        if ret['code'] != RETCODE.OK:
            raise ValueError(f"{url} Error: {ret['code']} {ret['message']}")
        return ret['data']

    def refresh_token(self):
        url = '/account/login'
        ret = requests.post(
            urljoin(API_HOST, url),
            json=self._login_data,
            timeout=HTTP_TIME_OUT,
        )
        dlog.debug(f"debug: login ret:{ret}")
        ret = json.loads(ret.text)
        if ret['code'] != RETCODE.OK:
            raise ValueError(f"{url} Error: {ret['code']} {ret['message']}")
        self._token = ret['data']['token']

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
                    headers={'Authorization': "jwt " + self._token},
                    stream=True
                )
            except Exception as e:
                dlog.error(f"request error {e}")
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
            'oss_path': oss_path,
        }
        if program_id is not None:
            post_data["program_id"] = program_id
        if group_id is not None:
            post_data["job_group_id"] = group_id
        if input_data.get('command') is not None:
            post_data["cmd"] = input_data.get('command')
        if input_data.get('backward_files') is not None:
            post_data["out_files"] = input_data.get('backward_files')
        for k, v in input_data.items():
            post_data[k] = v
        ret = self.post('/data/v2/insert_job', post_data)
        group_id = ret.get('job_group_id')
        return ret['job_id'], group_id

    def get_jobs(self, page=1, per_page=10):
        ret = self.get(
            '/data/jobs',
            {
                'page': page,
                'per_page': per_page,
            }
        )
        return ret['items']

    def get_tasks(self, job_id, group_id, page=1, per_page=10):
        ret = self.get(
            f'data/job/{group_id}/tasks',
            {
                'page': page,
                'per_page': per_page,
            }
        )
        for each in ret['items']:
            if job_id == each["task_id"]:
                return each
        if len(ret['items']) != 0:
            return self.get_tasks(job_id, group_id, page=page + 1)
        return None

    def get_tasks_list(self, group_id, per_page=30):
        result = []
        page = 0
        while True:
            ret = self.get(
                f'data/job/{group_id}/tasks',
                {
                    'page': page,
                    'per_page': per_page,
                }
            )
            if len(ret['items']) == 0:
                break
            for each in ret['items']:
                result.append(each)
            page += 1
        return result

    def check_job_has_uploaded(self, job_id):
        try:
            if not job_id:
                return False
            if 'job_group_id' in job_id:
                ids = job_id.split(":job_group_id:")
                job_id, _ = int(ids[0]), int(ids[1])
            ret = self.get(f'data/job/{job_id}', {})
            if len(ret) == 0:
                return False
            if ret.get('input_data'):
                return True
            else:
                return False
        except ValueError as e:
            dlog.error(e)
            return False

    def get_job_result_url(self, job_id):
        try:
            if not job_id:
                return None
            if 'job_group_id' in job_id:
                ids = job_id.split(":job_group_id:")
                job_id, _ = int(ids[0]), int(ids[1])
            ret = self.get(f'data/job/{job_id}', {})
            if 'result_url' in ret and len(ret['result_url']) != 0:
                return ret.get('result_url')
            else:
                return None
        except ValueError as e:
            dlog.error(e)
            return None

# %%

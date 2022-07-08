import os
HTTP_TIME_OUT = 30

API_HOST = os.environ.get('DPDISPATCHER_LEBESGUE_API_HOST', "https://bohrium.dp.tech/")
API_LOGGER_STACK_INFO = os.environ.get('API_LOGGER_STACK_INFO', "")
ALI_STS_ENDPOINT = os.environ.get('DPDISPATCHER_LEBESGUE_ALI_STS_ENDPOINT', 'http://oss-cn-shenzhen.aliyuncs.com')
ALI_STS_BUCKET_NAME = os.environ.get('DPDISPATCHER_LEBESGUE_ALI_STS_BUCKET_NAME', "dpcloudserver")
ALI_OSS_BUCKET_URL = os.environ.get('DPDISPATCHER_LEBESGUE_ALI_OSS_BUCKET_URL', "https://dpcloudserver.oss-cn-shenzhen.aliyuncs.com/")
# ALI_OSS_BUCKET_URL = 'https://dpcloudserver.oss-cn-shenzhen.aliyuncs.com/
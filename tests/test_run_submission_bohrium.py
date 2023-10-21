import os
import sys
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from test_run_submission import RunSubmission


@unittest.skipIf(
    os.environ.get("DPDISPATCHER_TEST") != "bohrium",
    "outside the Bohrium testing environment",
)
class TestBohriumRun(RunSubmission, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.machine_dict.update(
            batch_type="Bohrium",
            context_type="Bohrium",
            remote_profile={
                "email": os.environ["BOHRIUM_EMAIL"],
                "password": os.environ["BOHRIUM_PASSWORD"],
                "project_id": int(os.environ["BOHRIUM_PROJECT_ID"]),
                "input_data": {
                    "job_type": "indicate",
                    "log_file": "log",
                    "job_name": "dpdispather_test",
                    "disk_size": 20,
                    "scass_type": "c2_m4_cpu",
                    "platform": "ali",
                    "image_name": "registry.dp.tech/dptech/ubuntu:22.04-py3.10",
                    "on_demand": 0,
                },
            },
        )

    @unittest.skip("Manaually skip")  # comment this line to open unittest
    def test_async_run_submission(self):
        return super().test_async_run_submission()


@unittest.skipIf(
    os.environ.get("DPDISPATCHER_TEST") != "bohrium",
    "outside the Bohrium testing environment",
)
class TestOpenAPIRun(RunSubmission, unittest.TestCase):
    def setUp(self):
        super().setUp()
        bohrium_config = textwrap.dedent(
            """\
            [Credentials]
            accessKey={accesskey}
            """
        ).format(accesskey=os.environ["BOHRIUM_ACCESS_KEY"])
        Path.home().joinpath(".brmconfig").write_text(bohrium_config)
        self.machine_dict.update(
            batch_type="OpenAPI",
            context_type="OpenAPI",
            remote_profile={
                "project_id": int(os.environ["BOHRIUM_PROJECT_ID"]),
                "machine_type": "c2_m4_cpu",
                "platform": "ali",
                "image_address": "registry.dp.tech/dptech/ubuntu:22.04-py3.10",
                "job_name": "dpdispather_test",
            },
        )

    @unittest.skip("Manaually skip")  # comment this line to open unittest
    def test_async_run_submission(self):
        return super().test_async_run_submission()

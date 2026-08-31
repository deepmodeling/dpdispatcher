import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
__package__ = "tests"
from typing import Any

from .context import (
    JobStatus,
    Submission,
    setUpModule,  # noqa: F401
)
from .sample_class import SampleClass


class TestSubmission(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None
        pbs = SampleClass.get_sample_pbs_local_context()
        self.submission = SampleClass.get_sample_submission()
        self.submission.bind_machine(machine=pbs)

        #  self.submission2 = Submission.submission_from_json('jsons/submission.json')
        # self.submission2 = Submission.submission_from_json('jsons/submission.json')

    def test_serialize_deserialize(self) -> None:
        self.assertEqual(
            self.submission.serialize(),
            Submission.deserialize(
                submission_dict=self.submission.serialize()
            ).serialize(),
        )

    def test_get_hash(self) -> None:
        pass

    def test_bind_machine(self) -> None:
        self.assertIsNotNone(self.submission.machine.context.submission)
        for job in self.submission.belonging_jobs:
            self.assertIsNotNone(job.machine)

    def test_bind_machine_keeps_hash_and_context_root_in_sync(self) -> None:
        """A machine-bound submission must use its complete static hash."""
        machine = SampleClass.get_sample_pbs_local_context()
        submission = Submission(
            work_base="0_md/",
            machine=machine,
            resources=SampleClass.get_sample_resources(),
        )

        assert submission.submission_hash is not None
        self.assertEqual(submission.submission_hash, submission.get_hash())
        self.assertEqual(
            machine.context.remote_root,
            os.path.join(machine.context.temp_remote_root, submission.submission_hash),
        )

    def test_absolute_work_base_is_supported_and_serializable(self) -> None:
        """Absolute work directories retain their historical as-is behavior."""
        machine = SampleClass.get_sample_pbs_local_context()
        absolute_work_base = os.path.abspath(os.path.join("/tmp", "dpdispatcher-work"))
        submission = Submission(
            work_base=absolute_work_base,
            machine=machine,
            resources=SampleClass.get_sample_resources(),
        )

        self.assertEqual(submission.work_base, absolute_work_base)
        restored = Submission.deserialize(
            submission.serialize(), machine=machine, bind_context=False
        )
        self.assertEqual(restored.work_base, absolute_work_base)
        self.assertEqual(restored._abs_work_base, absolute_work_base)

    def test_get_submision_state(self) -> None:
        pass

    def test_handle_unexpected_submission_state(self) -> None:
        pass

    def test_submit_submission(self) -> None:
        pass

    def test_upload_jobs(self) -> None:
        pass

    def test_download_jobs(self) -> None:
        pass

    def test_submission_to_json(self) -> None:
        pass

    @patch("dpdispatcher.Submission.submission_to_json")
    @patch("dpdispatcher.Submission.update_submission_state")
    def test_check_all_finished(
        self,
        patch_update_submission_state: Any,  # noqa: ANN401
        patch_submission_to_json: Any,  # noqa: ANN401
    ) -> None:
        patch_update_submission_state = MagicMock(return_value=None)
        patch_submission_to_json = MagicMock(return_value=None)

        self.submission.belonging_jobs[0].job_state = JobStatus.running
        self.submission.belonging_jobs[1].job_state = JobStatus.waiting
        self.assertFalse(self.submission.check_all_finished())

        self.submission.belonging_jobs[0].job_state = JobStatus.finished
        self.submission.belonging_jobs[1].job_state = JobStatus.unsubmitted
        self.assertFalse(self.submission.check_all_finished())

        self.submission.belonging_jobs[0].job_state = JobStatus.completing
        self.submission.belonging_jobs[1].job_state = JobStatus.finished
        self.assertFalse(self.submission.check_all_finished())

        self.submission.belonging_jobs[0].job_state = JobStatus.finished
        self.submission.belonging_jobs[1].job_state = JobStatus.unknown
        self.assertFalse(self.submission.check_all_finished())

        self.submission.belonging_jobs[0].job_state = JobStatus.finished
        self.submission.belonging_jobs[1].job_state = JobStatus.finished
        self.assertTrue(self.submission.check_all_finished())

    def test_check_all_finished_rejects_uninitialized_jobs(self) -> None:
        """Jobs without a backend state are not completed jobs."""
        for job in self.submission.belonging_jobs:
            job.job_state = None

        self.assertFalse(self.submission.check_all_finished())

    def test_deserialize_preserves_tasks_and_absolute_work_base(self) -> None:
        """Deserialization keeps task ownership and the original work path."""
        serialized = self.submission.serialize()
        serialized["_abs_work_base"] = "/work/from/original/process"

        restored = Submission.deserialize(
            submission_dict=serialized,
            machine=self.submission.machine,
            bind_context=False,
        )

        self.assertEqual(restored._abs_work_base, serialized["_abs_work_base"])
        self.assertCountEqual(
            [task.serialize() for task in restored.belonging_tasks],
            [task.serialize() for task in self.submission.belonging_tasks],
        )
        for job in restored.belonging_jobs:
            for task in job.job_task_list:
                self.assertIn(task, restored.belonging_tasks)

    def test_deserialize_preserves_tasks_before_job_generation(self) -> None:
        """Unsubmitted task lists are serialized when no jobs exist yet."""
        machine = SampleClass.get_sample_pbs_local_context()
        submission = Submission(
            work_base="0_md/",
            machine=machine,
            resources=SampleClass.get_sample_resources(),
            task_list=[SampleClass.get_sample_task()],
        )

        restored = Submission.deserialize(
            submission_dict=submission.serialize(),
            machine=machine,
            bind_context=False,
        )

        self.assertEqual(
            [task.serialize() for task in restored.belonging_tasks],
            [task.serialize() for task in submission.belonging_tasks],
        )

    def test_submission_from_json(self) -> None:
        submission2 = Submission.submission_from_json("jsons/submission.json")
        # print('<<<<<<<', self.submission)
        # print('>>>>>>>', submission2)
        self.assertEqual(self.submission.serialize(), submission2.serialize())

    def test_submission_json(self) -> None:
        with open("jsons/submission.json") as f:
            submission_json_dict = json.load(f)
        self.assertTrue(submission_json_dict, self.submission.serialize())

    def test_try_recover_from_json(self) -> None:
        context = self.submission.machine.context
        context.check_file_exists = MagicMock(return_value=True)
        context.read_file = MagicMock(
            return_value=json.dumps(self.submission.serialize())
        )

        # Recovery must not deserialize the serialized machine because that would
        # establish a second connection instead of reusing the authenticated one.
        with patch("dpdispatcher.submission.Machine.deserialize") as deserialize:
            self.submission.try_recover_from_json()

        deserialize.assert_not_called()
        self.assertIs(self.submission.machine.context, context)

    def test_try_recover_from_json_mismatch_restores_context(self) -> None:
        context = self.submission.machine.context
        original_local_root = context.local_root
        original_remote_root = context.remote_root
        mismatched_submission = self.submission.serialize()
        mismatched_submission["work_base"] = "different_work_base"
        context.check_file_exists = MagicMock(return_value=True)
        context.read_file = MagicMock(return_value=json.dumps(mismatched_submission))

        with patch.object(
            context, "bind_submission", wraps=context.bind_submission
        ) as bind_submission:
            with self.assertRaisesRegex(RuntimeError, "Recover failed"):
                self.submission.try_recover_from_json()

        bind_submission.assert_not_called()
        self.assertIs(context.submission, self.submission)
        self.assertEqual(context.local_root, original_local_root)
        self.assertEqual(context.remote_root, original_remote_root)

    def test_repr(self) -> None:
        submission_repr = repr(self.submission)
        j = json.dumps(self.submission.serialize(), indent=4)
        self.assertEqual(submission_repr, j)
        # self.submission_to_json()

    def test_clean(self) -> None:
        pass

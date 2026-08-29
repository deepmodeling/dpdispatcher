import os
import tempfile
import unittest

from dpdispatcher import Machine, Resources, Submission, Task
from dpdispatcher.utils.job_status import JobStatus


class TestPreviousSubmissionResume(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.local_root = os.path.join(self.tempdir.name, "local")
        self.remote_root = os.path.join(self.tempdir.name, "remote")
        os.makedirs(self.local_root)
        os.makedirs(self.remote_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _machine(self) -> Machine:
        return Machine(
            batch_type="Shell",
            context_type="LocalContext",
            local_root=self.local_root,
            remote_root=self.remote_root,
        )

    def _old_submission(self) -> Submission:
        submission = Submission(
            work_base="work",
            machine=self._machine(),
            resources=Resources(1, 1, 0, "", 1, wait_time=0),
            task_list=[Task("true", "task", backward_files=["result"])],
        )
        submission.generate_jobs()
        os.makedirs(submission.machine.context.remote_root, exist_ok=True)
        submission.submission_to_json()
        return submission

    def test_resource_change_reuses_only_completed_tasks(self) -> None:
        previous = self._old_submission()
        task = previous.belonging_jobs[0].job_task_list[0]
        task_dir = os.path.join(previous.machine.context.remote_root, "task")
        os.makedirs(task_dir)
        open(os.path.join(task_dir, f"{task.task_hash}_task_tag_finished"), "w").close()

        current = Submission(
            work_base="work",
            machine=self._machine(),
            resources=Resources(1, 1, 0, "", 1, wait_time=30),
            task_list=[Task("true", "task", backward_files=["result"])],
            previous_submission_hash=previous.submission_hash,
        )
        current.generate_jobs()
        self.assertNotEqual(current.submission_hash, previous.submission_hash)

        current.try_recover_from_json()

        self.assertEqual(
            current.machine.context.remote_root,
            os.path.join(self.remote_root, previous.submission_hash),
        )
        self.assertEqual(current.belonging_jobs[0].job_state, JobStatus.finished)
        self.assertEqual(
            current.belonging_jobs[0].job_task_list[0].task_state,
            JobStatus.finished,
        )

    def test_non_resource_change_is_rejected(self) -> None:
        previous = self._old_submission()
        current = Submission(
            work_base="work",
            machine=self._machine(),
            resources=Resources(1, 1, 0, "", 1, wait_time=30),
            task_list=[Task("false", "task", backward_files=["result"])],
            previous_submission_hash=previous.submission_hash,
        )
        current.generate_jobs()

        with self.assertRaisesRegex(RuntimeError, "task grouping"):
            current.try_recover_from_json()

    def test_previous_hash_is_validated_before_path_binding(self) -> None:
        with self.assertRaisesRegex(ValueError, "40-character SHA-1"):
            Submission(
                work_base="work",
                machine=self._machine(),
                resources=Resources(1, 1, 0, "", 1),
                task_list=[Task("true", "task")],
                previous_submission_hash="../../another-directory",
            )

    def test_json_loader_accepts_previous_hash(self) -> None:
        previous = self._old_submission()
        serialized = previous.serialize()
        serialized["previous_submission_hash"] = previous.submission_hash
        recovered = Submission.deserialize(serialized)
        self.assertEqual(recovered.previous_submission_hash, previous.submission_hash)


if __name__ == "__main__":
    unittest.main()

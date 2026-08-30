import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from dpdispatcher import Job, Machine, Resources, Submission, Task
from dpdispatcher.contexts.hdfs_context import HDFSContext
from dpdispatcher.contexts.ssh_context import SSHContext
from dpdispatcher.utils.hdfs_cli import HDFS
from dpdispatcher.utils.job_status import JobStatus


class TestPreviousSubmissionResume(unittest.TestCase):
    def setUp(self) -> None:
        """Create isolated local and remote roots for each recovery test."""
        self.tempdir = tempfile.TemporaryDirectory()
        self.local_root = os.path.join(self.tempdir.name, "local")
        self.remote_root = os.path.join(self.tempdir.name, "remote")
        os.makedirs(self.local_root)
        os.makedirs(self.remote_root)

    def tearDown(self) -> None:
        """Remove the temporary roots created by :meth:`setUp`."""
        self.tempdir.cleanup()

    def _machine(self) -> Machine:
        """Build a LocalContext machine rooted in the test temporary directory."""
        return Machine(
            batch_type="Shell",
            context_type="LocalContext",
            local_root=self.local_root,
            remote_root=self.remote_root,
        )

    def _lazy_machine(self) -> Machine:
        """Build a LazyLocalContext machine sharing one hash-independent root."""
        return Machine(
            batch_type="Shell",
            context_type="LazyLocalContext",
            local_root=self.local_root,
        )

    def _old_submission(self) -> Submission:
        """Create and persist a baseline submission used as recovery input."""
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
        """Reuse a finished task tag while assigning the new resource hash."""
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
            os.path.join(self.remote_root, current.submission_hash),
        )
        self.assertEqual(current.belonging_jobs[0].job_state, JobStatus.finished)
        self.assertEqual(
            current.belonging_jobs[0].job_task_list[0].task_state,
            JobStatus.finished,
        )

    def test_missing_explicit_previous_state_fails_fast(self) -> None:
        """A mistyped prior hash must not silently submit into a new directory."""
        machine = self._machine()
        current = Submission(
            work_base="work",
            machine=machine,
            resources=Resources(1, 1, 0, "", 1, wait_time=30),
            task_list=[Task("true", "task", backward_files=["result"])],
            previous_submission_hash="0" * 40,
        )
        current.generate_jobs()

        with self.assertRaisesRegex(FileNotFoundError, "Previous submission state"):
            current.try_recover_from_json()

    def test_chained_resume_persists_state_under_new_hash(self) -> None:
        """A subsequent fresh process can resume from the migrated H1 state."""
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
        current.try_recover_from_json()
        current.submission_to_json()

        self.assertFalse(
            os.path.exists(os.path.join(self.remote_root, previous.submission_hash))
        )
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    self.remote_root,
                    current.submission_hash,
                    f"{current.submission_hash}.json",
                )
            )
        )

        chained = Submission(
            work_base="work",
            machine=self._machine(),
            resources=Resources(1, 1, 0, "", 1, wait_time=60),
            task_list=[Task("true", "task", backward_files=["result"])],
            previous_submission_hash=current.submission_hash,
        )
        chained.generate_jobs()
        chained.try_recover_from_json()
        self.assertEqual(
            chained.belonging_jobs[0].job_task_list[0].task_state,
            JobStatus.finished,
        )

    def test_recovered_state_clears_one_time_previous_locator(self) -> None:
        """Fresh deserialization must bind the migrated state under its new hash."""
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
        current.try_recover_from_json()
        current.submission_to_json()

        state_path = os.path.join(
            self.remote_root,
            current.submission_hash,
            f"{current.submission_hash}.json",
        )
        loaded = Submission.submission_from_json(state_path)
        self.assertIsNone(loaded.previous_submission_hash)
        self.assertEqual(
            loaded.machine.context.remote_root,
            os.path.join(self.remote_root, current.submission_hash),
        )
        loaded.try_recover_from_json()

    def test_lazy_local_recovery_keeps_shared_work_base(self) -> None:
        """LazyLocalContext must not move its hash-independent work directory."""
        previous = Submission(
            work_base="work",
            machine=self._lazy_machine(),
            resources=Resources(1, 1, 0, "", 1, wait_time=0),
            task_list=[Task("true", "task")],
        )
        previous.generate_jobs()
        os.makedirs(previous.machine.context.remote_root, exist_ok=True)
        previous.submission_to_json()
        task = previous.belonging_jobs[0].job_task_list[0]
        os.makedirs(previous.machine.context.remote_root + "/task", exist_ok=True)
        open(
            os.path.join(
                previous.machine.context.remote_root,
                "task",
                f"{task.task_hash}_task_tag_finished",
            ),
            "w",
        ).close()

        current = Submission(
            work_base="work",
            machine=self._lazy_machine(),
            resources=Resources(1, 1, 0, "", 1, wait_time=30),
            task_list=[Task("true", "task")],
            previous_submission_hash=previous.submission_hash,
        )
        current.generate_jobs()
        current.try_recover_from_json()

        self.assertEqual(
            current.machine.context.remote_root,
            os.path.join(self.local_root, "work"),
        )
        self.assertTrue(os.path.isdir(os.path.join(self.local_root, "work")))
        self.assertEqual(
            current.belonging_jobs[0].job_task_list[0].task_state,
            JobStatus.finished,
        )

    def test_local_recovery_rejects_conflicting_roots(self) -> None:
        """A stale LocalContext destination must not hide the source state."""
        previous = self._old_submission()
        current = Submission(
            work_base="work",
            machine=self._machine(),
            resources=Resources(1, 1, 0, "", 1, wait_time=30),
            task_list=[Task("true", "task", backward_files=["result"])],
            previous_submission_hash=previous.submission_hash,
        )
        current.generate_jobs()
        old_root = previous.machine.context.remote_root
        new_root = os.path.join(self.remote_root, current.submission_hash)
        os.makedirs(new_root)

        with self.assertRaisesRegex(FileExistsError, "both old and new"):
            current.try_recover_from_json()

        self.assertTrue(os.path.isdir(old_root))
        self.assertTrue(os.path.isdir(new_root))

    def test_ssh_recovery_rejects_conflicting_roots(self) -> None:
        """A stale SSH destination must not hide tags in the source root."""
        context = SSHContext.__new__(SSHContext)
        context.remote_root = "/remote/new"
        session = MagicMock()
        session.sftp.listdir.return_value = ["previous.json"]
        session.sftp.stat.return_value = MagicMock()
        context.ssh_session = session

        with self.assertRaisesRegex(FileExistsError, "both old and new"):
            context._recover_remote_root("/remote/old")

        session.sftp.rename.assert_not_called()

    def test_cloud_recovery_uses_persisted_finished_job_state(self) -> None:
        """Cloud recovery must not depend on unavailable task-tag paths."""
        task = Task("true", "task")
        machine = MagicMock()
        machine.serialize.return_value = {"cloud": "machine"}
        machine.context.supports_task_completion_tags = False
        machine.context.check_file_exists.return_value = False
        submission = Submission.__new__(Submission)
        submission.machine = machine
        submission.work_base = "work"
        submission._abs_work_base = os.path.abspath("work")
        submission.previous_submission_hash = "previous-hash"
        submission.submission_hash = "current-hash"
        submission.forward_common_files = []
        submission.backward_common_files = []
        submission.belonging_jobs = []
        submission.belonging_tasks = [task]
        job = Job(
            job_task_list=[task],
            machine=machine,
            resources=Resources(1, 1, 0, "", 1),
        )
        job.job_state = JobStatus.finished
        submission.belonging_jobs = [job]
        previous = {
            "work_base": "work",
            "_abs_work_base": submission._abs_work_base,
            "machine": {"cloud": "machine"},
            "forward_common_files": [],
            "backward_common_files": [],
            "belonging_jobs": [job.serialize()],
        }

        submission._recover_finished_tasks_from_previous(previous)

        self.assertEqual(task.task_state, JobStatus.finished)
        machine.context.check_file_exists.assert_not_called()

    def test_non_resource_change_is_rejected(self) -> None:
        """Reject recovery when task definitions change with the resources."""
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
        """Reject malformed prior hashes before touching any context paths."""
        with self.assertRaisesRegex(ValueError, "40-character SHA-1"):
            Submission(
                work_base="work",
                machine=self._machine(),
                resources=Resources(1, 1, 0, "", 1),
                task_list=[Task("true", "task")],
                previous_submission_hash="../../another-directory",
            )

    def test_json_loader_accepts_previous_hash(self) -> None:
        """Round-trip the explicit previous-submission hash in JSON state."""
        previous = self._old_submission()
        serialized = previous.serialize()
        serialized["previous_submission_hash"] = previous.submission_hash
        recovered = Submission.deserialize(serialized)
        self.assertEqual(recovered.previous_submission_hash, previous.submission_hash)

    def test_hdfs_recovery_moves_root_through_backend(self) -> None:
        """HDFS recovery must preserve completion state under the new hash."""
        context = HDFSContext.__new__(HDFSContext)
        old_root = "hdfs://cluster/work/old"
        new_root = "hdfs://cluster/work/new"
        with (
            patch.object(HDFS, "exists", side_effect=[False, True]) as exists,
            patch.object(HDFS, "move") as move,
        ):
            context.migrate_recovery_root(old_root, new_root)

        self.assertEqual(exists.call_args_list[0].args, (new_root,))
        self.assertEqual(exists.call_args_list[1].args, (old_root,))
        move.assert_called_once_with(old_root, new_root)

    def test_hdfs_recovery_rejects_conflicting_roots(self) -> None:
        """A stale destination must not hide completion tags in the source."""
        context = HDFSContext.__new__(HDFSContext)
        old_root = "hdfs://cluster/work/old"
        new_root = "hdfs://cluster/work/new"
        with patch.object(HDFS, "exists", side_effect=[True, True]):
            with self.assertRaisesRegex(FileExistsError, "both old and new"):
                context.migrate_recovery_root(old_root, new_root)


if __name__ == "__main__":
    unittest.main()

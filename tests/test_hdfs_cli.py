import os
import shlex
import tempfile
import unittest
from unittest.mock import Mock, call, patch

from dpdispatcher.machines.pbs import SGE
from dpdispatcher.utils.hdfs_cli import HDFS


class TestHDFSCommands(unittest.TestCase):
    """Verify HDFS paths are passed as argv without shell interpretation."""

    @patch("dpdispatcher.utils.hdfs_cli.run_cmd_with_all_output")
    def test_paths_with_spaces_and_metacharacters_remain_single_arguments(
        self, mock_run: Mock
    ) -> None:
        """Every dynamic HDFS path is an argv item and shell execution is off."""
        mock_run.return_value = (0, b"output", b"")
        unsafe_uri = "hdfs://cluster/path with space; touch injected"
        second_uri = "hdfs://cluster/other $(touch injected)"
        wildcard_uri = "hdfs://cluster/path with space/*_download.tar.gz"
        local_destination = "/tmp/result dir; touch injected"

        with tempfile.TemporaryDirectory() as temp_dir:
            local_source = os.path.join(temp_dir, "input file; touch injected")
            with open(local_source, "wb") as fp:
                fp.write(b"input")

            self.assertTrue(HDFS.exists(unsafe_uri))
            self.assertTrue(HDFS.remove(unsafe_uri))
            self.assertTrue(HDFS.mkdir(unsafe_uri))
            self.assertEqual(
                HDFS.copy_from_local(local_source, unsafe_uri), (True, b"output")
            )
            self.assertTrue(HDFS.copy_to_local(unsafe_uri, local_destination))
            self.assertTrue(HDFS.copy_to_local(wildcard_uri, local_destination))
            self.assertTrue(
                HDFS.copy_to_local((unsafe_uri, second_uri), local_destination)
            )
            self.assertEqual(HDFS.read_hdfs_file(unsafe_uri), b"output")
            self.assertTrue(HDFS.move(unsafe_uri, second_uri))

        expected_calls = [
            call(["hadoop", "fs", "-test", "-e", unsafe_uri], shell=False),
            call(["hadoop", "fs", "-rm", "-r", unsafe_uri], shell=False),
            call(["hadoop", "fs", "-mkdir", "-p", unsafe_uri], shell=False),
            call(
                [
                    "hadoop",
                    "fs",
                    "-copyFromLocal",
                    "-f",
                    local_source,
                    unsafe_uri,
                ],
                shell=False,
            ),
            call(
                ["hadoop", "fs", "-copyToLocal", unsafe_uri, local_destination],
                shell=False,
            ),
            call(
                ["hadoop", "fs", "-copyToLocal", wildcard_uri, local_destination],
                shell=False,
            ),
            call(
                [
                    "hadoop",
                    "fs",
                    "-copyToLocal",
                    unsafe_uri,
                    second_uri,
                    local_destination,
                ],
                shell=False,
            ),
            call(["hadoop", "fs", "-text", unsafe_uri], shell=False),
            call(["hadoop", "fs", "-mv", unsafe_uri, second_uri], shell=False),
        ]
        self.assertEqual(mock_run.call_args_list, expected_calls)

    @patch("dpdispatcher.utils.hdfs_cli.run_cmd_with_all_output")
    def test_exists_preserves_hadoop_missing_status(self, mock_run: Mock) -> None:
        """Hadoop's status 1 still means a URI is absent rather than an error."""
        mock_run.return_value = (1, b"", b"")

        self.assertFalse(HDFS.exists("hdfs://cluster/missing path"))
        mock_run.assert_called_once_with(
            ["hadoop", "fs", "-test", "-e", "hdfs://cluster/missing path"],
            shell=False,
        )

    @patch("dpdispatcher.utils.hdfs_cli.run_cmd_with_all_output")
    def test_rejects_option_like_and_invalid_operands(self, mock_run: Mock) -> None:
        """Unsafe argv operands are rejected before Hadoop is started."""
        invalid_values = ("", "-Ddangerous=true", "path\x00suffix", 12)
        for invalid_value in invalid_values:
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaises((TypeError, ValueError)):
                    HDFS.exists(invalid_value)  # type: ignore[arg-type]

        with self.assertRaises(ValueError):
            HDFS.copy_to_local([], "/tmp/output")
        with self.assertRaises(ValueError):
            HDFS.copy_to_local(["hdfs://valid", "-getmerge"], "/tmp/output")

        # A dash after a path separator is data, not an option prefix.
        mock_run.return_value = (0, b"", b"")
        self.assertTrue(HDFS.exists("hdfs://cluster/-valid-name"))
        mock_run.assert_called_once_with(
            ["hadoop", "fs", "-test", "-e", "hdfs://cluster/-valid-name"],
            shell=False,
        )


class TestSGESubmissionQuoting(unittest.TestCase):
    """Verify the unavoidable remote SGE shell command quotes dynamic paths."""

    def test_remote_root_and_script_name_are_shell_quoted(self) -> None:
        """Spaces and metacharacters cannot become additional shell commands."""
        context = Mock()
        context.remote_root = "-remote work/$(touch injected)"
        stdout = Mock()
        stdout.readlines.return_value = [b'Your job 123 ("test") has been submitted\n']
        context.block_checkcall.return_value = (None, stdout, None)

        machine = SGE(context=context)
        machine.gen_script = Mock(return_value="script")
        machine.gen_script_command = Mock(return_value="run script")

        job = Mock()
        job.script_file_name = "-job name; touch injected.sub"
        job.job_hash = "job-hash"

        self.assertEqual(machine.do_submit(job), b"123")

        expected_remote_root = f"./{context.remote_root}"
        expected_script_argument = f"./{job.script_file_name}"
        expected_command = (
            f"cd {shlex.quote(expected_remote_root)} && "
            f"qsub {shlex.quote(expected_script_argument)}"
        )
        context.block_checkcall.assert_called_once_with(expected_command)
        self.assertEqual(
            shlex.split(expected_command),
            ["cd", expected_remote_root, "&&", "qsub", expected_script_argument],
        )


if __name__ == "__main__":
    unittest.main()

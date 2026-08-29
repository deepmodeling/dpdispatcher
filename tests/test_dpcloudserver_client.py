import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import requests

from dpdispatcher.utils.dpcloudserver.client import Client, RequestInfoException
from dpdispatcher.utils.dpcloudserver.config import HTTP_TIME_OUT


class TestClientTicket(unittest.TestCase):
    def _successful_response(self):
        response = MagicMock(ok=True)
        response.json.return_value = {"code": "0000", "data": {}}
        return response

    def test_explicit_ticket_skips_login_when_environment_is_empty(self):
        client = Client(ticket="explicit-ticket", base_url="https://example.test")

        with patch.dict(os.environ, {"BOHR_TICKET": ""}):
            with patch(
                "dpdispatcher.utils.dpcloudserver.client.requests.get",
                return_value=self._successful_response(),
            ) as request_get:
                with patch(
                    "dpdispatcher.utils.dpcloudserver.client.requests.post"
                ) as request_post:
                    client.get("/jobs")

        request_post.assert_not_called()
        self.assertEqual(
            request_get.call_args[1]["headers"]["Brm-Ticket"],
            "explicit-ticket",
        )

    def test_environment_ticket_skips_login_without_explicit_ticket(self):
        client = Client(base_url="https://example.test")

        with patch.dict(os.environ, {"BOHR_TICKET": "environment-ticket"}):
            with patch(
                "dpdispatcher.utils.dpcloudserver.client.requests.get",
                return_value=self._successful_response(),
            ) as request_get:
                with patch(
                    "dpdispatcher.utils.dpcloudserver.client.requests.post"
                ) as request_post:
                    client.get("/jobs")

        request_post.assert_not_called()
        self.assertEqual(
            request_get.call_args[1]["headers"]["Brm-Ticket"],
            "environment-ticket",
        )

    def test_environment_ticket_temporarily_overrides_explicit_ticket(self):
        client = Client(ticket="explicit-ticket", base_url="https://example.test")

        with patch(
            "dpdispatcher.utils.dpcloudserver.client.requests.get",
            return_value=self._successful_response(),
        ) as request_get:
            with patch.dict(os.environ, {"BOHR_TICKET": "environment-ticket"}):
                client.get("/jobs")
            with patch.dict(os.environ, {"BOHR_TICKET": ""}):
                client.get("/jobs")

        self.assertEqual(
            request_get.call_args_list[0][1]["headers"]["Brm-Ticket"],
            "environment-ticket",
        )
        self.assertEqual(
            request_get.call_args_list[1][1]["headers"]["Brm-Ticket"],
            "explicit-ticket",
        )
        self.assertEqual(client.ticket, "explicit-ticket")

    def test_missing_ticket_uses_password_login(self):
        client = Client(
            email="user@example.test",
            password="secret",
            base_url="https://example.test",
        )
        login_response = MagicMock(ok=True, status_code=200)
        login_response.json.return_value = {
            "code": "0000",
            "data": {"token": "login-token"},
        }

        with patch.dict(os.environ, {"BOHR_TICKET": ""}):
            with patch(
                "dpdispatcher.utils.dpcloudserver.client.requests.get",
                return_value=self._successful_response(),
            ) as request_get:
                with patch(
                    "dpdispatcher.utils.dpcloudserver.client.requests.post",
                    return_value=login_response,
                ) as request_post:
                    client.get("/jobs")

        request_post.assert_called_once()
        self.assertEqual(client.token, "login-token")
        self.assertEqual(request_get.call_args[1]["headers"]["Brm-Ticket"], "")


class TestClientLogOffsets(unittest.TestCase):
    def test_log_offsets_are_independent_for_each_job(self):
        client = Client()
        client._get_job_log = MagicMock(
            side_effect=[
                ("https://example.test/a.log", 100),
                ("https://example.test/b.log", 100),
                ("https://example.test/a.log", 100),
            ]
        )
        responses = []
        for content in (b"abc", b"wxyz", b"def"):
            response = MagicMock(content=content, ok=True)
            responses.append(response)

        with patch(
            "dpdispatcher.utils.dpcloudserver.client.requests.get",
            side_effect=responses,
        ) as request_get:
            self.assertEqual(client.get_log("job-a"), "abc")
            self.assertEqual(client.get_log("job-b"), "wxyz")
            self.assertEqual(client.get_log("job-a"), "def")

        self.assertEqual(
            request_get.call_args_list,
            [
                call(
                    "https://example.test/a.log",
                    headers={"Range": "bytes=0-"},
                    timeout=HTTP_TIME_OUT,
                ),
                call(
                    "https://example.test/b.log",
                    headers={"Range": "bytes=0-"},
                    timeout=HTTP_TIME_OUT,
                ),
                call(
                    "https://example.test/a.log",
                    headers={"Range": "bytes=3-"},
                    timeout=HTTP_TIME_OUT,
                ),
            ],
        )

    def test_completed_job_does_not_suppress_another_job(self):
        client = Client()
        client._get_job_log = MagicMock(
            side_effect=[
                ("https://example.test/a.log", 3),
                ("https://example.test/a.log", 3),
                ("https://example.test/b.log", 2),
            ]
        )
        first_response = MagicMock(content=b"abc", ok=True)
        second_response = MagicMock(content=b"de", ok=True)

        with patch(
            "dpdispatcher.utils.dpcloudserver.client.requests.get",
            side_effect=[first_response, second_response],
        ) as request_get:
            self.assertEqual(client.get_log(1), "abc")
            self.assertEqual(client.get_log("1"), "")
            self.assertEqual(client.get_log(2), "de")

        self.assertEqual(
            request_get.call_args_list,
            [
                call(
                    "https://example.test/a.log",
                    headers={"Range": "bytes=0-"},
                    timeout=HTTP_TIME_OUT,
                ),
                call(
                    "https://example.test/b.log",
                    headers={"Range": "bytes=0-"},
                    timeout=HTTP_TIME_OUT,
                ),
            ],
        )

    def test_failed_response_does_not_advance_offset(self):
        """An HTTP error body is neither returned nor counted as log data."""
        client = Client()
        client._get_job_log = MagicMock(
            return_value=("https://example.test/job.log", 100)
        )
        failed_response = MagicMock(
            content=b"temporary error", ok=False, status_code=503
        )
        successful_response = MagicMock(content=b"abc", ok=True)

        with patch(
            "dpdispatcher.utils.dpcloudserver.client.requests.get",
            side_effect=[failed_response, successful_response],
        ) as request_get:
            with patch("dpdispatcher.utils.dpcloudserver.client.dlog.error"):
                self.assertEqual(client.get_log("job"), "")
                self.assertNotIn("job", client.last_log_offsets)
                self.assertEqual(client.get_log("job"), "abc")

        self.assertEqual(
            request_get.call_args_list,
            [
                call(
                    "https://example.test/job.log",
                    headers={"Range": "bytes=0-"},
                    timeout=HTTP_TIME_OUT,
                ),
                call(
                    "https://example.test/job.log",
                    headers={"Range": "bytes=0-"},
                    timeout=HTTP_TIME_OUT,
                ),
            ],
        )

    def test_request_exception_does_not_advance_offset(self):
        """A timed-out download is retried from the same byte position."""
        client = Client()
        client._get_job_log = MagicMock(
            return_value=("https://example.test/job.log", 100)
        )
        successful_response = MagicMock(content=b"abc", ok=True)

        with patch(
            "dpdispatcher.utils.dpcloudserver.client.requests.get",
            side_effect=[requests.Timeout("timed out"), successful_response],
        ) as request_get:
            with patch("dpdispatcher.utils.dpcloudserver.client.dlog.error"):
                self.assertEqual(client.get_log("job"), "")
                self.assertNotIn("job", client.last_log_offsets)
                self.assertEqual(client.get_log("job"), "abc")

        self.assertEqual(
            request_get.call_args_list,
            [
                call(
                    "https://example.test/job.log",
                    headers={"Range": "bytes=0-"},
                    timeout=HTTP_TIME_OUT,
                ),
                call(
                    "https://example.test/job.log",
                    headers={"Range": "bytes=0-"},
                    timeout=HTTP_TIME_OUT,
                ),
            ],
        )


class TestDownloadFromUrl(unittest.TestCase):
    """Verify exhausted downloads report the remote failure immediately."""

    @patch("dpdispatcher.utils.dpcloudserver.client.requests.get")
    def test_success_writes_chunks_and_closes_response(
        self, mock_get: MagicMock
    ) -> None:
        response = MagicMock(ok=True)
        response.iter_content.return_value = [b"zip-", b"content"]
        mock_get.return_value = response
        client = Client(ticket="ticket")
        client.token = "token"

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "result.zip"
            client.download_from_url("https://example.invalid/result.zip", target)

            self.assertEqual(target.read_bytes(), b"zip-content")

        response.iter_content.assert_called_once_with(chunk_size=8192)
        response.close.assert_called_once_with()

    @patch("dpdispatcher.utils.dpcloudserver.client.time.sleep")
    @patch("dpdispatcher.utils.dpcloudserver.client.requests.get")
    def test_http_failure_raises_with_response_details(
        self, mock_get: MagicMock, _mock_sleep: MagicMock
    ) -> None:
        response = MagicMock(
            ok=False,
            status_code=503,
            reason="Service Unavailable",
            text="temporary upstream failure",
        )
        mock_get.return_value = response
        client = Client(ticket="ticket")
        client.token = "token"

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "result.zip"
            with self.assertRaises(RequestInfoException) as context:
                client.download_from_url("https://example.invalid/result.zip", target)

            self.assertFalse(target.exists())

        message = str(context.exception)
        self.assertIn("https://example.invalid/result.zip", message)
        self.assertIn("status_code=503", message)
        self.assertIn("Service Unavailable", message)
        self.assertIn("temporary upstream failure", message)
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(response.close.call_count, 3)

    @patch("dpdispatcher.utils.dpcloudserver.client.requests.get")
    def test_transport_failure_raises_with_exception_details(
        self, mock_get: MagicMock
    ) -> None:
        mock_get.side_effect = ConnectionError("connection refused")
        client = Client(ticket="ticket")
        client.token = "token"

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "result.zip"
            with self.assertRaises(RequestInfoException) as context:
                client.download_from_url("https://example.invalid/result.zip", target)

            self.assertFalse(target.exists())

        message = str(context.exception)
        self.assertIn("ConnectionError", message)
        self.assertIn("connection refused", message)
        self.assertEqual(mock_get.call_count, 3)


if __name__ == "__main__":
    unittest.main()

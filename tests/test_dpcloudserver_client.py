import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from dpdispatcher.utils.dpcloudserver.client import Client, RequestInfoException


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

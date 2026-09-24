import io
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from forge.health import wait_for_health


class TestHealthCheck(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_wait_for_health_success_with_host_header(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = wait_for_health("my-app.localhost", port=80, timeout=1.0, interval=0.1)
        self.assertTrue(result)
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "http://127.0.0.1:80/")
        self.assertEqual(req.headers["Host"], "my-app.localhost")

    @patch("urllib.request.urlopen")
    def test_wait_for_health_custom_path(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = wait_for_health("my-app.localhost", port=80, path="/healthz", timeout=1.0, interval=0.1)
        self.assertTrue(result)
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "http://127.0.0.1:80/healthz")
        self.assertEqual(req.headers["Host"], "my-app.localhost")

    @patch("urllib.request.urlopen")
    def test_wait_for_health_fails_on_connection_error(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        result = wait_for_health("my-app.localhost", port=80, timeout=0.3, interval=0.1)
        self.assertFalse(result)
        self.assertGreaterEqual(mock_urlopen.call_count, 1)

    @patch("urllib.request.urlopen")
    def test_wait_for_health_fails_on_500_error(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://127.0.0.1:80/",
            code=500,
            msg="Internal Server Error",
            hdrs=MagicMock(),
            fp=io.BytesIO(b"error"),
        )

        result = wait_for_health("my-app.localhost", port=80, timeout=0.3, interval=0.1)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()

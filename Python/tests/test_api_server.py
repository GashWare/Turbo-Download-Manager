"""
Unit tests for embedded HTTP API Server and IPC communication.
"""

import unittest
import time
import json
import urllib.request
import os
import sys

# Ensure core packages can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.api_server import ApiServer, send_url_to_running_instance


class TestApiServer(unittest.TestCase):
    """Tests for the embedded REST API server and IPC."""

    @classmethod
    def setUpClass(cls):
        cls.received_downloads = []

        def on_add(data):
            cls.received_downloads.append(data)

        def get_status():
            return {"active_downloads": 2, "total_downloads": 5}

        cls.server = ApiServer(port=9777, on_add_download=on_add, status_callback=get_status)
        cls.server.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_health_and_status_endpoint(self):
        """Verify GET /health returns 200 with status and app metadata."""
        req = urllib.request.Request("http://127.0.0.1:9777/health")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "ok")
            self.assertEqual(data.get("app"), "Turbo Download Manager")
            self.assertEqual(data.get("active_downloads"), 2)

    def test_post_add_download(self):
        """Verify POST /add queues download data into callback."""
        payload = {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "filename": "custom_name.mp4",
            "auto_start": True,
            "audio_only": False
        }
        req = urllib.request.Request(
            "http://127.0.0.1:9777/add",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))

        self.assertTrue(len(self.received_downloads) > 0)
        last = self.received_downloads[-1]
        self.assertEqual(last["url"], payload["url"])
        self.assertEqual(last["filename"], payload["filename"])

    def test_send_url_to_running_instance_helper(self):
        """Verify the helper send_url_to_running_instance forwards requests properly."""
        test_url = "https://example.com/archive.iso"
        success = send_url_to_running_instance(test_url, port=9777)
        self.assertTrue(success)

        last = self.received_downloads[-1]
        self.assertEqual(last["url"], test_url)


if __name__ == "__main__":
    unittest.main()

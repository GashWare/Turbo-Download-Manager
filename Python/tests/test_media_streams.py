"""
Unit tests for Facebook Reels, Facebook Videos, YouTube, and Streaming Media Extractor.
"""

import unittest
import os
import sys

# Ensure core packages can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.prober import is_likely_media_streaming_url, probe_url
from core.models import DownloadCategory, DownloadTask, DownloadStatus
from core.media_downloader import MediaDownloader


class TestMediaStreams(unittest.TestCase):
    """Tests for Facebook Reels/Videos and social media streaming extractors."""

    def test_facebook_and_media_url_detection(self):
        """Verify URL detection recognizes Facebook reels, watch links, stories, and other social media."""
        # Facebook Reels & Videos
        self.assertTrue(is_likely_media_streaming_url("https://www.facebook.com/reel/1351928276956715"))
        self.assertTrue(is_likely_media_streaming_url("https://facebook.com/watch/?v=123456789"))
        self.assertTrue(is_likely_media_streaming_url("https://fb.watch/abcd1234/"))
        self.assertTrue(is_likely_media_streaming_url("https://m.facebook.com/reel/987654321"))
        self.assertTrue(is_likely_media_streaming_url("https://www.facebook.com/share/r/abc123xyz/"))

        # Other platforms: X / Twitter, Instagram, TikTok, Reddit, Vimeo, Twitch
        self.assertTrue(is_likely_media_streaming_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(is_likely_media_streaming_url("https://youtu.be/dQw4w9WgXcQ"))
        self.assertTrue(is_likely_media_streaming_url("https://x.com/OpenAI/status/1758229889585996024"))
        self.assertTrue(is_likely_media_streaming_url("https://twitter.com/NASA/status/123456789"))
        self.assertTrue(is_likely_media_streaming_url("https://www.instagram.com/reel/C8xyz123/"))
        self.assertTrue(is_likely_media_streaming_url("https://www.instagram.com/p/DBxyz123/"))
        self.assertTrue(is_likely_media_streaming_url("https://www.tiktok.com/@user/video/1234567890"))
        self.assertTrue(is_likely_media_streaming_url("https://www.reddit.com/r/videos/comments/abc123/cool_video/"))
        self.assertTrue(is_likely_media_streaming_url("https://vimeo.com/76979871"))
        self.assertTrue(is_likely_media_streaming_url("https://www.twitch.tv/videos/123456789"))
        self.assertTrue(is_likely_media_streaming_url("https://clips.twitch.tv/FrailTameCaterpillar"))
        self.assertTrue(is_likely_media_streaming_url("https://www.twitch.tv/shroud/clip/FrailTameCaterpillar"))

        # Non-media files
        self.assertFalse(is_likely_media_streaming_url("https://example.com/archive.zip"))
        self.assertFalse(is_likely_media_streaming_url("https://example.com/image.png"))
        self.assertFalse(is_likely_media_streaming_url("https://example.com/document.pdf"))

    def test_media_task_options_and_serialization(self):
        """Verify task serialization with audio-only, format, and quality presets."""
        url = "https://www.facebook.com/reel/1351928276956715"
        task = DownloadTask(
            url=url,
            save_path="C:\\Downloads",
            filename="facebook_reel.mp4",
            is_media_stream=True,
            audio_only=True,
            media_format="mp3",
            media_quality="best",
            category=DownloadCategory.AUDIO
        )

        self.assertTrue(task.is_media_stream)
        self.assertTrue(task.audio_only)
        self.assertEqual(task.media_format, "mp3")
        self.assertEqual(task.category, DownloadCategory.AUDIO)

    def test_youtube_playlist_url_detection(self):
        """Verify URL detection recognizes YouTube playlists and video playlist mixes."""
        from core.prober import is_likely_playlist_url
        self.assertTrue(is_likely_playlist_url("https://www.youtube.com/playlist?list=PL1234567890ABCDEF"))
        self.assertTrue(is_likely_playlist_url("https://youtube.com/playlist?list=PLxyz"))
        self.assertTrue(is_likely_playlist_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL1234567890ABCDEF"))
        self.assertTrue(is_likely_playlist_url("https://youtu.be/dQw4w9WgXcQ?list=PL1234567890ABCDEF"))

        # Single video without playlist
        self.assertFalse(is_likely_playlist_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertFalse(is_likely_playlist_url("https://example.com/video.mp4"))

    def test_playlist_task_batch_generation(self):
        """Verify playlist entries generate appropriate video and MP3 audio tasks."""
        entries = [
            {"title": "Song One", "url": "https://www.youtube.com/watch?v=aaa", "id": "aaa"},
            {"title": "Song Two", "url": "https://www.youtube.com/watch?v=bbb", "id": "bbb"},
        ]
        save_dir = os.path.join(os.path.expanduser("~"), "Music", "My Playlist")

        # MP3 Audio playlist
        audio_tasks = [
            DownloadTask(
                url=e["url"],
                save_path=save_dir,
                filename=f"{e['title']}.mp3",
                is_media_stream=True,
                audio_only=True,
                media_format="mp3",
                category=DownloadCategory.AUDIO
            )
            for e in entries
        ]
        self.assertEqual(len(audio_tasks), 2)
        self.assertTrue(all(t.audio_only for t in audio_tasks))
        self.assertTrue(all(t.filename.endswith(".mp3") for t in audio_tasks))
        self.assertTrue(all(t.save_path == save_dir for t in audio_tasks))

        # MP4 Video playlist
        video_tasks = [
            DownloadTask(
                url=e["url"],
                save_path=save_dir,
                filename=f"{e['title']}.mp4",
                is_media_stream=True,
                audio_only=False,
                media_format="mp4",
                media_quality="1080p",
                category=DownloadCategory.VIDEO
            )
            for e in entries
        ]
        self.assertEqual(len(video_tasks), 2)
        self.assertFalse(any(t.audio_only for t in video_tasks))
        self.assertTrue(all(t.filename.endswith(".mp4") for t in video_tasks))
        self.assertTrue(all(t.media_quality == "1080p" for t in video_tasks))


if __name__ == "__main__":
    unittest.main()


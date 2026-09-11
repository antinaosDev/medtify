"""
Tests for EvolutionClient chat methods — Medtify V15 WhatsApp Chat feature.
Run: venv/bin/python -m unittest tests.test_evolution_client_chat -v
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evolution_client import EvolutionClient


class TestUrlJoin(unittest.TestCase):
    """Regression: _url() must never produce a double slash."""

    def test_url_no_double_slash_with_leading_slash_path(self):
        client = EvolutionClient(base_url="https://host", api_key="k", instance="i")
        self.assertEqual(client._url("/chat/findChats/i"), "https://host/chat/findChats/i")

    def test_url_no_double_slash_without_leading_slash(self):
        client = EvolutionClient(base_url="https://host", api_key="k", instance="i")
        self.assertEqual(client._url("chat/findChats/i"), "https://host/chat/findChats/i")

    def test_url_base_url_with_trailing_slash(self):
        client = EvolutionClient(base_url="https://host/", api_key="k", instance="i")
        self.assertEqual(client._url("/chat/findChats/i"), "https://host/chat/findChats/i")


class TestListChats(unittest.TestCase):
    """Tests for EvolutionClient.list_chats."""

    def setUp(self):
        self.client = EvolutionClient(
            base_url="http://test:8080",
            api_key="test-key",
            instance="medtify-test"
        )
        self.mock_session = MagicMock()
        self.client._session = self.mock_session

    def test_list_chats_ok(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "chats": [
                {"remoteJid": "56912345678@s.whatsapp.net", "name": "Juan", "unreadCount": 2},
                {"remoteJid": "56987654321@s.whatsapp.net", "name": "Maria", "unreadCount": 0}
            ]
        }
        self.mock_session.post.return_value = mock_resp

        result = self.client.list_chats(limite=50)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "Juan")
        self.assertEqual(result[1]["unreadCount"], 0)

    def test_list_chats_plain_list(self):
        """Evolution API 2.x returns a plain LIST, not {"chats": [...]}."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"remoteJid": "56912345678@s.whatsapp.net", "pushName": "Juan", "unreadCount": 2},
            {"remoteJid": "56987654321@s.whatsapp.net", "pushName": "Maria", "unreadCount": 0}
        ]
        self.mock_session.post.return_value = mock_resp

        result = self.client.list_chats(limite=50)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["pushName"], "Juan")
        self.assertEqual(result[1]["unreadCount"], 0)

    def test_list_chats_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        self.mock_session.post.return_value = mock_resp

        result = self.client.list_chats()
        self.assertEqual(result, [])

    def test_list_chats_empty(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"chats": []}
        self.mock_session.post.return_value = mock_resp

        result = self.client.list_chats()
        self.assertEqual(result, [])

    def test_list_chats_exception(self):
        self.mock_session.post.side_effect = Exception("Connection refused")

        result = self.client.list_chats()
        self.assertEqual(result, [])


class TestGetMessages(unittest.TestCase):
    """Tests for EvolutionClient.get_messages."""

    def setUp(self):
        self.client = EvolutionClient(
            base_url="http://test:8080",
            api_key="test-key",
            instance="medtify-test"
        )
        self.mock_session = MagicMock()
        self.client._session = self.mock_session

    def test_get_messages_ok(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "messages": {
                "records": [
                    {
                        "key": {"remoteJid": "56912345678@s.whatsapp.net", "fromMe": True},
                        "message": {"conversation": "Hola paciente"},
                        "messageTimestamp": 1694360060
                    },
                    {
                        "key": {"remoteJid": "56912345678@s.whatsapp.net", "fromMe": False},
                        "message": {"conversation": "Hola doctor"},
                        "messageTimestamp": 1694360000
                    }
                ],
                "total": 2
            }
        }
        self.mock_session.post.return_value = mock_resp

        result = self.client.get_messages("56912345678", limite=100)
        self.assertEqual(len(result), 2)
        # Messages are reversed from DESC to ASC, so result[0] is the oldest
        self.assertEqual(result[0]["body"], "Hola doctor")
        self.assertFalse(result[0]["fromMe"])
        self.assertEqual(result[1]["body"], "Hola paciente")
        self.assertTrue(result[1]["fromMe"])

    def test_get_messages_jid_construction(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"messages": {"records": [], "total": 0}}
        self.mock_session.post.return_value = mock_resp

        self.client.get_messages("+56 9 1234 5678", limite=50)

        call_args = self.mock_session.post.call_args
        payload = call_args[1]["json"]
        jid = payload["where"]["key"]["remoteJid"]
        self.assertEqual(jid, "56912345678@s.whatsapp.net")

    def test_get_messages_no_key(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        self.mock_session.post.return_value = mock_resp

        result = self.client.get_messages("56912345678")
        self.assertEqual(result, [])

    def test_get_messages_image(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "messages": {
                "records": [
                    {
                        "key": {"remoteJid": "56912345678@s.whatsapp.net", "fromMe": False},
                        "message": {
                            "imageMessage": {
                                "caption": "Foto de prueba",
                                "mimetype": "image/jpeg",
                                "url": "http://media.test/img.jpg"
                            }
                        },
                        "messageTimestamp": 1694360000
                    }
                ],
                "total": 1
            }
        }
        self.mock_session.post.return_value = mock_resp

        result = self.client.get_messages("56912345678")
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["hasImage"])
        self.assertEqual(result[0]["body"], "Foto de prueba")
        self.assertIsNotNone(result[0]["imageUrl"])

    def test_get_messages_exception(self):
        self.mock_session.post.side_effect = Exception("Timeout")

        result = self.client.get_messages("56912345678")
        self.assertEqual(result, [])


class TestGetMediaB64(unittest.TestCase):
    """Tests for EvolutionClient.get_media_b64."""

    def setUp(self):
        self.client = EvolutionClient(
            base_url="http://test:8080",
            api_key="test-key",
            instance="medtify-test"
        )
        self.mock_session = MagicMock()
        self.client._session = self.mock_session

    def test_get_media_ok(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "base64": "abc123",
            "mimetype": "image/jpeg"
        }
        self.mock_session.get.return_value = mock_resp

        result = self.client.get_media_b64("http://media.test/img.jpg")
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith("data:image/jpeg;base64,"))
        self.assertIn("abc123", result)

    def test_get_media_already_data_uri(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "base64": "data:image/png;base64,xyz789"
        }
        self.mock_session.get.return_value = mock_resp

        result = self.client.get_media_b64("http://media.test/img.png")
        self.assertEqual(result, "data:image/png;base64,xyz789")

    def test_get_media_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        self.mock_session.get.return_value = mock_resp

        result = self.client.get_media_b64("http://media.test/missing.jpg")
        self.assertIsNone(result)

    def test_get_media_no_base64(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"error": "not found"}
        self.mock_session.get.return_value = mock_resp

        result = self.client.get_media_b64("http://media.test/img.jpg")
        self.assertIsNone(result)

    def test_get_media_exception(self):
        self.mock_session.get.side_effect = Exception("Connection refused")

        result = self.client.get_media_b64("http://media.test/img.jpg")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

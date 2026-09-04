"""
OpenWA Adapter for Medtify V15
==============================
Drop-in replacement for `EvolutionClient` that talks to the OpenWA API
(https://ghcr.io/rmyndharis/openwa) instead of the Evolution API.

The `medtify_app_v15.py` app imports this class via:

    from openwa_adapter import OpenWAAdapter as EvolutionClient

so the interface MUST match `EvolutionClient` exactly:
    - __init__(base_url, api_key, instance, timeout, safe_mode)
    - send_message(numero, mensaje) -> (bool, str)
    - check_qr_status() -> Dict
    - get_qr_code() -> Optional[str]
    - verificar_respuesta(numero, keywords_si, keywords_no) -> (str, str)
    - get_last_incoming_message(numero) -> Optional[Dict]
    - _check_connection() -> bool
    - format_phone(numero) -> str

OpenWA API specifics:
    - Requires an `x-api-key` header (NOT `apikey`)
    - Many endpoints require the session UUID (not the name). This adapter
      resolves the UUID from the session name automatically and caches it.
    - Session status values: "connected", "disconnected", "qr_ready",
      "initializing", etc.
    - Send endpoint: POST /api/sessions/{uuid}/messages/send-text
      body: {"chatId": "56912345678@c.us", "text": "..."}
"""

import time
import random
import logging
import requests
from typing import Optional, Tuple, Dict, List

logger = logging.getLogger("openwa_adapter")


class OpenWAAdapter:
    """HTTP client for the OpenWA API, compatible with EvolutionClient's
    interface so it can be swapped in via the WHATSAPP_BACKEND env var."""

    def __init__(self, base_url: str, api_key: str, instance: str = "medtify-session",
                 timeout: int = 30, safe_mode: bool = False):
        """
        Args:
            base_url: OpenWA API server URL (e.g. http://79.98.29.50:2785)
            api_key: Authentication API key (x-api-key header)
            instance: Session NAME (e.g. "medtify-session"). The adapter
                      resolves the session UUID from this name automatically.
            timeout: HTTP request timeout in seconds
            safe_mode: If True, logs messages but doesn't send them
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.instance = instance
        self.timeout = timeout
        if safe_mode is None:
            safe_mode = False
        self.safe_mode = safe_mode
        self._session = requests.Session()
        self._session.headers.update({
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        })
        self._uuid_cache: Optional[str] = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _resolve_uuid(self) -> Optional[str]:
        """Resolve the session UUID from the session name.

        OpenWA requires the session UUID in most endpoints; the app only knows
        the session NAME. We look it up via GET /api/sessions and cache it.
        """
        if self._uuid_cache:
            return self._uuid_cache
        try:
            r = self._session.get(
                f"{self.base_url}/api/sessions",
                timeout=self.timeout
            )
            if r.status_code == 200:
                sessions = r.json()
                for s in sessions or []:
                    if s.get("name") == self.instance:
                        self._uuid_cache = s.get("id")
                        return self._uuid_cache
                logger.warning(
                    f"Session '{self.instance}' not found. Available: "
                    f"{[s.get('name') for s in sessions or []]}"
                )
                return None
            return None
        except Exception as e:
            logger.error(f"Error resolving UUID: {e}")
            return None

    def _api(self, method: str, path: str, **kwargs) -> Optional[requests.Response]:
        """Perform a request to OpenWA, resolving the session UUID path marker
        `{uuid}` if present."""
        if "{uuid}" in path:
            uuid = self._resolve_uuid()
            if not uuid:
                return None
            path = path.replace("{uuid}", uuid)
        url = f"{self.base_url}/api{path}"
        try:
            return self._session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.Timeout:
            logger.error(f"Timeout hitting {url}")
            return None
        except requests.ConnectionError as e:
            logger.error(f"Connection error hitting {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error hitting {url}: {e}")
            return None

    # ------------------------------------------------------------------
    # Interface (must match EvolutionClient)
    # ------------------------------------------------------------------
    def _check_connection(self) -> bool:
        """Check if OpenWA server is reachable (no auth/IP dependency on the
        session itself)."""
        try:
            r = self._session.get(
                f"{self.base_url}/api/sessions",
                timeout=10
            )
            return r.status_code == 200
        except Exception:
            return False

    def check_qr_status(self) -> Dict:
        """Check QR code / connection status."""
        try:
            r = self._session.get(
                f"{self.base_url}/api/sessions",
                timeout=10
            )
            if r.status_code == 200:
                sessions = r.json()
                for s in sessions or []:
                    if s.get("name") == self.instance:
                        status = s.get("status", "unknown")
                        return {
                            "connected": status == "connected",
                            "state": status,
                            "qrcode": status in ("qr_ready", "initializing", "disconnected"),
                            "raw": s
                        }
                return {"connected": False, "state": "not_found", "qrcode": False}
            return {"connected": False, "state": "error", "qrcode": False}
        except Exception as e:
            return {"connected": False, "state": "error", "qrcode": False, "error": str(e)}

    def get_qr_code(self) -> Optional[str]:
        """Get QR code base64 string for scanning (if available)."""
        uuid = self._resolve_uuid()
        if not uuid:
            return None
        try:
            r = self._session.get(
                f"{self.base_url}/api/sessions/{uuid}/qr",
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                # OpenWA returns base64 in various keys depending on version
                return data.get("base64") or data.get("qr") or data.get("image")
            return None
        except Exception as e:
            logger.error(f"Error getting QR: {e}")
            return None

    def format_phone(self, numero: str) -> str:
        """Format phone number to WhatsApp JID format (@c.us).

        Same logic as EvolutionClient for consistency.
        """
        num = str(numero).replace("+", "").replace(" ", "").replace("-", "").strip()
        if len(num) == 9 and num.startswith("9"):
            num = "56" + num
        elif len(num) == 8:
            num = "56" + num
        elif len(num) >= 10 and not num.startswith("56"):
            pass
        return f"{num}@c.us"

    def send_message(self, numero: str, mensaje: str) -> Tuple[bool, str]:
        """Send a text message via OpenWA."""
        jid = self.format_phone(numero)
        chat_id = jid.replace("@c.us.", "@c.us")  # safety
        print(f"[SEND] safe_mode={self.safe_mode}, numero={numero} -> chatId={chat_id}",
              flush=True)
        logger.info(f"[SEND] safe_mode={self.safe_mode}, numero={numero} -> chatId={chat_id}")

        if self.safe_mode:
            logger.info(f"[SAFE_MODE] Would send to {chat_id}: {mensaje[:80]}...")
            print(f"[SAFE_MODE] Would send to {chat_id}: {mensaje[:80]}...", flush=True)
            return True, f"[SAFE_MODE] Mensaje registrado (no enviado): {chat_id}"

        uuid = self._resolve_uuid()
        if not uuid:
            print(f"[SEND] FAILED: session '{self.instance}' not found on OpenWA", flush=True)
            return False, f"Error: sesión '{self.instance}' no encontrada en OpenWA"

        payload = {"chatId": chat_id, "text": mensaje}
        url = f"{self.base_url}/api/sessions/{uuid}/messages/send-text"
        print(f"[SEND] Calling POST {url} chatId={chat_id} text_len={len(mensaje)}",
              flush=True)

        try:
            r = self._session.post(url, json=payload, timeout=self.timeout)
            print(f"[SEND] Response: {r.status_code} {r.text[:300]}", flush=True)

            if r.status_code in (200, 201):
                logger.info(f"Message sent to {chat_id}")
                print(f"[SEND] SUCCESS: Message sent to {chat_id}", flush=True)
                return True, "Enviado OK"
            else:
                error_msg = r.text[:300]
                logger.error(f"Send failed ({r.status_code}): {error_msg}")
                print(f"[SEND] FAILED: {r.status_code} {error_msg}", flush=True)
                return False, f"Error HTTP {r.status_code}: {error_msg}"
        except requests.Timeout:
            print(f"[SEND] TIMEOUT after {self.timeout}s", flush=True)
            return False, "Timeout: OpenWA no respondió"
        except requests.ConnectionError as e:
            print(f"[SEND] CONNECTION ERROR: {e}", flush=True)
            return False, "Error de conexión: No se puede alcanzar OpenWA"
        except Exception as e:
            print(f"[SEND] EXCEPTION: {type(e).__name__}: {e}", flush=True)
            return False, f"Error: {str(e)}"

    def get_last_incoming_message(self, numero: str) -> Optional[Dict]:
        """Get the last incoming message from a specific chat.

        Returns dict with keys: body, timestamp, fromMe, sender or None.
        """
        chat_id = self.format_phone(numero)
        uuid = self._resolve_uuid()
        if not uuid:
            return None

        try:
            r = self._session.get(
                f"{self.base_url}/api/sessions/{uuid}/chats/{chat_id}/messages",
                params={"limit": 10},
                timeout=self.timeout
            )
            if r.status_code != 200:
                return None
            data = r.json()
            messages = data.get("messages", []) if isinstance(data, dict) else (data or [])

            for msg in reversed(messages):
                if not msg.get("fromMe", False):
                    return {
                        "body": msg.get("body") or msg.get("text") or "",
                        "timestamp": msg.get("timestamp") or msg.get("messageTimestamp", ""),
                        "fromMe": False,
                        "sender": msg.get("sender") or msg.get("remoteJid", chat_id),
                        "raw": msg
                    }
            return None
        except Exception as e:
            logger.error(f"Error fetching messages for {chat_id}: {e}")
            return None

    def verificar_respuesta(self, numero: str, keywords_si: List[str] = None,
                            keywords_no: List[str] = None) -> Tuple[str, str]:
        """Verify patient response by fetching last message and classifying.
        Same behaviour as EvolutionClient. Uses the keyword lists
        (defaults imported from evolution_client's DEFAULT_RESPUESTAS_*)."""
        import re

        if keywords_si is None:
            from evolution_client import DEFAULT_RESPUESTAS_SI
            keywords_si = DEFAULT_RESPUESTAS_SI
        if keywords_no is None:
            from evolution_client import DEFAULT_RESPUESTAS_NO
            keywords_no = DEFAULT_RESPUESTAS_NO

        last_msg = self.get_last_incoming_message(numero)
        if not last_msg:
            return "PENDIENTE", "No hay mensajes del paciente"

        body = last_msg.get("body", "").strip()
        if not body:
            return "PENDIENTE", "Último mensaje vacío"

        msg_clean = body.lower()

        for frase in keywords_no:
            frase_clean = frase.lower()
            prefix = r'\b' if re.match(r'^\w', frase_clean) else r''
            suffix = r'\b' if re.search(r'\w$', frase_clean) else r''
            pattern = prefix + re.escape(frase_clean) + suffix
            if re.search(pattern, msg_clean):
                return "NO ASISTIRA", f"{body} (Match: {frase})"

        for frase in keywords_si:
            frase_clean = frase.lower()
            prefix = r'\b' if re.match(r'^\w', frase_clean) else r''
            suffix = r'\b' if re.search(r'\w$', frase_clean) else r''
            pattern = prefix + re.escape(frase_clean) + suffix
            if re.search(pattern, msg_clean):
                return "CONFIRMADO", f"{body} (Match: {frase})"

        return "AMBIGUO", f"No clasificado: {body}"

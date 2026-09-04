"""
Evolution API Client for Medtify V15
=====================================
Replaces Selenium/ChromeDriver with direct HTTP calls to Evolution API server.

Usage:
    client = EvolutionClient("http://your-server:8080", "your-api-key", "medtify")
    client.send_message("+56912345678", "Hola paciente")
    last_msg = client.get_last_incoming_message("+56912345678")
"""

import time
import random
import logging
import requests
from typing import Optional, Tuple, Dict, List

logger = logging.getLogger("evolution_client")


class EvolutionClient:
    """HTTP client for Evolution API v2."""

    def __init__(self, base_url: str, api_key: str, instance: str = "medtify",
                 timeout: int = 30, safe_mode: bool = False):
        """
        Args:
            base_url: Evolution API server URL (e.g. http://your-server:8080)
            api_key: Authentication API key
            instance: Instance name (default: medtify)
            timeout: HTTP request timeout in seconds
            safe_mode: If True, logs messages but doesn't send them
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.instance = instance
        self.timeout = timeout
        # If safe_mode is None or not set, default to False (send real messages)
        if safe_mode is None:
            safe_mode = False
        self.safe_mode = safe_mode
        self._session = requests.Session()
        self._session.headers.update({
            "apikey": self.api_key,
            "Content-Type": "application/json",
        })

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path}"

    def _check_connection(self) -> bool:
        """Check if Evolution API server is reachable and instance exists."""
        try:
            r = self._session.get(
                f"{self.base_url}/instance/fetchInstances",
                timeout=10
            )
            if r.status_code == 200:
                instances = r.json()
                logger.info(f"[DEBUG _check_connection] Raw response: {instances}")
                if not instances:
                    logger.warning("Instance list is empty")
                    return False
                for inst in instances:
                    # Evolution API v2.x returns flat objects:
                    # [{"id":..., "name":"medtify", "connectionStatus":"open", ...}]
                    # Also handle legacy format: {"instance":{"instanceName":"medtify"}}
                    inst_name = (
                        inst.get("name") or
                        inst.get("instance", {}).get("instanceName") or
                        ""
                    )
                    if inst_name == self.instance:
                        return True
                logger.warning(f"Instance '{self.instance}' not found in server. Found: {[inst.get('name') for inst in instances]}")
                return False
            return False
        except Exception as e:
            logger.error(f"Cannot reach Evolution API: {e}")
            return False

    def check_qr_status(self) -> Dict:
        """
        Check QR code / connection status.
        Returns dict with status info.
        """
        try:
            r = self._session.get(
                f"{self.base_url}/instance/connectionState/{self.instance}",
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                # Handle both response formats:
                # Format 1: {"instance":{"instanceName":"medtify","state":"open"}}
                # Format 2: {"state":{"state":"open"}}
                state = "unknown"
                if "instance" in data and isinstance(data["instance"], dict):
                    state = data["instance"].get("state", "unknown")
                elif "state" in data and isinstance(data["state"], dict):
                    state = data["state"].get("state", "unknown")
                elif "state" in data and isinstance(data["state"], str):
                    state = data["state"]
                
                return {
                    "connected": state == "open",
                    "state": state,
                    "qrcode": state == "close",
                    "raw": data
                }
            return {"connected": False, "state": "error", "qrcode": False}
        except Exception as e:
            return {"connected": False, "state": "error", "qrcode": False, "error": str(e)}

    def get_qr_code(self) -> Optional[str]:
        """
        Get QR code base64 string for scanning.
        Returns base64 image string or None.
        """
        try:
            r = self._session.get(
                f"{self.base_url}/instance/connect/{self.instance}",
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                return data.get("base64", None)
            return None
        except Exception as e:
            logger.error(f"Error getting QR: {e}")
            return None

    def format_phone(self, numero: str) -> str:
        """
        Format phone number to WhatsApp JID format.
        Chilean numbers: 9XXXXXXXX -> 569XXXXXXXX@c.us
        International: keeps as is with @c.us
        """
        num = str(numero).replace("+", "").replace(" ", "").replace("-", "").strip()
        # Chilean mobile: 9 digits starting with 9
        if len(num) == 9 and num.startswith("9"):
            num = "56" + num
        # Chilean landline: 8 digits
        elif len(num) == 8:
            num = "56" + num
        # Already has country code
        elif len(num) >= 10 and not num.startswith("56"):
            pass  # keep as is

        return f"{num}@c.us"

    def send_message(self, numero: str, mensaje: str) -> Tuple[bool, str]:
        """
        Send a text message via Evolution API.

        Args:
            numero: Phone number (raw, will be formatted)
            mensaje: Message text

        Returns:
            (success, log_message)
        """
        jid = self.format_phone(numero)

        if self.safe_mode:
            logger.info(f"[SAFE_MODE] Would send to {jid}: {mensaje[:80]}...")
            return True, f"[SAFE_MODE] Mensaje registrado (no enviado): {jid}"

        try:
            payload = {
                "number": jid,
                "text": mensaje,
                "delay": random.randint(1200, 3000),  # Simulate typing delay (ms)
            }

            r = self._session.post(
                f"{self.base_url}/message/sendText/{self.instance}",
                json=payload,
                timeout=self.timeout
            )

            if r.status_code in (200, 201):
                logger.info(f"Message sent to {jid}")
                return True, "Enviado OK"
            else:
                error_msg = r.text[:200]
                logger.error(f"Send failed ({r.status_code}): {error_msg}")
                return False, f"Error HTTP {r.status_code}: {error_msg}"

        except requests.Timeout:
            return False, "Timeout: Evolution API no respondió"
        except requests.ConnectionError:
            return False, "Error de conexión: No se puede alcanzar Evolution API"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def get_last_incoming_message(self, numero: str) -> Optional[Dict]:
        """
        Get the last incoming message from a specific chat.

        Returns:
            Dict with keys: body, timestamp, fromMe, sender
            or None if no messages found
        """
        jid = self.format_phone(numero)

        try:
            r = self._session.get(
                f"{self.base_url}/chat/findMessages/{self.instance}",
                json={
                    "where": {
                        "key": {
                            "remoteJid": jid,
                            "fromMe": False
                        }
                    },
                    "limit": 5,
                    "order": "DESC"
                },
                timeout=self.timeout
            )

            if r.status_code == 200:
                messages = r.json()
                if messages and len(messages) > 0:
                    msg = messages[0]
                    key = msg.get("key", {})
                    message_data = msg.get("message", {})

                    # Extract text content
                    body = message_data.get("conversation", "")
                    if not body:
                        body = message_data.get("extendedTextMessage", {}).get("text", "")

                    return {
                        "body": body,
                        "timestamp": msg.get("messageTimestamp", ""),
                        "fromMe": key.get("fromMe", False),
                        "sender": key.get("participant", jid),
                        "raw": msg
                    }
            return None

        except Exception as e:
            logger.error(f"Error fetching messages for {jid}: {e}")
            return None

    def verificar_respuesta(self, numero: str, keywords_si: List[str] = None,
                            keywords_no: List[str] = None) -> Tuple[str, str]:
        """
        Verify patient response by fetching last message and classifying it.

        Args:
            numero: Phone number
            keywords_si: List of confirmation keywords
            keywords_no: List of rejection keywords

        Returns:
            (estado, detalle) where estado is CONFIRMADO, NO ASISTIRA, or AMBIGUO
        """
        import re

        if keywords_si is None:
            keywords_si = DEFAULT_RESPUESTAS_SI
        if keywords_no is None:
            keywords_no = DEFAULT_RESPUESTAS_NO

        last_msg = self.get_last_incoming_message(numero)

        if not last_msg:
            return "PENDIENTE", "No hay mensajes del paciente"

        body = last_msg.get("body", "").strip()
        if not body:
            return "PENDIENTE", "Último mensaje vacío"

        msg_clean = body.lower()

        # 1. Check negations (priority)
        for frase in keywords_no:
            frase_clean = frase.lower()
            prefix = r'\b' if re.match(r'^\w', frase_clean) else r''
            suffix = r'\b' if re.search(r'\w$', frase_clean) else r''
            pattern = prefix + re.escape(frase_clean) + suffix
            if re.search(pattern, msg_clean):
                return "NO ASISTIRA", f"{body} (Match: {frase})"

        # 2. Check confirmations
        for frase in keywords_si:
            frase_clean = frase.lower()
            prefix = r'\b' if re.match(r'^\w', frase_clean) else r''
            suffix = r'\b' if re.search(r'\w$', frase_clean) else r''
            pattern = prefix + re.escape(frase_clean) + suffix
            if re.search(pattern, msg_clean):
                return "CONFIRMADO", f"{body} (Match: {frase})"

        # 3. Unclassified
        return "AMBIGUO", f"No clasificado: {body}"


# === DEFAULT KEYWORDS (same as medtify_app.py) ===
DEFAULT_RESPUESTAS_SI = [
    "sí", "si", "sip", "sii", "siii", "sipo", "sipu", "sipi", "sí, confirmo", "confirmo",
    "confirmado", "confirmada", "confirmadísimo", "claro", "claro que sí",
    "por supuesto", "obvio", "obvio que sí", "obvio po", "obvio que voy",
    "de todas maneras", "de todas formas", "de una", "de pana",
    "altiro", "altiro sí", "altiro voy", "bacán", "bacán voy",
    "filete", "la raja voy", "pulento", "terrible sí", "ahí estaré",
    "voy", "voy sí", "sí voy", "sí puedo", "puedo ir",
    "confirmo asistencia", "confirmo la hora", "confirmo cita", "asistiré", "llego",
    "llegaré", "cuento con ir", "ningún problema", "ningún drama",
    "todo bien", "todo ok", "ok", "okay", "okey", "oki", "okis",
    "dale sí", "dale no más", "vale", "vale sí", "va", "vamos",
    "yes", "simon", "afirmativo", "positivo", "sí, sin falta", "sí, estaré ahí",
    "me sirve", "me acomoda", "está bien", "está perfect", "perfecto",
    "excelente", "súper", "joya", "regio",
    "ya", "ya sí", "ya voy", "ya confirmo", "ya estaré", "listo",
    "listo confirmo", "todo listo", "listo voy",
    "simonazo", "seeh", "seee", "seeeh",
    "vamos pa' esa", "vamos nomás", "vamo'",
    "✔️", "👍", "👌", "🙌", "🤙", "💯", "🔥 voy", "✨ sí"
]

DEFAULT_RESPUESTAS_NO = [
    "no", "nop", "nope", "nah", "nada", "para nada", "en absoluto",
    "no puedo", "no voy", "no asistiré", "no me es posible",
    "cancelo", "cancelada", "cancelado", "anular", "anulada",
    "rechazar", "rechazado", "rechazada",
    "mejor no", "prefiero no", "no me conviene", "no me sirve",
    "otra vez no", "lástima", "qué pena", "qué lástima",
    "no alcanzo", "no me da el tiempo", "estoy ocupado", "estoy ocupada",
    "tengo otra cosa", "tengo otro compromiso", "no dispongo",
    "imposible", "no hay chance", "no da", "se me complica",
    "no creo", "dudo que pueda", "difícil",
    "😔", "😞", "😢", "❌", "🚫",
    "gracias pero no", "agradezco pero no",
]

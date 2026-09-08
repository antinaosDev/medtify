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
        # Evolution API v2 expects PLAIN number (e.g. 56963369748), NOT JID format
        plain_number = jid.replace("@c.us", "")
        print(f"[SEND] safe_mode={self.safe_mode}, numero={numero} -> plain={plain_number}", flush=True)
        logger.info(f"[SEND] safe_mode={self.safe_mode}, numero={numero} -> plain={plain_number}")

        if self.safe_mode:
            logger.info(f"[SAFE_MODE] Would send to {plain_number}: {mensaje[:80]}...")
            print(f"[SAFE_MODE] Would send to {plain_number}: {mensaje[:80]}...", flush=True)
            return True, f"[SAFE_MODE] Mensaje registrado (no enviado): {plain_number}"

        try:
            payload = {
                "number": plain_number,
                "text": mensaje,
                "delay": random.randint(1200, 3000),  # Simulate typing delay (ms)
            }

            url = f"{self.base_url}/message/sendText/{self.instance}"
            print(f"[SEND] Calling POST {url} number={plain_number} text_len={len(mensaje)}", flush=True)
            print(f"[SEND] Payload: number={plain_number}, delay={payload['delay']}", flush=True)
            r = self._session.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            print(f"[SEND] Response: {r.status_code} {r.text[:300]}", flush=True)

            if r.status_code in (200, 201):
                logger.info(f"Message sent to {plain_number}")
                print(f"[SEND] SUCCESS: Message sent to {plain_number}", flush=True)
                return True, "Enviado OK"
            else:
                error_msg = r.text[:300]
                logger.error(f"Send failed ({r.status_code}): {error_msg}")
                print(f"[SEND] FAILED: {r.status_code} {error_msg}", flush=True)
                return False, f"Error HTTP {r.status_code}: {error_msg}"

        except requests.Timeout:
            print(f"[SEND] TIMEOUT after {self.timeout}s", flush=True)
            return False, "Timeout: Evolution API no respondió"
        except requests.ConnectionError as e:
            print(f"[SEND] CONNECTION ERROR: {e}", flush=True)
            return False, "Error de conexión: No se puede alcanzar Evolution API"
        except Exception as e:
            print(f"[SEND] EXCEPTION: {type(e).__name__}: {e}", flush=True)
            return False, f"Error: {str(e)}"

    def get_last_incoming_message(self, numero: str) -> Optional[Dict]:
        """
        Get the last incoming message from a specific chat.

        Returns:
            Dict with keys: body, timestamp, fromMe, sender
            or None if no messages found
        """
        jid = self.format_phone(numero)
        plain = jid.replace("@c.us", "")
        jid_sw = f"{plain}@s.whatsapp.net"

        try:
            def _find(where: dict) -> list:
                try:
                    r = self._session.post(
                        f"{self.base_url}/chat/findMessages/{self.instance}",
                        json={
                            "where": where,
                            "limit": 50,
                            "offset": 0,
                            "order": "DESC"
                        },
                        timeout=self.timeout
                    )
                    print(f"[READ] POST findMessages http={r.status_code}", flush=True)
                    if r.status_code != 200:
                        print(f"[READ] body={r.text[:200]}", flush=True)
                        return []
                    data = r.json()
                    recs = (data or {}).get("messages", {}).get("records", [])
                    total = (data or {}).get("messages", {}).get("total", 0)
                    print(f"[READ] records={len(recs)} total={total}", flush=True)
                    return recs
                except Exception as e:
                    logger.error(f"Error in _find for {jid_sw}: {e}")
                    print(f"[READ] EXCEPTION: {e}", flush=True)
                    return []

            candidates = _find({"key": {"remoteJidAlt": jid_sw}})
            if not candidates:
                candidates = _find({"key": {"remoteJid": jid_sw}})

            for msg in candidates:
                key = msg.get("key", {}) or {}
                if key.get("fromMe"):
                    continue
                message_data = msg.get("message", {}) or {}

                body = ""
                if isinstance(message_data, dict):
                    body = message_data.get("conversation", "") or ""
                    if not body:
                        etm = message_data.get("extendedTextMessage") or {}
                        body = etm.get("text", "") or ""
                    if not body:
                        img = message_data.get("imageMessage") or {}
                        body = img.get("caption", "") or ""
                if not body:
                    continue

                return {
                    "body": body,
                    "timestamp": msg.get("messageTimestamp", ""),
                    "fromMe": False,
                    "sender": key.get("participant") or key.get("remoteJid") or jid,
                    "raw": msg
                }

            print(f"[READ] No incoming messages found for {jid_sw}", flush=True)
            return None

        except Exception as e:
            logger.error(f"Error fetching messages for {jid_sw}: {e}")
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

        # STEP 0 (v14 parity): si el último mensaje es notificación del bot → PENDIENTE
        if es_notificacion(body):
            return "PENDIENTE", "Ultimo mensaje es notificacion del bot, paciente aun no responde"

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


# === DEFAULT KEYWORDS (sincronizadas con master medtify_app_v15.py / v14) ===
DEFAULT_RESPUESTAS_SI = [
    "sí", "si", "sip", "sii", "siii", "sipo", "sipu", "sipi", "sí, confirmo", "confirmo",
    "confirmado", "confirmada", "confirmadísimo", "confirmadísima", "claro", "claro que sí",
    "por supuesto", "obvio", "obvio que sí", "obviao", "obvio po", "obvio que voy",
    "obvio hermano voy", "de todas maneras", "de todas formas", "de una", "de pana",
    "de pana sí", "de pana voy", "altiro", "altiro sí", "altiro voy", "bacán", "bacán voy",
    "filete", "la raja voy", "pulento", "terrible sí", "terrible filete voy", "ahí estaré",
    "voy", "voy sí", "sí voy", "sí voy a ir", "sí alcanzo", "sí puedo", "puedo ir",
    "confirmo asistencia", "confirmo la hora", "confirmo cita", "asistiré", "llego",
    "llego sí", "llegaré", "cuento con ir", "cualquier cosa llego", "ningún problema",
    "ningún drama", "todo bien", "todo ok", "ok", "okay", "okey", "oki", "okis",
    "dale sí", "dale no más", "vale", "vale sí", "va", "vamos", "yes", "yes bro",
    "simon", "affirmative", "afirmativo", "positivo", "sí, sin falta", "sí, estaré ahí",
    "me sirve", "me acomoda", "está bien", "está perfect", "perfect", "perfecto",
    "excelente", "súper", "super bien", "joya", "joyita", "regio", "maravilloso",
    "ya", "ya sí", "ya bacán", "ya voy", "ya confirmo", "ya estaré", "listo", "lito",
    "listo confirmo", "listoco", "todo listo", "listo entonces", "listo voy",
    "confirmadito", "simonazo", "seeh", "seee", "seeeh", "sehhh", "seee si",
    "vamos pa’ esa", "vamos nomás", "vamo’", "vamo altiro", "✔️", "👍", "👌", "🙌",
    "🤙", "💯", "🔥 voy", "🍀 voy", "✨ sí"
]

DEFAULT_RESPUESTAS_NO = [
    "no", "nop", "nope", "noo", "nooo", "noppo", "nopo", "no puedo", "no puedo ir",
    "no voy", "no alcanzo", "no me da", "no me da el tiempo", "no me sirve",
    "no me acomoda", "no estoy disponible", "no podré asistir", "no asistiré", "no iré",
    "no llego", "no estaré", "no me es posible", "me es imposible", "imposible",
    "negativo", "lamentablemente no puedo", "tengo que cancelar", "cancelo", "cancelado",
    "cancelada", "cancelar hora", "cancelar asistencia", "reagendar", "quiero reagendar",
    "necesito reagendar", "necesito otra hora", "cambiar hora", "no puedo a esa hora",
    "no puedo ese día", "no puedo no más", "no me tinca", "no me resulta",
    "hoy no me resulta", "no puedo sorry", "sorry no puedo", "no sorry", "no quiero ir",
    "prefiero no ir", "voy a faltar", "estoy ocupado", "estoy tapado de cosas",
    "estoy enfermo", "estoy enferma", "estoy pal gato", "estoy pa’ la cagá",
    "no tengo tiempo", "no llego ni cagando", "no alcanzo ni al metro", "no será posible",
    "no cacho si pueda", "no estoy en condiciones", "no doy más", "no puedo manejar",
    "mi pega no me deja", "tengo reunión", "no la hago", "no me da la agenda",
    "no lo lograré", "🚫", "❌", "🛑", "🙅", "🙅‍♂️", "🙅‍♀️"
]


# === MARKERS DE NOTIFICACIÓN DEL BOT (port desde medtify_app_rotacion.py v14) ===
NOTIF_MARKERS = [
    # Titulos de recordatorio
    'recordatorio hora medica',
    'aviso de hora medica',
    'informacion de hora medica',
    'informa cancelacion',
    'aviso de cancelacion',
    'informa hora medica cancelada',
    'hora medica cancelada',

    # Frases de introduccion
    'le recordamos su',
    'no olvide su hora agendada',
    'le enviamos los detalles',
    'su proxima atencion de salud',
    'lamentamos informarle',
    'por razones de fuerza mayor',
    'le comunicamos que',
    'su hora medica ha sido cancelada',

    # Datos de la cita
    'su cita es el',
    'su hora es el',
    'su turno es el',
    'fecha:', 'hora:', 'profesional:', 'motivo consulta:', 'lugar:',

    # Confirmacion
    'para confirmar su asistencia, responda',
    'responda con "si" para confirmar',
    'confirme su asistencia respondiendo',
    'para confirmar su nueva hora',

    # Importante / instrucciones
    'importante: llegar 15 minutos',
    'presentar su cedula de identidad',
    'presentar su carnet de control',
    'carnet de control de paciente cronico',
    'llegar 15 minutos antes',
    'presentar su',
    'horario de atencion',

    # Despedida
    'saluda atentamente',
    'saludos cordiales',
    'se despide,',
    'equipo some',
    'cesfam cholchol',

    # Mensaje automatico
    'este es un mensaje automatico',
    'este es un mensaje automático',
    'mensaje automatico. si necesitas',
    'visita nuestras dependencias',

    # Reagendamiento especifico
    'hora cancelada:',
    'nueva hora reagendada:',
    'agradecemos su comprension',
    'lamentamos los inconvenientes',
    'pedimos disculpas por las molestias',
    'nueva hora reagendada',
]


def es_notificacion(texto):
    """Requiere 2+ markers O >200 chars con 1 marker para clasificar como notificacion (port v14)."""
    t = texto.lower().strip()
    matches = sum(1 for pat in NOTIF_MARKERS if pat in t)
    if matches >= 2:
        print(f"  -> NOTIFICATION ({matches} markers): {t[:60]}...", flush=True)
        return True
    if len(t) > 200 and matches >= 1:
        print(f"  -> NOTIFICATION (long + {matches} marker): {t[:60]}...", flush=True)
        return True
    print(f"  -> NOT notification ({matches} markers, {len(t)} chars): {t[:60]}...", flush=True)
    return False

"""
chat_helpers.py — Helper functions for Medtify V15 WhatsApp Chat feature.
No Streamlit dependency (testable with plain unittest).
"""

import re
from datetime import datetime


def normalizar_telefono_chat(numero):
    """
    Normalize a Chilean phone number to format 569XXXXXXXX (11 digits).
    
    Accepts: +56 9 1234 5678, 0912345678, 56912345678, etc.
    Returns: '56912345678'
    Raises: ValueError if the result doesn't have valid digits.
    """
    if not numero:
        raise ValueError("Telefono vacio")
    num = re.sub(r'[^0-9]', '', str(numero).strip())
    if not num:
        raise ValueError("Telefono sin digitos")
    # Remove leading zeros
    num = num.lstrip('0')
    # Remove +56 or 56 country code
    if num.startswith('56') and len(num) >= 11:
        num = num[2:]
    # Now should be 9 digits starting with 9 (Chilean mobile)
    if len(num) == 9 and num.startswith('9'):
        return f"56{num}"
    # If it's 8 digits (landline), add 56 prefix
    if len(num) == 8:
        return f"56{num}"
    raise ValueError(f"Telefono invalido: {numero} -> quedo {num}")


def make_jid(numero):
    """
    Convert a normalized phone number to WhatsApp JID format.
    Input: '56912345678' -> Output: '56912345678@s.whatsapp.net'
    """
    num = normalizar_telefono_chat(numero)
    return f"{num}@s.whatsapp.net"


def build_pacientes_chat_index(df_base):
    """
    Build a lookup index from the Base de Pacientes DataFrame.
    
    Uses columns: TELEFONO, NOMBRE_PACIENTE, RUT, PROFESION, FECHA_AGENDADA, HORA_AGENDADA
    
    Returns: dict {jid: {"nombre": str, "rut": str, "pol": str, "etiqueta": str, "telefono": str}}
    """
    index = {}
    if df_base is None or df_base.empty:
        return index
    
    for _, row in df_base.iterrows():
        tel = str(row.get("TELEFONO", "")).strip()
        if not tel or tel == "nan":
            continue
        try:
            jid = make_jid(tel)
        except (ValueError, TypeError):
            continue
        
        nombre = str(row.get("NOMBRE_PACIENTE", "")).strip()
        rut = str(row.get("RUT", "")).strip()
        pol = str(row.get("PROFESION", "")).strip()
        fecha = str(row.get("FECHA_AGENDADA", "")).strip()
        hora = str(row.get("HORA_AGENDADA", "")).strip()
        
        etiqueta = ""
        if pol and pol != "nan":
            etiqueta = pol
        if fecha and fecha != "nan" and hora and hora != "nan":
            etiqueta = f"{etiqueta} | {fecha} {hora}".strip(" |")
        
        index[jid] = {
            "nombre": nombre if nombre != "nan" else "",
            "rut": rut if rut != "nan" else "",
            "pol": pol if pol != "nan" else "",
            "etiqueta": etiqueta,
            "telefono": tel,
        }
    
    return index


def formatear_hora_mensaje(timestamp):
    """
    Format a WhatsApp message timestamp to a human-readable time string.
    
    Accepts: int (unix timestamp), str (iso format), or datetime.
    Returns: 'HH:MM' if today, 'DD/MM HH:MM' otherwise.
    """
    if isinstance(timestamp, (int, float)):
        dt = datetime.fromtimestamp(timestamp)
    elif isinstance(timestamp, str):
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return timestamp[:16] if len(timestamp) >= 16 else str(timestamp)
    elif isinstance(timestamp, datetime):
        dt = timestamp
    else:
        return str(timestamp)
    
    now = datetime.now()
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    return dt.strftime("%d/%m %H:%M")


def build_autorizados_chat_index(df_base, col_estado="ESTADO", valor_ok="NOTIFICADO OK"):
    """
    Build a lookup index de USUARIOS AUTORIZADOS desde la hoja propia de la cuenta (URL_SHEET).

    SOLO incluye filas donde la columna ESTADO == 'NOTIFICADO OK'.
    Misma extracción que build_pacientes_chat_index (jid, nombre, rut, pol, etiqueta, telefono),
    pero NUNCA fusiona con la base completa: el universo de la bandeja es exclusivamente
    los números autorizados.

    Returns: dict {jid: {"nombre", "rut", "pol", "etiqueta", "telefono"}}
    """
    index = {}
    if df_base is None or df_base.empty:
        return index

    # Normalizar nombre de columna (trim) por si viene como "ESTADO "
    cols = {str(c).strip(): c for c in df_base.columns}
    col_estado_real = cols.get(col_estado)
    col_tel = cols.get("TELEFONO", "TELEFONO")
    if col_tel not in df_base.columns:
        col_tel = "TELEFONO"

    for _, row in df_base.iterrows():
        # Filtro ESTADO == NOTIFICADO OK (trim por robustez)
        estado = str(row.get(col_estado_real, "") if col_estado_real else row.get(col_estado, "")).strip()
        if estado != valor_ok:
            continue

        tel = str(row.get(col_tel, "")).strip()
        if not tel or tel == "nan":
            continue
        try:
            jid = make_jid(tel)
        except (ValueError, TypeError):
            continue

        nombre = str(row.get(cols.get("NOMBRE_PACIENTE", "NOMBRE_PACIENTE"), "")).strip()
        rut = str(row.get(cols.get("RUT", "RUT"), "")).strip()
        pol = str(row.get(cols.get("PROFESION", "PROFESION"), "")).strip()
        fecha = str(row.get(cols.get("FECHA_AGENDADA", "FECHA_AGENDADA"), "")).strip()
        hora = str(row.get(cols.get("HORA_AGENDADA", "HORA_AGENDADA"), "")).strip()

        etiqueta = ""
        if pol and pol != "nan":
            etiqueta = pol
        if fecha and fecha != "nan" and hora and hora != "nan":
            etiqueta = f"{etiqueta} | {fecha} {hora}".strip(" |")

        index[jid] = {
            "nombre": nombre if nombre != "nan" else "",
            "rut": rut if rut != "nan" else "",
            "pol": pol if pol != "nan" else "",
            "etiqueta": etiqueta,
            "telefono": tel,
        }

    return index


def ordenar_chats_por_ultimo_mensaje(chats_pacientes, reverse=True):
    """
    Ordena la lista de chats de la bandeja por el timestamp del último mensaje recibido,
    del más reciente al más antiguo (reverse=True).

    Cada chat DEBE traer la llave "ts_chat" (unix timestamp del último mensaje).
    Si falta, se usa 0 (va al final). No muta la lista original.
    """
    if not chats_pacientes:
        return []
    return sorted(
        chats_pacientes,
        key=lambda c: int(c.get("ts_chat", 0) or 0),
        reverse=reverse
    )

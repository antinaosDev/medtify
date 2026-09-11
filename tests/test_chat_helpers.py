"""
Tests for chat_helpers.py — Medtify V15 WhatsApp Chat feature.
Run: venv/bin/python -m unittest tests.test_chat_helpers -v
"""

import unittest
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chat_helpers import (
    normalizar_telefono_chat,
    make_jid,
    build_pacientes_chat_index,
    formatear_hora_mensaje
)


class TestNormalizarTelefonoChat(unittest.TestCase):
    """Tests for normalizar_telefono_chat."""

    def test_con_codigo_pais(self):
        self.assertEqual(normalizar_telefono_chat("+56 9 1234 5678"), "56912345678")

    def test_formato_569(self):
        self.assertEqual(normalizar_telefono_chat("56912345678"), "56912345678")

    def test_formato_09(self):
        self.assertEqual(normalizar_telefono_chat("0912345678"), "56912345678")

    def test_formato_9digitos(self):
        self.assertEqual(normalizar_telefono_chat("912345678"), "56912345678")

    def test_con_guiones(self):
        self.assertEqual(normalizar_telefono_chat("+56 9 1234-5678"), "56912345678")

    def test_numero_largo(self):
        self.assertEqual(normalizar_telefono_chat("56963369748"), "56963369748")

    def test_numero_sin_espacios(self):
        self.assertEqual(normalizar_telefono_chat("56911111111"), "56911111111")

    def test_numero_invalido_corto(self):
        with self.assertRaises(ValueError):
            normalizar_telefono_chat("123")

    def test_numero_vacio(self):
        with self.assertRaises(ValueError):
            normalizar_telefono_chat("")

    def test_none(self):
        with self.assertRaises(ValueError):
            normalizar_telefono_chat(None)

    def test_solo_letras(self):
        with self.assertRaises(ValueError):
            normalizar_telefono_chat("abc")


class TestMakeJid(unittest.TestCase):
    """Tests for make_jid."""

    def test_jid_format(self):
        self.assertEqual(make_jid("56912345678"), "56912345678@s.whatsapp.net")

    def test_jid_con_codigo_pais(self):
        self.assertEqual(make_jid("+56 9 1234 5678"), "56912345678@s.whatsapp.net")

    def test_jid_09(self):
        self.assertEqual(make_jid("0912345678"), "56912345678@s.whatsapp.net")


class TestBuildPacientesChatIndex(unittest.TestCase):
    """Tests for build_pacientes_chat_index."""

    def _make_df(self, rows):
        """Helper to create a DataFrame with the expected columns."""
        cols = ["TELEFONO", "NOMBRE_PACIENTE", "RUT", "PROFESION", "FECHA_AGENDADA", "HORA_AGENDADA"]
        return pd.DataFrame(rows, columns=cols)

    def test_index_basico(self):
        df = self._make_df([
            ["56912345678", "Juan Perez", "12345678-9", "Medicina General", "10/09/2026", "10:00"],
            ["56987654321", "Maria Lopez", "98765432-1", "Pediatria", "11/09/2026", "14:30"],
        ])
        index = build_pacientes_chat_index(df)
        self.assertEqual(len(index), 2)
        self.assertIn("56912345678@s.whatsapp.net", index)
        self.assertIn("56987654321@s.whatsapp.net", index)
        self.assertEqual(index["56912345678@s.whatsapp.net"]["nombre"], "Juan Perez")
        self.assertEqual(index["56912345678@s.whatsapp.net"]["pol"], "Medicina General")

    def test_etiqueta_con_profesion_y_hora(self):
        df = self._make_df([
            ["56911111111", "Test User", "11111111-1", "Enfermeria", "10/09/2026", "09:00"],
        ])
        index = build_pacientes_chat_index(df)
        info = index["56911111111@s.whatsapp.net"]
        self.assertIn("Enfermeria", info["etiqueta"])
        self.assertIn("10/09/2026", info["etiqueta"])
        self.assertIn("09:00", info["etiqueta"])

    def test_telefono_vacio_se_omite(self):
        df = self._make_df([
            ["", "Sin Telefono", "00000000-0", "Medicina General", "", ""],
            ["56912345678", "Con Telefono", "12345678-9", "Medicina General", "", ""],
        ])
        index = build_pacientes_chat_index(df)
        self.assertEqual(len(index), 1)
        self.assertIn("56912345678@s.whatsapp.net", index)

    def test_df_vacio(self):
        df = self._make_df([])
        index = build_pacientes_chat_index(df)
        self.assertEqual(len(index), 0)

    def test_df_none(self):
        index = build_pacientes_chat_index(None)
        self.assertEqual(len(index), 0)


class TestFormatearHoraMensaje(unittest.TestCase):
    """Tests for formatear_hora_mensaje."""

    def test_timestamp_unix_hoy(self):
        now = datetime.now()
        ts = int(now.timestamp())
        result = formatear_hora_mensaje(ts)
        self.assertEqual(result, now.strftime("%H:%M"))

    def test_timestamp_unix_ayer(self):
        yesterday = datetime.now() - timedelta(days=1)
        ts = int(yesterday.timestamp())
        result = formatear_hora_mensaje(ts)
        self.assertIn(yesterday.strftime("%d/%m"), result)

    def test_string_iso(self):
        result = formatear_hora_mensaje("2026-09-10T14:30:00")
        self.assertIn("14:30", result)

    def test_datetime_obj(self):
        dt = datetime(2026, 9, 10, 8, 15)
        result = formatear_hora_mensaje(dt)
        self.assertIn("08:15", result)

    def test_timestamp_invalido(self):
        result = formatear_hora_mensaje("invalid")
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()

import pytest
import sys
import os

# Додаємо кореневу папку проєкту до шляху пошуку модулів
# Це дозволяє Python бачити папку 'client' як пакет
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.auditor import HardwareAuditor

def test_ram_check_logic():
    # Твій тест логіки Hardware Auditor
    auditor = HardwareAuditor()
    # Приклад: якщо RAM > 8, має бути Ultimate [cite: 78-80]
    # (додай сюди свої ассерти)
    pass
# tests/test_auditor.py — Unit тести для HardwareAuditor
import pytest
import sys
import os

# Додаємо client/ до шляху щоб імпортувати модуль
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))

from auditor import HardwareAuditor


@pytest.fixture
def auditor():
    """Фікстура — створює екземпляр HardwareAuditor для тестів."""
    return HardwareAuditor()


class TestRecommendProfile:
    """Тести для методу recommend_profile()."""

    def test_lite_profile_very_low_ram(self, auditor):
        """4 GB RAM → має рекомендувати Lite."""
        result = auditor.recommend_profile(4.0)
        assert result == "Lite", f"Очікувалось 'Lite', отримано '{result}'"

    def test_lite_profile_boundary(self, auditor):
        """7.9 GB RAM (трохи менше 8) → Lite."""
        result = auditor.recommend_profile(7.9)
        assert result == "Lite"

    def test_ultimate_profile_exactly_8gb(self, auditor):
        """Рівно 8 GB RAM → Ultimate (межа включна)."""
        result = auditor.recommend_profile(8.0)
        assert result == "Ultimate", f"Очікувалось 'Ultimate' при 8GB, отримано '{result}'"

    def test_ultimate_profile_16gb(self, auditor):
        """16 GB RAM → Ultimate."""
        result = auditor.recommend_profile(16.0)
        assert result == "Ultimate"

    def test_ultimate_profile_32gb(self, auditor):
        """32 GB RAM → Ultimate."""
        result = auditor.recommend_profile(32.0)
        assert result == "Ultimate"

    def test_lite_profile_minimum(self, auditor):
        """2 GB RAM (мінімум) → Lite."""
        result = auditor.recommend_profile(2.0)
        assert result == "Lite"

    def test_return_type_is_string(self, auditor):
        """Метод має повертати рядок."""
        result = auditor.recommend_profile(16.0)
        assert isinstance(result, str)

    def test_only_two_possible_values(self, auditor):
        """Результат має бути або 'Lite' або 'Ultimate'."""
        valid_profiles = {"Lite", "Ultimate"}
        for ram in [2, 4, 6, 7.9, 8, 8.1, 16, 32, 64]:
            result = auditor.recommend_profile(ram)
            assert result in valid_profiles, f"Невалідний профіль '{result}' для {ram} GB"


class TestGetHardwareInfo:
    """Тести для методу get_hardware_info()."""

    def test_returns_dict(self, auditor):
        """Метод має повертати словник."""
        result = auditor.get_hardware_info()
        assert isinstance(result, dict)

    def test_has_required_keys(self, auditor):
        """Словник має містити всі необхідні ключі."""
        result = auditor.get_hardware_info()
        required_keys = ["ram_gb", "cpu_name", "cpu_cores_physical",
                         "disk_total_gb", "disk_free_gb", "os_name"]
        for key in required_keys:
            assert key in result, f"Відсутній ключ: '{key}'"

    def test_ram_is_positive(self, auditor):
        """RAM має бути позитивним числом."""
        result = auditor.get_hardware_info()
        assert result["ram_gb"] > 0

    def test_cpu_cores_positive(self, auditor):
        """Кількість ядер CPU має бути >= 1."""
        result = auditor.get_hardware_info()
        assert result["cpu_cores_physical"] >= 1

    def test_disk_values_valid(self, auditor):
        """Вільний диск не може бути більше загального."""
        result = auditor.get_hardware_info()
        assert result["disk_free_gb"] <= result["disk_total_gb"]

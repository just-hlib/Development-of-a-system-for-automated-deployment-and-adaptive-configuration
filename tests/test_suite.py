# tests/test_suite.py
# Run: pytest tests/test_suite.py -v
#
# Coverage:
#   - HardwareAuditor  (unit)
#   - is_app_installed (unit, mocked registry)
#   - save_build / load_build (unit)
#   - ExecutionEngine dry-run (unit)
#   - Full flow: select -> save -> apply dry-run (integration)
#   - Edge cases: bad build file, unknown app ID

from __future__ import annotations

import json
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Path setup: tests/ is inside prod_cloud/, client/ is a sibling
ROOT_DIR   = Path(__file__).parent.parent          # prod_cloud/
CLIENT_DIR = ROOT_DIR / "client"

# Insert both so "from client.X" and bare "from X" both work
if str(ROOT_DIR)   not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(CLIENT_DIR) not in sys.path:
    sys.path.insert(0, str(CLIENT_DIR))

from client.auditor import HardwareAuditor
from client.engine  import (
    ExecutionEngine,
    is_admin,
    is_app_installed,
    load_build,
    save_build,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def tmp_build_path(tmp_path: Path) -> Path:
    return tmp_path / "my_build.json"


@pytest.fixture
def sample_apps() -> list:
    return [
        {"id": "vscode",  "winget_id": "Microsoft.VisualStudioCode"},
        {"id": "git",     "winget_id": "Git.Git"},
        {"id": "chrome",  "winget_id": "Google.Chrome"},
    ]


@pytest.fixture
def sample_build(tmp_build_path: Path, sample_apps: list) -> Path:
    """Write a valid build file and return its path."""
    save_build(
        selected_app_ids=sample_apps,
        hw_profile="Ultimate",
        persona="developer",
        output_path=tmp_build_path,
        powershell_scripts=["apply_dark_theme", "disable_telemetry"],
    )
    return tmp_build_path


# =============================================================================
# UNIT -- HardwareAuditor
# =============================================================================

class TestHardwareAuditor:

    def test_recommend_profile_lite(self):
        """RAM < 8 GB -> Lite."""
        auditor = HardwareAuditor()
        assert auditor.recommend_profile(4.0) == "Lite"
        assert auditor.recommend_profile(7.9) == "Lite"
        assert auditor.recommend_profile(0.5) == "Lite"

    def test_recommend_profile_ultimate(self):
        """RAM >= 8 GB -> Ultimate."""
        auditor = HardwareAuditor()
        assert auditor.recommend_profile(8.0)  == "Ultimate"
        assert auditor.recommend_profile(16.0) == "Ultimate"
        assert auditor.recommend_profile(32.0) == "Ultimate"

    def test_boundary_exactly_8gb(self):
        """Exactly 8 GB is Ultimate (>= threshold, not >)."""
        assert HardwareAuditor().recommend_profile(8.0) == "Ultimate"

    def test_get_hardware_info_has_required_keys(self):
        """get_hardware_info must return all required keys."""
        info = HardwareAuditor().get_hardware_info()
        required = {
            "ram_gb", "ram_used_percent",
            "cpu_name", "cpu_cores_physical", "cpu_cores_logical", "cpu_usage",
            "disk_total_gb", "disk_free_gb", "disk_used_percent", "os_name",
        }
        missing = required - info.keys()
        assert not missing, f"Missing keys in hardware info: {missing}"

    def test_get_hardware_info_correct_types(self):
        info = HardwareAuditor().get_hardware_info()
        assert isinstance(info["ram_gb"],             float)
        assert isinstance(info["cpu_cores_physical"],  int)
        assert isinstance(info["disk_free_gb"],        float)
        assert isinstance(info["os_name"],             str)

    def test_get_hardware_info_values_are_sane(self):
        info = HardwareAuditor().get_hardware_info()
        assert info["ram_gb"]             > 0,   "RAM must be positive"
        assert info["cpu_cores_physical"] >= 1,  "Must have at least 1 core"
        assert info["disk_total_gb"]      > 0,   "Disk must be positive"
        assert 0 <= info["ram_used_percent"]  <= 100
        assert 0 <= info["disk_used_percent"] <= 100

    def test_run_audit_returns_recommended_profile_key(self):
        """run_audit() must add 'recommended_profile' to the returned dict."""
        info = HardwareAuditor().run_audit()
        assert "recommended_profile" in info
        assert info["recommended_profile"] in ("Lite", "Ultimate")


# =============================================================================
# UNIT -- is_app_installed  (registry, Windows-specific)
# =============================================================================

class TestIsAppInstalled:

    def test_non_windows_always_returns_false(self):
        """On Linux / macOS the function must return False, not raise."""
        with patch("client.engine.sys") as mock_sys:
            mock_sys.platform = "linux"
            result = is_app_installed("Microsoft.VisualStudioCode")
        assert result is False

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_returns_bool_on_windows(self):
        result = is_app_installed("Google.Chrome")
        assert isinstance(result, bool)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_mock_registry_match_found(self):
        """Registry contains 'Visual Studio Code' -> should return True."""
        import winreg

        mock_key = MagicMock()
        mock_key.__enter__ = lambda s: s
        mock_key.__exit__  = MagicMock(return_value=False)

        with patch("winreg.OpenKey",      return_value=mock_key), \
             patch("winreg.QueryInfoKey", return_value=(1, 0, 0)), \
             patch("winreg.EnumKey",      return_value="VSCodeKey"), \
             patch("winreg.QueryValueEx", return_value=("Visual Studio Code", 1)):
            result = is_app_installed("Microsoft.VisualStudioCode")

        assert result is True

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_mock_registry_no_match(self):
        """Registry raises OSError for every hive -> should return False."""
        with patch("winreg.OpenKey", side_effect=OSError):
            result = is_app_installed("SomeFake.App9999")
        assert result is False


# =============================================================================
# UNIT -- save_build / load_build
# =============================================================================

class TestBuildFile:

    def test_save_creates_file_on_disk(self, tmp_build_path, sample_apps):
        save_build(sample_apps, "Ultimate", "developer", tmp_build_path)
        assert tmp_build_path.exists(), "Build file was not created"

    def test_save_produces_valid_json(self, tmp_build_path, sample_apps):
        save_build(sample_apps, "Lite", "gamer", tmp_build_path)
        data = json.loads(tmp_build_path.read_text(encoding="utf-8"))
        assert data["autodeploy_version"] == "2.0"
        assert data["persona"]            == "gamer"
        assert data["hw_profile"]         == "Lite"
        assert isinstance(data["apps"],    list)
        assert len(data["apps"])          == 3

    def test_save_includes_powershell_scripts(self, tmp_build_path, sample_apps):
        scripts = ["apply_dark_theme", "disable_telemetry"]
        save_build(sample_apps, "Ultimate", "developer", tmp_build_path,
                   powershell_scripts=scripts)
        data = json.loads(tmp_build_path.read_text(encoding="utf-8"))
        assert data["powershell_scripts"] == scripts

    def test_save_includes_created_at_timestamp(self, tmp_build_path):
        save_build([], "Lite", "common", tmp_build_path)
        data = json.loads(tmp_build_path.read_text(encoding="utf-8"))
        assert "created_at" in data
        assert len(data["created_at"]) > 0

    def test_load_valid_build_succeeds(self, sample_build):
        build = load_build(sample_build)
        assert build["persona"]    == "developer"
        assert build["hw_profile"] == "Ultimate"
        assert len(build["apps"])  == 3

    def test_load_missing_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_build(tmp_path / "does_not_exist.json")

    def test_load_wrong_schema_raises_value_error(self, tmp_path):
        bad = tmp_path / "bad_schema.json"
        bad.write_text('{"completely_wrong_key": 123}', encoding="utf-8")
        with pytest.raises(ValueError, match="missing keys"):
            load_build(bad)

    def test_load_apps_not_list_raises_value_error(self, tmp_path):
        bad = tmp_path / "bad_apps.json"
        bad.write_text(
            '{"autodeploy_version": "2.0", "apps": "should-be-a-list"}',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="list"):
            load_build(bad)

    def test_corrupted_json_raises_decode_error(self, tmp_path):
        bad = tmp_path / "corrupt.json"
        bad.write_text("{this is NOT valid json!!!}", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_build(bad)

    def test_empty_apps_list_is_valid(self, tmp_build_path):
        """A build with zero apps is still a valid file."""
        save_build([], "Lite", "common", tmp_build_path)
        build = load_build(tmp_build_path)
        assert build["apps"] == []

    def test_roundtrip_preserves_all_data(self, tmp_build_path, sample_apps):
        scripts = ["apply_dark_theme", "enable_developer_mode"]
        save_build(sample_apps, "Ultimate", "developer",
                   tmp_build_path, powershell_scripts=scripts)
        build = load_build(tmp_build_path)
        assert build["apps"]               == sample_apps
        assert build["powershell_scripts"] == scripts
        assert build["hw_profile"]         == "Ultimate"
        assert build["persona"]            == "developer"


# =============================================================================
# UNIT -- ExecutionEngine (dry-run, no real Winget / PowerShell)
# =============================================================================

class TestExecutionEngineDryRun:
    """All tests use dry_run=True so nothing is installed or changed."""

    @pytest.fixture(autouse=True)
    def engine(self):
        with patch("client.engine.is_admin", return_value=True):
            yield ExecutionEngine(dry_run=True)

    def test_install_returns_true_in_dry_run(self, engine):
        assert engine.install_via_winget("Microsoft.VisualStudioCode") is True

    def test_dark_theme_returns_true(self, engine):
        assert engine.apply_dark_theme() is True

    def test_light_theme_returns_true(self, engine):
        assert engine.apply_light_theme() is True

    def test_disable_telemetry_returns_true(self, engine):
        assert engine.disable_telemetry() is True

    def test_ultimate_performance_returns_true(self, engine):
        assert engine.enable_ultimate_performance() is True

    def test_developer_mode_returns_true(self, engine):
        assert engine.enable_developer_mode() is True

    def test_apply_profile_apps_all_succeed(self, engine, sample_apps):
        apps = [{**a, "required": True} for a in sample_apps]
        results = engine.apply_profile_apps(apps)
        assert len(results["success"]) == 3
        assert len(results["failed"])  == 0
        assert len(results["skipped"]) == 0

    def test_apply_profile_apps_skips_empty_winget_id(self, engine):
        apps = [{"id": "broken_app", "winget_id": "", "required": True}]
        results = engine.apply_profile_apps(apps)
        assert "broken_app" in results["skipped"]
        assert len(results["failed"]) == 0

    def test_optional_app_failure_goes_to_skipped_not_failed(self, engine):
        """Optional apps that fail should land in 'skipped', not 'failed'."""
        apps = [{"id": "optional_thing", "winget_id": "", "required": False}]
        results = engine.apply_profile_apps(apps)
        assert "optional_thing" in results["skipped"]
        assert "optional_thing" not in results["failed"]

    def test_unknown_script_name_does_not_raise(self, engine):
        """_run_scripts must warn but never crash on unknown names."""
        engine._run_scripts(["totally_unknown_script_xyz"])
        # Reaching this line means no exception was raised

    def test_apply_build_dry_run_returns_dict(self, engine, sample_build):
        build   = load_build(sample_build)
        results = engine.apply_build(build)
        assert isinstance(results, dict)
        assert set(results.keys()) >= {"success", "failed", "skipped"}

    def test_apply_build_all_apps_succeed_in_dry_run(self, engine, sample_build):
        build   = load_build(sample_build)
        results = engine.apply_build(build)
        assert len(results["success"]) == 3
        assert len(results["failed"])  == 0


# =============================================================================
# INTEGRATION -- Full user flow: select -> save -> apply (dry-run)
# =============================================================================

class TestFullFlow:
    """
    Simulates the real user journey without a running server or Winget.
    Step 1: User picks apps in the Provisioning tab
    Step 2: Saves to a .json build file
    Step 3: Carries that file to a NEW machine
    Step 4: Applies it with dry-run (safe, no real changes)
    """

    def test_developer_full_flow(self, tmp_path):
        # 1. User on old machine selects apps
        selected = [
            {"id": "vscode", "winget_id": "Microsoft.VisualStudioCode"},
            {"id": "git",    "winget_id": "Git.Git"},
        ]
        hw_profile = HardwareAuditor().recommend_profile(16.0)
        assert hw_profile == "Ultimate"

        # 2. Save build file (portable)
        build_file = tmp_path / "my_dev_build.json"
        save_build(
            selected_app_ids=selected,
            hw_profile=hw_profile,
            persona="developer",
            output_path=build_file,
            powershell_scripts=["apply_dark_theme"],
        )
        assert build_file.exists()

        # 3. Load on "new machine"
        build = load_build(build_file)
        assert build["persona"]    == "developer"
        assert build["hw_profile"] == "Ultimate"
        assert len(build["apps"])  == 2

        # 4. Apply without real installs
        with patch("client.engine.is_admin", return_value=True):
            engine  = ExecutionEngine(dry_run=True)
            results = engine.apply_build(build)

        assert len(results["success"]) == 2
        assert len(results["failed"])  == 0

    def test_lite_profile_is_preserved_in_build(self, tmp_path):
        """A machine with 4 GB RAM creates a Lite build; Lite is preserved."""
        hw = HardwareAuditor().recommend_profile(4.0)
        assert hw == "Lite"
        build_file = tmp_path / "lite.json"
        save_build([], hw, "common", build_file)
        assert load_build(build_file)["hw_profile"] == "Lite"

    def test_app_with_empty_winget_id_is_skipped_not_failed(self, tmp_path):
        """If an app in the build has no winget_id, skip it gracefully."""
        apps = [{"id": "ghost_app", "winget_id": ""}]
        build_file = tmp_path / "ghost.json"
        save_build(apps, "Ultimate", "common", build_file)
        build = load_build(build_file)

        with patch("client.engine.is_admin", return_value=True):
            engine  = ExecutionEngine(dry_run=True)
            results = engine.apply_profile_apps(build["apps"])

        assert "ghost_app" in results["skipped"]
        assert len(results["failed"]) == 0

    def test_each_persona_build_is_independent(self, tmp_path):
        """Four separate build files do not share state."""
        personas_data = {
            "developer": ["apply_dark_theme",    "enable_developer_mode"],
            "gamer":     ["disable_xbox_game_bar","enable_ultimate_performance"],
            "designer":  ["apply_light_theme",   "enable_night_light"],
            "common":    ["apply_dark_theme",     "disable_telemetry"],
        }
        builds = {}
        for persona, scripts in personas_data.items():
            p = tmp_path / f"{persona}.json"
            save_build([], "Ultimate", persona, p, powershell_scripts=scripts)
            builds[persona] = load_build(p)

        for persona, scripts in personas_data.items():
            assert builds[persona]["persona"]            == persona
            assert builds[persona]["powershell_scripts"] == scripts

    def test_gamer_build_no_required_apps_all_optional(self, tmp_path):
        """Gamer build where all apps are optional: zero failures allowed."""
        apps = [
            {"id": "steam",   "winget_id": "Valve.Steam",     "required": False},
            {"id": "discord", "winget_id": "Discord.Discord",  "required": False},
        ]
        build_file = tmp_path / "gamer.json"
        save_build(apps, "Ultimate", "gamer", build_file,
                   powershell_scripts=["disable_xbox_game_bar"])
        build = load_build(build_file)

        with patch("client.engine.is_admin", return_value=True):
            engine  = ExecutionEngine(dry_run=True)
            results = engine.apply_profile_apps(build["apps"])

        assert len(results["failed"]) == 0
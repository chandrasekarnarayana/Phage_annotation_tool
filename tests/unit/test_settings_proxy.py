"""Tests for unified settings proxy behavior."""

from __future__ import annotations

from phage_annotator.ui_qt.services.settings_proxy import UnifiedSettingsProxy


class _FakeQSettings:
    def __init__(self) -> None:
        self._data = {}

    def value(self, key, default=None, type=None):  # noqa: A002 - Qt-compatible API
        value = self._data.get(key, default)
        if type is not None and value is not None and not isinstance(value, type):
            return type(value)
        return value

    def setValue(self, key, value):
        self._data[key] = value

    def contains(self, key):
        return key in self._data

    def remove(self, key):
        self._data.pop(key, None)

    def clear(self):
        self._data.clear()

    def allKeys(self):
        return list(self._data.keys())

    def sync(self):
        return None


class _FakeSettingsService:
    def __init__(self) -> None:
        self._data = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def remove(self, key):
        self._data.pop(key, None)


def test_proxy_prefers_service_get_set_remove() -> None:
    qsettings = _FakeQSettings()
    service = _FakeSettingsService()
    proxy = UnifiedSettingsProxy(qsettings, service)

    proxy.setValue("markerSize", 42)
    assert service.get("markerSize") == 42
    assert qsettings.value("markerSize", 0, type=int) == 42
    assert proxy.value("markerSize", 0, type=int) == 42

    proxy.remove("markerSize")
    assert service.get("markerSize") is None
    assert qsettings.contains("markerSize") is False


def test_proxy_falls_back_to_qsettings_when_service_missing_methods() -> None:
    class _BrokenService:
        pass

    qsettings = _FakeQSettings()
    proxy = UnifiedSettingsProxy(qsettings, _BrokenService())

    proxy.setValue("defaultFPS", 12)
    assert proxy.value("defaultFPS", 0, type=int) == 12

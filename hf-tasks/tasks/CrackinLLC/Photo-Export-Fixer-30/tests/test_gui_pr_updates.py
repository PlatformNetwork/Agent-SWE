import os
import types

import pytest

from pef.gui import main_window
from pef.gui.progress import InlineProgressView
from pef.gui.settings import Settings


class DummyCanvas:
    def __init__(self):
        self.bound = []
        self.unbound = []

    def bind_all(self, event, handler):
        self.bound.append((event, handler))

    def unbind_all(self, event):
        self.unbound.append(event)


class DummyThread:
    def __init__(self, target=None, daemon=None):
        self.target = target
        self.daemon = daemon
        self.started = False

    def start(self):
        self.started = True


class DummyRoot:
    def after(self, delay, callback):
        self.last_after = (delay, callback)

    def winfo_exists(self):
        return True


class DummyVar:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


class DummyProgress:
    def __init__(self):
        self.state = {"mode": "determinate", "value": 0}
        self.started = False
        self.stopped = False

    def __getitem__(self, key):
        return self.state[key]

    def __setitem__(self, key, value):
        self.state[key] = value

    def configure(self, **kwargs):
        self.state.update(kwargs)

    def start(self, *args, **kwargs):
        self.started = True

    def stop(self):
        self.stopped = True


class TestScrollableFrameBindings:
    def test_bind_and_unbind_mousewheel(self):
        frame = main_window.ScrollableFrame.__new__(main_window.ScrollableFrame)
        frame._canvas = DummyCanvas()

        frame._bind_mousewheel(None)
        frame._unbind_mousewheel(None)

        bound_events = [event for event, _ in frame._canvas.bound]
        assert "<MouseWheel>" in bound_events
        assert "<Button-4>" in bound_events
        assert "<Button-5>" in bound_events
        assert frame._canvas.unbound == ["<MouseWheel>", "<Button-4>", "<Button-5>"]


class TestStartupCheck:
    def test_windows_startup_creates_ui_immediately(self, monkeypatch):
        instance = main_window.PEFMainWindow.__new__(main_window.PEFMainWindow)
        instance.root = DummyRoot()
        instance._exiftool_available = False

        created = {"widgets": 0, "setup": 0}

        def create_widgets():
            created["widgets"] += 1

        def show_setup():
            created["setup"] += 1

        instance._create_widgets = create_widgets
        instance._show_setup_screen = show_setup
        instance._check_exiftool = lambda: None

        monkeypatch.setattr(main_window, "_reset_exiftool_cache", lambda: None)
        monkeypatch.setattr(instance, "_is_exiftool_installed", lambda: False)
        monkeypatch.setattr(main_window.sys, "platform", "win32")
        monkeypatch.setattr(main_window.threading, "Thread", DummyThread)

        main_window.PEFMainWindow._startup_check(instance)

        assert created["widgets"] == 1
        assert created["setup"] == 0


class TestProgressCapping:
    def test_update_progress_caps_percentage(self):
        view = InlineProgressView.__new__(InlineProgressView)
        view._progress = DummyProgress()
        view._percent_var = DummyVar()
        view._status_var = DummyVar()

        InlineProgressView.update_progress(view, current=150, total=100, message="Processing")

        assert view._progress.state["value"] == 100
        assert view._percent_var.value.startswith("100%")


class TestSettingsConfigPath:
    def test_respects_xdg_config_home(self, monkeypatch, tmp_path):
        xdg_path = tmp_path / "config_root"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_path))
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.setattr(main_window.os, "name", "posix", raising=False)
        monkeypatch.setattr(Settings, "_get_config_path", Settings._get_config_path, raising=False)

        settings = Settings()

        assert settings._config_path.startswith(str(xdg_path))
        assert os.path.isdir(os.path.dirname(settings._config_path))

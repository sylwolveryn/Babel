"""Minimising the overlay.

The overlay collapsed towards its top-left, so one parked along the bottom of
the screen jumped into the middle of it when minimised — which is the opposite
of what minimising it is for.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PyQt6", reason="this is the Qt frontend")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.config import AppConfig  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def overlay(qt_app):
    from app.overlay import ChatOverlay

    widget = ChatOverlay(AppConfig(wow_path=""))
    widget.show()
    QApplication.processEvents()
    yield widget
    widget.deleteLater()


# ── collapsing downwards ─────────────────────────────────────────────────────


def test_the_bottom_edge_stays_put_when_collapsing(overlay):
    """The point of the request: parked on the bottom edge of the screen, it
    has to stay on the bottom edge."""
    overlay.move(200, 400)
    overlay.resize(450, 300)
    QApplication.processEvents()
    bottom = overlay.y() + overlay.height()

    overlay._toggle_minimize()
    QApplication.processEvents()

    assert overlay.y() + overlay.height() == pytest.approx(bottom, abs=2)


def test_it_grows_back_from_the_same_edge(overlay):
    overlay.move(200, 400)
    overlay.resize(450, 300)
    QApplication.processEvents()
    bottom = overlay.y() + overlay.height()

    overlay._toggle_minimize()
    QApplication.processEvents()
    overlay._toggle_minimize()
    QApplication.processEvents()

    assert overlay.y() + overlay.height() == pytest.approx(bottom, abs=2)
    assert overlay.height() == 300, "the restored height is wrong"


def test_the_horizontal_position_is_left_alone(overlay):
    """Only the vertical anchor was asked about, and moving sideways as well
    would be a surprise."""
    overlay.move(321, 400)
    QApplication.processEvents()

    overlay._toggle_minimize()
    QApplication.processEvents()

    assert overlay.x() == 321


def test_collapsing_near_the_top_does_not_push_it_off_the_screen(overlay):
    """Growing back upwards from the bottom edge can ask for a negative y, and
    a window whose title bar is above the screen cannot be dragged back."""
    from app.overlay import _on_screen_y

    assert _on_screen_y(overlay, -500) >= 0


def test_collapsing_near_the_bottom_does_not_push_it_off_either(overlay):
    from app.overlay import _on_screen_y

    screen = overlay.screen() or QApplication.primaryScreen()
    available = screen.availableGeometry()

    assert _on_screen_y(overlay, available.bottom() + 500) < available.bottom()


def test_the_bottom_is_measured_before_anything_can_grow_the_window():
    """Behaviour cannot pin this: under the offscreen platform used in tests,
    showing the widgets back does not change the height until the event loop
    runs, so a measurement taken after them still reads the collapsed size and
    the test passes. On a real screen it does not — the window is already tall
    by then and the restored one lands a hundred pixels low. So the order is
    pinned in the source, which is where the mistake would be made."""
    import pathlib

    body = (pathlib.Path(__file__).resolve().parent.parent / "app" / "overlay.py").read_text(encoding="utf-8")
    restore = body[body.index("        else:\n            # Restore") :]
    restore = restore[: restore.index("def _on_opacity_changed")]

    measured = restore.index("bottom = self.y() + self.height()")
    for grows in ("self._toolbar.show()", "self.setMinimumSize(_MIN_WIDTH, _MIN_HEIGHT)"):
        assert measured < restore.index(grows), f"the bottom edge is measured after {grows}, which has already grown it"

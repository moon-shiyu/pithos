# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
"""
Validation tests for the enhanced buffering state logic in PithosWindow.

Since GStreamer and GTK are not available on all platforms, these tests mock
the GObject/GTK/Gst layer and validate the buffering state machine, threshold
behaviour, percentage tracking, and UI feedback in isolation.
"""

import time
import unittest
from enum import Enum
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Lightweight stand-ins for GStreamer / GTK types used by the code under test.
# ---------------------------------------------------------------------------

class _FakeGstState:
    PLAYING = 'PLAYING'
    PAUSED = 'PAUSED'
    NULL = 'NULL'


class PseudoGst(Enum):
    """Mirror of pithos.pithos.PseudoGst for testing."""
    PLAYING = 1
    PAUSED = 2
    BUFFERING = 3
    STOPPED = 4

    @property
    def state(self):
        return {
            1: _FakeGstState.PLAYING,
            2: _FakeGstState.PAUSED,
            3: _FakeGstState.PAUSED,
            4: _FakeGstState.NULL,
        }[self.value]


class FakeStatusbar:
    """Minimal GtkStatusbar mock that tracks push/pop calls."""

    def __init__(self):
        self._stacks = {}

    def get_context_id(self, context):
        return context

    def push(self, ctx, message):
        self._stacks.setdefault(ctx, []).append(message)

    def pop(self, ctx):
        stack = self._stacks.get(ctx, [])
        if stack:
            stack.pop()

    def current(self, ctx):
        stack = self._stacks.get(ctx, [])
        return stack[-1] if stack else None


# ---------------------------------------------------------------------------
# Minimal harness that extracts only the buffering-related behaviour of
# PithosWindow so we can exercise it without a real GTK/GStreamer runtime.
# ---------------------------------------------------------------------------

class BufferingHarness:
    """
    Reproduces the buffering-related fields and methods of PithosWindow
    exactly as they appear after the enhancement, but with all GTK/GStreamer
    calls replaced by simple fakes.
    """

    BUFFERING_DISPLAY_THRESHOLD_SECS = 0.5

    def __init__(self):
        self._current_state = PseudoGst.STOPPED
        self._buffer_recovery_state = PseudoGst.STOPPED
        self._buffering_start_time = 0
        self._buffering_percent = 0
        self._buffering_ui_timer_id = 0
        self.buffering_timer_id = 0
        self.ui_loop_timer_id = 0
        self.statusbar = FakeStatusbar()

        # Mocks for methods that interact with GStreamer / GLib / GTK.
        self.player = MagicMock()
        self._query_buffer = MagicMock()

        # Signals emitted (recorded for assertions).
        self.emitted_signals = []

        # Track calls to update_song_row.
        self.song_row_updates = 0

        # Simulate the query returning "still buffering" by default.
        self._sim_busy = True
        self._sim_percent = 0

    # -- Simulated GStreamer query -------------------------------------------

    def query_buffer(self):
        """Mirrors the enhanced query_buffer from pithos.py."""
        # In the real code this queries GStreamer; here we use sim values.
        self._buffering_percent = self._sim_percent
        return self._sim_busy

    def query_position(self):
        return 0

    # -- State helpers (simplified) ------------------------------------------

    def _set_player_state(self, target, change_gst_state=False):
        change_gst_state = change_gst_state or self._current_state is not PseudoGst.BUFFERING
        if change_gst_state:
            self._current_state = target
        if target is not PseudoGst.BUFFERING:
            self._buffer_recovery_state = target
        self.update_song_row()
        return True

    @property
    def playing(self):
        return self._buffer_recovery_state is not PseudoGst.PAUSED

    def play(self, change_gst_state=False):
        self._set_player_state(PseudoGst.PLAYING, change_gst_state=change_gst_state)
        return True

    def emit(self, signal, *args):
        self.emitted_signals.append((signal, args))

    def update_song_row(self, song=None):
        self.song_row_updates += 1

    # -- Buffering UI management (mirrors pithos.py) -------------------------

    def _start_buffering_ui(self):
        if not self._buffering_ui_timer_id:
            self._buffering_ui_timer_id = 1  # placeholder id

    def _stop_buffering_ui(self):
        if self._buffering_ui_timer_id:
            self._buffering_ui_timer_id = 0
        self.statusbar.pop(self.statusbar.get_context_id('buffering'))

    def _update_buffering_ui(self):
        if self._buffering_start_time == 0:
            return
        elapsed = time.time() - self._buffering_start_time
        if elapsed < self.BUFFERING_DISPLAY_THRESHOLD_SECS:
            return
        ctx = self.statusbar.get_context_id('buffering')
        self.statusbar.pop(ctx)
        self.statusbar.push(ctx, "正在缓冲 (%d%%)" % self._buffering_percent)
        self.update_song_row()

    # -- Core buffering handler (mirrors pithos.py) --------------------------

    def react_to_buffering_message(self, from_timeout):
        if from_timeout:
            self.buffering_timer_id = 0
        buffering = self.query_buffer()

        if buffering and self._current_state is not PseudoGst.BUFFERING:
            self._buffering_start_time = time.time()
            self._start_buffering_ui()
            if self._set_player_state(PseudoGst.BUFFERING):
                pass  # "Pausing pipeline"
        elif not buffering and self._current_state is PseudoGst.BUFFERING:
            self._stop_buffering_ui()
            self._buffering_start_time = 0
            self._buffering_percent = 0
            if self._buffer_recovery_state is PseudoGst.STOPPED:
                self.play(change_gst_state=True)
            elif self._buffer_recovery_state is PseudoGst.PLAYING:
                self._set_player_state(PseudoGst.PLAYING, change_gst_state=True)
            elif self._buffer_recovery_state is PseudoGst.PAUSED:
                self._set_player_state(PseudoGst.PAUSED, change_gst_state=True)
            self.emit('buffering-finished', self.query_position() or 0)
        elif buffering and self._current_state is PseudoGst.BUFFERING:
            self._update_buffering_ui()
        return buffering

    # -- song_text excerpt (buffering portion only) --------------------------

    def buffering_display_text(self):
        """Return the buffering status string that song_text would append."""
        if self._current_state is not PseudoGst.BUFFERING:
            return None
        elapsed = time.time() - self._buffering_start_time if self._buffering_start_time else 0
        if elapsed >= self.BUFFERING_DISPLAY_THRESHOLD_SECS:
            return "正在缓冲 (%d%%)" % self._buffering_percent
        else:
            return "Buffering…"


# ===========================================================================
# Test cases
# ===========================================================================

class TestBufferingStateTransitions(unittest.TestCase):
    """Verify state machine transitions on buffer underrun / overrun."""

    def setUp(self):
        self.h = BufferingHarness()
        # Simulate player is PLAYING and buffer underruns.
        self.h._current_state = PseudoGst.PLAYING
        self.h._buffer_recovery_state = PseudoGst.PLAYING

    def test_underrun_enters_buffering(self):
        self.h._sim_busy = True
        self.h._sim_percent = 30
        self.h.react_to_buffering_message(False)

        self.assertIs(self.h._current_state, PseudoGst.BUFFERING)
        self.assertEqual(self.h._buffering_percent, 30)
        self.assertNotEqual(self.h._buffering_start_time, 0)

    def test_overrun_recovers_to_playing(self):
        # First, enter buffering.
        self.h._sim_busy = True
        self.h.react_to_buffering_message(False)
        self.assertIs(self.h._current_state, PseudoGst.BUFFERING)

        # Now buffer is full.
        self.h._sim_busy = False
        self.h._sim_percent = 100
        self.h.react_to_buffering_message(False)

        self.assertIs(self.h._current_state, PseudoGst.PLAYING)
        self.assertEqual(self.h._buffering_start_time, 0)
        self.assertEqual(self.h._buffering_percent, 0)

    def test_overrun_recovers_to_paused(self):
        self.h._buffer_recovery_state = PseudoGst.PAUSED
        self.h._sim_busy = True
        self.h.react_to_buffering_message(False)

        self.h._sim_busy = False
        self.h.react_to_buffering_message(False)
        self.assertIs(self.h._current_state, PseudoGst.PAUSED)

    def test_overrun_from_stopped_calls_play(self):
        self.h._current_state = PseudoGst.STOPPED
        self.h._buffer_recovery_state = PseudoGst.STOPPED
        self.h._sim_busy = True
        self.h.react_to_buffering_message(False)

        self.h._sim_busy = False
        self.h.react_to_buffering_message(False)
        # play() transitions to PLAYING.
        self.assertIs(self.h._current_state, PseudoGst.PLAYING)

    def test_buffering_finished_signal_emitted(self):
        self.h._sim_busy = True
        self.h.react_to_buffering_message(False)

        self.h._sim_busy = False
        self.h.react_to_buffering_message(False)

        signals = [s[0] for s in self.h.emitted_signals]
        self.assertIn('buffering-finished', signals)


class TestBufferingPercentageTracking(unittest.TestCase):
    """Verify that the buffer fill percentage is tracked and exposed."""

    def setUp(self):
        self.h = BufferingHarness()
        self.h._current_state = PseudoGst.PLAYING
        self.h._buffer_recovery_state = PseudoGst.PLAYING

    def test_percentage_stored_on_query(self):
        self.h._sim_busy = True
        self.h._sim_percent = 42
        self.h.query_buffer()
        self.assertEqual(self.h._buffering_percent, 42)

    def test_percentage_updates_during_buffering(self):
        self.h._sim_busy = True
        self.h._sim_percent = 10
        self.h.react_to_buffering_message(False)
        self.assertEqual(self.h._buffering_percent, 10)

        self.h._sim_percent = 65
        self.h.react_to_buffering_message(False)
        self.assertEqual(self.h._buffering_percent, 65)

    def test_percentage_reset_on_overrun(self):
        self.h._sim_busy = True
        self.h._sim_percent = 80
        self.h.react_to_buffering_message(False)

        self.h._sim_busy = False
        self.h._sim_percent = 100
        self.h.react_to_buffering_message(False)
        self.assertEqual(self.h._buffering_percent, 0)


class TestBufferingThreshold(unittest.TestCase):
    """Verify that the UI display only activates after the threshold."""

    def setUp(self):
        self.h = BufferingHarness()
        self.h._current_state = PseudoGst.PLAYING
        self.h._buffer_recovery_state = PseudoGst.PLAYING

    def test_below_threshold_shows_simple_text(self):
        self.h._sim_busy = True
        self.h._sim_percent = 20
        self.h.react_to_buffering_message(False)

        # Immediately after entering buffering, threshold not exceeded yet.
        text = self.h.buffering_display_text()
        self.assertEqual(text, "Buffering…")

    def test_above_threshold_shows_percentage(self):
        self.h._sim_busy = True
        self.h._sim_percent = 45
        self.h.react_to_buffering_message(False)

        # Simulate time passing beyond threshold.
        self.h._buffering_start_time = time.time() - 1.0
        text = self.h.buffering_display_text()
        self.assertEqual(text, "正在缓冲 (45%)")

    def test_statusbar_updated_after_threshold(self):
        self.h._sim_busy = True
        self.h._sim_percent = 55
        self.h.react_to_buffering_message(False)

        # Before threshold: _update_buffering_ui should not push to statusbar.
        self.h._update_buffering_ui()
        self.assertIsNone(self.h.statusbar.current('buffering'))

        # After threshold: statusbar should show the message.
        self.h._buffering_start_time = time.time() - 1.0
        self.h._update_buffering_ui()
        msg = self.h.statusbar.current('buffering')
        self.assertEqual(msg, "正在缓冲 (55%)")

    def test_statusbar_cleared_on_overrun(self):
        self.h._sim_busy = True
        self.h._sim_percent = 50
        self.h.react_to_buffering_message(False)
        self.h._buffering_start_time = time.time() - 1.0
        self.h._update_buffering_ui()

        self.assertIsNotNone(self.h.statusbar.current('buffering'))

        # Buffer full.
        self.h._sim_busy = False
        self.h.react_to_buffering_message(False)
        self.assertIsNone(self.h.statusbar.current('buffering'))


class TestBufferingUITimerManagement(unittest.TestCase):
    """Verify the buffering UI timer is started and stopped correctly."""

    def setUp(self):
        self.h = BufferingHarness()
        self.h._current_state = PseudoGst.PLAYING
        self.h._buffer_recovery_state = PseudoGst.PLAYING

    def test_timer_started_on_underrun(self):
        self.h._sim_busy = True
        self.h.react_to_buffering_message(False)
        self.assertNotEqual(self.h._buffering_ui_timer_id, 0)

    def test_timer_stopped_on_overrun(self):
        self.h._sim_busy = True
        self.h.react_to_buffering_message(False)

        self.h._sim_busy = False
        self.h.react_to_buffering_message(False)
        self.assertEqual(self.h._buffering_ui_timer_id, 0)

    def test_not_buffering_returns_none_display(self):
        self.h._current_state = PseudoGst.PLAYING
        self.assertIsNone(self.h.buffering_display_text())


class TestFromTimeoutFlag(unittest.TestCase):
    """Verify the from_timeout parameter resets the timer id correctly."""

    def test_from_timeout_resets_timer_id(self):
        h = BufferingHarness()
        h._current_state = PseudoGst.PLAYING
        h._buffer_recovery_state = PseudoGst.PLAYING
        h.buffering_timer_id = 42
        h._sim_busy = True
        h.react_to_buffering_message(True)
        self.assertEqual(h.buffering_timer_id, 0)

    def test_not_from_timeout_preserves_timer_id(self):
        h = BufferingHarness()
        h._current_state = PseudoGst.PLAYING
        h._buffer_recovery_state = PseudoGst.PLAYING
        h.buffering_timer_id = 42
        h._sim_busy = True
        h.react_to_buffering_message(False)
        self.assertEqual(h.buffering_timer_id, 42)


if __name__ == '__main__':
    unittest.main()

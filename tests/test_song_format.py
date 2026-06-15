# -*- coding: utf-8 -*-
"""Tests for pithos/song_format.py — the shared song display formatting module.

These tests validate formatting functions in isolation.  They do not require
a running D-Bus session, desktop notification daemon, or MPRIS client.

Run with:  python -m pytest tests/test_song_format.py -v
"""

import sys
import os
import unittest

# Make the pithos package importable from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pithos.song_format import (
    rating_label,
    format_notification_title,
    format_notification_body,
    format_window_title,
    format_pulse_media_name,
    format_song_description,
    RATE_LOVE,
    RATE_BAN,
    RATE_NONE,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

class MockSong:
    """Lightweight stand-in for pithos.pandora.Song used by formatting tests."""

    def __init__(
        self,
        title='Midnight City',
        artist='M83',
        album='Hurry Up, We\'re Dreaming',
        rating=RATE_NONE,
        tired=False,
        is_ad=False,
    ):
        self.title = title
        self.artist = artist
        self.album = album
        self.rating = rating
        self.tired = tired
        self.is_ad = is_ad


# ---------------------------------------------------------------------------
# rating_label
# ---------------------------------------------------------------------------

class TestRatingLabel(unittest.TestCase):

    def test_no_rating(self):
        song = MockSong()
        self.assertEqual(rating_label(song), '')

    def test_loved(self):
        song = MockSong(rating=RATE_LOVE)
        self.assertEqual(rating_label(song), 'Loved')

    def test_banned(self):
        song = MockSong(rating=RATE_BAN)
        self.assertEqual(rating_label(song), 'Banned')

    def test_tired_overrides_love(self):
        song = MockSong(rating=RATE_LOVE, tired=True)
        self.assertEqual(rating_label(song), 'Tired')

    def test_tired_overrides_ban(self):
        song = MockSong(rating=RATE_BAN, tired=True)
        self.assertEqual(rating_label(song), 'Tired')

    def test_tired_alone(self):
        song = MockSong(rating=RATE_NONE, tired=True)
        self.assertEqual(rating_label(song), 'Tired')

    def test_unknown_rating_value(self):
        song = MockSong()
        song.rating = 'some_future_value'
        # Unknown ratings should not crash; they return an empty string.
        self.assertEqual(rating_label(song), '')

    def test_missing_rating_attribute(self):
        """Song objects that lack a rating attribute are treated as unrated."""
        class BareSong:
            tired = False
        self.assertEqual(rating_label(BareSong()), '')


# ---------------------------------------------------------------------------
# format_notification_title
# ---------------------------------------------------------------------------

class TestFormatNotificationTitle(unittest.TestCase):

    def test_normal_song(self):
        song = MockSong(artist='M83')
        self.assertEqual(format_notification_title(song), 'M83')

    def test_ad(self):
        song = MockSong(is_ad=True, artist='should be ignored')
        self.assertEqual(format_notification_title(song), 'Pandora Advertisement')

    def test_empty_artist(self):
        song = MockSong(artist='')
        self.assertEqual(format_notification_title(song), 'Unknown Artist')

    def test_none_artist(self):
        song = MockSong()
        song.artist = None
        self.assertEqual(format_notification_title(song), 'Unknown Artist')


# ---------------------------------------------------------------------------
# format_notification_body
# ---------------------------------------------------------------------------

class TestFormatNotificationBody(unittest.TestCase):

    def test_normal_song_unrated(self):
        song = MockSong()
        body = format_notification_body(song)
        self.assertIn('Midnight City', body)
        self.assertIn('Hurry Up, We\'re Dreaming', body)
        self.assertNotIn('Loved', body)
        self.assertNotIn('Banned', body)
        self.assertNotIn('Tired', body)

    def test_loved_song(self):
        song = MockSong(rating=RATE_LOVE)
        body = format_notification_body(song)
        self.assertIn('Midnight City', body)
        self.assertIn('Hurry Up, We\'re Dreaming', body)
        self.assertIn('Loved', body)

    def test_banned_song(self):
        song = MockSong(rating=RATE_BAN)
        body = format_notification_body(song)
        self.assertIn('Banned', body)

    def test_tired_song(self):
        song = MockSong(rating=RATE_LOVE, tired=True)
        body = format_notification_body(song)
        self.assertIn('Tired', body)
        self.assertNotIn('Loved', body)

    def test_advertisement(self):
        song = MockSong(is_ad=True)
        body = format_notification_body(song)
        self.assertEqual(body, 'Commercial Advertisement')
        self.assertNotIn('Midnight City', body)

    def test_missing_title_and_album(self):
        song = MockSong(title='', album='')
        body = format_notification_body(song)
        self.assertIn('Unknown Title', body)
        self.assertIn('Unknown Album', body)

    def test_body_contains_album_prefix(self):
        """The album line must start with 'from ' for readability."""
        song = MockSong(album='Random Access Memories')
        body = format_notification_body(song)
        self.assertIn('from Random Access Memories', body)

    def test_line_structure_unrated(self):
        """An unrated song body has exactly two lines: title and album."""
        song = MockSong()
        body = format_notification_body(song)
        lines = body.split('\n')
        self.assertEqual(len(lines), 2, f'Expected 2 lines, got {len(lines)}: {lines}')

    def test_line_structure_rated(self):
        """A rated song body has exactly three lines: title, album, rating."""
        song = MockSong(rating=RATE_LOVE)
        body = format_notification_body(song)
        lines = body.split('\n')
        self.assertEqual(len(lines), 3, f'Expected 3 lines, got {len(lines)}: {lines}')


# ---------------------------------------------------------------------------
# format_window_title
# ---------------------------------------------------------------------------

class TestFormatWindowTitle(unittest.TestCase):

    def test_normal_song(self):
        song = MockSong()
        self.assertEqual(format_window_title(song), 'Midnight City by M83 - Pithos')

    def test_empty_title(self):
        song = MockSong(title='')
        self.assertEqual(format_window_title(song), 'Unknown Title by M83 - Pithos')

    def test_empty_artist(self):
        song = MockSong(artist='')
        self.assertEqual(format_window_title(song), 'Midnight City by Unknown Artist - Pithos')

    def test_contains_pithos_suffix(self):
        song = MockSong()
        self.assertTrue(format_window_title(song).endswith(' - Pithos'))


# ---------------------------------------------------------------------------
# format_pulse_media_name
# ---------------------------------------------------------------------------

class TestFormatPulseMediaName(unittest.TestCase):

    def test_normal_song(self):
        song = MockSong()
        self.assertEqual(format_pulse_media_name(song), 'M83: Midnight City')

    def test_empty_fields(self):
        song = MockSong(artist='', title='')
        self.assertEqual(format_pulse_media_name(song), 'Unknown Artist: Unknown Title')

    def test_format_separator(self):
        """PulseAudio media name must use ': ' as the separator."""
        song = MockSong()
        self.assertIn(': ', format_pulse_media_name(song))


# ---------------------------------------------------------------------------
# format_song_description
# ---------------------------------------------------------------------------

class TestFormatSongDescription(unittest.TestCase):

    def test_unrated(self):
        song = MockSong()
        desc = format_song_description(song)
        self.assertEqual(desc, "Midnight City by M83 (from Hurry Up, We're Dreaming)")

    def test_loved(self):
        song = MockSong(rating=RATE_LOVE)
        desc = format_song_description(song)
        self.assertIn('[Loved]', desc)
        self.assertTrue(desc.endswith('[Loved]'))

    def test_banned(self):
        song = MockSong(rating=RATE_BAN)
        desc = format_song_description(song)
        self.assertIn('[Banned]', desc)

    def test_tired(self):
        song = MockSong(rating=RATE_LOVE, tired=True)
        desc = format_song_description(song)
        self.assertIn('[Tired]', desc)
        self.assertNotIn('[Loved]', desc)

    def test_ad(self):
        """format_song_description does not special-case ads (no is_ad branch)."""
        song = MockSong(is_ad=True, title='Ad Title', artist='Ad Artist', album='Ad Album')
        desc = format_song_description(song)
        # Still formats normally; ad handling is notification-specific.
        self.assertIn('Ad Title', desc)


# ---------------------------------------------------------------------------
# Cross-module consistency: notification and description use the same
# rating vocabulary and album representation.
# ---------------------------------------------------------------------------

class TestCrossFormatConsistency(unittest.TestCase):
    """Verify that different formatters agree on rating and album text."""

    def _all_rating_states(self):
        return [
            MockSong(rating=RATE_NONE),
            MockSong(rating=RATE_LOVE),
            MockSong(rating=RATE_BAN),
            MockSong(rating=RATE_LOVE, tired=True),
        ]

    def test_album_present_in_notification_and_description(self):
        album = 'Hurry Up, We\'re Dreaming'
        for song in self._all_rating_states():
            song.album = album
            self.assertIn(album, format_notification_body(song))
            self.assertIn(album, format_song_description(song))

    def test_rating_label_consistent_across_formatters(self):
        for song in self._all_rating_states():
            label = rating_label(song)
            body = format_notification_body(song)
            desc = format_song_description(song)
            if label:
                self.assertIn(label, body)
                self.assertIn('[{}]'.format(label), desc)
            else:
                self.assertNotIn('Loved', body)
                self.assertNotIn('Banned', body)
                self.assertNotIn('Tired', body)

    def test_notification_and_mpris_rating_agree(self):
        """MPRIS uses rating_label() for pithos:rating display text.

        If MPRIS and the notification plugin both call rating_label() with
        the same song they must get the same string.
        """
        songs = [
            MockSong(rating=RATE_LOVE),
            MockSong(rating=RATE_BAN),
            MockSong(rating=RATE_NONE),
            MockSong(rating=RATE_LOVE, tired=True),
        ]
        for song in songs:
            # MPRIS would call: rating_label(song) to fill pithos:rating display
            mpris_label = rating_label(song)
            # Notify would call: format_notification_body(song)
            body = format_notification_body(song)
            if mpris_label:
                self.assertIn(mpris_label, body,
                              f'Rating label {mpris_label!r} missing from notification body')
            else:
                # No rating — body must not contain any rating keyword.
                for kw in ('Loved', 'Banned', 'Tired'):
                    self.assertNotIn(kw, body)


# ---------------------------------------------------------------------------
# Edge cases: None / missing attributes
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):

    def test_song_with_none_fields(self):
        """None-valued fields must be replaced by fallback strings."""
        song = MockSong()
        song.title = None
        song.artist = None
        song.album = None
        self.assertIn('Unknown Title', format_notification_body(song))
        self.assertIn('Unknown Title', format_window_title(song))
        self.assertIn('Unknown Artist', format_window_title(song))
        self.assertIn('Unknown Title', format_pulse_media_name(song))

    def test_song_missing_attribute_entirely(self):
        """Objects lacking title/artist/album attrs must not raise."""
        class BareSong:
            tired = False
            rating = RATE_NONE
            is_ad = False
        song = BareSong()
        # All formatters should handle missing attributes gracefully.
        self.assertIn('Unknown Title', format_notification_body(song))
        self.assertIn('Unknown Artist', format_notification_title(song))
        self.assertIn('Unknown Title', format_window_title(song))
        self.assertIn('Unknown Artist', format_pulse_media_name(song))

    def test_unicode_content(self):
        """Non-ASCII characters must pass through without corruption."""
        song = MockSong(title='Ünïcödë', artist='Ólafur Arnalds', album='Ísland')
        body = format_notification_body(song)
        self.assertIn('Ünïcödë', body)
        self.assertIn('Ólafur Arnalds', format_notification_title(song))
        self.assertIn('Ísland', body)
        self.assertIn('Ünïcödë', format_window_title(song))

    def test_special_html_chars_not_escaped(self):
        """Formatting functions must NOT HTML-escape content (callers handle that)."""
        song = MockSong(title='A & B <C>', artist='X "Y" Z')
        body = format_notification_body(song)
        # Must contain raw '&', '<', '>', '"' — not escaped entities.
        self.assertIn('A & B <C>', body)
        self.assertIn('X "Y" Z', format_notification_title(song))


if __name__ == '__main__':
    unittest.main()

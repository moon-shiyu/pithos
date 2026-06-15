# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Tests for pithos.song_format — the shared song display formatting module.
# These tests verify formatting logic in isolation without requiring
# GTK, GLib, DBus, MPRIS, or any running desktop session.

import pytest

from pithos.song_format import (
    safe_title,
    safe_artist,
    safe_album,
    rating_icon,
    rating_indicator,
    mpris_rating_text,
    window_title,
    notification_title,
    notification_body,
    mpris_artist_list,
)


class FakeSong:
    """Minimal duck-typed song object for testing formatters."""

    def __init__(self, title='', artist='', album='', rating=None, tired=False):
        self.title = title
        self.artist = artist
        self.album = album
        self.rating = rating
        self.tired = tired


# --- Core accessor tests ---

class TestSafeTitle:
    def test_normal(self):
        assert safe_title(FakeSong(title='Hello')) == 'Hello'

    def test_empty_string(self):
        assert safe_title(FakeSong(title='')) == 'Title Unknown'

    def test_none(self):
        assert safe_title(FakeSong(title=None)) == 'Title Unknown'

    def test_whitespace_preserved(self):
        assert safe_title(FakeSong(title='  Spaces  ')) == '  Spaces  '


class TestSafeArtist:
    def test_normal(self):
        assert safe_artist(FakeSong(artist='Band')) == 'Band'

    def test_empty_string(self):
        assert safe_artist(FakeSong(artist='')) == 'Artist Unknown'

    def test_none(self):
        assert safe_artist(FakeSong(artist=None)) == 'Artist Unknown'


class TestSafeAlbum:
    def test_normal(self):
        assert safe_album(FakeSong(album='Record')) == 'Record'

    def test_empty_string(self):
        assert safe_album(FakeSong(album='')) == 'Album Unknown'

    def test_none(self):
        assert safe_album(FakeSong(album=None)) == 'Album Unknown'


class TestRatingIcon:
    def test_love(self):
        assert rating_icon(FakeSong(rating='love')) == 'love'

    def test_ban(self):
        assert rating_icon(FakeSong(rating='ban')) == 'ban'

    def test_none_rating(self):
        assert rating_icon(FakeSong(rating=None)) is None

    def test_tired(self):
        assert rating_icon(FakeSong(tired=True)) == 'tired'

    def test_tired_takes_precedence_over_love(self):
        assert rating_icon(FakeSong(tired=True, rating='love')) == 'tired'

    def test_tired_takes_precedence_over_ban(self):
        assert rating_icon(FakeSong(tired=True, rating='ban')) == 'tired'


class TestRatingIndicator:
    def test_love(self):
        result = rating_indicator(FakeSong(rating='love'))
        assert result == ' \u2665'

    def test_ban(self):
        assert rating_indicator(FakeSong(rating='ban')) == ''

    def test_none(self):
        assert rating_indicator(FakeSong(rating=None)) == ''

    def test_tired(self):
        assert rating_indicator(FakeSong(tired=True)) == ''


# --- Composed formatter tests ---

class TestWindowTitle:
    def test_normal(self):
        song = FakeSong(title='Song', artist='Artist')
        assert window_title(song) == 'Song by Artist - Pithos'

    def test_missing_artist(self):
        song = FakeSong(title='Song', artist='')
        assert window_title(song) == 'Song by Artist Unknown - Pithos'

    def test_missing_both(self):
        song = FakeSong(title='', artist='')
        assert window_title(song) == 'Title Unknown by Artist Unknown - Pithos'


class TestNotificationTitle:
    def test_normal(self):
        song = FakeSong(artist='Band')
        assert notification_title(song) == 'Band'

    def test_loved_song(self):
        song = FakeSong(artist='Band', rating='love')
        assert notification_title(song) == 'Band \u2665'

    def test_banned_song_no_indicator(self):
        song = FakeSong(artist='Band', rating='ban')
        assert notification_title(song) == 'Band'

    def test_missing_artist(self):
        song = FakeSong(artist='')
        assert notification_title(song) == 'Artist Unknown'

    def test_missing_artist_loved(self):
        song = FakeSong(artist='', rating='love')
        assert notification_title(song) == 'Artist Unknown \u2665'


class TestNotificationBody:
    def test_normal(self):
        song = FakeSong(title='Track', album='Record')
        assert notification_body(song) == 'Track\nRecord'

    def test_missing_album(self):
        song = FakeSong(title='Track', album='')
        assert notification_body(song) == 'Track\nAlbum Unknown'

    def test_missing_title(self):
        song = FakeSong(title='', album='Record')
        assert notification_body(song) == 'Title Unknown\nRecord'

    def test_missing_both(self):
        song = FakeSong(title='', album='')
        assert notification_body(song) == 'Title Unknown\nAlbum Unknown'


class TestMprisArtistList:
    def test_normal(self):
        assert mpris_artist_list(FakeSong(artist='Band')) == ['Band']

    def test_returns_list(self):
        result = mpris_artist_list(FakeSong(artist='Band'))
        assert isinstance(result, list)
        assert len(result) == 1

    def test_empty_artist_uses_fallback(self):
        """Regression: [song.artist] or ['Artist Unknown'] never triggered fallback."""
        song = FakeSong(artist='')
        result = mpris_artist_list(song)
        assert result == ['Artist Unknown']
        assert result != ['']  # The old buggy behavior

    def test_none_artist_uses_fallback(self):
        result = mpris_artist_list(FakeSong(artist=None))
        assert result == ['Artist Unknown']


# --- Cross-module consistency tests ---

class TestConsistency:
    """Verify MPRIS and notification formatters produce consistent base values."""

    def test_same_artist_fallback(self):
        song = FakeSong(artist='')
        mpris_artist = mpris_artist_list(song)[0]
        notif_title = notification_title(song)
        assert mpris_artist == notif_title  # Both use 'Artist Unknown'

    def test_same_title_fallback(self):
        song = FakeSong(title='')
        notif_body_first_line = notification_body(song).split('\n')[0]
        assert notif_body_first_line == 'Title Unknown'
        assert notif_body_first_line == safe_title(song)

    def test_same_album_fallback(self):
        song = FakeSong(album='')
        notif_body_second_line = notification_body(song).split('\n')[1]
        assert notif_body_second_line == 'Album Unknown'
        assert notif_body_second_line == safe_album(song)

    def test_loved_song_rating_consistent(self):
        song = FakeSong(rating='love')
        assert rating_icon(song) == 'love'
        assert '\u2665' in notification_title(song)
        assert '\u2665' in rating_indicator(song)

    def test_banned_song_no_heart_anywhere(self):
        song = FakeSong(artist='Band', rating='ban')
        assert rating_icon(song) == 'ban'
        assert '\u2665' not in notification_title(song)
        assert rating_indicator(song) == ''

    def test_tired_song_no_heart_anywhere(self):
        song = FakeSong(artist='Band', tired=True)
        assert rating_icon(song) == 'tired'
        assert '\u2665' not in notification_title(song)
        assert rating_indicator(song) == ''

    def test_mpris_and_notification_use_same_title(self):
        song = FakeSong(title='Track', album='Record')
        mpris_title = safe_title(song)
        notif_title_line = notification_body(song).split('\n')[0]
        assert mpris_title == notif_title_line

    def test_mpris_and_notification_use_same_album(self):
        song = FakeSong(title='Track', album='Record')
        mpris_album = safe_album(song)
        notif_album_line = notification_body(song).split('\n')[1]
        assert mpris_album == notif_album_line

    def test_mpris_rating_text_matches_rating_icon(self):
        """mpris_rating_text wraps rating_icon; verify they agree."""
        for rating in ('love', 'ban', None):
            song = FakeSong(rating=rating)
            expected = rating_icon(song) or ''
            assert mpris_rating_text(song) == expected

    def test_all_formatters_handle_all_empty_fields(self):
        song = FakeSong(title='', artist='', album='')
        assert safe_title(song) == 'Title Unknown'
        assert safe_artist(song) == 'Artist Unknown'
        assert safe_album(song) == 'Album Unknown'
        assert mpris_artist_list(song) == ['Artist Unknown']
        assert 'Title Unknown' in notification_body(song)
        assert 'Album Unknown' in notification_body(song)
        assert 'Artist Unknown' in notification_title(song)
        assert 'Title Unknown' in window_title(song)
        assert 'Artist Unknown' in window_title(song)


# --- MPRIS rating text tests ---

class TestMprisRatingText:
    def test_love(self):
        assert mpris_rating_text(FakeSong(rating='love')) == 'love'

    def test_ban(self):
        assert mpris_rating_text(FakeSong(rating='ban')) == 'ban'

    def test_tired(self):
        assert mpris_rating_text(FakeSong(tired=True)) == 'tired'

    def test_no_rating(self):
        assert mpris_rating_text(FakeSong(rating=None)) == ''

    def test_return_type_is_str(self):
        """MPRIS pithos:rating field expects a string, never None."""
        for rating in ('love', 'ban', None):
            for tired in (True, False):
                result = mpris_rating_text(FakeSong(rating=rating, tired=tired))
                assert isinstance(result, str)

    def test_tired_takes_precedence(self):
        assert mpris_rating_text(FakeSong(tired=True, rating='love')) == 'tired'


# --- Unicode and special character handling ---

class TestUnicodeHandling:
    """Verify formatters pass through international text without corruption."""

    def test_cjk_title(self):
        song = FakeSong(title='\u6d41\u8f6c\u661f\u7a7a', artist='Artist')
        assert safe_title(song) == '\u6d41\u8f6c\u661f\u7a7a'
        assert '\u6d41\u8f6c\u661f\u7a7a' in notification_body(song)

    def test_cjk_artist(self):
        song = FakeSong(title='Song', artist='\u5468\u6770\u4f26')
        assert safe_artist(song) == '\u5468\u6770\u4f26'
        assert mpris_artist_list(song) == ['\u5468\u6770\u4f26']
        assert '\u5468\u6770\u4f26' in notification_title(song)

    def test_accented_latin(self):
        song = FakeSong(title='Caf\u00e9 M\u00fcsik', artist='Bj\u00f6rk', album='\u00c9dith')
        assert safe_title(song) == 'Caf\u00e9 M\u00fcsik'
        assert safe_artist(song) == 'Bj\u00f6rk'
        assert safe_album(song) == '\u00c9dith'

    def test_emoji_in_title(self):
        song = FakeSong(title='\U0001f3b5 Music', artist='Artist')
        assert safe_title(song) == '\U0001f3b5 Music'

    def test_ampersand_passthrough(self):
        """Raw & is passed through; HTML escaping is the caller's job."""
        song = FakeSong(title='Tom & Jerry', artist='Simon & Garfunkel', album='S&G')
        assert safe_title(song) == 'Tom & Jerry'
        assert safe_artist(song) == 'Simon & Garfunkel'
        assert safe_album(song) == 'S&G'

    def test_angle_brackets_passthrough(self):
        song = FakeSong(title='<Hit>', artist='Art', album='Rec')
        assert safe_title(song) == '<Hit>'

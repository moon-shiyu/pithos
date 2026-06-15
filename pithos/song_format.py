# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2010-2012 Kevin Mehall <km@kevinmehall.net>
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

# Shared song display formatting for MPRIS, notifications, and the main window.
# All functions are pure Python with no GTK/GLib/DBus dependencies so they
# can be validated in isolation without a running desktop session.

from pithos.pandora import RATE_LOVE, RATE_BAN


# --- Core safe accessors ---

def safe_title(song):
    """Return song title with a fallback for missing values."""
    return song.title or 'Title Unknown'


def safe_artist(song):
    """Return song artist with a fallback for missing values."""
    return song.artist or 'Artist Unknown'


def safe_album(song):
    """Return song album with a fallback for missing values."""
    return song.album or 'Album Unknown'


def rating_icon(song):
    """Map song rating/tired state to an icon name string.

    Returns 'tired', 'love', 'ban', or None.
    Tired takes precedence over rating.
    """
    if song.tired:
        return 'tired'
    if song.rating == RATE_LOVE:
        return 'love'
    if song.rating == RATE_BAN:
        return 'ban'
    return None


def rating_indicator(song):
    """Return a short text indicator for rated songs.

    Returns a heart suffix for loved songs, empty string otherwise.
    """
    if song.rating == RATE_LOVE:
        return ' \u2665'
    return ''


def mpris_rating_text(song):
    """Return the rating string for the MPRIS pithos:rating field.

    Wraps rating_icon so MPRIS metadata does not need its own inline
    fallback logic.  Returns 'love', 'ban', 'tired', or ''.
    """
    return rating_icon(song) or ''


# --- Composed formatters ---

def window_title(song):
    """Format the main window title bar text."""
    return '{} by {} - Pithos'.format(safe_title(song), safe_artist(song))


def notification_title(song):
    """Format the notification heading (artist with optional rating indicator)."""
    return '{}{}'.format(safe_artist(song), rating_indicator(song))


def notification_body(song):
    """Format the notification body (title and album)."""
    return '{}\n{}'.format(safe_title(song), safe_album(song))


def mpris_artist_list(song):
    """Return artist as a single-element list for MPRIS xesam:artist.

    This fixes a bug where [song.artist] or ['Artist Unknown'] never
    triggered the fallback because a single-element list is always truthy.
    """
    return [safe_artist(song)]

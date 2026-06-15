# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2024 Pithos contributors
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

"""Shared song display formatting functions.

This module provides a single source of truth for how song information
(title, artist, album, and rating state) is formatted for display across
the UI, desktop notifications (notify plugin), and MPRIS metadata.

All functions in this module are pure (no GI/DBus dependencies) so they
can be tested in isolation without a running desktop session.
"""


# Rating constants — mirror pithos.pandora values but are self-contained
# so this module has no hard dependency on the pandora package.
RATE_LOVE = 'love'
RATE_BAN = 'ban'
RATE_NONE = None

# Human-readable labels for each rating state.
_RATING_LABELS = {
    RATE_LOVE: 'Loved',
    RATE_BAN: 'Banned',
    'tired': 'Tired',
}


def rating_label(song):
    """Return a human-readable rating label for *song*.

    Returns the display string for the song's current rating or tired
    state.  The tired flag takes precedence over the love/ban rating
    because a tired song is always skipped regardless of its rating.

    Returns:
        str: One of ``'Loved'``, ``'Banned'``, ``'Tired'``, or ``''``
        (empty string when the song has no rating and is not tired).
    """
    if getattr(song, 'tired', False):
        return _RATING_LABELS['tired']
    rating = getattr(song, 'rating', RATE_NONE)
    return _RATING_LABELS.get(rating, '')


def format_notification_title(song):
    """Return the notification summary line.

    Used as the title/summary of a desktop notification (``Gio.Notification``).
    For advertisements the string ``'Pandora Advertisement'`` is returned.
    For regular songs the artist name is returned, which matches the
    convention used by GNOME-Shell and most music players.

    Returns:
        str
    """
    if getattr(song, 'is_ad', False):
        return 'Pandora Advertisement'
    return getattr(song, 'artist', '') or 'Unknown Artist'


def format_notification_body(song):
    """Return the notification detail/body line.

    The body includes the song title, album, and rating label so the user
    sees the same information in the notification as in MPRIS metadata and
    the main window.

    Format for songs::

        <title>
        from <album>
        Loved           (only when rated/tired)

    Format for advertisements::

        Commercial Advertisement

    Returns:
        str
    """
    if getattr(song, 'is_ad', False):
        return 'Commercial Advertisement'

    title = getattr(song, 'title', '') or 'Unknown Title'
    album = getattr(song, 'album', '') or 'Unknown Album'

    lines = [title, 'from {}'.format(album)]

    label = rating_label(song)
    if label:
        lines.append(label)

    return '\n'.join(lines)


def format_window_title(song):
    """Return the main window title string.

    Format::

        <title> by <artist> - Pithos

    Returns:
        str
    """
    title = getattr(song, 'title', '') or 'Unknown Title'
    artist = getattr(song, 'artist', '') or 'Unknown Artist'
    return '{} by {} - Pithos'.format(title, artist)


def format_pulse_media_name(song):
    """Return the PulseAudio ``media.name`` property value.

    This is shown by PulseAudio/PipeWire volume controls and mixers.

    Format::

        <artist>: <title>

    Returns:
        str
    """
    artist = getattr(song, 'artist', '') or 'Unknown Artist'
    title = getattr(song, 'title', '') or 'Unknown Title'
    return '{}: {}'.format(artist, title)


def format_song_description(song):
    """Return a one-line plain-text description of the song.

    Useful for logging and any context that needs a compact human-readable
    representation.

    Format::

        <title> by <artist> (from <album>) [<rating>]

    The rating bracket is omitted when there is no rating.

    Returns:
        str
    """
    title = getattr(song, 'title', '') or 'Unknown Title'
    artist = getattr(song, 'artist', '') or 'Unknown Artist'
    album = getattr(song, 'album', '') or 'Unknown Album'

    desc = '{} by {} (from {})'.format(title, artist, album)

    label = rating_label(song)
    if label:
        desc += ' [{}]'.format(label)

    return desc

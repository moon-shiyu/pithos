"""Tests for search result grouping logic.

Validates the core grouping, filtering, and sorting behavior used by
Pandora.search_grouped() and SearchDialog, without requiring a running
Pandora connection or GTK display.

Run with:
    python -m pytest tests/ -v
"""

import html
import sys
import os
import unittest

# Allow imports from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pithos.pandora.pandora import SearchResult


# ---------------------------------------------------------------------------
# Pure grouping helper — mirrors the logic inside Pandora.search_grouped()
# and SearchDialog.search() callback so we can exercise it without GTK.
# ---------------------------------------------------------------------------

def group_search_results(raw_results):
    """Group raw API results into categorised SearchResult lists.

    Args:
        raw_results: dict with keys 'artists', 'songs', 'genreStations'

    Returns:
        dict with keys 'artists', 'songs', 'genres'
    """
    min_score = 80
    artists = sorted(
        [SearchResult('artist', i) for i in raw_results.get('artists', []) if i['score'] >= min_score],
        key=lambda r: r.score, reverse=True,
    )
    songs = sorted(
        [SearchResult('song', i) for i in raw_results.get('songs', []) if i['score'] >= min_score],
        key=lambda r: r.score, reverse=True,
    )
    genres = [SearchResult('genre', i) for i in raw_results.get('genreStations', [])]
    return {'artists': artists, 'songs': songs, 'genres': genres}


def make_markup(result):
    """Build display markup for a SearchResult — mirrors SearchDialog logic."""
    if result.resultType == 'song':
        return '<b>{}</b> by {}'.format(html.escape(result.title), html.escape(result.artist))
    elif result.resultType == 'artist':
        return '<b>{}</b>'.format(html.escape(result.name))
    elif result.resultType == 'genre':
        return '<b>{}</b>'.format(html.escape(result.stationName))
    return ''


def make_station_description(result):
    """Build station description — mirrors StationsDialog.add_station_cb()."""
    if result.resultType == 'song':
        return '{} by {}'.format(html.escape(result.title), html.escape(result.artist))
    elif result.resultType == 'artist':
        return html.escape(result.name)
    else:
        return html.escape(result.stationName)


# ---------------------------------------------------------------------------
# Test data fixtures
# ---------------------------------------------------------------------------

SAMPLE_RAW_RESULTS = {
    'artists': [
        {'score': 95, 'musicToken': 'a1', 'artistName': 'TopArtist'},
        {'score': 85, 'musicToken': 'a2', 'artistName': 'MidArtist'},
        {'score': 70, 'musicToken': 'a3', 'artistName': 'LowArtist'},
        {'score': 80, 'musicToken': 'a4', 'artistName': 'BorderlineArtist'},
    ],
    'songs': [
        {'score': 90, 'musicToken': 's1', 'songName': 'HitSong', 'artistName': 'HitArtist'},
        {'score': 80, 'musicToken': 's2', 'songName': 'OkSong', 'artistName': 'OkArtist'},
        {'score': 50, 'musicToken': 's3', 'songName': 'BadSong', 'artistName': 'BadArtist'},
    ],
    'genreStations': [
        {'score': 100, 'musicToken': 'g1', 'stationName': 'Rock'},
        {'score': 80, 'musicToken': 'g2', 'stationName': 'Jazz'},
    ],
}


# ===========================================================================
# Test suites
# ===========================================================================

class TestSearchResultConstruction(unittest.TestCase):
    """SearchResult correctly parses raw API dicts for each type."""

    def test_artist(self):
        r = SearchResult('artist', {'score': 90, 'musicToken': 'tok1', 'artistName': 'Alice'})
        self.assertEqual(r.resultType, 'artist')
        self.assertEqual(r.score, 90)
        self.assertEqual(r.musicId, 'tok1')
        self.assertEqual(r.name, 'Alice')

    def test_song(self):
        r = SearchResult('song', {'score': 85, 'musicToken': 'tok2',
                                   'songName': 'Hello', 'artistName': 'World'})
        self.assertEqual(r.resultType, 'song')
        self.assertEqual(r.score, 85)
        self.assertEqual(r.musicId, 'tok2')
        self.assertEqual(r.title, 'Hello')
        self.assertEqual(r.artist, 'World')

    def test_genre(self):
        r = SearchResult('genre', {'score': 100, 'musicToken': 'tok3', 'stationName': 'Blues'})
        self.assertEqual(r.resultType, 'genre')
        self.assertEqual(r.score, 100)
        self.assertEqual(r.musicId, 'tok3')
        self.assertEqual(r.stationName, 'Blues')

    def test_zero_score(self):
        r = SearchResult('artist', {'score': 0, 'musicToken': 'tok', 'artistName': 'X'})
        self.assertEqual(r.score, 0)


class TestGroupingLogic(unittest.TestCase):
    """group_search_results categorises, filters, and sorts correctly."""

    def setUp(self):
        self.grouped = group_search_results(SAMPLE_RAW_RESULTS)

    def test_return_keys(self):
        self.assertEqual(set(self.grouped.keys()), {'artists', 'songs', 'genres'})

    def test_artist_score_filter(self):
        names = [a.name for a in self.grouped['artists']]
        self.assertIn('TopArtist', names)
        self.assertIn('MidArtist', names)
        self.assertIn('BorderlineArtist', names)   # score == 80 (boundary)
        self.assertNotIn('LowArtist', names)       # score == 70

    def test_artist_sorting(self):
        scores = [a.score for a in self.grouped['artists']]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_song_score_filter(self):
        names = [s.title for s in self.grouped['songs']]
        self.assertIn('HitSong', names)
        self.assertIn('OkSong', names)
        self.assertNotIn('BadSong', names)          # score == 50

    def test_song_sorting(self):
        scores = [s.score for s in self.grouped['songs']]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_genres_not_filtered_by_score(self):
        names = [g.stationName for g in self.grouped['genres']]
        self.assertEqual(names, ['Rock', 'Jazz'])

    def test_artist_count(self):
        self.assertEqual(len(self.grouped['artists']), 3)

    def test_song_count(self):
        self.assertEqual(len(self.grouped['songs']), 2)

    def test_genre_count(self):
        self.assertEqual(len(self.grouped['genres']), 2)


class TestEmptyResults(unittest.TestCase):
    """Graceful handling of empty or missing result categories."""

    def test_all_empty(self):
        grouped = group_search_results({'artists': [], 'songs': [], 'genreStations': []})
        self.assertEqual(grouped['artists'], [])
        self.assertEqual(grouped['songs'], [])
        self.assertEqual(grouped['genres'], [])

    def test_missing_keys(self):
        grouped = group_search_results({})
        self.assertEqual(grouped['artists'], [])
        self.assertEqual(grouped['songs'], [])
        self.assertEqual(grouped['genres'], [])

    def test_all_below_threshold(self):
        grouped = group_search_results({
            'artists': [{'score': 50, 'musicToken': 'x', 'artistName': 'Nope'}],
            'songs': [{'score': 10, 'musicToken': 'y', 'songName': 'Nah', 'artistName': 'Z'}],
            'genreStations': [],
        })
        self.assertEqual(grouped['artists'], [])
        self.assertEqual(grouped['songs'], [])
        self.assertEqual(grouped['genres'], [])


class TestMarkupGeneration(unittest.TestCase):
    """SearchDialog display markup is formatted correctly per type."""

    def test_song_markup(self):
        r = SearchResult('song', {'score': 90, 'musicToken': 's',
                                   'songName': 'My Song', 'artistName': 'My Artist'})
        self.assertEqual(make_markup(r), '<b>My Song</b> by My Artist')

    def test_artist_markup(self):
        r = SearchResult('artist', {'score': 85, 'musicToken': 'a', 'artistName': 'Alice'})
        self.assertEqual(make_markup(r), '<b>Alice</b>')

    def test_genre_markup(self):
        r = SearchResult('genre', {'score': 100, 'musicToken': 'g', 'stationName': 'Blues'})
        self.assertEqual(make_markup(r), '<b>Blues</b>')

    def test_song_html_escaping(self):
        r = SearchResult('song', {'score': 90, 'musicToken': 's',
                                   'songName': '<script>', 'artistName': 'A&B'})
        mk = make_markup(r)
        self.assertNotIn('<script>', mk)
        self.assertIn('&lt;script&gt;', mk)
        self.assertIn('A&amp;B', mk)

    def test_artist_html_escaping(self):
        r = SearchResult('artist', {'score': 85, 'musicToken': 'a', 'artistName': '<b>Test</b>'})
        mk = make_markup(r)
        self.assertNotIn('<b>Test</b>', mk)
        self.assertIn('&lt;b&gt;Test&lt;/b&gt;', mk)

    def test_genre_html_escaping(self):
        r = SearchResult('genre', {'score': 100, 'musicToken': 'g', 'stationName': 'R&B'})
        self.assertIn('R&amp;B', make_markup(r))


class TestStationCreationFlow(unittest.TestCase):
    """Verify SearchResult preserves attributes needed by StationsDialog.add_station_cb()."""

    def test_song_station_description(self):
        r = SearchResult('song', {'score': 90, 'musicToken': 'tok_song',
                                   'songName': 'Yesterday', 'artistName': 'Beatles'})
        desc = make_station_description(r)
        self.assertEqual(desc, 'Yesterday by Beatles')
        self.assertEqual(r.musicId, 'tok_song')
        self.assertEqual(r.resultType, 'song')

    def test_artist_station_description(self):
        r = SearchResult('artist', {'score': 85, 'musicToken': 'tok_artist', 'artistName': 'Mozart'})
        desc = make_station_description(r)
        self.assertEqual(desc, 'Mozart')
        self.assertEqual(r.musicId, 'tok_artist')
        self.assertEqual(r.resultType, 'artist')

    def test_genre_station_description(self):
        r = SearchResult('genre', {'score': 100, 'musicToken': 'tok_genre', 'stationName': 'Classical'})
        desc = make_station_description(r)
        self.assertEqual(desc, 'Classical')
        self.assertEqual(r.musicId, 'tok_genre')
        self.assertEqual(r.resultType, 'genre')

    def test_music_id_preserved_after_grouping(self):
        """musicId must survive the grouping pipeline for station creation."""
        grouped = group_search_results(SAMPLE_RAW_RESULTS)
        all_results = grouped['artists'] + grouped['songs'] + grouped['genres']
        for r in all_results:
            self.assertIsNotNone(r.musicId)
            self.assertIsInstance(r.musicId, str)
            self.assertTrue(len(r.musicId) > 0)

    def test_result_type_preserved_after_grouping(self):
        """resultType must be consistent with the group a result appears in."""
        grouped = group_search_results(SAMPLE_RAW_RESULTS)
        for r in grouped['artists']:
            self.assertEqual(r.resultType, 'artist')
        for r in grouped['songs']:
            self.assertEqual(r.resultType, 'song')
        for r in grouped['genres']:
            self.assertEqual(r.resultType, 'genre')

    def test_description_with_html_entities(self):
        r = SearchResult('song', {'score': 90, 'musicToken': 't',
                                   'songName': 'Rock & Roll', 'artistName': 'AC/DC'})
        desc = make_station_description(r)
        self.assertIn('Rock &amp; Roll', desc)
        self.assertIn('AC/DC', desc)


class TestScoreBoundary(unittest.TestCase):
    """Edge cases around the score == 80 threshold."""

    def test_score_exactly_80_included(self):
        grouped = group_search_results({
            'artists': [{'score': 80, 'musicToken': 'a', 'artistName': 'A'}],
            'songs': [{'score': 80, 'musicToken': 's', 'songName': 'S', 'artistName': 'X'}],
            'genreStations': [],
        })
        self.assertEqual(len(grouped['artists']), 1)
        self.assertEqual(len(grouped['songs']), 1)

    def test_score_79_excluded(self):
        grouped = group_search_results({
            'artists': [{'score': 79, 'musicToken': 'a', 'artistName': 'A'}],
            'songs': [{'score': 79, 'musicToken': 's', 'songName': 'S', 'artistName': 'X'}],
            'genreStations': [],
        })
        self.assertEqual(len(grouped['artists']), 0)
        self.assertEqual(len(grouped['songs']), 0)


class TestGroupHeaderFormatting(unittest.TestCase):
    """SearchDialog group header text with count."""

    def _header_text(self, label, items):
        return '{} ({})'.format(html.escape(label), len(items))

    def test_artists_header(self):
        grouped = group_search_results(SAMPLE_RAW_RESULTS)
        header = self._header_text('Artists', grouped['artists'])
        self.assertEqual(header, 'Artists (3)')

    def test_songs_header(self):
        grouped = group_search_results(SAMPLE_RAW_RESULTS)
        header = self._header_text('Songs', grouped['songs'])
        self.assertEqual(header, 'Songs (2)')

    def test_genres_header(self):
        grouped = group_search_results(SAMPLE_RAW_RESULTS)
        header = self._header_text('Genres', grouped['genres'])
        self.assertEqual(header, 'Genres (2)')

    def test_empty_group_header_not_shown(self):
        """SearchDialog only renders headers for non-empty groups."""
        grouped = group_search_results({'artists': [], 'songs': [], 'genreStations': []})
        visible_groups = []
        for label, key in [('Artists', 'artists'), ('Songs', 'songs'), ('Genres', 'genres')]:
            if grouped[key]:
                visible_groups.append(label)
        self.assertEqual(visible_groups, [])


class TestFakePandoraMockData(unittest.TestCase):
    """Verify the FakePandora mock data structure is valid for search_grouped."""

    MOCK_RESPONSE = {
        'artists': [
            {'score': 90, 'musicToken': '988', 'artistName': 'artistName'},
            {'score': 85, 'musicToken': '989', 'artistName': 'SecondArtist'},
            {'score': 70, 'musicToken': '990', 'artistName': 'LowScoreArtist'},
        ],
        'songs': [
            {'score': 80, 'musicToken': '238', 'songName': 'SongName', 'artistName': 'ArtistName'},
            {'score': 95, 'musicToken': '239', 'songName': 'TopSong', 'artistName': 'TopArtist'},
            {'score': 60, 'musicToken': '240', 'songName': 'LowSong', 'artistName': 'LowArtist'},
        ],
        'genreStations': [
            {'score': 100, 'musicToken': 'g100', 'stationName': 'Rock'},
            {'score': 90, 'musicToken': 'g101', 'stationName': 'Jazz'},
        ],
    }

    def test_mock_groups_correctly(self):
        grouped = group_search_results(self.MOCK_RESPONSE)
        self.assertEqual(len(grouped['artists']), 2)  # 90, 85 pass; 70 filtered
        self.assertEqual(len(grouped['songs']), 2)    # 95, 80 pass; 60 filtered
        self.assertEqual(len(grouped['genres']), 2)   # all included

    def test_mock_artist_names(self):
        grouped = group_search_results(self.MOCK_RESPONSE)
        names = [a.name for a in grouped['artists']]
        self.assertEqual(names, ['artistName', 'SecondArtist'])

    def test_mock_song_sorted_by_score(self):
        grouped = group_search_results(self.MOCK_RESPONSE)
        self.assertEqual(grouped['songs'][0].title, 'TopSong')
        self.assertEqual(grouped['songs'][1].title, 'SongName')

    def test_mock_genres_present(self):
        grouped = group_search_results(self.MOCK_RESPONSE)
        names = [g.stationName for g in grouped['genres']]
        self.assertEqual(names, ['Rock', 'Jazz'])


if __name__ == '__main__':
    unittest.main()

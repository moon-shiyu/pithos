# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Tests for search result grouping logic

import unittest
import sys
import os

# Add the project root to sys.path so we can import pithos modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pithos.pandora.pandora import SearchResult, group_search_results, SEARCH_RESULT_TYPE_ORDER, SEARCH_RESULT_TYPE_LABELS


def make_artist(name, score=90, token='tok_a'):
    return SearchResult('artist', {'artistName': name, 'score': score, 'musicToken': token})

def make_song(title, artist, score=80, token='tok_s'):
    return SearchResult('song', {'songName': title, 'artistName': artist, 'score': score, 'musicToken': token})

def make_genre(station_name, score=50, token='tok_g'):
    return SearchResult('genre', {'stationName': station_name, 'score': score, 'musicToken': token})


class TestSearchResult(unittest.TestCase):
    """Test SearchResult construction for all three result types."""

    def test_artist_result(self):
        r = make_artist('Radiohead', score=95, token='art1')
        self.assertEqual(r.resultType, 'artist')
        self.assertEqual(r.name, 'Radiohead')
        self.assertEqual(r.score, 95)
        self.assertEqual(r.musicId, 'art1')

    def test_song_result(self):
        r = make_song('Creep', 'Radiohead', score=88, token='song1')
        self.assertEqual(r.resultType, 'song')
        self.assertEqual(r.title, 'Creep')
        self.assertEqual(r.artist, 'Radiohead')
        self.assertEqual(r.score, 88)
        self.assertEqual(r.musicId, 'song1')

    def test_genre_result(self):
        r = make_genre('Alt Rock Radio', score=60, token='gen1')
        self.assertEqual(r.resultType, 'genre')
        self.assertEqual(r.stationName, 'Alt Rock Radio')
        self.assertEqual(r.score, 60)
        self.assertEqual(r.musicId, 'gen1')


class TestGroupSearchResults(unittest.TestCase):
    """Test the group_search_results function."""

    def test_empty_results(self):
        groups = group_search_results([])
        self.assertEqual(groups, [])

    def test_all_three_types(self):
        results = [
            make_artist('Artist A', score=95),
            make_song('Song B', 'Someone', score=90),
            make_genre('Genre Station', score=50),
        ]
        groups = group_search_results(results)
        self.assertEqual(len(groups), 3)
        labels = [label for label, _ in groups]
        self.assertEqual(labels, ['Artists', 'Songs', 'Stations'])

    def test_display_order_is_artists_songs_stations(self):
        """Groups always appear in order: Artists, Songs, Stations regardless of input order."""
        results = [
            make_genre('Pop Radio', score=99),
            make_song('Hit Song', 'Singer', score=50),
            make_artist('Cool Band', score=70),
        ]
        groups = group_search_results(results)
        labels = [label for label, _ in groups]
        self.assertEqual(labels, ['Artists', 'Songs', 'Stations'])

    def test_empty_groups_omitted(self):
        """If a result type has no entries, its group is not included."""
        results = [
            make_artist('Only Artist', score=90),
            make_song('Only Song', 'Only Singer', score=85),
        ]
        groups = group_search_results(results)
        self.assertEqual(len(groups), 2)
        labels = [label for label, _ in groups]
        self.assertEqual(labels, ['Artists', 'Songs'])
        self.assertNotIn('Stations', labels)

    def test_single_type_only(self):
        results = [make_song('A', 'X', score=80), make_song('B', 'Y', score=70)]
        groups = group_search_results(results)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0][0], 'Songs')
        self.assertEqual(len(groups[0][1]), 2)

    def test_preserves_order_within_group(self):
        """Results within a group maintain their input order (typically score-sorted)."""
        results = [
            make_artist('High Score', score=99),
            make_artist('Mid Score', score=85),
            make_artist('Low Score', score=80),
        ]
        groups = group_search_results(results)
        artists = groups[0][1]
        self.assertEqual(artists[0].name, 'High Score')
        self.assertEqual(artists[1].name, 'Mid Score')
        self.assertEqual(artists[2].name, 'Low Score')

    def test_multiple_items_per_group(self):
        results = [
            make_artist('A1', score=95, token='a1'),
            make_artist('A2', score=90, token='a2'),
            make_song('S1', 'X', score=88, token='s1'),
            make_song('S2', 'Y', score=82, token='s2'),
            make_song('S3', 'Z', score=80, token='s3'),
            make_genre('G1', score=50, token='g1'),
        ]
        groups = group_search_results(results)
        self.assertEqual(len(groups[0][1]), 2)  # 2 artists
        self.assertEqual(len(groups[1][1]), 3)  # 3 songs
        self.assertEqual(len(groups[2][1]), 1)  # 1 genre

    def test_unknown_result_type_excluded(self):
        """Results with unrecognized types are silently ignored."""
        unknown = SearchResult.__new__(SearchResult)
        unknown.resultType = 'podcast'
        unknown.score = 90
        unknown.musicId = 'pod1'

        results = [
            make_artist('Real Artist', score=90),
            unknown,
        ]
        groups = group_search_results(results)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0][0], 'Artists')
        self.assertEqual(len(groups[0][1]), 1)


class TestGroupSearchResultsWithFakeData(unittest.TestCase):
    """Integration test using data shaped like the Pandora API / FakePandora responses."""

    def _simulate_search(self, api_response):
        """Simulate what Pandora.search() does: build SearchResults and sort by score."""
        results = [SearchResult('artist', i) for i in api_response['artists'] if i['score'] >= 80]
        results += [SearchResult('song', i) for i in api_response['songs'] if i['score'] >= 80]
        results += [SearchResult('genre', i) for i in api_response.get('genreStations', [])]
        results.sort(key=lambda i: i.score, reverse=True)
        return results

    def test_fake_pandora_response(self):
        """Test grouping with the FakePandora response data."""
        fake_response = {
            'artists': [
                {'score': 90, 'musicToken': '988', 'artistName': "artistName"},
                {'score': 85, 'musicToken': '989', 'artistName': "Another Artist"},
            ],
            'songs': [
                {'score': 80, 'musicToken': '238', 'songName': "SongName", 'artistName': "ArtistName"},
                {'score': 95, 'musicToken': '239', 'songName': "Top Hit", 'artistName': "Star Singer"},
            ],
            'genreStations': [
                {'score': 50, 'musicToken': 'gen1', 'stationName': "Pop Hits Radio"},
                {'score': 40, 'musicToken': 'gen2', 'stationName': "Rock Classics Radio"},
            ],
        }

        results = self._simulate_search(fake_response)
        groups = group_search_results(results)

        # All three groups present
        self.assertEqual(len(groups), 3)
        labels = [l for l, _ in groups]
        self.assertEqual(labels, ['Artists', 'Songs', 'Stations'])

        # Check group contents
        artists = groups[0][1]
        songs = groups[1][1]
        genres = groups[2][1]

        self.assertEqual(len(artists), 2)
        self.assertEqual(len(songs), 2)
        self.assertEqual(len(genres), 2)

        # Check artist details
        self.assertEqual(artists[0].name, 'artistName')
        self.assertEqual(artists[0].score, 90)
        self.assertEqual(artists[1].name, 'Another Artist')

        # Check song details
        self.assertEqual(songs[0].title, 'Top Hit')
        self.assertEqual(songs[0].score, 95)
        self.assertEqual(songs[1].title, 'SongName')

        # Check genre details
        self.assertEqual(genres[0].stationName, 'Pop Hits Radio')
        self.assertEqual(genres[1].stationName, 'Rock Classics Radio')

    def test_missing_genre_stations(self):
        """Test that missing genreStations key (old FakePandora) doesn't crash."""
        fake_response = {
            'artists': [{'score': 90, 'musicToken': '1', 'artistName': "Solo"}],
            'songs': [{'score': 80, 'musicToken': '2', 'songName': "Track", 'artistName': "Solo"}],
        }

        results = self._simulate_search(fake_response)
        groups = group_search_results(results)

        self.assertEqual(len(groups), 2)
        labels = [l for l, _ in groups]
        self.assertNotIn('Stations', labels)

    def test_score_filtering(self):
        """Artists and songs below score 80 are filtered out by search()."""
        fake_response = {
            'artists': [
                {'score': 90, 'musicToken': '1', 'artistName': "Good Match"},
                {'score': 50, 'musicToken': '2', 'artistName': "Bad Match"},
            ],
            'songs': [
                {'score': 79, 'musicToken': '3', 'songName': "Almost", 'artistName': "X"},
                {'score': 80, 'musicToken': '4', 'songName': "Exact", 'artistName': "Y"},
            ],
            'genreStations': [
                {'score': 10, 'musicToken': '5', 'stationName': "Low Score Genre"},
            ],
        }

        results = self._simulate_search(fake_response)
        groups = group_search_results(results)

        # Only 1 artist passes (score >= 80)
        artist_group = [g for l, g in groups if l == 'Artists']
        self.assertEqual(len(artist_group[0]), 1)
        self.assertEqual(artist_group[0][0].name, 'Good Match')

        # Only 1 song passes (score >= 80)
        song_group = [g for l, g in groups if l == 'Songs']
        self.assertEqual(len(song_group[0]), 1)
        self.assertEqual(song_group[0][0].title, 'Exact')

        # Genre stations have no score filter
        genre_group = [g for l, g in groups if l == 'Stations']
        self.assertEqual(len(genre_group[0]), 1)

    def test_empty_search_results(self):
        """All categories empty after filtering."""
        fake_response = {
            'artists': [{'score': 10, 'musicToken': '1', 'artistName': "Low"}],
            'songs': [{'score': 20, 'musicToken': '2', 'songName': "Low", 'artistName': "X"}],
            'genreStations': [],
        }

        results = self._simulate_search(fake_response)
        groups = group_search_results(results)
        self.assertEqual(groups, [])


class TestConfigConstants(unittest.TestCase):
    """Verify the grouping configuration constants."""

    def test_type_order(self):
        self.assertEqual(SEARCH_RESULT_TYPE_ORDER, ['artist', 'song', 'genre'])

    def test_all_types_have_labels(self):
        for t in SEARCH_RESULT_TYPE_ORDER:
            self.assertIn(t, SEARCH_RESULT_TYPE_LABELS)

    def test_labels(self):
        self.assertEqual(SEARCH_RESULT_TYPE_LABELS['artist'], 'Artists')
        self.assertEqual(SEARCH_RESULT_TYPE_LABELS['song'], 'Songs')
        self.assertEqual(SEARCH_RESULT_TYPE_LABELS['genre'], 'Stations')


if __name__ == '__main__':
    unittest.main()

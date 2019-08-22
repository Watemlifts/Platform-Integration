"""The tests for the Reddit platform."""
import copy
import unittest
from unittest.mock import patch

from homeassistant.components.reddit.sensor import (
    DOMAIN, ATTR_SUBREDDIT, ATTR_POSTS, CONF_SORT_BY,
    ATTR_ID, ATTR_URL, ATTR_TITLE, ATTR_SCORE, ATTR_COMMENTS_NUMBER,
    ATTR_CREATED, ATTR_BODY)
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, CONF_MAXIMUM)
from homeassistant.setup import setup_component

from tests.common import (get_test_home_assistant,
                          MockDependency)


VALID_CONFIG = {
    'sensor': {
        'platform': DOMAIN,
        'client_id':  'test_client_id',
        'client_secret': 'test_client_secret',
        CONF_USERNAME: 'test_username',
        CONF_PASSWORD: 'test_password',
        'subreddits': ['worldnews', 'news'],

    }
}

VALID_LIMITED_CONFIG = {
    'sensor': {
        'platform': DOMAIN,
        'client_id':  'test_client_id',
        'client_secret': 'test_client_secret',
        CONF_USERNAME: 'test_username',
        CONF_PASSWORD: 'test_password',
        'subreddits': ['worldnews', 'news'],
        CONF_MAXIMUM: 1
    }
}


INVALID_SORT_BY_CONFIG = {
    'sensor': {
        'platform': DOMAIN,
        'client_id':  'test_client_id',
        'client_secret': 'test_client_secret',
        CONF_USERNAME: 'test_username',
        CONF_PASSWORD: 'test_password',
        'subreddits': ['worldnews', 'news'],
        'sort_by': 'invalid_sort_by'
    }
}


class ObjectView():
    """Use dict properties as attributes."""

    def __init__(self, d):
        """Set dict as internal dict."""
        self.__dict__ = d


MOCK_RESULTS = {
    'results': [
        ObjectView({
            'id': 0,
            'url': 'http://example.com/1',
            'title': 'example1',
            'score': '1',
            'num_comments': '1',
            'created': '',
            'selftext': 'example1 selftext'
        }),
        ObjectView({
            'id': 1,
            'url': 'http://example.com/2',
            'title': 'example2',
            'score': '2',
            'num_comments': '2',
            'created': '',
            'selftext': 'example2 selftext'
        })
    ]
}

MOCK_RESULTS_LENGTH = len(MOCK_RESULTS['results'])


class MockPraw():
    """Mock class for tmdbsimple library."""

    def __init__(self, client_id: str, client_secret:
                 str, username: str, password: str,
                 user_agent: str):
        """Add mock data for API return."""
        self._data = MOCK_RESULTS

    def subreddit(self, subreddit: str):
        """Return an instance of a sunbreddit."""
        return MockSubreddit(subreddit, self._data)


class MockSubreddit():
    """Mock class for a subreddit instance."""

    def __init__(self, subreddit: str, data):
        """Add mock data for API return."""
        self._subreddit = subreddit
        self._data = data

    def top(self, limit):
        """Return top posts for a subreddit."""
        return self._return_data(limit)

    def controversial(self, limit):
        """Return controversial posts for a subreddit."""
        return self._return_data(limit)

    def hot(self, limit):
        """Return hot posts for a subreddit."""
        return self._return_data(limit)

    def new(self, limit):
        """Return new posts for a subreddit."""
        return self._return_data(limit)

    def _return_data(self, limit):
        """Test method to return modified data."""
        data = copy.deepcopy(self._data)
        return data['results'][:limit]


class TestRedditSetup(unittest.TestCase):
    """Test the Reddit platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @MockDependency('praw')
    @patch('praw.Reddit', new=MockPraw)
    def test_setup_with_valid_config(self, mock_praw):
        """Test the platform setup with movie configuration."""
        setup_component(self.hass, 'sensor', VALID_CONFIG)

        state = self.hass.states.get('sensor.reddit_worldnews')
        assert int(state.state) == MOCK_RESULTS_LENGTH

        state = self.hass.states.get('sensor.reddit_news')
        assert int(state.state) == MOCK_RESULTS_LENGTH

        assert state.attributes[ATTR_SUBREDDIT] == 'news'

        assert state.attributes[ATTR_POSTS][0] == {
            ATTR_ID: 0,
            ATTR_URL: 'http://example.com/1',
            ATTR_TITLE: 'example1',
            ATTR_SCORE: '1',
            ATTR_COMMENTS_NUMBER: '1',
            ATTR_CREATED: '',
            ATTR_BODY: 'example1 selftext'
        }

        assert state.attributes[CONF_SORT_BY] == 'hot'

    @MockDependency('praw')
    @patch('praw.Reddit', new=MockPraw)
    def test_setup_with_invalid_config(self, mock_praw):
        """Test the platform setup with invalid movie configuration."""
        setup_component(self.hass, 'sensor', INVALID_SORT_BY_CONFIG)
        assert not self.hass.states.get('sensor.reddit_worldnews')

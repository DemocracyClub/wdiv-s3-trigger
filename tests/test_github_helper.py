import io
import json
import sys
from unittest import TestCase, mock
import responses
from trigger.github_helpers import raise_github_issue


class GitHubHelperTests(TestCase):
    def setUp(self):
        sys.stdout = io.StringIO()
        pass

    def tearDown(self):
        sys.stdout = sys.__stdout__
        pass

    @mock.patch(
        'trigger.github_helpers.gss_to_council',
        lambda x: 'Piddleton Parish Council'
    )
    def test_raise_issue_without_key(self):
        m = mock.Mock()
        with mock.patch("trigger.github_helpers.requests.post", m):
            report = {'gss': 'X01000000', 'ems': 'Xpress'}
            self.assertIsNone(raise_github_issue(None, 'chris48s/does-not-exist', report))
            m.assert_not_called()

    @mock.patch(
        'trigger.github_helpers.gss_to_council',
        lambda x: 'Piddleton Parish Council'
    )
    @responses.activate
    def test_raise_issue_with_key(self):
        repo = 'chris48s/does-not-exist'
        key = 'f00b42'
        responses.add(
            responses.POST,
            f'https://api.github.com/repos/{repo}/issues',
            json={'url': f'https://github.com/{repo}/issues/1'},
            status=200,
        )
        report = {'gss': 'X01000000', 'ems': 'Xpress'}

        issue_link = raise_github_issue(key, repo, report)
        self.assertEqual(
            f'https://github.com/{repo}/issues/1',
            issue_link
        )
        self.assertEqual(
            f'https://api.github.com/repos/{repo}/issues',
            responses.calls[0].request.url
        )
        self.assertEqual(
            f'token {key}',
            responses.calls[0].request.headers['Authorization']
        )
        self.assertDictEqual(
            {"title": "Import X01000000-Piddleton Parish Council", "body": "EMS: Xpress", "labels": ["Data Import", "ready"]},
            json.loads(responses.calls[0].request.body)
        )

import io
import json
import sys
from unittest import TestCase, mock

import responses

from trigger.github_helpers import raise_github_issue


class GitHubHelperTests(TestCase):
    def setUp(self):
        responses.start()
        responses.add(
            responses.GET,
            f"https://wheredoivote.co.uk/api/beta/councils/X01000000.json",
            status=200,
            body=json.dumps({"name": "Piddleton Parish Council"}),
        )
        sys.stdout = io.StringIO()

    def tearDown(self):
        responses.stop()
        responses.reset()
        sys.stdout = sys.__stdout__

    def test_raise_issue_without_key(self):
        m = mock.Mock()
        with mock.patch("trigger.github_helpers.requests.post", m):
            report = {"gss": "X01000000", "ems": "Xpress"}
            self.assertIsNone(
                raise_github_issue(None, "chris48s/does-not-exist", report)
            )
            m.assert_not_called()

    def test_raise_issue_with_key(self):
        repo = "chris48s/does-not-exist"
        key = "f00b42"
        responses.add(
            responses.POST,
            f"https://api.github.com/repos/{repo}/issues",
            json={"url": f"https://github.com/{repo}/issues/1"},
            status=200,
        )
        report = {"gss": "X01000000", "ems": "Xpress"}

        issue_link = raise_github_issue(key, repo, report)
        github_call = responses.calls[1]
        self.assertEqual(f"https://github.com/{repo}/issues/1", issue_link)
        self.assertEqual(
            f"https://api.github.com/repos/{repo}/issues", github_call.request.url
        )
        self.assertEqual(f"token {key}", github_call.request.headers["Authorization"])
        self.assertDictEqual(
            {
                "title": "Import X01000000-Piddleton Parish Council",
                "body": "EMS: Xpress",
                "labels": ["Data Import", "ready"],
            },
            json.loads(github_call.request.body),
        )

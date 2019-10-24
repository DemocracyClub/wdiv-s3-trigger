import requests
from requests.exceptions import HTTPError


class GitHubIssue:
    def __init__(self, api_key, repo, title, body):
        self.api_key = api_key
        self.url = f"https://api.github.com/repos/{repo}/issues"
        self.payload = {
            "title": title,
            "body": body,
            "labels": ["Data Import", "ready"],
        }

    def post(self):

        # TODO: Call
        # https://api.github.com/repos/DemocracyClub/UK-Polling-Stations/issues?state=open
        # if there is already an OPEN issue with the tile {title}
        # post an issue comment saying "updated data available"
        # instead of raising a duplicate issue

        r = requests.post(
            self.url,
            json=self.payload,
            headers={"Authorization": f"token {self.api_key}"},
        )
        try:
            r.raise_for_status()
        except HTTPError:
            # TODO: what should we do here if we can't raise an issue?
            raise
        issue = r.json()
        # TODO: issue['number'] ??
        return issue["url"]

    def debug(self):
        print("GITHUB_API_KEY not set")
        print(self.url)
        print(self.payload)
        print("---")
        return None

    def raise_issue(self):
        if self.api_key:
            return self.post()
        return self.debug()


def raise_github_issue(api_key, repo, report):
    title = f"Import {report['gss']}-{report['council_name']}"
    try:
        # TODO: put more info from the report in the GH issue?
        body = f"EMS: {report['ems']}"
    except KeyError:
        body = ""
    issue = GitHubIssue(api_key, repo, title, body)
    return issue.raise_issue()

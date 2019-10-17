import io
import json
import os
import sys
from unittest import TestCase

import boto3
import responses
from moto import mock_s3

from trigger.handler import main

trigger_payload = json.loads(
    """{
  "Records": [
    {
      "eventVersion": "2.0",
      "eventSource": "aws:s3",
      "awsRegion": "eu-west-1",
      "eventTime": "1970-01-01T00:00:00.000Z",
      "eventName": "ObjectCreated:Put",
      "userIdentity": {
        "principalId": "EXAMPLE"
      },
      "requestParameters": {
        "sourceIPAddress": "127.0.0.1"
      },
      "responseElements": {
        "x-amz-request-id": "EXAMPLE123456789",
        "x-amz-id-2": "EXAMPLE123/5678abcdefghijklambdaisawesome/mnopqrstuvwxyzABCDEFGH"
      },
      "s3": {
        "s3SchemaVersion": "1.0",
        "configurationId": "testConfigRule",
        "bucket": {
          "name": "fakebucket",
          "ownerIdentity": {
            "principalId": "EXAMPLE"
          },
          "arn": "arn:aws:s3:::fakebucket"
        },
        "object": {
          "key": "X01000000/2019-09-30T17%3A00%3A02.396833/data",
          "size": 1024,
          "eTag": "0123456789abcdef0123456789abcdef",
          "sequencer": "0A1B2C3D4E5F678901"
        }
      }
    }
  ]
}"""
)


class HandlerTests(TestCase):
    """
    This is a very high-level integration test touching most of the codebase.
    In general, this codebase reaches out to a lot of external services,
    so there is a lot of mocking to be done.

    As we add additional interactions and associated credentials,
    its important to remember to remember to add mocks for them.
    Responses should help wit this by throwing
    `Connection refused by Responses: POST https://thing.i/didnt/mock/yet doesn't match Responses Mock`
    """

    def setUp(self):
        # ensure we definitely don't have any real credentials set for AWS
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SECURITY_TOKEN"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"

        # don't send errors to senty under test
        os.environ["SENTRY_DSN"] = ""

        # set fake credentials for services
        # we're going to have mocked interactions with
        self.repo = "chris48s/does-not-exist"
        os.environ["GITHUB_REPO"] = self.repo
        os.environ["GITHUB_API_KEY"] = "testing"
        os.environ["WDIV_API_KEY"] = "testing"

        # set up pretend s3 bucket
        self.s3mock = mock_s3()
        self.s3mock.start()
        self.conn = boto3.client("s3")
        self.conn.create_bucket(Bucket="fakebucket")

        # mock all the HTTP responses we're going to make
        responses.start()
        responses.add(
            responses.GET,
            f"https://wheredoivote.co.uk/api/beta/councils/X01000000.json",
            status=200,
            body=json.dumps({"name": "Piddleton Parish Council"}),
        )
        responses.add(
            responses.POST,
            f"https://api.github.com/repos/{self.repo}/issues",
            json={"url": f"https://github.com/{self.repo}/issues/1"},
            status=200,
        )
        responses.add(
            responses.POST,
            "https://wheredoivote.co.uk/api/doesnt/exist/yet",
            json={},
            status=200,
        )

        sys.stdout = io.StringIO()

    def tearDown(self):
        responses.stop()
        responses.reset()
        self.s3mock.stop()
        sys.stdout = sys.__stdout__

    def load_fixture(self, filename):
        # load a fixture into our pretend S3 bucket
        guess_content_type = (
            lambda filename: "text/tab-separated-values"
            if filename.endswith((".tsv", ".TSV"))
            else "text/csv"
        )
        fixture = open(f"tests/fixtures/{filename}", "rb").read()
        self.conn.put_object(
            Bucket="fakebucket",
            Key="X01000000/2019-09-30T17:00:02.396833/data",
            Body=fixture,
            ContentType=guess_content_type(filename),
        )

    def test_valid(self):
        self.load_fixture("ems-idox-eros.csv")

        main(trigger_payload, None)

        self.assertEqual(3, len(responses.calls))
        self.assertEqual(
            f"https://api.github.com/repos/{self.repo}/issues",
            responses.calls[1].request.url,
        )
        self.assertEqual(
            "https://wheredoivote.co.uk/api/doesnt/exist/yet",
            responses.calls[2].request.url,
        )
        expected_dict = {
            "csv_valid": True,
            "csv_rows": 10,
            "ems": "Idox Eros (Halarose)",
            "errors": [],
            "gh_issue": f"https://github.com/{self.repo}/issues/1",
            "gss": "X01000000",
            "timestamp": "2019-09-30T17:00:02.396833",
        }
        self.assertDictEqual(expected_dict, json.loads(responses.calls[2].request.body))

    def test_invalid(self):
        self.load_fixture("incomplete-file.CSV")

        main(trigger_payload, None)

        self.assertEqual(1, len(responses.calls))
        self.assertEqual(
            "https://wheredoivote.co.uk/api/doesnt/exist/yet",
            responses.calls[0].request.url,
        )
        expected_dict = {
            "csv_valid": False,
            "csv_rows": 10,
            "ems": "Xpress DC",
            "errors": ["Incomplete file: Expected 38 columns on row 10 found 7"],
            "gh_issue": None,
            "gss": "X01000000",
            "timestamp": "2019-09-30T17:00:02.396833",
        }
        self.assertDictEqual(expected_dict, json.loads(responses.calls[0].request.body))
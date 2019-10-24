import json
import os
import urllib.parse

import boto3
import sentry_sdk

from .csv_helpers import get_csv_report, get_object_report
from .github_helpers import raise_github_issue
from .wdiv_helpers import gss_to_council, submit_report


def register_env():
    SENTRY_DSN = os.getenv("SENTRY_DSN", "")
    if SENTRY_DSN:
        sentry_sdk.init(SENTRY_DSN)
    return {
        "SENTRY_DSN": SENTRY_DSN,
        "GITHUB_REPO": os.getenv("GITHUB_REPO", ""),
        "GITHUB_API_KEY": os.getenv("GITHUB_API_KEY", ""),
        "WDIV_API_KEY": os.getenv("WDIV_API_KEY", ""),
        "FINAL_BUCKET_NAME": os.getenv("FINAL_BUCKET_NAME", ""),
    }


def main(event, context):
    CONSTANTS = register_env()

    s3 = boto3.client("s3")
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(
        event["Records"][0]["s3"]["object"]["key"], encoding="utf-8"
    )
    response = s3.get_object(Bucket=bucket, Key=key)

    """
    TODO: This isn't going to work well for Democracy Counts
    because we're just processing one file at a time.

    Maybe if its Democracy Counts, we can submit
    { 'errors': [ 'expected 2 files, found 1' ] }
    the first time. Then the second time, we can update that to
    { 'valid': True } when we pick up the second one?
    """

    path = key.split("/")
    report = {
        "csv_valid": False,
        "csv_rows": None,
        "ems": "unknown",
        "errors": [],
        "gss": path[0],
        "timestamp": path[1],
        "gh_issue": None,
    }

    report = {**report, **get_object_report(response)}

    if not report["errors"]:
        report = {**report, **get_csv_report(response)}

    report["council_name"] = gss_to_council(report["gss"])

    if report["csv_valid"]:
        s3.copy({"Bucket": bucket, "Key": key}, CONSTANTS["FINAL_BUCKET_NAME"], key)
        issue = raise_github_issue(
            CONSTANTS["GITHUB_API_KEY"], CONSTANTS["GITHUB_REPO"], report
        )
        report["gh_issue"] = issue
        report_path = "/".join(path[:-1]) + "/report.json"
        s3.put_object(
            Bucket=CONSTANTS["FINAL_BUCKET_NAME"],
            Key=report_path,
            Body=json.dumps(report, indent=2),
            ContentType="application/json",
        )
        print("success")
    else:
        ses = boto3.client("ses")
        reasons = "\n".join(report["errors"])
        council = f"{report['gss']}-{report['council_name']}"
        response = ses.send_email(
            Source="pollingstations@democracyclub.org.uk",
            Destination={"ToAddresses": ["pollingstations@democracyclub.org.uk"]},
            Message={
                "Subject": {
                    "Data": f"Error with data for council {council}",
                    "Charset": "utf-8",
                },
                "Body": {
                    "Text": {
                        "Data": f"Data for council {council} "
                        f"failed because:\n{reasons}\n\nPlease follow up.",
                        "Charset": "utf-8",
                    }
                },
            },
        )
        print("failure")

    submit_report(CONSTANTS["WDIV_API_KEY"], report)

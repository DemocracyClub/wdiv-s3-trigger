import json
import os
import urllib.parse
from pathlib import PurePath

import boto3
import botocore
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
        "AWS_REGION": os.getenv("AWS_REGION", ""),
        "ERROR_REPORT_EMAIL": os.getenv("ERROR_REPORT_EMAIL", ""),
    }


def get_file_report(s3, bucket, key):
    report = {
        "csv_valid": False,
        "csv_rows": None,
        "ems": "unknown",
        "errors": [],
        "key": key,
    }

    obj = s3.get_object(Bucket=bucket, Key=key)
    report = {**report, **get_object_report(obj)}

    if not report["errors"]:
        report = {**report, **get_csv_report(obj)}

    return report


def get_report(s3, bucket, key):
    path = PurePath(key)
    prefix = str(path.parent)

    report = {
        "gss": path.parts[0],
        "council_name": gss_to_council(path.parts[0]),
        "timestamp": path.parts[1],
        "gh_issue": None,
        "files": [],
    }

    objects = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

    files = [
        obj["Key"]
        for obj in objects["Contents"]
        if obj["Key"] != prefix
        and obj["Key"] != f"{prefix}/"
        and "report.json" not in obj["Key"]
    ]

    for f in files:
        report["files"].append(get_file_report(s3, bucket, f))

    return report


def all_files_valid(files):
    return sum(1 if f["csv_valid"] else 0 for f in files) == len(files)


def get_email_text(report):
    text = ""
    errors = {f["key"]: "\n".join(f["errors"]) for f in report["files"] if f["errors"]}
    for key, error in errors.items():
        text = text + f"\n{key}:\n{error}\n"
    return text


def send_error_email(ses, report, email_address):
    reasons = get_email_text(report)
    council = f"{report['gss']}-{report['council_name']}"
    ses.send_email(
        Source="pollingstations@democracyclub.org.uk",
        Destination={"ToAddresses": [email_address]},
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


def sync_report_to_s3(s3, bucket, prefix, report):
    report_path = f"{prefix}/report.json"
    try:
        # Account for the situation where we're processing multiple files
        # if there's already a report.json and it has more files in it
        # than the new one we're trying to write, assume an out-of-order
        # delivery has happened (entirely possible) return early
        # and leave the existing report in place.
        resp = s3.get_object(Bucket=bucket, Key=report_path)
        old_report = json.loads(resp["Body"].read())
        if len(old_report["files"]) >= len(report["files"]):
            return
        # Only overwrite the old report with the new report
        # if the new one has more stuff in it
    except botocore.exceptions.ClientError:
        pass

    s3.put_object(
        Bucket=bucket,
        Key=report_path,
        Body=json.dumps(report, indent=2),
        ContentType="application/json",
    )


def main(event, context):
    CONSTANTS = register_env()

    s3 = boto3.client("s3")
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(
        event["Records"][0]["s3"]["object"]["key"], encoding="utf-8"
    )
    path = PurePath(key)
    prefix = str(path.parent)

    report = get_report(s3, bucket, key)
    surpress_email = False

    if len(report["files"]) == 1 and report["files"][0]["ems"] == "Democracy Counts":
        if len(report["files"][0]["errors"]) == 0:
            # If the only error is that EMS is Democracy Counts and we've only
            # got one file, don't send an email notification about this problem.
            # Otherwise, we'll generate an email notification every time we
            # process file 1 of 2.
            surpress_email = True
        report["files"][0]["csv_valid"] = False
        report["files"][0]["errors"].append("Expected 2 files, found 1")

    if all_files_valid(report["files"]):
        # copy all the files from the temp bucket to the final bucket
        for f in report["files"]:
            s3.copy(
                {"Bucket": bucket, "Key": f["key"]},
                CONSTANTS["FINAL_BUCKET_NAME"],
                f["key"],
            )

        issue = raise_github_issue(
            CONSTANTS["GITHUB_API_KEY"], CONSTANTS["GITHUB_REPO"], report
        )
        report["gh_issue"] = issue

        sync_report_to_s3(s3, CONSTANTS["FINAL_BUCKET_NAME"], prefix, report)
        print("success")
    else:
        ses = boto3.client("ses", CONSTANTS["AWS_REGION"])
        if not surpress_email and CONSTANTS["ERROR_REPORT_EMAIL"]:
            send_error_email(ses, report, CONSTANTS["ERROR_REPORT_EMAIL"])
        print("failure")

    submit_report(CONSTANTS["WDIV_API_KEY"], report)

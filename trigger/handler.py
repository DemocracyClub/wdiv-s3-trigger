import os
import urllib.parse
import boto3
import sentry_sdk
from .csv_helpers import get_csv_report
from .github_helpers import raise_github_issue


s3 = boto3.client('s3')
CONSTANTS = {
    'SENTRY_DSN': os.getenv('SENTRY_DSN', ''),

    'GITHUB_REPO': os.getenv('GITHUB_REPO', ''),
    'GITHUB_API_KEY': os.getenv('GITHUB_API_KEY', ''),
    'WDIV_API_KEY': os.getenv('WDIV_API_KEY', ''),
}
if CONSTANTS['SENTRY_DSN']:
    sentry_sdk.init(CONSTANTS['SENTRY_DSN'])


def get_object_report(response):
    if response['ContentLength'] < 1024:
        return {'errors': ['Expected file to be at least 1KB']}
    if response['ContentLength'] > 150000000:
        return {'errors': ['Expected file to be under 150MB']}
    if response['ContentType'] not in ('text/tab-separated-values', 'text/csv'):
        return {'errors': [f"Unexpected file type {response['ContentType']}"]}
    return {'errors': []}


def submit_report(wdiv_api_key, report):
    wdiv_url = 'https://wheredoivote.co.uk/api/doesnt/exist/yet'  # TODO
    if wdiv_api_key:
        r = requests.post(self.url,
            json=report,
            headers={'Authorization': f'Token {wdiv_api_key}'}
        )
        r.raise_for_status()
    else:
        print('WDIV_API_KEY not set')
        print(wdiv_url)
        print(report)
        print('---')


def main(event, context):
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(
        event['Records'][0]['s3']['object']['key'], encoding='utf-8'
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

    path = key.split('/')
    report = {
        'csv_valid': False,
        'csv_rows': None,
        'ems': 'unknown',
        'errors': [],
        'gss': path[0],
        'timestamp': path[1],
        'gh_issue': None,
    }

    report = {**report, **get_object_report(response)}

    if not report['errors']:
        report = {**report, **get_csv_report(response)}

    if report['csv_valid']:
        # TODO: copy the file from temp bucket to real bucket

        issue = raise_github_issue(
            CONSTANTS['GITHUB_API_KEY'],
            CONSTANTS['GITHUB_REPO'],
            report
        )
        report['gh_issue'] = issue
    else:
        # TODO: email pollingstations@democracyclub.org.uk
        print("oh noes! :(")

    submit_report(CONSTANTS['WDIV_API_KEY'], report)

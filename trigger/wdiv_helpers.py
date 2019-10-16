import requests


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

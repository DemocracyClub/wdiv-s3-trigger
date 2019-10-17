import requests


def gss_to_council(gss):
    r = requests.get(f'https://wheredoivote.co.uk/api/beta/councils/{gss}.json')
    try:
        r.raise_for_status()
        council = r.json()
        return council['name']
    except (HTTPError, KeyError):
        # if we can't get the name,
        # raising the issue with only a GSS code
        # isn't the end of the world
        return gss


def submit_report(wdiv_api_key, report):
    wdiv_url = 'https://wheredoivote.co.uk/api/doesnt/exist/yet'  # TODO
    if wdiv_api_key:
        r = requests.post(wdiv_url,
            json=report,
            headers={'Authorization': f'Token {wdiv_api_key}'}
        )
        r.raise_for_status()
    else:
        print('WDIV_API_KEY not set')
        print(wdiv_url)
        print(report)
        print('---')

"""Cache Semantic Scholar citation counts for the papers in the directory."""
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def merge_reports(ids, records, previous, checked_at):
    if not isinstance(records, list) or len(records) != len(ids):
        raise ValueError('Invalid batch response; previous results retained')
    reports = {key: value for key, value in previous.items() if key in ids}
    for identifier, record in zip(ids, records):
        if record is None:
            if identifier not in reports:
                reports[identifier] = {'citationCount': None, 'checkedAt': checked_at}
            continue
        count = record.get('citationCount')
        paper_id = record.get('paperId', '')
        if type(count) is not int or count < 0 or not re.fullmatch(r'[0-9a-f]{40}', paper_id):
            raise ValueError('Invalid paper response; previous results retained')
        reports[identifier] = {'citationCount': count, 'url': 'https://www.semanticscholar.org/paper/' + paper_id, 'checkedAt': checked_at}
    return reports


def main():
    ids = sorted(set(re.findall(r'arXiv:(\d{4}\.\d{4,5})v\d+', (ROOT / 'index.html').read_text())))
    if not ids:
        raise ValueError('No paper IDs found')
    target = ROOT / 'assets/citations.json'
    previous = json.loads(target.read_text()) if target.exists() else {'reports': {}}
    headers = {'Content-Type': 'application/json', 'User-Agent': 'llm-report-translations/1.0'}
    if os.environ.get('SEMANTIC_SCHOLAR_API_KEY'):
        headers['x-api-key'] = os.environ['SEMANTIC_SCHOLAR_API_KEY']
    request = urllib.request.Request(
        'https://api.semanticscholar.org/graph/v1/paper/batch?fields=citationCount',
        data=json.dumps({'ids': ['ARXIV:' + identifier for identifier in ids]}).encode(), headers=headers)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                records = json.load(response)
            break
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
            time.sleep(10 * (attempt + 1))
    checked_at = datetime.now(timezone.utc).isoformat()
    reports = merge_reports(ids, records, previous['reports'], checked_at)
    result = {'checkedAt': checked_at, 'reports': reports}
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(target)
    print(f'Citation counts: {sum(row["citationCount"] is not None for row in reports.values())}/{len(ids)} papers')


if __name__ == '__main__':
    main()

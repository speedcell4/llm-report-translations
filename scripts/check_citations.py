"""Cache Semantic Scholar citation counts for the papers in the directory."""
import json
import os
import re
import time
import urllib.error
import urllib.request
import urllib.parse
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def select_record(identifier, original, candidates):
    def title_key(record):
        return re.sub(r'[^\w]', '', unicodedata.normalize('NFKC', record.get('title', '')).casefold())

    matching = [original]
    for candidate in candidates:
        if not candidate or not title_key(original) or title_key(candidate) != title_key(original):
            continue
        external = candidate.get('externalIds') or {}
        arxiv = external.get('ArXiv', '')
        # Duplicate S2 records can lack ArXiv but retain the same ID in DBLP or DOI.
        if arxiv and arxiv != identifier:
            continue
        same_id = (arxiv == identifier or external.get('DBLP') == 'journals/corr/abs-' + identifier.replace('.', '-')
                   or external.get('DOI', '').casefold() == '10.48550/arxiv.' + identifier)
        original_authors = {author['authorId'] for author in original.get('authors', []) if author.get('authorId')}
        candidate_authors = {author['authorId'] for author in candidate.get('authors', []) if author.get('authorId')}
        same_authors = (original_authors and len(original_authors & candidate_authors) >= min(2, len(original_authors)))
        same_year = original.get('year') is not None and original.get('year') == candidate.get('year')
        if same_id or (not arxiv and same_year and same_authors):
            if type(candidate.get('citationCount')) is int and candidate['citationCount'] >= 0:
                matching.append(candidate)
    return max(matching, key=lambda record: record['citationCount'])


def query_api(path, headers, data=None):
    request = urllib.request.Request('https://api.semanticscholar.org/graph/v1/' + path,
                                     data=json.dumps(data).encode() if data is not None else None, headers=headers)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
            time.sleep(10 * (attempt + 1))


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
        reports[identifier] = {'citationCount': count, 'url': 'https://www.semanticscholar.org/paper/' + paper_id, 'checkedAt': checked_at,
                               'paperId': paper_id, 'title': record.get('title'),
                               'externalIds': record.get('externalIds')}
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
    fields = 'title,citationCount,externalIds,year,authors'
    saved_ids = sorted({row['paperId'] for row in previous['reports'].values() if row.get('paperId')})
    requested = ['ARXIV:' + identifier for identifier in ids] + saved_ids
    records = query_api('paper/batch?fields=' + fields, headers, {'ids': requested})
    if not isinstance(records, list) or len(records) != len(requested):
        raise ValueError('Invalid batch response; previous results retained')
    saved = {record['paperId']: record for record in records[len(ids):] if record}
    records = records[:len(ids)]
    for start in range(0, len(ids), 8):
        group = records[start:start + 8]
        titles = list(dict.fromkeys(record['title'] for record in group if record))
        if not titles:
            continue
        candidates = []
        token = None
        while True:
            params = {'query': ' | '.join('"' + title.replace('"', '') + '"' for title in titles), 'fields': fields}
            if token:
                params['token'] = token
            result = query_api('paper/search/bulk?' + urllib.parse.urlencode(params), headers)
            if not isinstance(result.get('data'), list):
                raise ValueError('Invalid title search response; previous results retained')
            candidates.extend(result['data'])
            token = result.get('token')
            time.sleep(1)
            if not token:
                break
        for position, original in enumerate(group, start):
            if original is None:
                continue
            identifier = ids[position]
            cached = saved.get(previous['reports'].get(identifier, {}).get('paperId'))
            selected = select_record(identifier, original, candidates + [cached])
            records[position] = selected
            if selected['paperId'] != original['paperId']:
                print(f'{identifier}: resolved duplicate {original["citationCount"]} -> {selected["citationCount"]} ({selected["paperId"]})', flush=True)
        print(f'Duplicate audit: {min(start + 8, len(ids))}/{len(ids)} papers', flush=True)
    checked_at = datetime.now(timezone.utc).isoformat()
    reports = merge_reports(ids, records, previous['reports'], checked_at)
    result = {'checkedAt': checked_at, 'reports': reports}
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(target)
    print(f'Citation counts: {sum(row["citationCount"] is not None for row in reports.values())}/{len(ids)} papers')


if __name__ == '__main__':
    main()

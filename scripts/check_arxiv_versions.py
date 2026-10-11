import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_versions(xml):
    versions = {}
    for entry in ET.fromstring(xml).findall('{http://www.w3.org/2005/Atom}entry'):
        identifier = entry.findtext('{http://www.w3.org/2005/Atom}id', '')
        match = re.search(r'/abs/(\d{4}\.\d{4,5})v(\d+)$', identifier)
        if match:
            versions[match[1]] = {
                'version': int(match[2]),
                'date': entry.findtext('{http://www.w3.org/2005/Atom}updated', '')[:10],
            }
    return versions


if __name__ == '__main__':
    ids = sorted(set(re.findall(r'arXiv:(\d{4}\.\d{4,5})v\d+', (ROOT / 'index.html').read_text())))
    query = urllib.parse.urlencode({'id_list': ','.join(ids), 'max_results': len(ids)})
    with urllib.request.urlopen('https://export.arxiv.org/api/query?' + query, timeout=60) as response:
        versions = parse_versions(response.read())
    if not versions:
        raise RuntimeError('arXiv returned no version records; previous results retained')
    result = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'reports': versions}
    (ROOT / 'assets/arxiv-versions.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f'Found {len(versions)}/{len(ids)} reports')

"""Move embedded report images into shared assets without changing image bytes."""
from pathlib import Path
import base64
import hashlib
import io
import json
import re
import shutil

from PIL import Image
from lxml import html

ROOT = Path(__file__).resolve().parents[3]
SITE = ROOT / 'tmp/image-assets-site'
DATA = re.compile(r'data:image/(png|jpeg|webp|gif);base64,([A-Za-z0-9+/=\s]+)')
TAG = re.compile(r'<img\b[^>]*>', re.I)


def extract(source, folder):
    def replace(match):
        payload = base64.b64decode(match[2], validate=False)
        with Image.open(io.BytesIO(payload)) as image:
            image.verify()
        extension = 'jpg' if match[1] == 'jpeg' else match[1]
        relative = 'assets/images/' + hashlib.sha256(payload).hexdigest() + '.' + extension
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(payload)
        assert target.read_bytes() == payload
        return relative

    source = DATA.sub(replace, source)

    def lazy(match):
        tag = match[0]
        if 'assets/images/' in tag:
            src = re.search(r'src=["\'](assets/images/[^"\']+)["\']', tag)[1]
            with Image.open(folder / src) as image:
                width, height = image.size
            for name, value in [('width', width), ('height', height)]:
                if not re.search(r'\b' + name + r'\s*=', tag):
                    tag = tag.replace('<img', f'<img {name}="{value}"', 1)
            for name, value in [('loading', 'lazy'), ('decoding', 'async')]:
                if not re.search(r'\b' + name + r'\s*=', tag):
                    tag = tag.replace('<img', f'<img {name}="{value}"', 1)
        return tag

    return TAG.sub(lazy, source)


if __name__ == '__main__':
    assert SITE.joinpath('.git').exists(), 'Clone the current published site first'
    before = after = count = 0
    for path in sorted(SITE.glob('*.html')):
        source = path.read_text()
        result = extract(source, SITE)
        before += len(source.encode())
        after += len(result.encode())
        old = html.fromstring(source, parser=html.HTMLParser(huge_tree=True))
        new = html.fromstring(result, parser=html.HTMLParser(huge_tree=True))
        assert old.text_content() == new.text_content(), path
        assert len(old.xpath('//img')) == len(new.xpath('//img')), path
        assert 'data:image/' not in result, path
        for image in new.xpath('//img[starts-with(@src,"assets/images/")]'):
            assert (SITE / image.get('src')).is_file()
            count += 1
        path.write_text(result)
    index = html.fromstring((SITE / 'index.html').read_text())
    sections = index.xpath('//section[starts-with(@id,"series-")]')
    assert [s.get('id') for s in sections[:3]] == ['series-deepseek', 'series-qwen', 'series-kimi']
    for section in sections:
        entries = section.xpath('./ul/li')
        dates = [item.get('data-date') for item in entries]
        assert dates == sorted(dates), section.get('id')
    minicpm = index.get_element_by_id('series-minicpm')
    assert 'MiniCPM / InfLLM' in minicpm.text_content()
    assert {'infllm-zh.html', 'minicpm4-zh.html'} <= set(minicpm.xpath('.//a/@href'))
    for href in index.xpath('//section[starts-with(@id,"series-")]//li/a/@href'):
        assert (SITE / href).is_file(), href
    for folder in [ROOT / 'output/html', ROOT / 'output/github-pages']:
        shutil.copytree(SITE / 'assets/images', folder / 'assets/images', dirs_exist_ok=True)
        for path in SITE.glob('*.html'):
            shutil.copy2(path, folder / path.name)
    # Keep page fragments ready for existing report assembly scripts.
    for path in (ROOT / 'tmp').rglob('*.html'):
        if 'fragments' in path.parts or 'pages' in path.parts:
            source = path.read_text()
            result = extract(source, ROOT / 'output/html')
            if result != source:
                path.write_text(result)
    shutil.copytree(ROOT / 'output/html/assets/images', ROOT / 'output/github-pages/assets/images', dirs_exist_ok=True)
    report = {'html_bytes_before': before, 'html_bytes_after': after, 'images': count}
    (ROOT / 'tmp/image-assets-verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))

from pathlib import Path
import unittest
from check_citations import merge_reports, select_record


class CitationTests(unittest.TestCase):
    def test_zero_missing_and_retained_count(self):
        old = {'c': {'citationCount': 7, 'checkedAt': 'old'}}
        result = merge_reports(['a', 'b', 'c'], [{'citationCount': 0, 'paperId': 'a' * 40}, None, None], old, 'now')
        self.assertEqual(result['a']['citationCount'], 0)
        self.assertIsNone(result['b']['citationCount'])
        self.assertEqual(result['c'], old['c'])
        self.assertEqual(old, {'c': {'citationCount': 7, 'checkedAt': 'old'}})

    def test_deepseek_v3_duplicate_record(self):
        import json
        fixtures = Path(__file__).with_name('citation-fixtures.json')
        data = json.loads(fixtures.read_text())
        result = select_record('2412.19437', data['original'], data['candidates'])
        self.assertEqual(result['paperId'], '5b6fdb2aea424d02c141da81d62b04d739d62b96')
        self.assertGreater(result['citationCount'], 0)

    def test_rejects_unrelated_high_citation_paper(self):
        original = {'title': 'Report', 'year': 2024, 'citationCount': 0,
                    'externalIds': {'ArXiv': '2412.19437'}, 'authors': [{'authorId': '1'}]}
        unrelated = dict(original, citationCount=9999, externalIds={'ArXiv': '2401.00001'})
        self.assertIs(select_record('2412.19437', original, [unrelated]), original)
        unrelated = dict(original, citationCount=9999, externalIds={}, authors=[{'authorId': '2'}])
        self.assertIs(select_record('2412.19437', original, [unrelated]), original)

    def test_positive_count_uses_highest_matching_record(self):
        original = {'paperId': 'a' * 40, 'title': 'A Report', 'citationCount': 50,
                    'externalIds': {'ArXiv': '2412.19437'}}
        duplicate = dict(original, paperId='b' * 40, citationCount=800,
                         externalIds={'DBLP': 'journals/corr/abs-2412-19437'})
        self.assertIs(select_record('2412.19437', original, [duplicate]), duplicate)

    def test_matching_title_year_and_authors_without_external_id(self):
        original = {'title': 'A Report', 'year': 2024, 'citationCount': 5,
                    'authors': [{'authorId': '1'}, {'authorId': '2'}]}
        duplicate = dict(original, citationCount=10, externalIds={})
        self.assertIs(select_record('2412.19437', original, [duplicate]), duplicate)
        unrelated = dict(duplicate, year=2023, citationCount=100)
        self.assertIs(select_record('2412.19437', original, [unrelated]), original)

    def test_audit_paginates_and_does_not_sum_duplicates(self):
        import json
        import tempfile
        from unittest.mock import patch
        import check_citations
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'assets').mkdir()
            (root / 'index.html').write_text('arXiv:2412.19437v1')
            original = {'paperId': 'a' * 40, 'title': 'A Report', 'citationCount': 50,
                        'externalIds': {'ArXiv': '2412.19437'}}
            duplicate = dict(original, paperId='b' * 40, citationCount=800)
            with patch.object(check_citations, 'ROOT', root), patch.object(check_citations.time, 'sleep'), patch.object(
                    check_citations, 'query_api', side_effect=[[original], {'data': [], 'token': 'next'}, {'data': [duplicate]}]) as query:
                check_citations.main()
            self.assertIn('token=next', query.call_args_list[-1].args[0])
            result = json.loads((root / 'assets/citations.json').read_text())
            self.assertEqual(result['reports']['2412.19437']['citationCount'], 800)
            old = (root / 'assets/citations.json').read_bytes()
            with patch.object(check_citations, 'ROOT', root), patch.object(check_citations, 'query_api', side_effect=ValueError('failure')):
                with self.assertRaises(ValueError):
                    check_citations.main()
            self.assertEqual((root / 'assets/citations.json').read_bytes(), old)

    def test_invalid_response_does_not_replace_cache(self):
        for records in ([], {}, [{'citationCount': -1, 'paperId': 'a' * 40}]):
            with self.assertRaises(ValueError):
                merge_reports(['a'], records, {}, 'now')


if __name__ == '__main__':
    unittest.main()

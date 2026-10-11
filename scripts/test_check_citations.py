import unittest
from check_citations import merge_reports


class CitationTests(unittest.TestCase):
    def test_zero_missing_and_retained_count(self):
        old = {'c': {'citationCount': 7, 'checkedAt': 'old'}}
        result = merge_reports(['a', 'b', 'c'], [{'citationCount': 0, 'paperId': 'a' * 40}, None, None], old, 'now')
        self.assertEqual(result['a']['citationCount'], 0)
        self.assertIsNone(result['b']['citationCount'])
        self.assertEqual(result['c'], old['c'])
        self.assertEqual(old, {'c': {'citationCount': 7, 'checkedAt': 'old'}})

    def test_invalid_response_does_not_replace_cache(self):
        for records in ([], {}, [{'citationCount': -1, 'paperId': 'a' * 40}]):
            with self.assertRaises(ValueError):
                merge_reports(['a'], records, {}, 'now')


if __name__ == '__main__':
    unittest.main()

from unittest import TestCase
from trigger.csv_helpers import get_csv_report


def get_fixture(filename, content_type):
    return {
        'ContentType': content_type,
        'Body': open(f'tests/fixtures/{filename}', 'rb')
    }

class CsvHelperTests(TestCase):
    def test_valid_idox_eros(self):
        report = get_csv_report(get_fixture('ems-idox-eros.csv', 'text/csv'))
        self.assertTrue(report['csv_valid'])
        self.assertEqual(10, report['csv_rows'])
        self.assertEqual('Idox Eros (Halarose)', report['ems'])

    def test_valid_xpress_dc(self):
        report = get_csv_report(get_fixture('ems-xpress-dc.csv', 'text/csv'))
        self.assertTrue(report['csv_valid'])
        self.assertEqual(10, report['csv_rows'])
        self.assertEqual('Xpress DC', report['ems'])

    def test_valid_weblookup(self):
        report = get_csv_report(get_fixture('ems-xpress-weblookup.CSV', 'text/csv'))
        self.assertTrue(report['csv_valid'])
        self.assertEqual(10, report['csv_rows'])
        self.assertEqual('Xpress WebLookup', report['ems'])

    def test_valid_other(self):
        report = get_csv_report(get_fixture('ems-other.csv', 'text/csv'))
        self.assertTrue(report['csv_valid'])
        self.assertEqual(10, report['csv_rows'])
        self.assertEqual('unknown', report['ems'])

    def test_valid_windows1252(self):
        report = get_csv_report(get_fixture('encoding-windows1252.tsv', 'text/tab-separated-values'))
        self.assertTrue(report['csv_valid'])
        self.assertEqual(10, report['csv_rows'])
        self.assertEqual('Xpress DC', report['ems'])

    def test_edgecase_csv_with_tsv_ext(self):
        report = get_csv_report(get_fixture('ext-csv-with-tsv-ext.tsv', 'text/tab-separated-values'))
        self.assertTrue(report['csv_valid'])
        self.assertEqual(10, report['csv_rows'])

    def test_edgecase_tsv_with_csv_ext(self):
        report = get_csv_report(get_fixture('ext-tsv-with-csv-ext.csv', 'text/csv'))
        self.assertTrue(report['csv_valid'])
        self.assertEqual(10, report['csv_rows'])

    def test_edgecase_nearly_empty_file(self):
        report = get_csv_report(get_fixture('small-files-nearly_empty.csv', 'text/csv'))
        self.assertTrue(report['csv_valid'])
        self.assertEqual(1, report['csv_rows'])
        self.assertEqual('unknown', report['ems'])

    def test_invalid_empty_file(self):
        report = get_csv_report(get_fixture('small-files-empty.csv', 'text/csv'))
        self.assertFalse(report['csv_valid'])
        self.assertEqual('File is empty', report['errors'][0])

    def test_invalid_empty_file2(self):
        report = get_csv_report(get_fixture('small-files-empty2.csv', 'text/csv'))
        # this file is just a single line break
        self.assertFalse(report['csv_valid'])
        self.assertEqual('File has only 0 columns. We might have failed to detect the delimiter', report['errors'][0])

    def test_invalid_incomplete_file(self):
        report = get_csv_report(get_fixture('incomplete-file.CSV', 'text/csv'))
        self.assertFalse(report['csv_valid'])
        self.assertEqual('Incomplete file: Expected 38 columns on row 10 found 7', report['errors'][0])

    def test_invalid_not_a_csv(self):
        report = get_csv_report(get_fixture('not-a-csv.csv', 'text/csv'))
        self.assertFalse(report['csv_valid'])
        self.assertEqual('Failed to parse body', report['errors'][0])

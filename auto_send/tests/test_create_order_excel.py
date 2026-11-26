import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import xlrd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / '1_create_order_excel.py'
spec = importlib.util.spec_from_file_location('create_order_excel_test', SCRIPT_PATH)
order_excel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(order_excel)


class CreateOrderExcelTests(unittest.TestCase):
    HEADERS = [
        '날짜', '신청자', '받는분', '전화번호', '주소', '도서명',
        'ISBN\n(vlookup 적용중)', '부수', '대분류', '중분류',
        '증정체크', '비고', '비고2', '발송요청일', '재고유무',
    ]

    def make_row(self, title, isbn='9781234567890', remark='', request_date='', stock=''):
        return [
            '2026-10-02', '신청자', '받는분', '010-1234-5678', '테스트 주소',
            title, isbn, '1', '', '', 'N', '', remark, request_date, stock,
        ]

    def run_orders(self, rows, headers=None):
        worksheet = Mock()
        worksheet.get_all_values.return_value = [headers or self.HEADERS] + rows
        client = Mock()
        client.open_by_key.return_value.worksheet.return_value = worksheet
        settings = SimpleNamespace(
            DB_SPREADSHEET_ID='test-sheet', TARGET_SHEET_NAME='test',
            TARGET_DATE='2026-10-02', EMAIL_RECIPIENTS=['test@example.invalid'],
            GOOGLE_CHAT_USER_ID='',
        )
        with tempfile.TemporaryDirectory() as directory:
            script_path = str(Path(directory) / SCRIPT_PATH.name)
            with (
                patch.object(order_excel, 'config', settings),
                patch.object(order_excel, '__file__', script_path),
                patch.object(order_excel, 'send_email_with_attachment') as email,
                patch.object(order_excel, 'send_google_chat_message') as chat,
                redirect_stdout(io.StringIO()) as log,
            ):
                order_excel.create_daily_order_excel(client)
                output = Path(directory) / 'send_excel' / '택배발주사내_1002_바스클.xls'
                exported_rows = None
                if output.exists():
                    book = xlrd.open_workbook(str(output))
                    sheet = book.sheet_by_index(0)
                    exported_rows = [sheet.row_values(i) for i in range(sheet.nrows)]
                    book.release_resources()
                updates = [
                    (cell.row, cell.col, cell.value)
                    for call in worksheet.update_cells.call_args_list
                    for cell in call.args[0]
                ]
                return SimpleNamespace(
                    rows=exported_rows, updates=updates, email=email, chat=chat,
                    log=log.getvalue(),
                )

    def test_headquarters_missing_isbn_is_excluded_and_dated(self):
        result = self.run_orders([
            self.make_row('본사 도서', '#N/A', ' 본사 출고 '),
            self.make_row('해피데이 도서'),
        ])
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.rows[1][4], '해피데이 도서')
        self.assertEqual(result.rows[1][5], '9781234567890')
        self.assertCountEqual(result.updates, [(2, 14, '2026-10-02'), (3, 14, '2026-10-02')])
        result.chat.assert_not_called()
        result.email.assert_called_once()
        self.assertIn('1건', result.email.call_args.args[3])

    def test_headquarters_with_valid_isbn_is_also_excluded(self):
        result = self.run_orders([
            self.make_row('본사 도서', remark='본사 출고'),
            self.make_row('해피데이 도서', remark='일반 배송'),
        ])
        self.assertEqual([row[4] for row in result.rows[1:]], ['해피데이 도서'])
        result.email.assert_called_once()

    def test_headquarters_spelling_variants_are_excluded_regardless_of_isbn(self):
        for remark in ['본사 출고', '본사출고', '본사 츌고', '본사츌고']:
            for isbn in ['9781234567890', '#N/A', '']:
                with self.subTest(remark=remark, isbn=isbn):
                    result = self.run_orders([
                        self.make_row('본사 도서', isbn, remark),
                        self.make_row('해피데이 도서'),
                    ])
                    self.assertEqual([row[4] for row in result.rows[1:]], ['해피데이 도서'])
                    self.assertCountEqual(result.updates, [(2, 14, '2026-10-02'), (3, 14, '2026-10-02')])
                    result.chat.assert_not_called()
                    result.email.assert_called_once()

    def test_only_headquarters_orders_are_dated_without_export_or_email(self):
        result = self.run_orders([self.make_row('본사 도서', '#N/A', '본사 출고')])
        self.assertIsNone(result.rows)
        self.assertEqual(result.updates, [(2, 14, '2026-10-02')])
        result.chat.assert_not_called()
        result.email.assert_not_called()

    def test_regular_isbn_error_still_blocks_export_but_headquarters_is_dated(self):
        result = self.run_orders([
            self.make_row('본사 도서', '#N/A', '본사 출고'),
            self.make_row('오류 도서', '#N/A'),
        ])
        self.assertIsNone(result.rows)
        self.assertEqual(result.updates, [(2, 14, '2026-10-02')])
        result.email.assert_not_called()
        result.chat.assert_called_once()
        self.assertIn('1건', result.chat.call_args.args[0])

    def test_already_requested_or_stock_marked_orders_are_untouched(self):
        result = self.run_orders([
            self.make_row('기처리 본사 도서', '#N/A', '본사 출고', '2026-10-01'),
            self.make_row('재고 표시 본사 도서', '#N/A', '본사 출고', stock='없음'),
            self.make_row('해피데이 도서'),
        ])
        self.assertEqual(result.updates, [(4, 14, '2026-10-02')])
        self.assertEqual([row[4] for row in result.rows[1:]], ['해피데이 도서'])

    def test_sheets_without_remark2_keep_existing_behavior(self):
        headers = self.HEADERS[:12] + self.HEADERS[13:]
        row = self.make_row('해피데이 도서')
        result = self.run_orders([row[:12] + row[13:]], headers=headers)
        self.assertEqual(result.updates, [(2, 13, '2026-10-02')])
        self.assertEqual([row[4] for row in result.rows[1:]], ['해피데이 도서'])
        result.email.assert_called_once()


if __name__ == '__main__':
    unittest.main()

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import StockLot, Symbol, Sale, SaleAllocation
from .services import PriceFetchError, build_dashboard_summary, parse_date_param, get_user_lots

User = get_user_model()


class BuildDashboardSummaryTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='trader', password='pw')
        self.aapl = Symbol.objects.create(ticker='AAPL')
        self.tsla = Symbol.objects.create(ticker='TSLA')

    def test_no_lots_returns_zeroed_summary(self):
        summary = build_dashboard_summary(self.owner)
        self.assertEqual(summary['rows'], [])
        self.assertEqual(summary['allocation'], [])
        self.assertEqual(summary['total_cost_thb'], Decimal('0'))
        self.assertEqual(summary['total_value_thb'], Decimal('0'))
        self.assertEqual(summary['total_unrealized_gain_thb'], Decimal('0'))
        self.assertEqual(summary['total_realized_gain_thb'], Decimal('0'))

    @patch('portfolio.services.fetch_current_price')
    @patch('portfolio.services.fetch_usd_thb_rate')
    def test_computes_live_value_and_unrealized_gain(self, mock_fx, mock_price):
        mock_fx.return_value = Decimal('35')
        mock_price.return_value = Decimal('150')

        StockLot.objects.create(
            owner=self.owner, symbol=self.aapl, buy_date='2026-01-01',
            price_usd=Decimal('100'), qty=Decimal('10'), fx_rate_usd_thb=Decimal('33'),
        )

        summary = build_dashboard_summary(self.owner)

        self.assertEqual(len(summary['rows']), 1)
        row = summary['rows'][0]
        self.assertEqual(row['cost_thb'], Decimal('33000'))  # 10 * 100 * 33
        self.assertEqual(row['current_value_thb'], Decimal('52500'))  # 10 * 150 * 35
        self.assertEqual(row['unrealized_gain_thb'], Decimal('19500'))
        self.assertEqual(summary['total_value_thb'], Decimal('52500'))
        self.assertEqual(summary['total_unrealized_gain_thb'], Decimal('19500'))
        self.assertEqual(summary['allocation'], [{'ticker': 'AAPL', 'cost_thb': 33000.0}])

    @patch('portfolio.services.fetch_current_price')
    @patch('portfolio.services.fetch_usd_thb_rate')
    def test_price_fetch_failure_degrades_gracefully(self, mock_fx, mock_price):
        mock_fx.return_value = Decimal('35')
        mock_price.side_effect = PriceFetchError('boom')

        StockLot.objects.create(
            owner=self.owner, symbol=self.aapl, buy_date='2026-01-01',
            price_usd=Decimal('100'), qty=Decimal('10'), fx_rate_usd_thb=Decimal('33'),
        )

        summary = build_dashboard_summary(self.owner)

        row = summary['rows'][0]
        self.assertIsNone(row['current_value_thb'])
        self.assertIsNone(row['unrealized_gain_thb'])
        self.assertIsNone(summary['total_value_thb'])
        self.assertIsNone(summary['total_unrealized_gain_thb'])
        # cost basis still shown even when live price fails
        self.assertEqual(summary['total_cost_thb'], Decimal('33000'))


class ParseDateParamTests(TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(parse_date_param(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_date_param(''))

    def test_valid_iso_date_returns_date(self):
        self.assertEqual(parse_date_param('2026-03-15'), date(2026, 3, 15))

    def test_malformed_string_returns_none(self):
        self.assertIsNone(parse_date_param('not-a-date'))
        self.assertIsNone(parse_date_param('2026-13-40'))


class GetUserLotsDateFilterTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='trader', password='pw')
        self.aapl = Symbol.objects.create(ticker='AAPL')
        self.lot_jan = StockLot.objects.create(
            owner=self.owner, symbol=self.aapl, buy_date='2026-01-10',
            price_usd=Decimal('100'), qty=Decimal('10'), fx_rate_usd_thb=Decimal('33'),
        )
        self.lot_jun = StockLot.objects.create(
            owner=self.owner, symbol=self.aapl, buy_date='2026-06-10',
            price_usd=Decimal('120'), qty=Decimal('5'), fx_rate_usd_thb=Decimal('34'),
        )

    def test_no_date_filter_returns_all_lots_with_full_remaining(self):
        lots = get_user_lots(self.owner)
        self.assertEqual(len(lots), 2)
        by_date = {lot.buy_date: lot for lot in lots}
        self.assertEqual(by_date[date(2026, 1, 10)].windowed_remaining, Decimal('10'))
        self.assertEqual(by_date[date(2026, 6, 10)].windowed_remaining, Decimal('5'))

    def test_date_from_excludes_earlier_lots(self):
        lots = get_user_lots(self.owner, date_from=date(2026, 3, 1))
        self.assertEqual([lot.buy_date for lot in lots], [date(2026, 6, 10)])

    def test_date_to_excludes_later_lots(self):
        lots = get_user_lots(self.owner, date_to=date(2026, 3, 1))
        self.assertEqual([lot.buy_date for lot in lots], [date(2026, 1, 10)])

    def test_bounds_are_inclusive(self):
        lots = get_user_lots(self.owner, date_from=date(2026, 1, 10), date_to=date(2026, 1, 10))
        self.assertEqual([lot.buy_date for lot in lots], [date(2026, 1, 10)])

    def test_windowed_remaining_excludes_out_of_window_sales(self):
        sale_in_window = Sale.objects.create(
            owner=self.owner, symbol=self.aapl, sell_date='2026-02-01',
            qty_sold=Decimal('3'), sale_price_usd=Decimal('110'),
            fx_rate_usd_thb=Decimal('33'),
        )
        SaleAllocation.objects.create(
            sale=sale_in_window, lot=self.lot_jan, qty_allocated=Decimal('3'),
            cost_basis_thb=Decimal('9900'),
        )
        sale_out_of_window = Sale.objects.create(
            owner=self.owner, symbol=self.aapl, sell_date='2026-08-01',
            qty_sold=Decimal('2'), sale_price_usd=Decimal('115'),
            fx_rate_usd_thb=Decimal('33'),
        )
        SaleAllocation.objects.create(
            sale=sale_out_of_window, lot=self.lot_jan, qty_allocated=Decimal('2'),
            cost_basis_thb=Decimal('6600'),
        )

        # Window only covers Jan-Mar: the Feb sale counts against remaining,
        # the Aug sale (outside window) must not.
        lots = get_user_lots(
            self.owner, date_from=date(2026, 1, 1), date_to=date(2026, 3, 1),
        )
        jan_lot = next(lot for lot in lots if lot.buy_date == date(2026, 1, 10))
        self.assertEqual(jan_lot.windowed_remaining, Decimal('7'))  # 10 - 3, not 10 - 5

        # No window: both sales count, matching the real qty_remaining property.
        lots_unfiltered = get_user_lots(self.owner)
        jan_lot_unfiltered = next(lot for lot in lots_unfiltered if lot.buy_date == date(2026, 1, 10))
        self.assertEqual(jan_lot_unfiltered.windowed_remaining, Decimal('5'))  # 10 - 3 - 2
        self.assertEqual(jan_lot_unfiltered.windowed_remaining, jan_lot_unfiltered.qty_remaining)

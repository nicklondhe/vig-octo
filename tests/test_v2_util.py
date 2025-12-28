'''Unit tests for v2 utility functions'''

from datetime import date

from v2.util import get_week_start


class TestGetWeekStart:
    '''Tests for get_week_start function'''

    def test_monday_returns_same_day(self):
        '''Test that Monday returns itself as week start'''
        monday = date(2025, 1, 6)  # Monday, January 6, 2025
        assert monday.weekday() == 0  # Verify it's Monday
        assert get_week_start(monday) == monday

    def test_tuesday_returns_previous_monday(self):
        '''Test that Tuesday returns the previous Monday'''
        tuesday = date(2025, 1, 7)  # Tuesday, January 7, 2025
        monday = date(2025, 1, 6)   # Previous Monday
        assert get_week_start(tuesday) == monday

    def test_wednesday_returns_previous_monday(self):
        '''Test that Wednesday returns the previous Monday'''
        wednesday = date(2025, 1, 8)  # Wednesday, January 8, 2025
        monday = date(2025, 1, 6)     # Previous Monday
        assert get_week_start(wednesday) == monday

    def test_thursday_returns_previous_monday(self):
        '''Test that Thursday returns the previous Monday'''
        thursday = date(2025, 1, 9)  # Thursday, January 9, 2025
        monday = date(2025, 1, 6)    # Previous Monday
        assert get_week_start(thursday) == monday

    def test_friday_returns_previous_monday(self):
        '''Test that Friday returns the previous Monday'''
        friday = date(2025, 1, 10)  # Friday, January 10, 2025
        monday = date(2025, 1, 6)   # Previous Monday
        assert get_week_start(friday) == monday

    def test_saturday_returns_previous_monday(self):
        '''Test that Saturday returns the previous Monday'''
        saturday = date(2025, 1, 11)  # Saturday, January 11, 2025
        monday = date(2025, 1, 6)     # Previous Monday
        assert get_week_start(saturday) == monday

    def test_sunday_returns_previous_monday(self):
        '''Test that Sunday returns the previous Monday'''
        sunday = date(2025, 1, 12)  # Sunday, January 12, 2025
        monday = date(2025, 1, 6)   # Previous Monday
        assert get_week_start(sunday) == monday

    def test_defaults_to_today(self):
        '''Test that calling without argument uses today'''
        today = date.today()
        week_start = get_week_start()

        # Week start should be Monday
        assert week_start.weekday() == 0

        # Week start should be on or before today
        assert week_start <= today

        # Week start should be within 7 days before today
        days_diff = (today - week_start).days
        assert 0 <= days_diff < 7

    def test_year_boundary(self):
        '''Test behavior across year boundaries'''
        # Wednesday, January 1, 2025
        jan_1_2025 = date(2025, 1, 1)
        # Should return Monday, December 30, 2024
        expected = date(2024, 12, 30)
        assert get_week_start(jan_1_2025) == expected

    def test_month_boundary(self):
        '''Test behavior across month boundaries'''
        # Thursday, May 1, 2025
        may_1_2025 = date(2025, 5, 1)
        # Should return Monday, April 28, 2025
        expected = date(2025, 4, 28)
        assert get_week_start(may_1_2025) == expected

    def test_leap_year(self):
        '''Test behavior in leap year'''
        # Saturday, February 29, 2020 (leap year)
        leap_day = date(2020, 2, 29)
        # Should return Monday, February 24, 2020
        expected = date(2020, 2, 24)
        assert get_week_start(leap_day) == expected

    def test_consistent_results(self):
        '''Test that same input gives same output'''
        test_date = date(2025, 6, 15)
        result1 = get_week_start(test_date)
        result2 = get_week_start(test_date)
        assert result1 == result2

    def test_week_start_is_always_monday(self):
        '''Test that result is always a Monday for various dates'''
        test_dates = [
            date(2025, 1, 15),
            date(2025, 3, 20),
            date(2025, 6, 10),
            date(2025, 9, 5),
            date(2025, 12, 25),
        ]

        for test_date in test_dates:
            week_start = get_week_start(test_date)
            assert week_start.weekday() == 0, f"Week start for {test_date} is not Monday"

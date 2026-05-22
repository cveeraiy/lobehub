from datetime import UTC, datetime

from app.services.workflows.handlers import is_execution_time


def test_is_execution_time_matches_current_minute_without_prior_run():
    assert is_execution_time(
        cron_pattern="*/5 * * * *",
        current_time=datetime(2026, 5, 21, 10, 15, tzinfo=UTC),
        last_executed_at=None,
        timezone="UTC",
    )


def test_is_execution_time_skips_when_last_run_is_current_minute():
    current = datetime(2026, 5, 21, 10, 15, tzinfo=UTC)

    assert not is_execution_time(
        cron_pattern="*/5 * * * *",
        current_time=current,
        last_executed_at=current,
        timezone="UTC",
    )


def test_is_execution_time_respects_timezone():
    assert is_execution_time(
        cron_pattern="0 9 * * *",
        current_time=datetime(2026, 5, 21, 14, 0, tzinfo=UTC),
        last_executed_at=None,
        timezone="America/Chicago",
    )

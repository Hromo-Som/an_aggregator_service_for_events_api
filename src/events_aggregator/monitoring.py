import logging

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from events_aggregator.config import settings

logger = logging.getLogger(__name__)


def setup_sentry() -> None:
    """Инициализировать Sentry/GlitchTip, если DSN задан."""
    dsn = settings.sentry_dsn.get_secret_value()

    if not dsn:
        logger.info("sentry_disabled reason=no_dsn")
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.environment,
        release=settings.release,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
        send_default_pii=False,
        include_local_variables=False,
        max_breadcrumbs=50,
    )
    logger.info(
        "sentry_initialized environment=%s release=%s",
        settings.environment,
        settings.release,
    )

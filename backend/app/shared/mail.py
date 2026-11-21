"""Sending email: over SMTP when one is configured, otherwise into the log.

Without ``SMTP_HOST`` (local runs, tests) a message is logged instead of sent, so flows
like the email-change code work with no mail server. Production requires SMTP
(see ``Settings.reject_debug_in_production``), so codes never end up in its logs.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Annotated, Protocol

from fastapi import Depends

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 15


class MailError(Exception):
    """A message couldn't be handed to the mail server."""


class Mailer(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


class LogMailer:
    """Writes each message to the log instead of sending it."""

    async def send(self, to: str, subject: str, body: str) -> None:
        logger.info("Email not sent (no SMTP_HOST set) to=%s subject=%r\n%s", to, subject, body)


class SmtpMailer:
    def __init__(self, settings: Settings) -> None:
        assert settings.smtp_host is not None and settings.smtp_from is not None
        self.settings = settings

    async def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.settings.smtp_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        try:
            # smtplib blocks, so it runs off the event loop.
            await asyncio.to_thread(self._deliver, message)
        except (smtplib.SMTPException, OSError) as error:
            raise MailError(str(error)) from error

    def _deliver(self, message: EmailMessage) -> None:
        settings = self.settings
        assert settings.smtp_host is not None
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            smtp.send_message(message)


def get_mailer(settings: Annotated[Settings, Depends(get_settings)]) -> Mailer:
    if settings.smtp_host and settings.smtp_from:
        return SmtpMailer(settings)
    return LogMailer()

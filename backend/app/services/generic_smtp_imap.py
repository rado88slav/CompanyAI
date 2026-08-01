"""Strict Generic SMTP/IMAP mailbox connectivity checks."""

from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from enum import StrEnum
import imaplib
import smtplib
import socket
import ssl
from typing import Protocol


GENERIC_MAILBOX_HEALTH_KEY = "generic_smtp_imap_health"
DEFAULT_MAILBOX_TIMEOUT_SECONDS = 10


class MailboxProtocol(StrEnum):
    SMTP = "smtp"
    IMAP = "imap"


class MailboxTestCategory(StrEnum):
    SUCCESS = "success"
    INVALID_CONFIGURATION = "invalid_configuration"
    DNS_FAILURE = "dns_failure"
    CONNECTION_FAILURE = "connection_failure"
    TLS_FAILURE = "tls_failure"
    AUTHENTICATION_FAILURE = "authentication_failure"
    FOLDER_NOT_FOUND = "folder_not_found"
    TIMEOUT = "timeout"
    UNKNOWN_FAILURE = "unknown_failure"


@dataclass(frozen=True, slots=True)
class MailboxTestResult:
    protocol: MailboxProtocol
    status: str
    tested_at: datetime
    category: MailboxTestCategory
    message: str

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"

    def safe_metadata(self) -> dict[str, str]:
        return {
            "status": self.status,
            "tested_at": self.tested_at.isoformat(),
            "category": self.category.value,
            "message": self.message,
        }


class MailboxTransport(Protocol):
    def test_smtp(
        self,
        *,
        host: str,
        port: int,
        security: str,
        username: str,
        password: str,
        timeout_seconds: int,
    ) -> None: ...

    def test_imap(
        self,
        *,
        host: str,
        port: int,
        security: str,
        username: str,
        password: str,
        folder: str,
        timeout_seconds: int,
    ) -> None: ...


class MailboxTestError(Exception):
    category: MailboxTestCategory = MailboxTestCategory.UNKNOWN_FAILURE
    safe_message = "The mailbox connection test failed."


class InvalidMailboxConfigurationError(MailboxTestError):
    category = MailboxTestCategory.INVALID_CONFIGURATION
    safe_message = "Mailbox settings are incomplete or invalid."


class MailboxDnsError(MailboxTestError):
    category = MailboxTestCategory.DNS_FAILURE
    safe_message = "The mailbox host could not be resolved."


class MailboxConnectionError(MailboxTestError):
    category = MailboxTestCategory.CONNECTION_FAILURE
    safe_message = "The mailbox server could not be reached."


class MailboxTlsError(MailboxTestError):
    category = MailboxTestCategory.TLS_FAILURE
    safe_message = "TLS certificate verification failed."


class MailboxAuthenticationError(MailboxTestError):
    category = MailboxTestCategory.AUTHENTICATION_FAILURE
    safe_message = "Mailbox authentication failed."


class MailboxFolderError(MailboxTestError):
    category = MailboxTestCategory.FOLDER_NOT_FOUND
    safe_message = "The configured IMAP folder is not accessible."


class MailboxTimeoutError(MailboxTestError):
    category = MailboxTestCategory.TIMEOUT
    safe_message = "The mailbox server did not respond before the timeout."


class MailboxSendError(Exception):
    safe_category = "smtp_send_failed_before_send"
    safe_message = "SMTP send failed before the message was accepted."


class MailboxSendConfigurationError(MailboxSendError):
    safe_category = "invalid_configuration"
    safe_message = "Mailbox settings are incomplete or invalid."


class MailboxSendAuthenticationError(MailboxSendError):
    safe_category = "authentication_failure"
    safe_message = "Mailbox authentication failed."


class MailboxSendTlsError(MailboxSendError):
    safe_category = "tls_failure"
    safe_message = "TLS certificate verification failed."


class MailboxSendTimeoutError(MailboxSendError):
    safe_category = "timeout_before_send"
    safe_message = "SMTP server did not respond before the send started."


class MailboxSendOutcomeUncertainError(MailboxSendError):
    safe_category = "outcome_uncertain"
    safe_message = "SMTP connection was lost during DATA; server acceptance is uncertain."


@dataclass(frozen=True, slots=True)
class MailboxSendResult:
    status: str
    accepted_at: datetime
    server_response: str
    provider_message_id: str | None = None


def _require_string(configuration: dict, key: str) -> str:
    value = configuration.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidMailboxConfigurationError
    return value.strip()


def _require_port(configuration: dict, key: str) -> int:
    value = configuration.get(key)
    if not isinstance(value, int) or value < 1 or value > 65535:
        raise InvalidMailboxConfigurationError
    return value


def _require_security(configuration: dict, key: str) -> str:
    value = _require_string(configuration, key)
    if value not in {"ssl_tls", "starttls"}:
        raise InvalidMailboxConfigurationError
    return value


def _classify_exception(exc: Exception) -> MailboxTestError:
    if isinstance(exc, MailboxTestError):
        return exc
    if isinstance(exc, TimeoutError | socket.timeout):
        return MailboxTimeoutError()
    if isinstance(exc, socket.gaierror):
        return MailboxDnsError()
    if isinstance(exc, ssl.SSLCertVerificationError):
        return MailboxTlsError()
    if isinstance(exc, ssl.SSLError):
        return MailboxTlsError()
    if isinstance(exc, (smtplib.SMTPAuthenticationError, imaplib.IMAP4.error)):
        return MailboxAuthenticationError()
    if isinstance(exc, (ConnectionError, OSError, smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected)):
        return MailboxConnectionError()
    return MailboxTestError()


class StandardMailboxTransport:
    """Network transport with strict TLS verification and no side effects."""

    def _resolve(self, host: str, port: int) -> None:
        socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)

    def test_smtp(
        self,
        *,
        host: str,
        port: int,
        security: str,
        username: str,
        password: str,
        timeout_seconds: int,
    ) -> None:
        self._resolve(host, port)
        context = ssl.create_default_context()
        if security == "ssl_tls":
            with smtplib.SMTP_SSL(host, port, timeout=timeout_seconds, context=context) as client:
                client.login(username, password)
            return
        with smtplib.SMTP(host, port, timeout=timeout_seconds) as client:
            client.starttls(context=context)
            client.login(username, password)

    def test_imap(
        self,
        *,
        host: str,
        port: int,
        security: str,
        username: str,
        password: str,
        folder: str,
        timeout_seconds: int,
    ) -> None:
        self._resolve(host, port)
        context = ssl.create_default_context()
        if security == "ssl_tls":
            client = imaplib.IMAP4_SSL(host, port, ssl_context=context, timeout=timeout_seconds)
        elif security == "starttls":
            client = imaplib.IMAP4(host, port, timeout=timeout_seconds)
        else:
            raise InvalidMailboxConfigurationError
        with client:
            if security == "starttls":
                client.starttls(ssl_context=context)
            client.login(username, password)
            status, _ = client.select(folder, readonly=True)
            if status != "OK":
                raise MailboxFolderError


class GenericSmtpLiveTransport:
    """Strict SMTP live transport for one plain-text message."""

    name = "generic-smtp-live"

    def _resolve(self, host: str, port: int) -> None:
        socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)

    def send_email(
        self,
        *,
        configuration: dict,
        password: str,
        sender_email: str,
        recipient_email: str,
        subject: str,
        body: str,
        timeout_seconds: int,
    ) -> MailboxSendResult:
        try:
            username = _require_string(configuration, "username")
            host = _require_string(configuration, "smtp_host")
            port = _require_port(configuration, "smtp_port")
            security = _require_security(configuration, "smtp_security")
            if not password:
                raise InvalidMailboxConfigurationError
        except MailboxTestError as exc:
            raise MailboxSendConfigurationError from exc

        message = EmailMessage()
        message["From"] = sender_email
        message["To"] = recipient_email
        message["Subject"] = subject
        message.set_content(body, subtype="plain")
        try:
            self._resolve(host, port)
            context = ssl.create_default_context()
            if security == "ssl_tls":
                with smtplib.SMTP_SSL(host, port, timeout=timeout_seconds, context=context) as client:
                    client.login(username, password)
                    response = client.send_message(message, from_addr=sender_email, to_addrs=[recipient_email])
            else:
                with smtplib.SMTP(host, port, timeout=timeout_seconds) as client:
                    client.starttls(context=context)
                    client.login(username, password)
                    response = client.send_message(message, from_addr=sender_email, to_addrs=[recipient_email])
            if response:
                raise MailboxSendError
            return MailboxSendResult(status="accepted", accepted_at=datetime.now(UTC), server_response="accepted")
        except MailboxSendError:
            raise
        except (TimeoutError, socket.timeout) as exc:
            raise MailboxSendTimeoutError from exc
        except (ssl.SSLCertVerificationError, ssl.SSLError) as exc:
            raise MailboxSendTlsError from exc
        except smtplib.SMTPAuthenticationError as exc:
            raise MailboxSendAuthenticationError from exc
        except (smtplib.SMTPDataError, smtplib.SMTPServerDisconnected) as exc:
            raise MailboxSendOutcomeUncertainError from exc
        except (socket.gaierror, ConnectionError, OSError, smtplib.SMTPConnectError) as exc:
            raise MailboxSendError from exc


class GenericMailboxTester:
    def __init__(
        self,
        transport: MailboxTransport | None = None,
        *,
        timeout_seconds: int = DEFAULT_MAILBOX_TIMEOUT_SECONDS,
    ) -> None:
        self._transport = transport or StandardMailboxTransport()
        self._timeout_seconds = timeout_seconds

    def test_smtp(self, *, configuration: dict, secrets: dict) -> MailboxTestResult:
        return self._run(MailboxProtocol.SMTP, configuration, secrets)

    def test_imap(self, *, configuration: dict, secrets: dict) -> MailboxTestResult:
        return self._run(MailboxProtocol.IMAP, configuration, secrets)

    def _run(self, protocol: MailboxProtocol, configuration: dict, secrets: dict) -> MailboxTestResult:
        now = datetime.now(UTC)
        try:
            username = _require_string(configuration, "username")
            password = secrets.get("password")
            if not isinstance(password, str) or not password:
                raise InvalidMailboxConfigurationError
            if protocol is MailboxProtocol.SMTP:
                self._transport.test_smtp(
                    host=_require_string(configuration, "smtp_host"),
                    port=_require_port(configuration, "smtp_port"),
                    security=_require_security(configuration, "smtp_security"),
                    username=username,
                    password=password,
                    timeout_seconds=self._timeout_seconds,
                )
            else:
                self._transport.test_imap(
                    host=_require_string(configuration, "imap_host"),
                    port=_require_port(configuration, "imap_port"),
                    security=_require_security(configuration, "imap_security"),
                    username=username,
                    password=password,
                    folder=_require_string(configuration, "imap_folder"),
                    timeout_seconds=self._timeout_seconds,
                )
            return MailboxTestResult(protocol, "succeeded", now, MailboxTestCategory.SUCCESS, "Connection test succeeded.")
        except Exception as exc:
            error = _classify_exception(exc)
            return MailboxTestResult(protocol, "failed", now, error.category, error.safe_message)

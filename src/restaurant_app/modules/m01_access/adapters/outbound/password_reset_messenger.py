"""SMTP delivery adapter for password recovery."""

import asyncio
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode


class SmtpPasswordResetMessenger:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        reset_url: str,
        use_starttls: bool,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_email = from_email
        self._reset_url = reset_url
        self._use_starttls = use_starttls

    async def send_password_reset(self, *, email: str, display_name: str, token: str) -> None:
        await asyncio.to_thread(self._send, email=email, display_name=display_name, token=token)

    def _send(self, *, email: str, display_name: str, token: str) -> None:
        separator = "&" if "?" in self._reset_url else "?"
        link = f"{self._reset_url}{separator}{urlencode({'token': token})}"
        message = EmailMessage()
        message["Subject"] = "Restablece tu contraseña de KAIRO"
        message["From"] = self._from_email
        message["To"] = email
        message.set_content(
            f"Hola {display_name},\n\n"
            "Recibimos una solicitud para restablecer tu contraseña de KAIRO.\n"
            f"Abre este enlace o copia el token en la app:\n{link}\n\n"
            f"Token: {token}\n\n"
            "Si no lo solicitaste, ignora este mensaje. El token vence pronto y solo puede usarse una vez."
        )
        with smtplib.SMTP(self._host, self._port, timeout=10) as client:
            if self._use_starttls:
                client.starttls()
            client.login(self._username, self._password)
            client.send_message(message)


class DisabledPasswordResetMessenger:
    """Explicit local adapter used when SMTP has not been configured."""

    async def send_password_reset(self, *, email: str, display_name: str, token: str) -> None:
        del email, display_name, token

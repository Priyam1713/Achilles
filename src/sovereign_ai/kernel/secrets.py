from __future__ import annotations

SERVICE = "local-sovereign-ai"


def _keyring():
    try:
        import keyring

        return keyring
    except ImportError as exc:
        raise RuntimeError(
            "keyring is required for secret operations; install the kernel environment with uv sync"
        ) from exc


class SecretStore:
    """Secret values stay in the OS credential store; model context should contain handles only."""

    def set(self, name: str, value: str) -> None:
        _keyring().set_password(SERVICE, name, value)

    def get(self, name: str) -> str | None:
        return _keyring().get_password(SERVICE, name)

    def delete(self, name: str) -> None:
        keyring = _keyring()
        try:
            keyring.delete_password(SERVICE, name)
        except keyring.errors.PasswordDeleteError:
            pass

    @staticmethod
    def handle(name: str) -> str:
        return f"secret://{name}"

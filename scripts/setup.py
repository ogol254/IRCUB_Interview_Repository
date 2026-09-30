"""Generate local-only credentials without overwriting existing configuration."""

from pathlib import Path
import secrets

p = Path(".env")
if not p.exists():
    p.write_text(
        "\n".join(
            f"{key}={secrets.token_hex(32)}"
            for key in (
                "POSTGRES_PASSWORD",
                "CALLBACK_SECRET",
                "OFFICER_API_KEY",
                "FMIS_API_KEY",
            )
        )
        + "\n"
    )
    try:
        p.chmod(0o600)
    except OSError:
        pass
    print("Created .env with random local credentials. Do not commit it.")
else:
    print("Existing .env preserved.")

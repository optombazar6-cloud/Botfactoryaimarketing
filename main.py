from __future__ import annotations

import argparse
import asyncio
from typing import Sequence

from dotenv import load_dotenv
from rich.console import Console

from botfactory.config import build_config, build_parser, email_transport_label
from botfactory.env_utils import (
    getenv_bool,
    getenv_float,
    getenv_int,
    getenv_optional_int,
    getenv_raw,
    getenv_str,
    normalize_secret,
)
from botfactory.leads import load_leads_dataframe
from botfactory.models import (
    AppConfig,
    BrandConfig,
    EmailDraft,
    GoogleSheetsConfig,
    LeadBuildResult,
    ReplySyncResult,
    SMTPConfig,
    ScrapePhaseResult,
    SendPhaseResult,
)
from botfactory.pipeline import main_async

__all__ = [
    "AppConfig",
    "BrandConfig",
    "EmailDraft",
    "GoogleSheetsConfig",
    "LeadBuildResult",
    "ReplySyncResult",
    "SMTPConfig",
    "ScrapePhaseResult",
    "SendPhaseResult",
    "build_config",
    "build_parser",
    "email_transport_label",
    "getenv_bool",
    "getenv_float",
    "getenv_int",
    "getenv_optional_int",
    "getenv_raw",
    "getenv_str",
    "load_leads_dataframe",
    "main_async",
    "normalize_secret",
]


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    console = Console()

    try:
        config = build_config(args)
        asyncio.run(main_async(config, console))
    except KeyboardInterrupt:
        console.print("[bold yellow]Interrupted.[/bold yellow]")
        return 130
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

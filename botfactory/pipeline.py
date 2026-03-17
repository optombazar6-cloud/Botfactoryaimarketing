from __future__ import annotations

import asyncio
import random
from datetime import datetime

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from botfactory.blacklist import apply_blacklist_to_leads, load_blacklist, sync_reply_blacklist
from botfactory.config import email_transport_label
from botfactory.email_compose import compose_outreach_email
from botfactory.email_sender import send_email_with_backoff
from botfactory.leads import (
    build_leads_dataframe,
    load_email_template,
    load_leads_dataframe,
    merge_with_existing_leads,
    save_leads_dataframe,
)
from botfactory.models import AppConfig, ReplySyncResult, ScrapePhaseResult, SendPhaseResult
from botfactory.reporting import build_scrape_summary_table, build_send_summary_table
from botfactory.utils import truncate_error, write_json_log
from botfactory.validation import validate_email_config
from botfactory.warmup import plan_warm_up_allowance, record_warm_up_progress


async def main_async(config: AppConfig, console: Console) -> None:
    console.print(
        Panel.fit(
            f"Mode: {config.mode}\n"
            f"Leads file: {config.leads_file}\n"
            f"Seed URL: {config.seed_url or '-'}\n"
            f"Priority filter: {'on' if config.filter_priority_categories else 'off'}\n"
            f"MX validation: {'on' if config.validate_email_mx else 'off'}\n"
            f"Warm-up mode: {'on' if config.warm_up_mode else 'off'}\n"
            f"Reply sync: {'on' if config.reply_sync_enabled else 'off'}\n"
            f"Email transport: {email_transport_label(config.smtp)}\n"
            f"Storage: {'Google Sheets + Excel backup' if config.sheets else 'Excel'}",
            title="Botfactory Lead Machine",
            border_style="cyan",
        )
    )

    if config.mode in {"scrape", "all"}:
        scrape_result = await run_scrape_phase(config, console)
        console.print(build_scrape_summary_table(scrape_result))

    if config.mode == "sync-replies":
        reply_result = await run_reply_sync_phase(config, console)
        if reply_result.error:
            console.print(f"[yellow]Reply sync warning:[/yellow] {reply_result.error}")
        else:
            console.print(
                f"[green]Reply sync[/green] matched={reply_result.matched_messages} "
                f"new_blacklist={reply_result.blacklisted_now} total_blacklist={reply_result.total_blacklisted}"
            )

    if config.mode in {"email", "all"}:
        send_result = await run_email_phase(config, console)
        console.print(build_send_summary_table(send_result))


async def run_scrape_phase(config: AppConfig, console: Console) -> ScrapePhaseResult:
    from goldenpages_scraper.scraper import GoldenPagesScraper, ScraperSettings
    console.print("[bold cyan]Scrape phase started[/bold cyan]")
    settings = ScraperSettings(
        seed_urls=[config.seed_url or ""],
        max_companies=config.max_companies,
        max_pages_per_seed=config.max_pages_per_seed,
        output_dir=config.scraper_output_dir,
    )
    scraper = GoldenPagesScraper(settings=settings, console=console)
    summary = await asyncio.to_thread(scraper.run)
    scraped_df = pd.read_excel(summary.xlsx_path)
    lead_build = build_leads_dataframe(
        scraped_df,
        filter_priority_categories=config.filter_priority_categories,
        validate_email_mx=config.validate_email_mx,
        default_language=config.default_language,
    )
    merged_df, new_count, updated_count = merge_with_existing_leads(config.leads_file, lead_build.dataframe, config.sheets)
    save_leads_dataframe(merged_df, config.leads_file, config.sheets)
    result = ScrapePhaseResult(
        total_scraped_rows=len(scraped_df.index),
        rows_with_email=lead_build.rows_with_email,
        targeted_valid_rows=lead_build.targeted_valid_rows,
        skipped_priority_rows=lead_build.skipped_priority_rows,
        invalid_email_rows=lead_build.invalid_email_rows,
        new_leads_added=new_count,
        existing_leads_updated=updated_count,
        total_leads_in_file=len(merged_df.index),
        output_file=config.leads_file,
    )
    write_json_log(
        config.logs_dir,
        "scrape",
        {
            "seed_url": config.seed_url,
            "total_scraped_rows": result.total_scraped_rows,
            "rows_with_email": result.rows_with_email,
            "targeted_valid_rows": result.targeted_valid_rows,
            "skipped_priority_rows": result.skipped_priority_rows,
            "invalid_email_rows": result.invalid_email_rows,
            "new_leads_added": result.new_leads_added,
            "existing_leads_updated": result.existing_leads_updated,
            "total_leads_in_file": result.total_leads_in_file,
            "output_file": str(result.output_file),
        },
    )
    return result


async def run_reply_sync_phase(config: AppConfig, console: Console) -> ReplySyncResult:
    if not config.reply_sync_enabled:
        return ReplySyncResult(
            matched_messages=0,
            blacklisted_now=0,
            total_blacklisted=len(load_blacklist(config.blacklist_file)),
        )

    console.print("[bold cyan]Reply sync started[/bold cyan]")
    result = await asyncio.to_thread(sync_reply_blacklist, config)
    write_json_log(
        config.logs_dir,
        "reply_sync",
        {
            "matched_messages": result.matched_messages,
            "blacklisted_now": result.blacklisted_now,
            "total_blacklisted": result.total_blacklisted,
            "error": result.error,
        },
    )
    return result


async def run_email_phase(config: AppConfig, console: Console) -> SendPhaseResult:
    validate_email_config(config)
    reply_result = (
        await run_reply_sync_phase(config, console)
        if config.reply_sync_enabled
        else ReplySyncResult(0, 0, len(load_blacklist(config.blacklist_file)))
    )
    from botfactory.leads import ensure_lead_columns
    leads_df = ensure_lead_columns(load_leads_dataframe(config.leads_file, config.sheets))
    blacklist = load_blacklist(config.blacklist_file)
    blacklisted_skipped = apply_blacklist_to_leads(leads_df, blacklist)
    score_series = pd.to_numeric(leads_df["Lead Score"], errors="coerce").fillna(0)
    leads_df["_lead_score_sort"] = score_series
    status_series = leads_df["Status"].fillna("").astype(str).str.strip().str.casefold()
    pending_mask = (leads_df["Email"].astype(str).str.strip() != "") & (~status_series.isin({"sent", "blacklisted"}))
    pending_frame = leads_df[pending_mask].sort_values(
        by=["_lead_score_sort", "Company Name", "Email"],
        ascending=[False, True, True],
    )
    pending_indexes = [int(index) for index in pending_frame.index.tolist()]
    pending_before = len(pending_indexes)
    skipped_sent = len(leads_df.index) - pending_before - blacklisted_skipped

    def _write_email_log(extra: dict) -> None:
        write_json_log(config.logs_dir, "email", {**extra, "output_file": str(config.leads_file)})

    if not pending_indexes:
        console.print("[bold yellow]No pending emails found.[/bold yellow]")
        leads_df = leads_df.drop(columns="_lead_score_sort")
        save_leads_dataframe(leads_df, config.leads_file, config.sheets)
        result = SendPhaseResult(0, 0, 0, skipped_sent, blacklisted_skipped, 0, reply_result.blacklisted_now, config.leads_file)
        _write_email_log({
            "pending_before": 0, "sent_now": 0, "failed_now": 0,
            "skipped_sent": skipped_sent, "blacklisted_skipped": blacklisted_skipped,
            "warm_up_remaining": 0, "reply_blacklisted_now": reply_result.blacklisted_now,
        })
        return result

    allowed_to_send, warm_up_remaining = plan_warm_up_allowance(config)
    send_cap = min(config.email_max_per_run, allowed_to_send) if config.warm_up_mode else config.email_max_per_run
    if send_cap < 1:
        console.print("[bold yellow]Warm-up daily limit reached. No emails sent in this run.[/bold yellow]")
        leads_df = leads_df.drop(columns="_lead_score_sort")
        save_leads_dataframe(leads_df, config.leads_file, config.sheets)
        result = SendPhaseResult(
            pending_before=pending_before, sent_now=0, failed_now=0,
            skipped_sent=skipped_sent, blacklisted_skipped=blacklisted_skipped,
            warm_up_remaining=warm_up_remaining, reply_blacklisted_now=reply_result.blacklisted_now,
            output_file=config.leads_file,
        )
        _write_email_log({
            "pending_before": pending_before, "sent_now": 0, "failed_now": 0,
            "skipped_sent": skipped_sent, "blacklisted_skipped": blacklisted_skipped,
            "warm_up_remaining": warm_up_remaining, "reply_blacklisted_now": reply_result.blacklisted_now,
        })
        return result

    send_indexes = pending_indexes[:send_cap]
    template_text = load_email_template(config.template_file)
    sent_now = 0
    failed_now = 0

    console.print(f"[bold cyan]Email phase started[/bold cyan] Pending: {pending_before}")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Sending outreach", total=len(send_indexes))

        for offset, row_index in enumerate(send_indexes):
            row = leads_df.loc[row_index]
            draft = compose_outreach_email(config, row, template_text)
            progress.update(task_id, description=f"Sending to {row['Email']}")
            success, error_message = await asyncio.to_thread(
                send_email_with_backoff,
                config.smtp,
                str(row["Email"]).strip(),
                draft.subject,
                draft.html_body,
                draft.plain_text_body,
            )

            now_iso = datetime.now().isoformat(timespec="seconds")
            leads_df.at[row_index, "LastContacted"] = now_iso
            leads_df.at[row_index, "Template Used"] = draft.template_used
            if success:
                leads_df.at[row_index, "Status"] = "Sent"
                leads_df.at[row_index, "Sent At"] = now_iso
                leads_df.at[row_index, "Last Error"] = ""
                sent_now += 1
                console.print(f"[green]Sent[/green] {row['Email']} via {email_transport_label(config.smtp)}")
            else:
                leads_df.at[row_index, "Status"] = "Error"
                leads_df.at[row_index, "Last Error"] = truncate_error(error_message)
                failed_now += 1
                console.print(
                    f"[red]Failed[/red] {row['Email']} via {email_transport_label(config.smtp)}: "
                    f"{truncate_error(error_message, limit=160)}"
                )

            save_leads_dataframe(leads_df, config.leads_file, config.sheets)
            progress.advance(task_id)

            if offset < len(send_indexes) - 1:
                await asyncio.sleep(random.uniform(config.delay_min_seconds, config.delay_max_seconds))

    leads_df = leads_df.drop(columns="_lead_score_sort")
    save_leads_dataframe(leads_df, config.leads_file, config.sheets)
    if config.warm_up_mode and sent_now:
        record_warm_up_progress(config, sent_now)
    result = SendPhaseResult(
        pending_before=pending_before,
        sent_now=sent_now,
        failed_now=failed_now,
        skipped_sent=skipped_sent,
        blacklisted_skipped=blacklisted_skipped,
        warm_up_remaining=max(warm_up_remaining - sent_now, 0),
        reply_blacklisted_now=reply_result.blacklisted_now,
        output_file=config.leads_file,
    )
    _write_email_log({
        "pending_before": result.pending_before, "sent_now": result.sent_now,
        "failed_now": result.failed_now, "skipped_sent": result.skipped_sent,
        "blacklisted_skipped": result.blacklisted_skipped,
        "warm_up_remaining": result.warm_up_remaining,
        "reply_blacklisted_now": result.reply_blacklisted_now,
    })
    return result

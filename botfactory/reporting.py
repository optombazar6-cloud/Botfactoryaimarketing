from __future__ import annotations

from rich.table import Table

from botfactory.models import ScrapePhaseResult, SendPhaseResult


def build_scrape_summary_table(result: ScrapePhaseResult) -> Table:
    table = Table(title="Scrape Dashboard", header_style="bold cyan")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Total scraped", str(result.total_scraped_rows))
    table.add_row("Rows with email", str(result.rows_with_email))
    table.add_row("Targeted valid leads", str(result.targeted_valid_rows))
    table.add_row("Skipped by category", str(result.skipped_priority_rows))
    table.add_row("Rejected by validation", str(result.invalid_email_rows))
    table.add_row("New leads", str(result.new_leads_added))
    table.add_row("Updated leads", str(result.existing_leads_updated))
    table.add_row("Workbook rows", str(result.total_leads_in_file))
    table.add_row("Output file", str(result.output_file))
    return table


def build_send_summary_table(result: SendPhaseResult) -> Table:
    table = Table(title="Email Dashboard", header_style="bold green")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Pending before run", str(result.pending_before))
    table.add_row("Emails sent", str(result.sent_now))
    table.add_row("Failed", str(result.failed_now))
    table.add_row("Skipped", str(result.skipped_sent))
    table.add_row("Blacklisted skipped", str(result.blacklisted_skipped))
    table.add_row("Warm-up remaining", str(result.warm_up_remaining))
    table.add_row("Reply blacklisted now", str(result.reply_blacklisted_now))
    table.add_row("Output file", str(result.output_file))
    return table

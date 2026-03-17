# Botfactory Lead Machine

## Overview
A Python-based web scraper and email outreach automation tool targeting GoldenPages.uz. It scrapes business leads, generates personalized email content using Google Gemini AI, and sends cold outreach emails via Gmail SMTP or Gmail API.

## Architecture
- **Language**: Python 3.10
- **Web Framework**: Flask (via `render_web_service.py`)
- **Production Server**: Gunicorn
- **Scraper**: `goldenpages_scraper/` package — scrapes business listings from GoldenPages.uz
- **Core Package**: `botfactory/` — all main logic, split into focused modules
- **Email**: Gmail SMTP or Gmail API transport
- **AI**: Google Gemini (optional, for email personalization)
- **Storage**: Excel (.xlsx) file or Google Sheets
- **Scheduler**: APScheduler (optional, cron-based pipeline scheduling)
- **Notifications**: Telegram bot (optional)

## Package Structure

### `botfactory/` (core package)
| Module | Responsibility |
|--------|----------------|
| `models.py` | All dataclasses: AppConfig, SMTPConfig, BrandConfig, EmailDraft, etc. |
| `constants.py` | EMAIL_RE, keyword lists, LEAD_COLUMNS, DEFAULT_HTML_TEMPLATE |
| `campaign_data.py` | LANGUAGE_LABELS, CAMPAIGN_COPY (uz/ru marketing copy) |
| `env_utils.py` | getenv_str, getenv_int, getenv_bool, getenv_float, normalize_secret |
| `config.py` | build_parser, build_config, email_transport_label |
| `validation.py` | validate_email_address, is_usable_email_validation, validate_email_config |
| `utils.py` | safe_float, safe_int, email_key, normalize_pipe_list, write_json_log, etc. |
| `leads.py` | build_leads_dataframe, merge_with_existing_leads, load/save leads, infer_category |
| `sheets.py` | Google Sheets read/write integration |
| `blacklist.py` | load/save blacklist, apply_blacklist_to_leads, sync_reply_blacklist |
| `warmup.py` | plan_warm_up_allowance, record_warm_up_progress |
| `gemini.py` | Gemini AI client, prompt builder, generate_ai_outreach |
| `email_compose.py` | compose_outreach_email, render_html_template, campaign selection |
| `email_sender.py` | send_email_with_backoff, Gmail API, Brevo API, SMTP senders |
| `reporting.py` | Rich table summaries for scrape/email results |
| `pipeline.py` | main_async, run_scrape_phase, run_email_phase, run_reply_sync_phase |

### `goldenpages_scraper/` (scraper sub-package)
Original scraper package for GoldenPages.uz.

## Entry Points
- `render_web_service.py` — Flask web app with REST API + state persistence
- `main.py` — Thin CLI entry point, re-exports from `botfactory/`

## Web Service Endpoints
- `GET /` — Dashboard: shows status, lead counts, config
- `GET /healthz` — Health check
- `GET /status` — Detailed pipeline state
- `POST /trigger` — Trigger the pipeline (`{"mode": "scrape"|"email"|"all"|"sync-replies"}`)

## Running
The workflow runs: `PORT=5000 python render_web_service.py`
Listens on `0.0.0.0:5000`.

## Improvements Made
1. **Modular architecture**: `main.py` (2365 lines) split into 15 focused modules in `botfactory/`
2. **State persistence**: Pipeline state now saved to `logs/web_state.json` — survives server restarts
3. **Error logs**: Full stack traces saved to `logs/pipeline_error_*.log` on failure
4. **Clean entry points**: `main.py` is now a thin re-export layer (~60 lines)

## Configuration
All configuration is via environment variables. See `.env.example` for the full list.
Key variables:
- `SCRAPE_SEED_URL` — GoldenPages.uz category URL to scrape
- `GEMINI_API_KEY` / `GEMINI_ENABLED` — Gemini AI for email generation
- `GMAIL_EMAIL` / `GMAIL_APP_PASSWORD` — Gmail SMTP credentials
- `GMAIL_API_*` — Gmail API OAuth credentials (alternative transport)
- `GOOGLE_SHEETS_*` — Google Sheets integration for lead storage
- `TELEGRAM_BOT_TOKEN` — Optional Telegram bot
- `RENDER_TRIGGER_TOKEN` — Optional auth token for `/trigger` endpoint
- `RENDER_ENABLE_SCHEDULER` — Enable APScheduler for cron-based runs

## Deployment
Deployed as a VM (always-running) with gunicorn:
```
gunicorn render_web_service:app --bind=0.0.0.0:5000 --workers=1 --threads=4 --timeout=180
```

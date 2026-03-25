#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from playwright.sync_api import BrowserContext, Download, Page, TimeoutError, sync_playwright


CHATGPT_URL = "https://chatgpt.com/"

# User-provided selectors from the requested click flow.
STEP_1_SELECTOR = "#radix-_R_bhqld36753kqicm_ > div.min-w-0"
STEP_2_SELECTOR = "#radix-_R_bhqld36753kqicmH1_ > div > div:nth-child(7)"
STEP_3_SELECTOR = "#radix-_r_8i_-trigger-Account > div.flex.min-w-0.grow.items-center.gap-2\\.5"
STEP_4_SELECTOR = "#radix-_r_8i_-content-Account > section:nth-child(1) > div:nth-child(5) > div > div > button > div"
STEP_7_SELECTOR = (
    "#root > div > div.flex-item.width-grow > div > div.App-contents.flex-container.spacing-16.direction-column.width-12 "
    "> div.flex-item.width-auto > div > div.App-InvoiceDetails.flex-item.width-grow.flex-container.direction-column "
    "> table > tbody > tr:nth-child(4) > td > div > button:nth-child(1) > div"
)

MONTH_TO_SELECTOR = {
    "march": (
        "#customer_portal_page_body > div.db-CustomerPortalRoot > div > div > div.⚙.rs-0.as-0.as-1.as-2.as-3.as-4.as-5.as-6.as-7.as-8.⚙1te0h1l "
        "> div > div > div > div:nth-child(2) > div > div > div:nth-child(2) > div > div:nth-child(2) > div > div > div:nth-child(4) > div > div "
        "> div.⚙.rs-0.as-5.as-1n.⚙bitx8m > div > a:nth-child(1) > div"
    ),
    "february": (
        "#customer_portal_page_body > div.db-CustomerPortalRoot > div > div > div.⚙.rs-0.as-0.as-1.as-2.as-3.as-4.as-5.as-6.as-7.as-8.⚙1te0h1l "
        "> div > div > div > div:nth-child(2) > div > div > div:nth-child(2) > div > div:nth-child(2) > div > div > div:nth-child(4) > div > div "
        "> div.⚙.rs-0.as-5.as-1n.⚙bitx8m > div > a:nth-child(2)"
    ),
    "january": (
        "#customer_portal_page_body > div.db-CustomerPortalRoot > div > div > div.⚙.rs-0.as-0.as-1.as-2.as-3.as-4.as-5.as-6.as-7.as-8.⚙1te0h1l "
        "> div > div > div > div:nth-child(2) > div > div > div:nth-child(2) > div > div:nth-child(2) > div > div > div:nth-child(4) > div > div "
        "> div.⚙.rs-0.as-5.as-1n.⚙bitx8m > div > a:nth-child(3)"
    ),
}

MONTH_ALIASES = {
    "january": ["january", "jan"],
    "february": ["february", "feb"],
    "march": ["march", "mar"],
    "april": ["april", "apr"],
    "may": ["may"],
    "june": ["june", "jun"],
    "july": ["july", "jul"],
    "august": ["august", "aug"],
    "september": ["september", "sep", "sept"],
    "october": ["october", "oct"],
    "november": ["november", "nov"],
    "december": ["december", "dec"],
}


def _normalize_month(month_text: str) -> str:
    value = re.sub(r"\s+", " ", month_text or "").strip().lower()
    for canonical, aliases in MONTH_ALIASES.items():
        if value in aliases:
            return canonical
    return value


def _month_regex(month_text: str) -> re.Pattern[str]:
    canonical = _normalize_month(month_text)
    aliases = MONTH_ALIASES.get(canonical, [canonical])
    pattern = "|".join(re.escape(item) for item in aliases if item)
    return re.compile(rf"\b({pattern})\b", re.IGNORECASE)


def _wait_new_page(context: BrowserContext, before_pages: Iterable[Page], timeout_ms: int = 20000) -> Optional[Page]:
    before_ids = {id(p) for p in before_pages}
    end_time = time.time() + (timeout_ms / 1000)
    while time.time() < end_time:
        for page in context.pages:
            if id(page) not in before_ids:
                page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
                return page
        time.sleep(0.2)
    return None


def _click_if_visible(page: Page, selector: str, timeout_ms: int = 5000) -> bool:
    try:
        locator = page.locator(selector).first
        locator.wait_for(state="visible", timeout=timeout_ms)
        locator.click(timeout=timeout_ms)
        return True
    except Exception:
        return False


def _click_in_order(page: Page, selectors: list[str], action_name: str) -> None:
    for selector in selectors:
        if _click_if_visible(page, selector):
            return
    raise RuntimeError(f"Could not perform step: {action_name}. Tried selectors: {selectors}")


def _open_billing_portal(page: Page, context: BrowserContext) -> Page:
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1200)

    _click_in_order(
        page,
        [
            STEP_1_SELECTOR,
            "button[aria-haspopup='menu'] div.min-w-0",
            "button:has(div.min-w-0)",
        ],
        "open sidebar/account menu",
    )
    _click_in_order(
        page,
        [
            STEP_2_SELECTOR,
            "[id^='radix-'] div:nth-child(7)",
            "div[role='menuitem']:has-text('Settings')",
            "div[role='menuitem']:has-text('Param')",
        ],
        "open settings",
    )
    _click_in_order(
        page,
        [
            STEP_3_SELECTOR,
            "[id*='trigger-Account']",
            "button:has-text('Account')",
        ],
        "open Account tab in popup",
    )

    previous_pages = list(context.pages)
    _click_in_order(
        page,
        [
            STEP_4_SELECTOR,
            "[id*='content-Account'] button:has-text('Manage')",
            "[id*='content-Account'] button:has-text('Plan')",
            "button:has-text('Manage my subscription')",
            "button:has-text('Gerer')",
        ],
        "open billing portal",
    )

    new_page = _wait_new_page(context, previous_pages, timeout_ms=25000)
    if new_page is not None:
        return new_page
    page.wait_for_load_state("domcontentloaded")
    return page


def _click_month_invoice(page: Page, month_text: str, context: BrowserContext) -> Page:
    month = _normalize_month(month_text)
    month_pattern = _month_regex(month_text)

    previous_pages = list(context.pages)
    clicked = False

    if month in MONTH_TO_SELECTOR:
        clicked = _click_if_visible(page, MONTH_TO_SELECTOR[month], timeout_ms=6000)

    if not clicked:
        try:
            by_link = page.get_by_role("link", name=month_pattern).first
            by_link.wait_for(state="visible", timeout=12000)
            by_link.click(timeout=12000)
            clicked = True
        except Exception:
            clicked = False

    if not clicked:
        try:
            invoice_link = page.locator("a").filter(has_text=month_pattern).first
            invoice_link.wait_for(state="visible", timeout=12000)
            invoice_link.click(timeout=12000)
            clicked = True
        except Exception:
            clicked = False

    if not clicked:
        raise RuntimeError(f"Could not find invoice row for month '{month_text}'.")

    new_page = _wait_new_page(context, previous_pages, timeout_ms=20000)
    if new_page is not None:
        return new_page
    page.wait_for_load_state("domcontentloaded")
    return page


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for idx in range(1, 500):
        candidate = path.with_name(f"{path.stem}_{idx}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not create unique filename for {path.name}")


def _download_invoice(invoice_page: Page, destination_dir: Path, month_text: str) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)

    download_locators = [
        STEP_7_SELECTOR,
        "button:has-text('Download invoice')",
        "button:has-text('Download')",
        "a:has-text('Download invoice')",
        "a:has-text('Download')",
    ]

    for selector in download_locators:
        try:
            locator = invoice_page.locator(selector).first
            locator.wait_for(state="visible", timeout=9000)
            with invoice_page.expect_download(timeout=20000) as dl_info:
                locator.click(timeout=9000)
            download: Download = dl_info.value
            suggested = download.suggested_filename or f"chatgpt-invoice-{month_text}.pdf"
            target = _unique_path(destination_dir / suggested)
            download.save_as(str(target))
            return target
        except TimeoutError:
            continue
        except Exception:
            continue

    raise RuntimeError("Could not trigger invoice download button.")


def _run(month: str, output_dir: Path, headless: bool, user_data_dir: Path) -> Path:
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=headless,
            accept_downloads=True,
        )
        try:
            page = context.new_page()
            page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=60000)
            billing_page = _open_billing_portal(page, context)
            invoice_page = _click_month_invoice(billing_page, month, context)
            return _download_invoice(invoice_page, output_dir, month)
        finally:
            context.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download ChatGPT invoice for a selected month (assumes session is already logged in)."
    )
    parser.add_argument("--month", required=True, help='Month to download (e.g. "March").')
    parser.add_argument(
        "--output-dir",
        default="downloads/chatgpt-invoices",
        help="Folder where invoice PDF is saved.",
    )
    parser.add_argument(
        "--user-data-dir",
        default=".chatgpt-profile",
        help="Persistent browser profile directory used to keep logged-in session.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser headless. Keep headed mode if selectors fail and you need visual debugging.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    month = args.month.strip()
    if not month:
        print("Month cannot be empty.")
        return 1

    output_dir = Path(args.output_dir).expanduser()
    profile_dir = Path(args.user_data_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"Starting invoice download for month: {month}")
    print(f"Profile dir: {profile_dir}")
    print(f"Output dir:  {output_dir}")

    try:
        saved_file = _run(month=month, output_dir=output_dir, headless=args.headless, user_data_dir=profile_dir)
    except Exception as exc:
        print(f"Invoice download failed: {exc}")
        return 1

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] Download complete: {saved_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

try:
    from playwright.sync_api import (
        BrowserContext,
        Download,
        Page,
        TimeoutError as PlaywrightTimeoutError,
        sync_playwright,
    )
    _PLAYWRIGHT_IMPORT_ERROR: Optional[Exception] = None
except ModuleNotFoundError as exc:
    BrowserContext = Download = Page = object  # type: ignore[assignment]
    PlaywrightTimeoutError = TimeoutError  # type: ignore[assignment]
    sync_playwright = None  # type: ignore[assignment]
    _PLAYWRIGHT_IMPORT_ERROR = exc


CHATGPT_URL = "https://chatgpt.com/"
LOGIN_EMAIL = "denvercdp1@gmail.com"

# User-provided selectors from the requested click flow.
LOGIN_STEP_1_SELECTOR = (
    "#stage-slideover-sidebar > div > div.opacity-100.motion-safe\\:transition-opacity.motion-safe\\:duration-150."
    "motion-safe\\:ease-linear.h-full.w-\\(--sidebar-width\\).overflow-x-clip.overflow-y-auto.text-clip.whitespace-nowrap."
    "bg-\\(--sidebar-bg\\,var\\(--bg-elevated-secondary\\)\\) > nav > div.sticky.bottom-0.p-5.border-token-border-heavy."
    "border-t > div.-mx-1\\.5 > button > div"
)
LOGIN_STEP_3_SELECTOR = "#radix-_r_5k_ > div > div > div > form > button > div"
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


def _is_captcha_present(page: Page) -> bool:
    selectors = [
        "iframe[src*='turnstile']",
        "iframe[src*='captcha']",
        "iframe[title*='challenge']",
        "iframe[title*='captcha']",
        "input[name='cf-turnstile-response']",
        "text=/verify you are human|captcha|security check/i",
    ]
    for selector in selectors:
        try:
            if page.locator(selector).count() > 0:
                return True
        except Exception:
            continue
    return False


def _try_auto_click_captcha(page: Page) -> bool:
    # Best-effort attempt for common widget styles (Cloudflare/ReCAPTCHA).
    frame_selectors = [
        "iframe[src*='turnstile']",
        "iframe[src*='captcha']",
        "iframe[title*='challenge']",
        "iframe[title*='captcha']",
    ]
    checkbox_selectors = [
        "input[type='checkbox']",
        "#recaptcha-anchor",
        "div.recaptcha-checkbox-border",
    ]

    for frame_selector in frame_selectors:
        for checkbox_selector in checkbox_selectors:
            try:
                frame_checkbox = page.frame_locator(frame_selector).first.locator(checkbox_selector).first
                frame_checkbox.click(timeout=2000)
                return True
            except Exception:
                continue
    return False


def _handle_captcha_if_present(page: Page, headless: bool, captcha_wait_seconds: int) -> None:
    if not _is_captcha_present(page):
        return

    print("Captcha detected after login start.")
    if headless:
        print("Headless mode reduces captcha solve reliability. Consider running without --headless.")

    end_time = time.time() + max(captcha_wait_seconds, 30)
    last_auto_attempt = 0.0
    notified_manual = False

    while time.time() < end_time:
        if not _is_captcha_present(page):
            page.wait_for_timeout(800)
            return

        # Retry automatic interaction occasionally, then rely on manual solve.
        if time.time() - last_auto_attempt > 4:
            _try_auto_click_captcha(page)
            last_auto_attempt = time.time()

        if not headless and not notified_manual:
            print("Please solve the captcha manually in the opened browser window.")
            notified_manual = True

        page.wait_for_timeout(1000)

    raise RuntimeError(
        f"Captcha was not solved within {captcha_wait_seconds} seconds. "
        "Please rerun and solve captcha manually sooner (headed mode recommended)."
    )


def _run_login_start_flow(page: Page, headless: bool, captcha_wait_seconds: int) -> None:
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1000)

    _click_in_order(
        page,
        [
            LOGIN_STEP_1_SELECTOR,
            "#stage-slideover-sidebar button div",
            "#stage-slideover-sidebar button",
        ],
        "open login popup from sidebar",
    )

    email_input = page.locator("#email").first
    email_input.wait_for(state="visible", timeout=20000)
    email_input.fill(LOGIN_EMAIL, timeout=10000)

    _click_in_order(
        page,
        [
            LOGIN_STEP_3_SELECTOR,
            "#radix-_r_5k_ form button",
            "form button:has-text('Continue')",
        ],
        "submit login email in popup",
    )
    page.wait_for_timeout(1800)
    _handle_captcha_if_present(page, headless=headless, captcha_wait_seconds=captcha_wait_seconds)


def _open_billing_portal(
    page: Page,
    context: BrowserContext,
    headless: bool,
    captcha_wait_seconds: int,
) -> Page:
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1200)

    _run_login_start_flow(page, headless=headless, captcha_wait_seconds=captcha_wait_seconds)

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
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue

    raise RuntimeError("Could not trigger invoice download button.")


def _run(
    month: str,
    output_dir: Path,
    headless: bool,
    user_data_dir: Path,
    captcha_wait_seconds: int,
) -> Path:
    if _PLAYWRIGHT_IMPORT_ERROR is not None or sync_playwright is None:
        raise RuntimeError(
            "Missing dependency 'playwright'. Install requirements with "
            "'pip install -r requirements.txt' and run "
            "'python -m playwright install chromium' (or python3 -m ...)."
        ) from _PLAYWRIGHT_IMPORT_ERROR

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=headless,
            accept_downloads=True,
        )
        try:
            page = context.new_page()
            page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=60000)
            billing_page = _open_billing_portal(
                page,
                context,
                headless=headless,
                captcha_wait_seconds=captcha_wait_seconds,
            )
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
    parser.add_argument(
        "--captcha-wait-seconds",
        type=int,
        default=240,
        help="How long to wait for captcha resolution after login email submit.",
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
        saved_file = _run(
            month=month,
            output_dir=output_dir,
            headless=args.headless,
            user_data_dir=profile_dir,
            captcha_wait_seconds=int(args.captcha_wait_seconds),
        )
    except Exception as exc:
        print(f"Invoice download failed: {exc}")
        return 1

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] Download complete: {saved_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

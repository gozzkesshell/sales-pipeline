"""LinkedIn Sales Navigator search result exporter.

Uses a dedicated browser profile (./chrome-profile/). You log in once
manually; the session is reused on later runs.

Conservative by design: one run per calendar day, max 4 pages / 100
results per run, randomized human-like delays, warm-up browsing, no
interaction with LinkedIn's DOM or scripts. Read-only extraction via
Playwright's text/locator APIs.

Fingerprint defenses (USE_STEALTH=True): init scripts patch the
browser's own fingerprint surface BEFORE any page loads. They do not
read, modify, or interact with LinkedIn's DOM. Set USE_STEALTH=False
to disable.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import random
import sys
import time
from datetime import date, datetime
from pathlib import Path

try:
    from playwright.sync_api import TimeoutError as PWTimeout
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright not installed. Run setup.sh (Mac) or setup.bat (Windows) first.")
    sys.exit(1)


SCRIPT_DIR = Path(__file__).parent.resolve()
PROFILE_DIR = SCRIPT_DIR / "chrome-profile"
STATE_FILE = SCRIPT_DIR / ".scrape-state.json"
OUTPUT_CSV = SCRIPT_DIR / "results.csv"

MAX_RESULTS_PER_RUN = 100
MAX_PAGES_PER_RUN = 4
DAILY_RUN_LIMIT = 1
USE_STEALTH = True
EARLY_EXIT_PROBABILITY = 0.15  # chance to stop early after page 2 or 3

# Realistic Chrome UA matching the actual host OS. We always run real
# Google Chrome (channel="chrome") on Win/Mac, so we only need to match
# the OS in the UA string.
def _user_agent() -> str:
    system = platform.system()
    if system == "Darwin":
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        )
    # Default to Windows
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    )


USER_AGENT = _user_agent()

# Minimal fingerprint patches for real Google Chrome controlled via CDP.
# Because we run actual Chrome (not Chromium), plugins/WebGL/window.chrome/
# codecs/hardwareConcurrency are already genuine — patching them would
# create detectable inconsistencies. We only patch what Playwright/CDP
# itself alters or leaks.
#
# Runs on every new document BEFORE page scripts execute. Does NOT touch
# LinkedIn's DOM or scripts.
STEALTH_INIT_SCRIPT = r"""
(() => {
  // 1. navigator.webdriver is set to true by CDP — the #1 automation tell.
  // Delete the property entirely, matching unautomated Chrome.
  try { delete Object.getPrototypeOf(navigator).webdriver; } catch(e) {}
  try {
    Object.defineProperty(Navigator.prototype, 'webdriver', {
      get: () => undefined, configurable: true,
    });
  } catch(e) {}

  // 2. navigator.languages: pin to a Ukraine-consistent list matching
  // what a Ukrainian professional using English LinkedIn typically has.
  try {
    Object.defineProperty(Navigator.prototype, 'languages', {
      get: () => ['en-US', 'en', 'uk'], configurable: true,
    });
  } catch(e) {}

  // 3. permissions.query: Playwright makes Notification.permission report
  // "default" even when it should be "denied" — fix the inconsistency.
  const origQuery = window.navigator.permissions && window.navigator.permissions.query;
  if (origQuery) {
    window.navigator.permissions.query = (params) =>
      params && params.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission, onchange: null })
        : origQuery(params);
  }
})();
"""


def rand_sleep(lo: float, hi: float) -> None:
    time.sleep(random.uniform(lo, hi))


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"last_run_date": None, "runs_today": 0}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def check_daily_limit() -> dict:
    state = load_state()
    today = date.today().isoformat()
    if state.get("last_run_date") == today:
        if state.get("runs_today", 0) >= DAILY_RUN_LIMIT:
            print(
                f"Daily limit reached ({DAILY_RUN_LIMIT} run/day). "
                "Try again tomorrow — this keeps your account safe."
            )
            sys.exit(1)
    else:
        state["last_run_date"] = today
        state["runs_today"] = 0
    return state


def record_run(state: dict) -> None:
    state["runs_today"] = state.get("runs_today", 0) + 1
    save_state(state)


def random_viewport() -> dict:
    # Common real-laptop resolutions, slightly jittered
    widths = [1366, 1440, 1536, 1600, 1680]
    heights = [768, 800, 864, 900, 1050]
    return {
        "width": random.choice(widths) + random.randint(-8, 8),
        "height": random.choice(heights) + random.randint(-6, 6),
    }


def bezier_move(page, x: float, y: float) -> None:
    """Move mouse from current-ish position to (x,y) along a curve."""
    # Start from a random nearby point — Playwright doesn't expose current
    # mouse position, so we approximate with two preliminary moves.
    start_x = x + random.randint(-400, 400)
    start_y = y + random.randint(-300, 300)
    page.mouse.move(start_x, start_y, steps=1)

    # Cubic bezier with two random control points
    cp1 = (start_x + random.randint(-200, 200), start_y + random.randint(-200, 200))
    cp2 = (x + random.randint(-200, 200), y + random.randint(-200, 200))
    steps = random.randint(18, 34)
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        bx = mt**3 * start_x + 3 * mt**2 * t * cp1[0] + 3 * mt * t**2 * cp2[0] + t**3 * x
        by = mt**3 * start_y + 3 * mt**2 * t * cp1[1] + 3 * mt * t**2 * cp2[1] + t**3 * y
        # ease-in-out: slower at start/end
        page.mouse.move(bx, by, steps=1)
        # micro-pause, heavier near endpoints
        edge = min(t, 1 - t)
        time.sleep(random.uniform(0.004, 0.018) * (1 + (0.5 - edge)))


def human_scroll(page, passes: int | None = None) -> None:
    """Scroll with acceleration, deceleration, and occasional pauses."""
    if passes is None:
        passes = random.randint(7, 12)
    for i in range(passes):
        # variable step — accelerate then decelerate
        phase = i / max(1, passes - 1)
        base = 200 + int(300 * math.sin(phase * math.pi))  # peak in middle
        delta = base + random.randint(-80, 80)
        page.mouse.wheel(0, delta)
        rand_sleep(0.35, 1.1)
        # Occasional mid-scroll "stop and read"
        if random.random() < 0.18:
            rand_sleep(1.4, 3.2)
    # Occasional scroll-back, as if re-reading
    if random.random() < 0.35:
        page.mouse.wheel(0, -random.randint(120, 320))
        rand_sleep(0.6, 1.4)


def hover_read_random_cards(page, n: int = 2) -> None:
    """Hover over a couple of result cards for realism."""
    try:
        items = page.locator("ol[role='list'] > li").all()
        if not items:
            items = page.locator("li.artdeco-list__item").all()
        if not items:
            return
        sample = random.sample(items, min(n, len(items)))
        for item in sample:
            try:
                box = item.bounding_box()
                if not box:
                    continue
                tx = box["x"] + box["width"] * random.uniform(0.2, 0.8)
                ty = box["y"] + box["height"] * random.uniform(0.2, 0.8)
                bezier_move(page, tx, ty)
                rand_sleep(0.8, 2.4)
            except Exception:
                continue
    except Exception:
        pass


def is_blocked_page(page) -> tuple[bool, str]:
    url = page.url.lower()
    for marker in ["/checkpoint/challenge", "/authwall", "security-verification", "captcha"]:
        if marker in url:
            return True, f"URL contains '{marker}'"
    # Text signals
    try:
        body_text = page.locator("body").inner_text(timeout=3000).lower()
    except PWTimeout:
        return False, ""
    signals = [
        "let's do a quick security check",
        "unusual activity",
        "verify you're a human",
        "we've detected automated behavior",
        "your account has been restricted",
        "please complete this security check",
        "confirm you're not a robot",
        "puzzle",
    ]
    for s in signals:
        if s in body_text:
            return True, f"page text: '{s}'"
    return False, ""


def prompt_solve_challenge(page, why: str) -> bool:
    """Pause and let the user solve a captcha/challenge manually.

    Returns True if the page is clear after the user solves it, False
    if they give up or it's still blocked after retries.
    """
    print()
    print("=" * 60)
    print("!!! Security challenge detected.")
    print(f"!!! Reason: {why}")
    print("!!! Current URL:", page.url)
    print("=" * 60)
    print()
    print(">>> Please solve the challenge manually in the opened browser.")
    print(">>> Take your time — no rush. Move the mouse naturally.")
    print(">>> When you're back on a normal Sales Navigator page,")
    print(">>> come here and press Enter. Type 'skip' + Enter to abort.")
    print()

    for attempt in range(3):
        answer = input(f"[attempt {attempt + 1}/3] Press Enter when solved (or 'skip'): ").strip().lower()
        if answer == "skip":
            print("Aborting at user request.")
            return False
        # Small pause so any post-solve redirect settles
        rand_sleep(2.0, 4.0)
        still_blocked, new_why = is_blocked_page(page)
        if not still_blocked:
            print("Challenge cleared. Continuing with a longer cooldown...")
            # Extra cooldown — LinkedIn just challenged us, slow down
            rand_sleep(20.0, 40.0)
            return True
        print(f"Still looks blocked: {new_why}. Try again or type 'skip'.")
    print("Could not clear challenge after 3 attempts. Aborting.")
    return False


def _abs_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return f"https://www.linkedin.com{href}"


def extract_results_on_page(page) -> list[dict]:
    """Read visible result cards from the current search results page."""
    results: list[dict] = []
    try:
        page.wait_for_selector("ol[role='list'] li, li.artdeco-list__item", timeout=15000)
    except PWTimeout:
        print("  (timed out waiting for results list)")
        return results

    items = page.locator("ol[role='list'] > li").all()
    if not items:
        items = page.locator("li.artdeco-list__item").all()

    for item in items:
        try:
            text = item.inner_text(timeout=2500)
        except PWTimeout:
            continue
        if not text or len(text.strip()) < 5:
            continue

        name = ""
        profile_url = ""
        try:
            link = item.locator("a[href*='/sales/lead/']").first
            href = link.get_attribute("href", timeout=1500)
            profile_url = _abs_url(href or "")
            raw_name = link.inner_text(timeout=1500) or ""
            name = raw_name.strip().split("\n")[0].strip()
        except Exception:
            pass

        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        if not name and lines:
            name = lines[0]

        title = ""
        company = ""
        for ln in lines[1:8]:
            if " at " in ln.lower() and not title:
                parts = ln.split(" at ", 1)
                title = parts[0].strip()
                company = parts[1].strip() if len(parts) > 1 else ""
                break
        if not title and len(lines) > 1:
            title = lines[1]

        description = " | ".join(lines[:8])
        results.append({
            "name": name, "title": title, "company": company,
            "description": description, "profile_url": profile_url,
        })
    return results


def go_to_next_page(page) -> bool:
    """Click the Next button with bezier mouse movement."""
    try:
        btn = page.get_by_role("button", name="Next").first
        if not btn.is_visible(timeout=3000):
            return False
        if btn.is_disabled():
            return False
        box = btn.bounding_box()
        if not box:
            return False
        tx = box["x"] + box["width"] / 2 + random.randint(-5, 5)
        ty = box["y"] + box["height"] / 2 + random.randint(-3, 3)
        bezier_move(page, tx, ty)
        rand_sleep(0.25, 0.8)
        btn.click()
        return True
    except Exception as e:
        print(f"  could not advance to next page: {e}")
        return False


def append_csv(rows: list[dict]) -> None:
    if not rows:
        print("No rows to write.")
        return
    fields = ["name", "title", "company", "description", "profile_url", "scraped_at", "source_url"]
    new_file = not OUTPUT_CSV.exists()
    with OUTPUT_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def is_logged_in(page) -> bool:
    url = page.url
    if "login" in url or "/checkpoint/" in url or "/authwall" in url:
        return False
    return "linkedin.com/sales" in url


def warmup(page) -> None:
    """Browse Sales Nav home like a human before hitting the search URL."""
    print("Warming up session (idle browsing)...")
    try:
        page.goto("https://www.linkedin.com/sales/home", wait_until="domcontentloaded", timeout=30000)
    except PWTimeout:
        pass
    rand_sleep(3.0, 6.0)
    human_scroll(page, passes=random.randint(3, 6))
    rand_sleep(2.0, 5.0)
    # Move mouse aimlessly
    for _ in range(random.randint(2, 4)):
        x = random.randint(200, 1100)
        y = random.randint(200, 700)
        bezier_move(page, x, y)
        rand_sleep(0.5, 1.8)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export LinkedIn Sales Navigator search results to CSV."
    )
    parser.add_argument("url", nargs="?", help="Sales Navigator search URL")
    args = parser.parse_args()

    url = args.url or input("Paste Sales Navigator search URL: ").strip()
    if "linkedin.com/sales/search" not in url:
        print("That doesn't look like a Sales Navigator search URL.")
        sys.exit(1)

    state = check_daily_limit()
    PROFILE_DIR.mkdir(exist_ok=True)
    viewport = random_viewport()

    print(f"Launching browser (viewport {viewport['width']}x{viewport['height']})...")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            channel="chrome",  # use real Google Chrome, not bundled Chromium
            headless=False,
            viewport=viewport,
            locale="en-US",
            timezone_id="Europe/Kyiv",
            user_agent=USER_AGENT,
            color_scheme="light",
            reduced_motion="no-preference",
            # NOTE: intentionally NOT passing --disable-blink-features=AutomationControlled;
            # that flag alone is now a detection tell. Stealth init scripts below handle it.
        )
        if USE_STEALTH:
            ctx.add_init_script(STEALTH_INIT_SCRIPT)

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        page.goto("https://www.linkedin.com/sales/", wait_until="domcontentloaded")
        rand_sleep(2.0, 4.0)

        blocked, why = is_blocked_page(page)
        if blocked:
            if not prompt_solve_challenge(page, why):
                ctx.close()
                sys.exit(2)

        if not is_logged_in(page):
            print()
            print(">>> Please log into LinkedIn Sales Navigator in the opened browser.")
            print(">>> When you're on the Sales Navigator home page, press Enter here.")
            print()
            input()

        warmup(page)

        print("Navigating to search URL...")
        page.goto(url, wait_until="domcontentloaded")
        rand_sleep(4.0, 7.0)

        blocked, why = is_blocked_page(page)
        if blocked:
            if not prompt_solve_challenge(page, why):
                ctx.close()
                sys.exit(2)
            # After solving, re-navigate to the search URL
            print("Re-navigating to search URL after challenge...")
            page.goto(url, wait_until="domcontentloaded")
            rand_sleep(4.0, 7.0)

        all_results: list[dict] = []
        pages_done = 0
        source_url = page.url
        scraped_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        while pages_done < MAX_PAGES_PER_RUN and len(all_results) < MAX_RESULTS_PER_RUN:
            print(f"Page {pages_done + 1}: scrolling to load results...")
            human_scroll(page)
            rand_sleep(1.5, 3.5)

            # Occasionally pause to "read" a few cards
            if random.random() < 0.7:
                hover_read_random_cards(page, n=random.randint(1, 3))

            blocked, why = is_blocked_page(page)
            if blocked:
                if not prompt_solve_challenge(page, why):
                    print("  saving what we have and exiting.")
                    break
                # After solving mid-scrape, the current page state is
                # unreliable — skip to saving and let user re-run later.
                print("  challenge cleared, but ending this run to be safe.")
                break

            page_results = extract_results_on_page(page)
            print(f"  extracted {len(page_results)} results")

            for r in page_results:
                r["scraped_at"] = scraped_at
                r["source_url"] = source_url
                all_results.append(r)
                if len(all_results) >= MAX_RESULTS_PER_RUN:
                    break

            pages_done += 1
            if pages_done >= MAX_PAGES_PER_RUN or len(all_results) >= MAX_RESULTS_PER_RUN:
                break

            # Random early exit — real humans don't always finish
            if pages_done >= 2 and random.random() < EARLY_EXIT_PROBABILITY:
                print(f"  stopping early after {pages_done} pages (human-like).")
                break

            pause = random.uniform(30.0, 90.0)
            print(f"  pausing {pause:.0f}s before next page...")
            time.sleep(pause)

            if not go_to_next_page(page):
                print("  no more pages available.")
                break
            rand_sleep(4.0, 7.0)

        # Dedupe
        seen: set[str] = set()
        unique: list[dict] = []
        for r in all_results:
            key = r.get("profile_url") or r.get("name") or ""
            if key and key not in seen:
                seen.add(key)
                unique.append(r)

        append_csv(unique)
        record_run(state)

        print()
        print(f"Saved {len(unique)} rows to {OUTPUT_CSV}")
        print("Closing browser in 5s...")
        time.sleep(5)
        ctx.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)

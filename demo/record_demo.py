"""
Poly-QL demo recorder — uses Playwright to drive the app and capture a video.
Output: demo/polyql_demo.webm

Demo flow:
  1. Login
  2. Select Codex (o4-mini) as the provider
  3. Ask a tough multi-condition question → assistant asks a clarifying question
  4. Answer the clarifying question → get the SQL
  5. Schema / ERD tab tour
  6. Join Path — find route between two tables
"""

import time
from playwright.sync_api import sync_playwright

BASE_URL  = "http://localhost:5173"
USERNAME  = "demo"
PASSWORD  = "demo1234"

# Tough question designed to trigger a clarifying question from the assistant
TOUGH_QUESTION = (
    "Find customers who placed more than 3 orders in the last 6 months "
    "but whose average order value dropped by more than 20% compared to "
    "the previous 6 months, and rank them by the size of the drop"
)

# Plausible answer to whatever clarifying question the assistant asks
CLARIFY_ANSWER = (
    "Use calendar months. Count only completed orders, not cancelled ones. "
    "Order value means the total amount on the order."
)


def slow_type(element, text, delay=55):
    element.click()
    for ch in text:
        element.type(ch)
        time.sleep(delay / 1000)


def wait_for_response(page, timeout=30):
    """Wait until the assistant bubble stops loading (spinner disappears)."""
    try:
        page.wait_for_selector(".loading, [data-loading]", state="hidden", timeout=3000)
    except Exception:
        pass
    time.sleep(timeout)


def run_demo(page):
    page.set_viewport_size({"width": 1440, "height": 900})

    # ── 1. Login ──────────────────────────────────────────────────────────────
    print("Step 1: Login")
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    time.sleep(1.5)

    page.locator('input[type="text"]').first.fill(USERNAME)
    page.locator('input[type="password"]').first.fill(PASSWORD)
    page.locator('button[type="submit"]').click()
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    # ── 2. Select Codex as provider ───────────────────────────────────────────
    print("Step 2: Select Codex provider")
    try:
        # Provider dropdown — look for a select that has 'codex' as an option
        selects = page.locator("select").all()
        for sel in selects:
            opts = sel.locator("option").all()
            values = [o.get_attribute("value") or "" for o in opts]
            if "codex" in values:
                sel.select_option("codex")
                time.sleep(0.8)
                break
    except Exception as e:
        print(f"  Provider select skipped: {e}")

    # ── 3. Ask the tough question ─────────────────────────────────────────────
    print("Step 3: Ask tough question (expecting clarify)")
    textarea = page.locator("textarea").first
    slow_type(textarea, TOUGH_QUESTION)
    time.sleep(0.5)
    # Click send button or press Ctrl+Enter
    try:
        page.locator('button[aria-label="Send"], button:has-text("Send")').first.click()
    except Exception:
        page.keyboard.press("Control+Enter")
    time.sleep(1)

    print("  Waiting for assistant clarifying question (~20s)...")
    time.sleep(22)   # give the LLM time to respond with a clarify bubble

    # ── 4. Answer the clarifying question ─────────────────────────────────────
    print("Step 4: Answer clarifying question")
    textarea2 = page.locator("textarea").first
    slow_type(textarea2, CLARIFY_ANSWER)
    time.sleep(0.5)
    try:
        page.locator('button[aria-label="Send"], button:has-text("Send")').first.click()
    except Exception:
        page.keyboard.press("Control+Enter")

    print("  Waiting for SQL response (~25s)...")
    time.sleep(27)   # wait for full SQL generation

    # ── 5. Schema / ERD tab ───────────────────────────────────────────────────
    print("Step 5: Schema / ERD tour")
    page.click("text=Schema / ERD")
    page.wait_for_load_state("networkidle")
    time.sleep(4)

    # ── 6. Join Path ──────────────────────────────────────────────────────────
    print("Step 6: Join Path")
    page.click("text=Join Path")
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    try:
        page.wait_for_function(
            "() => [...document.querySelectorAll('select option')].length > 5",
            timeout=8000,
        )
        selects = page.locator("select").all()
        # Instance selector is index 0; From = 1, To = 2
        if len(selects) >= 3:
            selects[1].select_option(index=1)
            time.sleep(0.6)
            selects[2].select_option(index=4)
            time.sleep(0.6)
            page.click("text=Find Path")
            time.sleep(5)
    except Exception as e:
        print(f"  Join path skipped: {e}")

    print("Demo complete")
    time.sleep(2)


def main():
    import os, glob, shutil
    os.makedirs("demo", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=150)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir="demo/",
            record_video_size={"width": 1440, "height": 900},
        )
        page = context.new_page()
        try:
            run_demo(page)
        except Exception as e:
            print(f"Error: {e}")
            import traceback; traceback.print_exc()
        finally:
            page.close()
            context.close()
            browser.close()

    videos = sorted(
        [f for f in glob.glob("demo/*.webm") if "polyql_demo" not in f],
        key=os.path.getmtime,
    )
    target = "demo/polyql_demo.webm"
    if videos:
        shutil.move(videos[-1], target)
        print(f"\nDemo saved → {target}  ({os.path.getsize(target)//1024} KB)")
    else:
        print("No new video file found.")


if __name__ == "__main__":
    main()

"""
Poly-QL demo recorder - Playwright headless-off with video capture.

Flow:
  1. Login
  2. Select Codex provider + SQL query type
  3. Ask a tough question -> assistant asks clarifying question
  4. Answer clarify -> SQL is generated and displayed in full
  5. Brief pause to read the SQL
  6. Join Path tab - pick two tables, show graph
  7. Schema / ERD tab - quick tour

Run:  python demo/record_demo.py
Out:  demo/polyql_demo.webm
"""

import os, glob, shutil, time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE_URL  = "http://localhost:5173"
USERNAME  = "demo"
PASSWORD  = "demo1234"

# Viewport & video - must match so nothing is cut
W, H = 1280, 800

QUESTION = (
    "Which product categories had a month-over-month revenue decline "
    "for at least 3 consecutive months in 2024, and what was the "
    "average order size for those categories during that period?"
)

CLARIFY_ANSWER = (
    "Use order date to determine the month. "
    "Revenue means sum of unit price times quantity. "
    "Include all order statuses."
)


# -- Helpers --------------------------------------------------------------------

def slow_type(locator, text, delay_ms=60):
    locator.click()
    locator.fill("")
    for ch in text:
        locator.type(ch)
        time.sleep(delay_ms / 1000)


def wait_for_loading_then_done(page, timeout=90000):
    """Wait for the loading dots (●) to appear, then disappear."""
    # Wait for loading to START (up to 8s), then wait for it to END
    try:
        page.locator('span', has_text="●").first.wait_for(state="visible", timeout=8000)
    except Exception:
        pass  # may already be gone or never appeared
    try:
        page.locator('span', has_text="●").first.wait_for(state="hidden", timeout=timeout)
    except Exception:
        pass


def scroll_to_bottom(page):
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    # Also scroll the messages pane to the bottom
    page.evaluate("""
        const divs = [...document.querySelectorAll('div')];
        const chat = divs.find(d => d.scrollHeight > d.clientHeight && d.clientHeight > 400);
        if (chat) chat.scrollTop = chat.scrollHeight;
    """)
    time.sleep(0.5)


# -- Demo steps -----------------------------------------------------------------

def step_login(page):
    print("[1/6] Login")
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    time.sleep(1)

    page.locator('input[type="text"]').first.fill(USERNAME)
    page.locator('input[type="password"]').first.fill(PASSWORD)
    time.sleep(0.4)
    page.locator('button[type="submit"]').click()
    page.wait_for_load_state("networkidle")
    time.sleep(2)


def step_select_provider(page):
    print("[2/6] Select Codex provider")
    # The toolbar has multiple selects; find the one with provider options
    selects = page.locator("select").all()
    for sel in selects:
        opts = [o.get_attribute("value") or "" for o in sel.locator("option").all()]
        if "codex" in opts or "anthropic" in opts:
            sel.select_option("codex")
            time.sleep(0.6)
            break
    # Set query type to SQL explicitly
    for sel in page.locator("select").all():
        opts = [o.get_attribute("value") or "" for o in sel.locator("option").all()]
        if "sql" in opts and "spark_sql" in opts:
            sel.select_option("sql")
            time.sleep(0.4)
            break


def step_ask_question(page):
    print("[3/6] Ask tough question - expecting clarify")
    ta = page.locator('textarea[placeholder*="Ask"]')
    slow_type(ta, QUESTION, delay_ms=45)
    time.sleep(0.6)
    page.locator('button:has-text("Send")').click()
    print("     Waiting for clarifying question...")
    wait_for_loading_then_done(page, timeout=45000)
    scroll_to_bottom(page)
    time.sleep(3)   # let viewer read the clarify bubble


def step_answer_clarify(page):
    print("[4/6] Answer clarifying question - waiting for SQL...")
    ta = page.locator('textarea[placeholder*="Ask"]')
    slow_type(ta, CLARIFY_ANSWER, delay_ms=50)
    time.sleep(0.6)
    page.locator('button:has-text("Send")').click()
    # Wait for loading to start then finish
    wait_for_loading_then_done(page, timeout=90000)
    # Hard guarantee: wait for the <pre> SQL block to appear
    print("     Waiting for <pre> SQL block...")
    page.wait_for_selector("pre", timeout=90000)
    scroll_to_bottom(page)
    time.sleep(6)   # let viewer read the full SQL


def step_join_path(page):
    print("[5/6] Join Path tab")
    page.click("text=Join Path")
    page.wait_for_load_state("networkidle")
    time.sleep(1.5)

    try:
        # Wait for table options to load
        page.wait_for_function(
            "() => [...document.querySelectorAll('select option')].length > 6",
            timeout=8000,
        )
        selects = page.locator("select").all()
        # Layout: [instance, from_table, to_table]  - skip instance (idx 0)
        from_sel = next(
            (s for s in selects if len(s.locator("option").all()) > 3
             and any(o.get_attribute("value") for o in s.locator("option").all())),
            None
        )
        if from_sel:
            opts = [o.get_attribute("value") or "" for o in from_sel.locator("option").all()]
            real = [v for v in opts if v]
            if len(real) >= 2:
                from_sel.select_option(real[0])
                time.sleep(0.6)
            # Find the To select (next select with options)
            idx = selects.index(from_sel)
            if idx + 1 < len(selects):
                to_sel = selects[idx + 1]
                to_opts = [o.get_attribute("value") or "" for o in to_sel.locator("option").all()]
                to_real = [v for v in to_opts if v]
                if len(to_real) >= 4:
                    to_sel.select_option(to_real[3])
                elif len(to_real) >= 2:
                    to_sel.select_option(to_real[-1])
                time.sleep(0.6)

        page.locator("text=Find Path").click()
        time.sleep(5)
        scroll_to_bottom(page)
    except Exception as e:
        print(f"     Join path partial: {e}")


def step_schema_erd(page):
    print("[6/6] Schema / ERD")
    page.click("text=Schema / ERD")
    page.wait_for_load_state("networkidle")
    time.sleep(4)


# -- Main -----------------------------------------------------------------------

def main():
    os.makedirs("demo", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[f"--window-size={W},{H}", "--window-position=0,0"],
        )
        context = browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir="demo/",
            record_video_size={"width": W, "height": H},
        )
        page = context.new_page()

        try:
            step_login(page)
            step_select_provider(page)
            step_ask_question(page)
            step_answer_clarify(page)
            step_join_path(page)
            step_schema_erd(page)
            print("Demo complete.")
            time.sleep(2)
        except Exception as e:
            import traceback
            print(f"Error: {e}")
            traceback.print_exc()
        finally:
            page.close()
            context.close()
            browser.close()

    # Save video
    new_vids = sorted(
        [f for f in glob.glob("demo/*.webm") if "polyql_demo" not in f],
        key=os.path.getmtime,
    )
    target = "demo/polyql_demo.webm"
    if new_vids:
        shutil.move(new_vids[-1], target)
        print(f"Saved: {target}  ({os.path.getsize(target) // 1024} KB)")
    else:
        print("No new video found.")


if __name__ == "__main__":
    main()

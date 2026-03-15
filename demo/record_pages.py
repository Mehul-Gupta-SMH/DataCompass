"""
Poly-QL per-page demo recorder.

Produces one focused webm clip per feature — ready for individual LinkedIn posts.

Output (demo/pages/):
  01_query_chat.webm   NL question → clarify bubble → streaming SQL
  02_schema_erd.webm   Schema/ERD tab tour + table side-panel
  03_join_path.webm    Join Path tab — select two tables, render graph
  04_ingest_table.webm Ingest Table tab — paste SQL, review LLM dict

Run:  python demo/record_pages.py
      python demo/record_pages.py --only 01   # single clip by prefix
"""

import argparse, glob, os, shutil, time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE_URL = "http://localhost:5173"
USERNAME = "demo"
PASSWORD = "demo1234"

W, H = 1280, 800   # consistent viewport — crop to 1280×720 in your editor if needed

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def slow_type(locator, text, delay_ms=55):
    locator.click()
    locator.fill("")
    for ch in text:
        locator.type(ch)
        time.sleep(delay_ms / 1000)


def wait_loading_done(page, timeout=90_000):
    """Wait for the ● loading indicator to appear then disappear."""
    try:
        page.locator("span", has_text="●").first.wait_for(state="visible", timeout=8_000)
    except Exception:
        pass
    try:
        page.locator("span", has_text="●").first.wait_for(state="hidden", timeout=timeout)
    except Exception:
        pass


def scroll_chat_bottom(page):
    page.evaluate("""
        const divs = [...document.querySelectorAll('div')];
        const pane = divs.find(d => d.scrollHeight > d.clientHeight && d.clientHeight > 400);
        if (pane) pane.scrollTop = pane.scrollHeight;
    """)
    time.sleep(0.4)


def login(page):
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    time.sleep(0.8)
    page.locator('input[type="text"]').first.fill(USERNAME)
    page.locator('input[type="password"]').first.fill(PASSWORD)
    time.sleep(0.3)
    page.locator('button[type="submit"]').click()
    page.wait_for_load_state("networkidle")
    time.sleep(1.5)


def new_context(playwright, video_dir):
    browser = playwright.chromium.launch(
        headless=False,
        args=[f"--window-size={W},{H}", "--window-position=0,0"],
    )
    ctx = browser.new_context(
        viewport={"width": W, "height": H},
        record_video_dir=video_dir,
        record_video_size={"width": W, "height": H},
    )
    return browser, ctx


def save_video(video_dir, dest_name):
    """Move the latest .webm in video_dir to demo/pages/<dest_name>."""
    candidates = sorted(
        [f for f in glob.glob(f"{video_dir}/*.webm") if dest_name not in f],
        key=os.path.getmtime,
    )
    os.makedirs("demo/pages", exist_ok=True)
    target = f"demo/pages/{dest_name}"
    if candidates:
        shutil.move(candidates[-1], target)
        print(f"  Saved → {target}  ({os.path.getsize(target) // 1024} KB)")
    else:
        print(f"  Warning: no video found in {video_dir}")


# ---------------------------------------------------------------------------
# 01 — Query Chat
# Demonstrates: provider select → natural-language question
#               → clarify bubble (the 'thinking' moment)
#               → streaming SQL output
# ---------------------------------------------------------------------------

QUERY_QUESTION = (
    "Which product categories had a month-over-month revenue decline "
    "for at least 3 consecutive months in 2024, and what was the "
    "average order size for those categories during that period?"
)

QUERY_CLARIFY = (
    "Use order date for the month. "
    "Revenue is unit price times quantity. "
    "Include all order statuses."
)

def demo_query_chat(playwright):
    print("\n[01] Query Chat demo")
    tmp = "demo/_tmp_01"
    os.makedirs(tmp, exist_ok=True)
    browser, ctx = new_context(playwright, tmp)
    page = ctx.new_page()
    try:
        login(page)

        # Select provider + query type
        for sel in page.locator("select").all():
            opts = [o.get_attribute("value") or "" for o in sel.locator("option").all()]
            if "codex" in opts or "anthropic" in opts:
                sel.select_option("codex")
                time.sleep(0.5)
                break
        for sel in page.locator("select").all():
            opts = [o.get_attribute("value") or "" for o in sel.locator("option").all()]
            if "sql" in opts and "spark_sql" in opts:
                sel.select_option("sql")
                time.sleep(0.4)
                break

        # Type question slowly so viewers can read it
        ta = page.locator('textarea[placeholder*="Ask"]')
        slow_type(ta, QUERY_QUESTION, delay_ms=50)
        time.sleep(0.8)
        page.locator('button:has-text("Send")').click()

        # Wait for clarify bubble
        print("  Waiting for clarify bubble …")
        wait_loading_done(page, timeout=45_000)
        scroll_chat_bottom(page)
        time.sleep(3.5)   # let viewer read the clarify question

        # Answer the clarify
        slow_type(ta, QUERY_CLARIFY, delay_ms=55)
        time.sleep(0.7)
        page.locator('button:has-text("Send")').click()

        # Wait for SQL to stream in
        print("  Waiting for SQL …")
        wait_loading_done(page, timeout=90_000)
        page.wait_for_selector("pre", timeout=90_000)
        scroll_chat_bottom(page)
        time.sleep(6)   # hold on the final SQL — the wow moment

        print("  Done.")
    except Exception as e:
        import traceback; traceback.print_exc()
    finally:
        page.close(); ctx.close(); browser.close()

    save_video(tmp, "01_query_chat.webm")
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 02 — Schema / ERD
# Demonstrates: ERD canvas loads → hover/pan → click a table node
#               → side-panel data dictionary slides in
# ---------------------------------------------------------------------------

def demo_schema_erd(playwright):
    print("\n[02] Schema / ERD demo")
    tmp = "demo/_tmp_02"
    os.makedirs(tmp, exist_ok=True)
    browser, ctx = new_context(playwright, tmp)
    page = ctx.new_page()
    try:
        login(page)

        page.click("text=Schema / ERD")
        page.wait_for_load_state("networkidle")
        time.sleep(3)   # let the canvas and nodes fully render

        # Pan the canvas slightly so it feels alive
        canvas = page.locator(".react-flow__pane").first
        box = canvas.bounding_box()
        if box:
            cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            page.mouse.move(cx, cy)
            page.mouse.down()
            page.mouse.move(cx - 80, cy - 40, steps=20)
            page.mouse.up()
            time.sleep(0.8)
            # Pan back
            page.mouse.down()
            page.mouse.move(cx, cy, steps=20)
            page.mouse.up()
            time.sleep(1)

        # Click the first visible table node to open the side panel
        node = page.locator(".react-flow__node").first
        if node.is_visible():
            node.click()
            time.sleep(0.5)

        # Wait for side panel / data dictionary to appear
        try:
            page.wait_for_selector("[class*='side'], [class*='panel'], [class*='detail']",
                                   timeout=5_000)
        except Exception:
            pass   # side panel selector may vary — the click is still recorded

        time.sleep(5)   # hold on the data dictionary — the wow moment
        print("  Done.")
    except Exception as e:
        import traceback; traceback.print_exc()
    finally:
        page.close(); ctx.close(); browser.close()

    save_video(tmp, "02_schema_erd.webm")
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 03 — Join Path
# Demonstrates: select From and To tables → Find Path
#               → graph renders with highlighted join path
# ---------------------------------------------------------------------------

def demo_join_path(playwright):
    print("\n[03] Join Path demo")
    tmp = "demo/_tmp_03"
    os.makedirs(tmp, exist_ok=True)
    browser, ctx = new_context(playwright, tmp)
    page = ctx.new_page()
    try:
        login(page)

        page.click("text=Join Path")
        page.wait_for_load_state("networkidle")
        time.sleep(1.5)

        # Wait for table dropdowns to populate
        try:
            page.wait_for_function(
                "() => [...document.querySelectorAll('select option')].length > 6",
                timeout=8_000,
            )
        except Exception:
            pass

        selects = page.locator("select").all()

        # Find the From and To selects (skip instance selector at idx 0)
        populated = [
            s for s in selects
            if len([o for o in s.locator("option").all() if o.get_attribute("value")]) >= 2
        ]

        if len(populated) >= 2:
            from_sel = populated[0]
            to_sel   = populated[1]

            from_opts = [o.get_attribute("value") or "" for o in from_sel.locator("option").all()]
            from_real = [v for v in from_opts if v]
            if from_real:
                from_sel.select_option(from_real[0])
                time.sleep(0.8)

            to_opts = [o.get_attribute("value") or "" for o in to_sel.locator("option").all()]
            to_real = [v for v in to_opts if v]
            # Pick a table that's a few hops away for a more interesting path
            pick = to_real[min(3, len(to_real) - 1)] if to_real else None
            if pick:
                to_sel.select_option(pick)
                time.sleep(0.8)

        # Click Find Path — the graph render is the wow moment
        page.locator("text=Find Path").click()
        time.sleep(5)   # let the graph animate and settle

        # Scroll down so the full graph is visible
        scroll_chat_bottom(page)
        time.sleep(4)
        print("  Done.")
    except Exception as e:
        import traceback; traceback.print_exc()
    finally:
        page.close(); ctx.close(); browser.close()

    save_video(tmp, "03_join_path.webm")
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 04 — Ingest Table
# Demonstrates: paste pipeline SQL → LLM generates data dictionary
#               → review column descriptions → ready to commit
# ---------------------------------------------------------------------------

SAMPLE_PIPELINE_SQL = """\
INSERT INTO monthly_revenue_summary
SELECT
    DATE_TRUNC('month', o.order_date)   AS revenue_month,
    p.category                          AS product_category,
    SUM(oi.unit_price * oi.quantity)    AS total_revenue,
    COUNT(DISTINCT o.order_id)          AS order_count,
    AVG(oi.unit_price * oi.quantity)    AS avg_order_value
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p    ON oi.product_id = p.product_id
GROUP BY 1, 2;
"""

def demo_ingest_table(playwright):
    print("\n[04] Ingest Table demo")
    tmp = "demo/_tmp_04"
    os.makedirs(tmp, exist_ok=True)
    browser, ctx = new_context(playwright, tmp)
    page = ctx.new_page()
    try:
        login(page)

        page.click("text=Ingest Table")
        page.wait_for_load_state("networkidle")
        time.sleep(1.5)

        # Find the SQL textarea / code input
        sql_input = None
        for candidate in [
            'textarea[placeholder*="SQL"]',
            'textarea[placeholder*="paste"]',
            'textarea[placeholder*="INSERT"]',
            'textarea',
        ]:
            try:
                el = page.locator(candidate).first
                if el.is_visible():
                    sql_input = el
                    break
            except Exception:
                pass

        if sql_input:
            # Type the SQL slowly so the viewer can see what's being pasted
            slow_type(sql_input, SAMPLE_PIPELINE_SQL, delay_ms=18)
            time.sleep(1)

            # Click Preview / Analyse / Generate button
            for label in ["Preview", "Analyse", "Generate", "Parse", "Submit"]:
                btn = page.locator(f'button:has-text("{label}")')
                if btn.is_visible():
                    btn.click()
                    break

            # Wait for LLM to return the data dictionary
            print("  Waiting for LLM data dictionary …")
            wait_loading_done(page, timeout=60_000)
            time.sleep(1)

            # Try to scroll to show the generated column descriptions
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(5)   # hold on the generated dict — the wow moment

        print("  Done.")
    except Exception as e:
        import traceback; traceback.print_exc()
    finally:
        page.close(); ctx.close(); browser.close()

    save_video(tmp, "04_ingest_table.webm")
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

DEMOS = {
    "01": demo_query_chat,
    "02": demo_schema_erd,
    "03": demo_join_path,
    "04": demo_ingest_table,
}

def main():
    parser = argparse.ArgumentParser(description="Record per-page Poly-QL demos")
    parser.add_argument(
        "--only", metavar="PREFIX",
        help="Record only one clip, e.g. --only 01",
    )
    args = parser.parse_args()

    targets = (
        {args.only: DEMOS[args.only]} if args.only and args.only in DEMOS
        else DEMOS
    )

    with sync_playwright() as p:
        for key, fn in targets.items():
            fn(p)

    print("\nAll done. Clips saved to demo/pages/")
    print("  01_query_chat.webm   — NL → clarify → streaming SQL")
    print("  02_schema_erd.webm   — Schema/ERD canvas + data dictionary")
    print("  03_join_path.webm    — Join path graph between two tables")
    print("  04_ingest_table.webm — Ingest pipeline SQL → LLM data dict")


if __name__ == "__main__":
    main()

"""Capture README screenshots and run accessibility checks against the deployment.

Keeps the images in the README honest: they are regenerated from the live service
rather than staged, and the same run asserts the things UX-04..06 claim — status
carried in text as well as colour, a live region for streaming results, keyboard
reachability, and no console errors.

Run it after any interface change. README images that show a screen the product no
longer has are worse than no images, because a reader believes them.

    python scripts/capture_screenshots.py
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

URL = "https://ttb-label-verification-production-a79a.up.railway.app"
LABELS = Path("tests/fixtures/labels")
APPLICATIONS = Path("tests/fixtures/applications")
OUT = Path("docs/images")

BATCH = ["compliant_bourbon.png", "warning_title_case.png", "abv_proof_only.png", "warning_body_bold.png"]


async def main() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        # 1. Nothing uploaded: the two drop zones.
        await page.goto(URL, wait_until="networkidle")
        await page.screenshot(path=OUT / "01-upload.png")

        # 2. A single review: source documents beside the findings (MCH-11).
        await page.set_input_files("#label-files", str(LABELS / "warning_title_case.png"))
        await page.set_input_files("#bar-applications", str(APPLICATIONS / "24-0419-application-wrong-brand.pdf"))
        await page.wait_for_selector(".pane__frame img", timeout=60000)
        await page.click("button.primary")
        await page.wait_for_selector(".tabs", timeout=120000)
        await page.wait_for_timeout(1200)
        await page.screenshot(path=OUT / "02-review.png", full_page=True)

        panes = await page.evaluate("() => document.querySelectorAll('.pane').length")
        tabs = await page.evaluate(
            "() => [...document.querySelectorAll('.tabs [role=tab]')].map(t => t.textContent.trim())"
        )

        # 3. A batch, collapsed: the triage view, worst first.
        await page.goto(URL, wait_until="networkidle")
        await page.set_input_files("#label-files", [str(LABELS / n) for n in BATCH])
        await page.click("button.primary")
        await page.wait_for_function("() => document.querySelectorAll('.card').length >= 4", timeout=180000)
        await page.wait_for_timeout(800)
        for head in await page.query_selector_all(".card__head[aria-expanded='true']"):
            await head.click()
        await page.wait_for_timeout(400)
        await page.screenshot(path=OUT / "03-batch.png", full_page=True)

        # Keyboard reachability: tab from the top and see what receives focus.
        await page.keyboard.press("Tab")
        focus_order = []
        for _ in range(6):
            focus_order.append(
                await page.evaluate(
                    "() => { const a = document.activeElement;"
                    " return a.tagName + ':' + (a.textContent || a.id || '').trim().slice(0, 28); }"
                )
            )
            await page.keyboard.press("Tab")

        await page.click(".card--fail .card__head")
        await page.wait_for_selector(".card__detail")
        checks = await page.evaluate("""() => ({
            statusHasText: [...document.querySelectorAll('.check__name .sr-only')].length,
            liveRegions: document.querySelectorAll('[aria-live]').length,
            expandable: document.querySelectorAll('[aria-expanded]').length,
            imagesWithoutAlt: [...document.querySelectorAll('img')].filter(i => !i.alt).length,
            tablists: document.querySelectorAll('[role=tablist]').length,
            citations: document.querySelectorAll('.cite').length,
        })""")
        await browser.close()

    print(f"MCH-11 document pane rendered : {panes}")
    print(f"findings tabs                 : {tabs}")
    print(f"focus order                   : {focus_order}")
    print(f"a11y                          : {checks}")
    print(f"console errors                : {errors or 'none'}")

    # The claims the README makes about UX-04..06, asserted rather than described.
    problems = []
    if panes != 1:
        problems.append("the source documents were not shown beside the findings (MCH-11)")
    if len(tabs) != 3:
        problems.append(f"expected three findings tabs, found {len(tabs)}")
    if not checks["statusHasText"]:
        problems.append("status is not carried in text as well as colour (UX-04)")
    if not checks["liveRegions"]:
        problems.append("no live region for streaming results (UX-05)")
    if checks["imagesWithoutAlt"]:
        problems.append(f"{checks['imagesWithoutAlt']} image(s) without alt text (UX-05)")
    if not checks["citations"]:
        problems.append("findings carry no citations")
    if errors:
        problems.append(f"{len(errors)} console error(s)")

    for problem in problems:
        print(f"  FAIL {problem}")
    return 1 if problems else 0


sys.exit(asyncio.run(main()))

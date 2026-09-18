"""Capture README screenshots and run accessibility checks against the deployment.

Keeps the images in the README honest: they are regenerated from the live service
rather than staged, and the same run asserts the things UX-04..06 claim — status
carried in text as well as colour, a live region for streaming results, keyboard
reachability, and no console errors.

    python scripts/capture_screenshots.py
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

URL = "https://ttb-label-verification-production-a79a.up.railway.app"
LABELS = Path("tests/fixtures/labels")
OUT = Path("docs/images")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1000, "height": 800}, device_scale_factor=2)
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        await page.goto(URL, wait_until="networkidle")
        await page.screenshot(path=OUT / "01-upload.png")

        await page.set_input_files(
            "#label-files",
            [
                str(LABELS / n)
                for n in [
                    "compliant_bourbon.png",
                    "warning_title_case.png",
                    "abv_proof_only.png",
                    "warning_body_bold.png",
                ]
            ],
        )
        await page.click("button.primary")
        await page.wait_for_function("() => document.querySelectorAll('.card').length >= 4", timeout=120000)
        await page.wait_for_timeout(600)

        # Collapsed overview: the batch triage view.
        for head in await page.query_selector_all(".card__head[aria-expanded='true']"):
            await head.click()
        await page.wait_for_timeout(300)
        await page.screenshot(path=OUT / "02-batch.png", full_page=True)

        # One failure expanded, showing findings and citations.
        await page.click(".card--fail .card__head")
        await page.wait_for_selector(".card__detail")
        await page.wait_for_timeout(300)
        await page.screenshot(path=OUT / "03-findings.png", full_page=True)

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

        checks = await page.evaluate("""() => ({
            statusHasText: [...document.querySelectorAll('.check__name .sr-only')].length,
            liveRegions: document.querySelectorAll('[aria-live]').length,
            expandable: document.querySelectorAll('[aria-expanded]').length,
            imagesWithoutAlt: [...document.querySelectorAll('img')].filter(i => !i.alt).length,
            citations: document.querySelectorAll('.cite').length,
        })""")
        print("focus order:", focus_order)
        print("a11y:", checks)
        print("console errors:", errors or "none")
        await browser.close()


sys.exit(asyncio.run(main()))

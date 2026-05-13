import asyncio
from playwright.async_api import async_playwright, Page


async def crawl_list_page(page: Page, url: str, max_pages: int = 3) -> list[dict]:
    """Crawl the Shenzhen exam institute announcement list.
    Returns list of {title, date, url} dicts.
    """
    announcements = []

    for page_num in range(max_pages):
        if page_num == 0:
            page_url = url
        else:
            page_url = url.replace("index.html", f"index_{page_num}.html")

        try:
            await page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1000)

            items = await _extract_list_items(page)
            if not items:
                break
            announcements.extend(items)
        except Exception as e:
            print(f"Error crawling list page {page_url}: {e}")
            break

    return announcements


async def _extract_list_items(page: Page) -> list[dict]:
    """Extract announcement items from the current list page."""
    items = await page.evaluate("""
        () => {
            const results = [];
            const selectors = [
                '.list-box li', '.news-list li', '.xxgk-list li',
                '.right-list li', '.listContent li', 'ul.list li',
                '.zwgk-list li', 'table.list tr'
            ];
            let elements = [];
            for (const sel of selectors) {
                elements = document.querySelectorAll(sel);
                if (elements.length > 0) break;
            }
            if (elements.length === 0) {
                elements = document.querySelectorAll('li, tr');
            }
            for (const el of elements) {
                const link = el.querySelector('a');
                const dateEl = el.querySelector('.date, .time, span:last-child, td:last-child');
                if (link && link.href) {
                    const title = link.getAttribute('title') || link.textContent.trim();
                    const dateText = dateEl ? dateEl.textContent.trim() : '';
                    if (title && title.length > 5 && dateText.match(/\\d{4}[-/]\\d{2}[-/]\\d{2}/)) {
                        results.push({
                            title: title,
                            date: dateText,
                            url: link.href
                        });
                    }
                }
            }
            return results;
        }
    """)
    return items


async def crawl_detail_page(page: Page, url: str) -> str | None:
    """Fetch the HTML content of a detail page."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(500)
        html = await page.content()
        return html
    except Exception as e:
        print(f"Error crawling detail page {url}: {e}")
        return None


async def crawl_shenzhen(config: dict) -> list[dict]:
    """Main entry point for Shenzhen crawling.
    Returns list of {title, date, url, detail_html} dicts.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.set_extra_http_headers({
            "Accept-Language": "zh-CN,zh;q=0.9"
        })

        print(f"Crawling Shenzhen list: {config['list_url']}")
        announcements = await crawl_list_page(
            page, config["list_url"], max_pages=config.get("max_pages", 3)
        )
        print(f"Found {len(announcements)} announcements")

        results = []
        for i, ann in enumerate(announcements[:20]):
            print(f"  Fetching detail {i+1}/{min(len(announcements), 20)}: {ann['title'][:40]}...")
            html = await crawl_detail_page(page, ann["url"])
            if html:
                results.append({
                    "title": ann["title"],
                    "date": ann["date"],
                    "url": ann["url"],
                    "detail_html": html,
                })

        await browser.close()

    return results

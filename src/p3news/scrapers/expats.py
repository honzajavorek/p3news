from datetime import datetime
import logging
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext


logger = logging.getLogger(__name__)


async def main() -> list[dict]:
    crawler = BeautifulSoupCrawler(configure_logging=False)

    @crawler.router.default_handler
    async def default_handler(context: BeautifulSoupCrawlingContext) -> None:
        await context.enqueue_links(selector=".top.title h3 a", label="article")
        await context.enqueue_links(selector=".content article h3 a", label="article")

    @crawler.router.handler("article")
    async def article_handler(context: BeautifulSoupCrawlingContext) -> None:
        dt_text = context.soup.select_one(".about .created").text.strip()
        dt = datetime.strptime(dt_text, "Published on %d.%m.%Y %H:%M:%S")
        dt = dt.replace(tzinfo=ZoneInfo("Europe/Prague"))

        await context.push_data(
            {
                "title": context.soup.select_one(".title h1").text.strip(),
                "author": context.soup.select_one(".about .written-by a").text.strip(),
                "lead": context.soup.select_one(".title h3").text.strip(),
                "image_url": urljoin(
                    context.request.url,
                    context.soup.select_one(".featured-image img")["src"],
                ),
                "url": context.request.url,
                "tags": [
                    tag.text.strip() for tag in context.soup.select(".categories a")
                ],
                "published_at": dt.isoformat(),
                "lang": "en",
            }
        )

    await crawler.run(
        [
            "https://www.expats.cz/czech-news/tag/prague-3",
            "https://www.expats.cz/czech-news/tag/zizkov",
        ]
    )
    data = await crawler.get_data()
    logger.info(f"Scraped {len(data.items)} items")
    return data.items


if __name__ == "__main__":
    import asyncio
    from pprint import pp

    pp(asyncio.run(main()))

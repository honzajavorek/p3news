from datetime import UTC, datetime
import logging
from crawlee.crawlers import HttpCrawler, HttpCrawlingContext
import feedparser


logger = logging.getLogger(__name__)


async def main() -> list[dict]:
    crawler = HttpCrawler(configure_logging=False)

    @crawler.router.default_handler
    async def default_handler(context: HttpCrawlingContext) -> None:
        feed = feedparser.parse(await context.http_response.read())
        for entry in feed.entries:
            tags = [tag.term for tag in entry.tags if tag.term not in ["seznam"]]
            if "Praha 3" not in tags:
                continue
            data = {
                "title": str(entry.title),
                "lead": entry.summary.strip(),
                "url": str(entry.link),
                "tags": tags,
                "published_at": datetime(
                    *entry.published_parsed[:6], tzinfo=UTC
                ).isoformat(),
                "lang": "cs",
            }
            await context.push_data(data)

    await crawler.run(["https://zdopravy.cz/feed/"])
    data = await crawler.get_data()
    logger.info(f"Scraped {len(data.items)} items")
    return data.items



if __name__ == "__main__":
    import asyncio
    from pprint import pp

    pp(asyncio.run(main()))

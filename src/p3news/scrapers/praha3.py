from datetime import datetime
import logging
from zoneinfo import ZoneInfo
from crawlee import Request
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from crawlee.http_clients import HttpxHttpClient


logger = logging.getLogger(__name__)


async def main(pages: int = 5) -> list[dict]:
    http_client = HttpxHttpClient(verify=False)  # crawlee bug?
    crawler = BeautifulSoupCrawler(configure_logging=False, http_client=http_client)

    @crawler.router.default_handler
    async def default_handler(context: BeautifulSoupCrawlingContext) -> None:
        for item in context.soup.select(".news-list-item"):
            dt_text = item.select_one(".date").text.strip()
            dt = datetime.strptime(dt_text, "%d. %m. %Y")
            dt = dt.replace(tzinfo=ZoneInfo("Europe/Prague"))
            data = {
                "title": item.select_one("h3").text.strip(),
                "lead": item.select_one("p").text.strip(),
                "published_at": dt.isoformat(),
                "tags": [tag.text.strip() for tag in item.select(".item-tags .tag")],
            }
            await context.add_requests(
                [
                    Request.from_url(
                        item.select_one(".item-link")["href"],
                        label="article",
                        user_data={"data": data},
                    )
                ]
            )

    @crawler.router.handler("article")
    async def article_handler(context: BeautifulSoupCrawlingContext) -> None:
        await context.push_data(
            {
                "author": context.soup.select(".news-detail-aside p")[-2].text.strip()
                or None,
                "image_url": context.soup.select_one('meta[property="og:image"]')[
                    "content"
                ],
                "url": context.request.url,
                "lang": "cs",
            }
            | dict(context.request.user_data["data"])
        )

    await crawler.run(
        [
            f"https://www.praha3.cz/aktualne-z-trojky/zpravy/page:{n}/"
            for n in range(1, pages + 1)
        ]
    )
    data = await crawler.get_data()
    logger.info(f"Scraped {len(data.items)} items")
    return data.items


if __name__ == "__main__":
    import asyncio
    from pprint import pp

    pp(asyncio.run(main()))

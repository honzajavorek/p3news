from datetime import UTC, datetime
from pprint import pp
from bs4 import BeautifulSoup
from crawlee import Request
from crawlee.crawlers import HttpCrawler, HttpCrawlingContext
import feedparser


async def main() -> None:
    crawler = HttpCrawler()

    @crawler.router.default_handler
    async def default_handler(context: HttpCrawlingContext) -> None:
        feed = feedparser.parse(context.http_response.read())
        for entry in feed.entries:
            content = entry.content[0]["value"]
            content_soup = BeautifulSoup(content, "html.parser")
            data = {
                "title": str(entry.title),
                "lead": content_soup.select_one("p").get_text(" ", strip=True),
                "url": str(entry.link),
                "tags": ["Nová Trojka", "rodina"],
                "published_at": datetime(
                    *entry.published_parsed[:6], tzinfo=UTC
                ).isoformat(),
                "lang": "cs",
            }
            await context.add_requests(
                [
                    Request.from_url(
                        str(entry.link), label="article", user_data={"data": data}
                    )
                ]
            )

    @crawler.router.handler("article")
    async def article_handler(context: HttpCrawlingContext) -> None:
        data = dict(context.request.user_data["data"])
        soup = BeautifulSoup(context.http_response.read(), "html.parser")
        data["image_url"] = soup.select_one('meta[property="og:image"]')["content"]
        await context.push_data(data)

    await crawler.run(["https://www.nova-trojka.cz/index.php/feed/"])
    data = await crawler.get_data()
    pp(data.items)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

from datetime import date, timedelta
import json
import logging
from bs4 import BeautifulSoup
from crawlee import Request
from crawlee.crawlers import HttpCrawler, HttpCrawlingContext


logger = logging.getLogger(__name__)


async def main(
    date_from: date | None = None, date_to: date | None = None
) -> list[dict]:
    date_from = date_from or (date.today() - timedelta(days=30))
    date_to = date_to or (date.today() + timedelta(days=5))

    crawler = HttpCrawler(configure_logging=False)

    @crawler.router.default_handler
    async def default_handler(context: HttpCrawlingContext) -> None:
        text = (await context.http_response.read()).decode()
        print(text)
        # data = json.loads(text)
        # events = [
        #     event
        #     for event in data["events"]
        #     if event.get("administrativeDistrict") == "Praha 3"
        # ]
        # for event in events:
        #     lead_soup = BeautifulSoup(event["description"], "html.parser")
        #     lead = lead_soup.get_text(" ", strip=True)
        #     await context.push_data(
        #         {
        #             "title": event["title"],
        #             "lead": lead,
        #             "url": f"https://bezpecnost.praha.eu/udalosti/{event['relativeUrl']}",
        #             "tags": [event["type"]],
        #             "published_at": event["publication"]["date"],
        #             "lang": "cs",
        #         }
        #     )

    url = (
        "https://bezpecnost.praha.eu/Intens.CrisisPortalInfrastructureApp/events"
        f"?from={date_from.isoformat()}T00:00:00.000Z&to={date_to.isoformat()}T00:00:00.000Z"
        "&groupType=OSKS_ACTUALITY&showHistory=true&format=json"
    )
    await crawler.run(
        [
            Request.from_url(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:143.0) Gecko/20100101 Firefox/143.0",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.8,cs;q=0.6,sk;q=0.4,es;q=0.2",
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "DNT": "1",
                    "Sec-GPC": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Priority": "u=0, i",
                },
            )
        ]
    )
    data = await crawler.get_data()
    logger.info(f"Scraped {len(data.items)} items")
    return data.items


if __name__ == "__main__":
    import asyncio
    from pprint import pp

    pp(asyncio.run(main()))

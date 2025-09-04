from datetime import date, datetime, timedelta
import json
import logging
import re
from zoneinfo import ZoneInfo
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
        api_token = re.search(
            r'"mrApiToken":"([^"]+)"', context.http_response.read().decode()
        ).group(1)
        csrf_token = re.search(
            r'"csrfToken":"([^"]+)"', context.http_response.read().decode()
        ).group(1)
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRF-TOKEN": csrf_token,
            "X-HTTP-METHOD-OVERRIDE": "GET",
            "pagination": "cursor",
            "Origin": "https://praha3.munipolis.cz",
            "Referer": "https://praha3.munipolis.cz/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:139.0) Gecko/20100101 Firefox/139.0",
        }
        request = Request.from_url(
            "https://api.munipolis.com/api/timeline",
            method="POST",
            headers=headers,
            payload=json.dumps(
                {
                    "filter": {
                        "types": ["news", "calendarEvent"],
                        "cityId": [3209],
                    },
                    "include": ["mrCity", "files", "poll", "images", "lastComment"],
                    "order": ["isPinned", "-publishAt"],
                    "cursor": None,
                    "perPage": 50,
                    "includeExpiredPosts": False,
                }
            ),
            label="api",
        )
        await context.add_requests([request])

    @crawler.router.handler("api")
    async def api_handler(context: HttpCrawlingContext) -> None:
        data = json.loads(context.http_response.read())
        for article in data["data"]:
            dt = datetime.fromisoformat(article["publishAt"]).replace(tzinfo=ZoneInfo("Europe/Prague")).isoformat()
            if lead := article["description"].strip():
                lead = re.sub(r"^(vážení|milí)\s*sousedé\s*,\s*", "", lead, flags=re.I)
                lead = lead.split("\n")[0].strip()
                lead = lead[0].upper() + lead[1:]
            else:
                lead = None
            await context.push_data(
                {
                    "title": article["title"],
                    "lead": lead,
                    "url": article["shareUrl"],
                    "image_url": article["image"]["data"]["path"] if article["image"] else None,
                    "tags": [],
                    "published_at": dt,
                    "lang": "cs",
                }
            )

    await crawler.run(["https://praha3.munipolis.cz/"])
    data = await crawler.get_data()
    logger.info(f"Scraped {len(data.items)} items")
    return data.items


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

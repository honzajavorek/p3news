import asyncio
from importlib import import_module
import json
import logging
from pathlib import Path
import click


logger = logging.getLogger(__name__)


@click.group()
@click.option("--debug", "-d", is_flag=True)
def main(debug: bool):
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    for logger_name in ["httpx", "crawlee", "HttpCrawler", "BeautifulSoupCrawler"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


@main.command()
@click.option(
    "--scrapers",
    "-s",
    multiple=True,
    help="List of scrapers to run",
    default=["bezpecnost", "expats", "munipolis", "novatrojka", "praha3"],
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path, dir_okay=False, writable=True),
    default="items.json",
)
def scrape(scrapers: list[str], output_path: Path):
    async def _run() -> list[dict]:
        items = []
        for scraper in scrapers:
            items.extend(await import_module(f"p3news.scrapers.{scraper}").main())
        return items
    items = asyncio.run(_run())
    logger.info(f"Scraped {len(items)} items in total")
    output_path.write_text(json.dumps(items, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

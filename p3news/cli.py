import asyncio
from datetime import datetime
from importlib import import_module
import json
import logging
from operator import attrgetter
from pathlib import Path
from typing import Annotated, Literal
import click
from pydantic import BaseModel, ConfigDict, HttpUrl, PlainSerializer


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
    default="articles.json",
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


class Article(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    author: str | None = None
    lead: str | None = None
    url: Annotated[HttpUrl, PlainSerializer(str)]
    image_url: Annotated[HttpUrl, PlainSerializer(str)] | None = None
    tags: list[str]
    published_at: datetime
    lang: Literal["cs", "en"]


@main.command()
@click.option(
    "--input",
    "-i",
    "input_path",
    type=click.Path(path_type=Path, dir_okay=False, readable=True, exists=True),
    default="articles.json",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path, file_okay=False, writable=True),
    default="site",
)
def build(input_path: Path, output_path: Path):
    articles = map(Article.model_validate, json.loads(input_path.read_text()))
    articles = sorted(articles, key=attrgetter("published_at"), reverse=True)
    logger.info(f"Loaded {len(articles)} articles from {input_path}")
    output_path.mkdir(parents=True, exist_ok=True)
    # TODO


if __name__ == "__main__":
    main()

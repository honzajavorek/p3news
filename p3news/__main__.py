from datetime import date, datetime
from operator import itemgetter
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
import click
from bs4 import BeautifulSoup, Tag
from feedgen.feed import FeedGenerator

import httpx


@click.command()
@click.option(
    "--url-template",
    "url_template",
    default="https://www.praha3.cz/aktualne-z-trojky/zpravy/page:{n}/",
    help="URL of the news",
)
@click.option("-p", "--pages", default=5, type=int, help="Number of pages to fetch")
@click.option(
    "-o",
    "--output",
    "output_path",
    default="feed.xml",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Output file path for the feed",
)
@click.option(
    "--user-agent", default="P3news (+https://github.com/honzajavorek/p3news/)"
)
@click.option("--feed-id", default="bvRcCoa!d_UeE4WBeZLcG6qnB*!9xP")
def main(
    url_template: str,
    pages: int,
    output_path: Path,
    user_agent: str,
    feed_id: str,
):
    click.echo("Initializing file system")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    articles = []
    for n in range(1, pages + 1):
        url = url_template.format(n=n)
        click.echo(f"Fetching news page {url}")
        response = httpx.get(
            url,
            follow_redirects=True,
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8",
            },
            verify=False,
        )
        response.raise_for_status()
        click.echo("Parsing news page")
        articles.extend(parse_page(response))
    articles.sort(key=itemgetter("published_at"), reverse=True)

    click.echo("Generating feed")
    feed = FeedGenerator()
    feed.id(feed_id)
    feed.title("P3news")
    feed.author(name="Honza Javorek", email="mail@honzajavorek.cz")
    feed.link(href="https://github.com/honzajavorek/p3news", rel="alternate")
    feed.logo("https://www.praha3.cz/getFile/id:1185227/praha-3-A-02_RGB.png")
    feed.language("cs")
    for article in articles:
        entry = feed.add_entry()
        entry.id(article["url"])
        entry.title(article["title"])
        entry.link(href=article["url"])
        entry.description(article["lead"])
        entry.published(article["published_at"])
        entry.enclosure(article["image"])
        entry.category([{"label": tag, "term": tag} for tag in article["tags"]])

    click.echo(f"Writing feed to {output_path}")
    Path(output_path).write_bytes(feed.atom_str())


def parse_page(response: httpx.Response) -> list[dict[str, str | date | list[str]]]:
    base_url = str(response.url)
    soup = BeautifulSoup(response.content, "html.parser")
    return [parse_article(item, base_url) for item in soup.select(".news-list-item")]


def parse_article(item: Tag, base_url: str) -> dict[str, str | date | list[str]]:
    dt = datetime.strptime(item.select_one(".date").text.strip(), "%d. %m. %Y")
    dt = dt.replace(tzinfo=ZoneInfo("Europe/Prague"))

    img = item.select_one(".item-image img")
    img_url = img.get("data-lazyload", img.get("src"))

    return {
        "title": item.select_one(".item-text h3").text.strip(),
        "lead": item.select_one(".item-text p").text.strip(),
        "image": urljoin(base_url, img_url),
        "url": urljoin(base_url, item.select_one(".item-link").get("href")),
        "tags": [tag.text for tag in item.select(".item-tags .tag")],
        "published_at": dt,
    }

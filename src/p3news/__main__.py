from datetime import UTC, datetime
from operator import attrgetter
from pathlib import Path
import time
from typing import cast
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
import click
from bs4 import BeautifulSoup, Tag
from feedgen.feed import FeedGenerator
import feedparser
import httpx
from mastodon import Mastodon
from diskcache import Cache
from pydantic import BaseModel
from slugify import slugify
import stamina


class Article(BaseModel):
    title: str
    lead: str
    image_url: str | None = None
    url: str
    tags: list[str]
    published_at: datetime


@click.command()
@click.option(
    "--url-template",
    "url_template",
    default="https://www.praha3.cz/aktualne-z-trojky/zpravy/page:{n}/",
    help="URL of the news",
)
@click.option("-p", "--pages", default=5, type=int, help="Number of pages to fetch")
@click.option("-w", "--wait", default=1, type=float, help="Wait time between requests")
@click.option(
    "-o",
    "--output",
    "output_path",
    default="feed.xml",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Output file path for the feed",
)
@click.option("-l", "--limit", default=1, type=float, help="How many articles to post")
@click.option(
    "--server-url", default="https://mastodonczech.cz/", help="Mastodon server URL"
)
@click.option(
    "--access-token", envvar="MASTODON_ACCESS_TOKEN", help="Mastodon access token"
)
@click.option(
    "--user-agent", default="P3news (+https://github.com/honzajavorek/p3news/)"
)
@click.option("--feed-id", default="bvRcCoa!d_UeE4WBeZLcG6qnB*!9xP")
@click.option(
    "--today", default=lambda: datetime.today().isoformat(), type=datetime.fromisoformat
)
def main(
    url_template: str,
    pages: int,
    wait: float,
    output_path: Path,
    limit: int,
    server_url: str,
    access_token: str,
    user_agent: str,
    feed_id: str,
    today: datetime,
):
    cache = Cache(".cache")

    click.echo("Initializing file system")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    click.echo("Fetching P3 news")
    articles: list[Article] = []
    for n in range(1, pages + 1):
        url = url_template.format(n=n)
        if response := cache.get(url):
            click.echo(f"Using cached response for {url}")
            response = cast(httpx.Response, response)
        else:
            click.echo(f"Fetching news page {url}")
            response = download(url, user_agent, wait if n > 1 else None)
            cache.set(url, response, expire=60 * 60)
        click.echo("Parsing news page")
        articles.extend(parse_page(response, today))

    # TODO refactor
    nt_feed_url = "https://www.nova-trojka.cz/index.php/feed/"
    if response := cache.get(nt_feed_url):
        click.echo("Using cached response for NT news")
        response = cast(httpx.Response, response)
    else:
        click.echo("Fetching NT news feed")
        response = download(nt_feed_url, user_agent)
    feed = feedparser.parse(response.content)
    for entry in feed.entries:
        content = entry.content[0]["value"]
        content_soup = BeautifulSoup(content, "html.parser")
        first_paragraph = content_soup.select_one("p").get_text(" ", strip=True)
        articles.append(
            Article(
                title=entry.title,
                lead=first_paragraph,
                url=entry.link,
                tags=["Nová Trojka", "rodina"],
                published_at=datetime(*entry.published_parsed[:6], tzinfo=UTC),
            )
        )

    # TODO refactor
    zd_feed_url = "https://zdopravy.cz/feed/"
    if response := cache.get(zd_feed_url):
        click.echo("Using cached response for Zdopravy.cz news")
        response = cast(httpx.Response, response)
    else:
        click.echo("Fetching Zdopravy.cz news feed")
        response = download(zd_feed_url, user_agent)
    feed = feedparser.parse(response.content)
    for entry in feed.entries:
        tags = [tag.term for tag in entry.tags if tag not in ["seznam"]]
        if "Praha 3" not in tags:
            continue
        # image_url = entry.enclosures[0].href
        articles.append(
            Article(
                title=entry.title,
                lead=entry.summary.strip(),
                url=entry.link,
                tags=tags,
                published_at=datetime(*entry.published_parsed[:6], tzinfo=UTC),
            )
        )

    click.echo(f"Sorting {len(articles)} articles")
    articles.sort(key=attrgetter("published_at"), reverse=True)

    click.echo("Fetching images")
    for article in articles:
        if article.image_url:
            if response := cache.get(article.image_url):
                click.echo(f"Using cached response for {article.image_url}")
            else:
                click.echo(f"Fetching image {article.image_url}")
                response = download(article.image_url, user_agent, wait)
                cache.set(article.image_url, response, expire=60 * 60 * 24 * 30)

    from pprint import pp

    pp(articles)

    click.echo("Generating feed")
    feed = FeedGenerator()
    feed.id(feed_id)
    feed.title("P3news")
    feed.author(name="Honza Javorek", email="mail@honzajavorek.cz")
    feed.link(href="https://github.com/honzajavorek/p3news", rel="alternate")
    feed.language("cs")
    for article in articles:
        entry = feed.add_entry()
        entry.id(article.url)
        entry.title(article.title)
        entry.link(href=article.url)
        entry.description(article.lead)
        entry.published(article.published_at)
        if article.image_url:
            image_response = cast(httpx.Response, cache.get(article.image_url))
            entry.enclosure(
                article.image_url,
                image_response.headers["Content-Length"],
                image_response.headers["Content-Type"],
            )
        entry.category([{"label": tag, "term": slugify(tag)} for tag in article.tags])

    click.echo(f"Writing feed to {output_path}")
    Path(output_path).write_bytes(feed.atom_str())

    click.echo("Connecting to Mastodon")
    client = Mastodon(
        api_base_url=server_url, user_agent=user_agent, access_token=access_token
    )
    account_id = client.me()["id"]

    click.echo("Figuring out which articles to post")
    posted_urls = set()
    for status in client.account_statuses(account_id, limit=100):
        if status["account"]["id"] == account_id:
            status_soup = BeautifulSoup(status["content"], "html.parser")
            posted_urls.update(
                [
                    a.get("href")
                    for a in status_soup.select("a")
                    if not a.get("href").startswith(server_url)
                ]
            )

    click.echo("Posting articles")
    articles = sorted(
        [article for article in articles if article.url not in posted_urls],
        key=attrgetter("published_at"),
    )
    for i, article in enumerate(articles):
        if i >= limit:
            break
        if article.image_url:
            image_response = cast(httpx.Response, cache.get(article.image_url))
            media = client.media_post(
                image_response.content, image_response.headers["Content-Type"]
            )
            media_ids = [media["id"]]
        else:
            media_ids = []
        tags = ["#" + slugify(tag, separator="") for tag in article.tags]
        text = f"{article.title} — {article.url}\n\n{' '.join(tags)} #praha3 #zizkov #zpravy"
        client.status_post(
            text, language="cs", visibility="public", media_ids=media_ids
        )


@stamina.retry(on=httpx.HTTPError, attempts=3)
def download(url: str, user_agent: str, wait: float | None = None) -> httpx.Response:
    if wait:
        time.sleep(wait)
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
    return response


def parse_page(response: httpx.Response, today: datetime) -> list[Article]:
    base_url = str(response.url)
    soup = BeautifulSoup(response.content, "html.parser")
    return [
        parse_article(item, base_url, today) for item in soup.select(".news-list-item")
    ]


def parse_article(item: Tag, base_url: str, today: datetime) -> Article:
    dt_text = item.select_one(".date").text.strip()
    if dt_text.lower() == "dnes":
        dt = today
    else:
        dt = datetime.strptime(dt_text, "%d. %m. %Y")
    dt = dt.replace(tzinfo=ZoneInfo("Europe/Prague"))

    img = item.select_one(".item-image img")
    img_url = img.get("data-lazyload", img.get("src"))

    return Article(
        title=item.select_one(".item-text h3").text.strip(),
        lead=item.select_one(".item-text p").text.strip(),
        image_url=urljoin(base_url, img_url),
        url=urljoin(base_url, item.select_one(".item-link").get("href")),
        tags=[tag.text for tag in item.select(".item-tags .tag")],
        published_at=dt,
    )

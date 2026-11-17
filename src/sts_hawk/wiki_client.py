"""Retrieve wiki-only reference information for the replay-based Inspect task."""

import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from bs4 import BeautifulSoup
from inspect_ai.tool import ToolError
from markdownify import markdownify

WIKI_HOST = "slaythespire.wiki.gg"


def validate_wiki_url(url: str) -> str:
    """Reject page addresses outside the benchmark's permitted wiki host."""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise ToolError("The wiki page address is invalid.") from None
    if (
        parsed.scheme != "https"
        or parsed.hostname != WIKI_HOST
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        raise ToolError("Only https://slaythespire.wiki.gg/ pages are allowed.")
    return url


def tavily_request(endpoint: str, body: dict) -> dict:
    """Send a Tavily request without including credentials in tool output."""
    credential = os.environ.get("TAVILY_API_KEY", "").strip()
    if not credential:
        key_file = Path.home() / ".config/tavily/api-key"
        if not key_file.exists():
            raise ToolError(
                "Tavily is not configured: the private API key file is missing."
            )
        credential = key_file.read_text().strip()
    request = Request(
        f"https://api.tavily.com/{endpoint}",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {credential}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=35) as response:
            result = json.load(response)
            if not isinstance(result, dict) or not isinstance(
                result.get("results"), list
            ):
                raise ToolError("Tavily returned an invalid result; you may retry.")
            return result
    except HTTPError as error:
        raise ToolError(
            f"Tavily returned HTTP {error.code}; retry or adjust the query."
        ) from None
    except (URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
        raise ToolError(
            "The Tavily request failed or timed out; you may retry."
        ) from None


def wiki_search(query: str) -> str:
    """Return up to five wiki pages as titles, addresses and snippets."""
    if not query.strip():
        raise ToolError("Provide a non-empty wiki search query.")
    response = tavily_request(
        "search",
        {
            "query": query,
            "include_domains": [WIKI_HOST],
            "include_domains_mode": "restrict",
            "max_results": 5,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
        },
    )
    pages = []
    for result in response.get("results", []):
        if not isinstance(result, dict) or not all(
            isinstance(result.get(field), str) for field in ("url", "title", "content")
        ):
            continue
        try:
            url = validate_wiki_url(result.get("url", ""))
        except ToolError:
            continue
        snippet = " ".join(result.get("content", "").split())[:400]
        pages.append(f"{result.get('title', '')}\n{url}\n{snippet}")
    return (
        "\n\n".join(pages[:5])
        or "No matching wiki pages found. Try different search words."
    )


def wiki_fetch(url: str) -> str:
    """Retrieve the wiki's article body as Markdown without navigation or images."""
    url = validate_wiki_url(url)
    request = Request(url, headers={"User-Agent": "SpireResearch/0.1"})
    try:
        with build_opener(WikiRedirectHandler()).open(request, timeout=35) as response:
            html = response.read().decode("utf-8")
    except HTTPError as error:
        raise ToolError(
            f"The wiki returned HTTP {error.code}; retry or choose another page."
        ) from None
    except (URLError, TimeoutError, ConnectionError):
        raise ToolError(
            "The wiki request failed or timed out; you may retry."
        ) from None
    return article_markdown(html)


class WikiRedirectHandler(HTTPRedirectHandler):
    """Keep article redirects inside the same permitted wiki host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Validate redirect destinations before opening a new connection."""
        validate_wiki_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def article_markdown(html: str) -> str:
    """Convert only the MediaWiki article, retaining headings, paragraphs and tables."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("#firstHeading")
    body = soup.select_one(".mw-parser-output")
    if heading is None or body is None:
        raise ToolError(
            "The wiki response has no article body; retry or choose another page."
        )
    for node in body.select(
        "script, style, img, .mw-editsection, .navbox, .printfooter, "
        ".mw-empty-elt, .toccolours.navbox"
    ):
        node.decompose()
    article = markdownify(str(body), heading_style="ATX", strip=["a"])
    article = re.sub(r"\n{3,}", "\n\n", article).strip()
    return f"# {heading.get_text(' ', strip=True)}\n\n{article}"

"""
RE/MAX RD property detail scraper.

Fetches a listing URL (from DB ``PropertyListing.url`` or a live slug) and returns
rich detail: description HTML, image gallery, agent contacts, specs.

Extraction order (fallback chain):
  A) ``__NEXT_DATA__`` JSON embedded in the Next.js HTML document
  B) RE/MAX public API ``GET /v2/realestates/{id}`` when A lacks a property node
  C) BeautifulSoup DOM fallback (class-agnostic selectors, stable URL/tel/wa patterns)

Uses ``curl_cffi`` (Chrome TLS fingerprint) — same stack as RemaxRdDriver.
"""

from __future__ import annotations

import json
import logging
import re
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup
from curl_cffi import requests

from observability.scraper_errors import map_detail_source_to_method, scraper_error_scope
from scrapers.utils.normalization import CHROME_USER_AGENT, resolve_bathroom_count

logger = logging.getLogger(__name__)

REMAX_API_DETAIL_URL = "https://api.remaxrd.com/v2/realestates/{remote_id}"
REMAX_IMAGE_HOST = "images.remaxrd.com"
IMPERSONATE = "chrome120"

DEFAULT_HEADERS = {
    "User-Agent": CHROME_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-DO,es;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}

# Known hydration paths for the property record inside __NEXT_DATA__
_NEXT_DATA_PROPERTY_PATHS: tuple[tuple[str, ...], ...] = (
    ("props", "pageProps", "data", "data"),
    ("props", "pageProps", "property"),
    ("props", "pageProps", "listing"),
    ("props", "pageProps", "initialState", "property"),
    ("props", "pageProps", "initialState", "listing"),
)

_REMOTE_ID_RE = re.compile(r"(\d{5,})\s*$")
_CODIGO_RE = re.compile(r"C[oó]digo\s*:\s*(\d+)", re.IGNORECASE)
_WHATSAPP_RE = re.compile(r"wa\.me|api\.whatsapp\.com", re.IGNORECASE)


class RemaxDetailScrapeError(Exception):
    """Raised when no extraction method could build a property detail payload."""


def extract_remote_id_from_url(url: str) -> str | None:
    """Pull trailing numeric portal id from slug (e.g. ...-222598 -> 222598)."""
    path = urlparse(url).path.rstrip("/")
    match = _REMOTE_ID_RE.search(path.split("/")[-1])
    return match.group(1) if match else None


def normalize_remax_listing_url(url: str, city_slug: str | None = None) -> str:
    """
    Convert stored English storefront URLs to Spanish ``/propiedad/`` routes.

    Example:
        /en/propiedad/foo-222574 -> /propiedad/foo-222574?city=higüey
    """
    parsed = urlparse(url.strip())
    path = parsed.path.replace("/en/propiedad/", "/propiedad/").replace(
        "/en/property/", "/propiedad/"
    )
    if "/propiedad/" not in path and "/property/" not in path:
        path = f"/propiedad/{path.lstrip('/')}"

    query = parse_qs(parsed.query)
    if city_slug and "city" not in query:
        query["city"] = [city_slug]

    flat_query = urlencode({k: v[0] for k, v in query.items()})
    return urlunparse((parsed.scheme or "https", parsed.netloc or "www.remaxrd.com", path, "", flat_query, ""))


def _dig(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    node: Any = data
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _find_property_in_next_data(payload: dict[str, Any]) -> dict[str, Any] | None:
    for path in _NEXT_DATA_PROPERTY_PATHS:
        candidate = _dig(payload, path)
        if isinstance(candidate, dict) and candidate.get("id"):
            return candidate
    return None


def _fetch_html(url: str, timeout: int = 30) -> str:
    response = requests.get(
        url,
        headers=DEFAULT_HEADERS,
        impersonate=IMPERSONATE,
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise RemaxDetailScrapeError(
            f"HTML fetch failed ({response.status_code}) for {url}"
        )
    return response.text


def _parse_next_data(html: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not script or not script.string:
        return None
    try:
        return json.loads(script.string)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid __NEXT_DATA__ JSON: %s", exc)
        return None


def _fetch_api_detail(remote_id: str, timeout: int = 20) -> dict[str, Any] | None:
    url = REMAX_API_DETAIL_URL.format(remote_id=remote_id)
    try:
        response = requests.get(url, impersonate=IMPERSONATE, timeout=timeout)
        if response.status_code >= 400:
            return None
        body = response.json()
        data = body.get("data")
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("API detail fetch failed for %s: %s", remote_id, exc)
        return None


def _city_to_slug(city_label: str | None) -> str | None:
    if not city_label:
        return None
    slug = city_label.strip().lower()
    slug = slug.replace("á", "a").replace("é", "e").replace("í", "i")
    slug = slug.replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or None


def is_canonical_remax_url(url: str | None) -> bool:
    """True when URL targets a RE/MAX detail route that loads (redirected/{id})."""
    return bool(url and "/propiedad/redirected/" in url)


def remax_portal_detail_url(remote_id: str, city: str | None = None) -> str:
    """
    Public RE/MAX RD detail URL that loads in the browser.

    Slug paths like ``/propiedad/{slug}?city=`` redirect to ``/propiedades`` (2026 site).
    The storefront uses ``/propiedad/redirected/{remote_id}`` per og:url on live pages.
    """
    rid = str(remote_id).strip()
    base = urlunparse(("https", "www.remaxrd.com", f"/propiedad/redirected/{rid}", "", "", ""))
    city_slug = _city_to_slug(city)
    if city_slug:
        return normalize_remax_listing_url(base, city_slug=city_slug)
    return base


def build_remax_portal_url(
    slug: str,
    city: str | None = None,
    *,
    remote_id: str | None = None,
) -> str:
    """Resolve ``remote_id`` from API slug/path and return the redirected detail URL."""
    rid = str(remote_id or extract_remote_id_from_url(slug) or "").strip()
    if not rid:
        tail = str(slug or "").strip().rstrip("/").split("/")[-1]
        match = _REMOTE_ID_RE.search(tail)
        rid = match.group(1) if match else tail
    return remax_portal_detail_url(rid, city)


def _extract_images_from_record(record: dict[str, Any]) -> list[str]:
    images: list[str] = []
    pictures = record.get("pictures") or []
    if isinstance(pictures, list):
        for entry in pictures:
            if isinstance(entry, str) and REMAX_IMAGE_HOST in entry:
                images.append(entry)
            elif isinstance(entry, dict):
                url = entry.get("pictures") or entry.get("url") or entry.get("src")
                if isinstance(url, str) and url.startswith("http"):
                    images.append(url)
    return images


def _extract_agent_from_record(
    record: dict[str, Any],
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    agents = record.get("agents") or record.get("agent_list") or []
    if not isinstance(agents, list) or not agents:
        return None, None, None, None, None
    agent = agents[0] if isinstance(agents[0], dict) else {}
    name = agent.get("name")
    phone = agent.get("mobile") or agent.get("phone") or agent.get("phone2")
    email = agent.get("email")
    agency = agent.get("agency_name")
    whatsapp = None
    if phone:
        digits = re.sub(r"\D", "", str(phone))
        if digits:
            whatsapp = f"https://wa.me/1{digits}" if not digits.startswith("1") else f"https://wa.me/{digits}"
    return (
        str(name).strip() if name else None,
        str(phone).strip() if phone else None,
        str(email).strip() if email else None,
        whatsapp,
        str(agency).strip() if agency else None,
    )


def _build_specs(record: dict[str, Any]) -> dict[str, Any]:
    remote_id = str(record.get("id") or record.get("parent_id") or "") or None
    with scraper_error_scope(
        "json",
        remote_id=remote_id,
        swallow=True,
        reraise=False,
    ):
        return _build_specs_inner(record)
    return {}


def _build_specs_inner(record: dict[str, Any]) -> dict[str, Any]:
    bedrooms = record.get("bedrooms")
    description_raw = record.get("description")
    description_source = (
        description_raw if isinstance(description_raw, str) else None
    )
    bathroom_count = resolve_bathroom_count(
        record.get("bathrooms"),
        record.get("half_bathrooms"),
        description_source,
    )
    sqm_construction = record.get("sqm_construction")
    sqm_land = record.get("sqm_land")
    return {
        "bedrooms": bedrooms,
        "bathroom_count": bathroom_count,
        "bathrooms": record.get("bathrooms"),
        "half_bathrooms": record.get("half_bathrooms"),
        "sqm_construction": sqm_construction,
        "sqm_land": sqm_land,
        "parking_spots": record.get("parking_spots"),
        "business_type": record.get("business_type"),
        "realstate_type": record.get("realstate_type"),
        "status": record.get("status"),
        "sector": record.get("sector"),
        "city": record.get("city"),
    }


def _record_to_detail(
    record: dict[str, Any],
    *,
    source: str,
    scrape_url: str,
) -> dict[str, Any]:
    remote_id = str(record.get("id") or record.get("parent_id") or "")
    method = map_detail_source_to_method(source)
    with scraper_error_scope(
        method,
        remote_id=remote_id or None,
        url=scrape_url,
        swallow=True,
        reraise=False,
    ):
        return _record_to_detail_inner(record, source=source, scrape_url=scrape_url)
    raise RemaxDetailScrapeError(f"Record parse failed for {scrape_url} (id={remote_id})")


def _record_to_detail_inner(
    record: dict[str, Any],
    *,
    source: str,
    scrape_url: str,
) -> dict[str, Any]:
    remote_id = str(record.get("id") or record.get("parent_id") or "")
    currency_block = record.get("currency") or {}
    currency_iso = str(currency_block.get("iso", "USD")).upper() if isinstance(currency_block, dict) else "USD"
    price = record.get("price")
    title = record.get("name") or record.get("property_title") or record.get("title")
    description = record.get("description") or ""
    if isinstance(description, str):
        description = _strip_html_to_text(description)

    agent_name, agent_phone, agent_email, whatsapp_api, agent_agency = _extract_agent_from_record(
        record
    )

    return {
        "property_id": remote_id,
        "title": title,
        "price": price,
        "currency": currency_iso,
        "specs": _build_specs(record),
        "image_list": _extract_images_from_record(record),
        "agent_name": agent_name,
        "agent_phone": agent_phone,
        "agent_email": agent_email,
        "agent_agency": agent_agency,
        "whatsapp_link": whatsapp_api,
        "description_text": description,
        "source": source,
        "scrape_url": scrape_url,
        "slug": record.get("slug"),
    }


def _extract_from_dom(html: str, scrape_url: str) -> dict[str, Any]:
    remote_guess = extract_remote_id_from_url(scrape_url)
    with scraper_error_scope(
        "dom",
        remote_id=remote_guess,
        url=scrape_url,
        swallow=True,
        reraise=False,
    ):
        return _extract_from_dom_inner(html, scrape_url)
    return {
        "property_id": remote_guess,
        "title": None,
        "price": None,
        "currency": None,
        "specs": {},
        "image_list": [],
        "agent_name": None,
        "agent_phone": None,
        "whatsapp_link": None,
        "description_text": None,
        "source": "dom_fallback",
        "scrape_url": scrape_url,
        "slug": None,
    }


def _extract_from_dom_inner(html: str, scrape_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    property_id = None
    codigo_node = soup.find(string=_CODIGO_RE)
    if codigo_node:
        match = _CODIGO_RE.search(str(codigo_node))
        if match:
            property_id = match.group(1)
    if not property_id:
        property_id = extract_remote_id_from_url(scrape_url)

    title = None
    for img in soup.find_all("img", alt=True):
        alt = (img.get("alt") or "").strip()
        if alt and alt.lower() not in {"remax", "logo", "icon"}:
            title = alt
            break

    image_list: list[str] = []
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if isinstance(src, str) and REMAX_IMAGE_HOST in src and "watermark/big" in src:
            image_list.append(src)

    agent_phone = None
    tel_link = soup.find("a", href=re.compile(r"^tel:", re.IGNORECASE))
    if tel_link and tel_link.get("href"):
        agent_phone = tel_link["href"].replace("tel:", "").strip()

    whatsapp_link = None
    wa_link = soup.find("a", href=_WHATSAPP_RE)
    if wa_link and wa_link.get("href"):
        whatsapp_link = wa_link["href"]

    agent_name = None
    for text in soup.stripped_strings:
        if "RE/MAX" in text and len(text) < 80:
            continue
        if re.search(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]{3,}\s+[A-Za-zÁÉÍÓÚáéíóúñÑ]{3,}", text):
            if len(text) < 60:
                agent_name = text
                break

    price = None
    price_match = re.search(
        r"(RD\$|US\$|\$)\s*([\d,]+(?:\.\d+)?)",
        soup.get_text(" ", strip=True),
    )
    if price_match:
        price = price_match.group(0)

    return {
        "property_id": property_id,
        "title": title,
        "price": price,
        "currency": None,
        "specs": {},
        "image_list": image_list,
        "agent_name": agent_name,
        "agent_phone": agent_phone,
        "whatsapp_link": whatsapp_link,
        "description_text": None,
        "source": "dom_fallback",
        "scrape_url": scrape_url,
        "slug": None,
    }


def _strip_html_to_text(html_fragment: str) -> str:
    soup = BeautifulSoup(unescape(html_fragment), "html.parser")
    return soup.get_text("\n", strip=True)


def scrape_remax_property_detail(
    url_to_scrape: str,
    *,
    city_slug: str | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Scrape one RE/MAX property page and return a unified detail dictionary.

    Args:
        url_to_scrape: Full storefront URL (English or Spanish). Reused from DB ``PropertyListing.url``.
        city_slug: Optional ``?city=`` query (e.g. higüey) required for some SSR hydrations.
        timeout: HTTP timeout seconds.

    Returns:
        Dict with keys: property_id, title, price, specs, image_list,
        agent_name, agent_phone, whatsapp_link, description_text, source, scrape_url.

    Raises:
        RemaxDetailScrapeError: When all extraction strategies fail.
    """
    remote_id = extract_remote_id_from_url(url_to_scrape)
    resolved_city = city_slug

    if remote_id and not resolved_city:
        api_seed = _fetch_api_detail(remote_id, timeout=timeout)
        if api_seed:
            resolved_city = _city_to_slug(str(api_seed.get("city") or ""))

    scrape_url = normalize_remax_listing_url(url_to_scrape, city_slug=resolved_city)
    html: str | None = None

    # --- Method A: __NEXT_DATA__ ---
    try:
        html = _fetch_html(scrape_url, timeout=timeout)
        next_payload = _parse_next_data(html)
        if next_payload:
            record = _find_property_in_next_data(next_payload)
            if record:
                with scraper_error_scope(
                    "json",
                    remote_id=remote_id,
                    url=scrape_url,
                    swallow=True,
                    reraise=False,
                ):
                    detail = _record_to_detail(record, source="next_data", scrape_url=scrape_url)
                    detail = _merge_dom_contacts(detail, html)
                    if detail.get("property_id") or detail.get("image_list"):
                        return detail
    except RemaxDetailScrapeError:
        raise
    except Exception as exc:
        logger.warning("Method A (__NEXT_DATA__) failed for %s: %s", scrape_url, exc)

    # --- Method A2: public API (same shape as hydration record) ---
    if remote_id:
        with scraper_error_scope("api", remote_id=remote_id, url=scrape_url, swallow=True, reraise=False):
            api_record = _fetch_api_detail(remote_id, timeout=timeout)
            if api_record:
                detail = _record_to_detail(api_record, source="remax_api", scrape_url=scrape_url)
                if detail.get("property_id") or detail.get("title"):
                    return detail

    # --- Method B: DOM fallback ---
    if html is None:
        html = _fetch_html(scrape_url, timeout=timeout)

    dom_detail = _extract_from_dom(html, scrape_url)
    if dom_detail.get("property_id") or dom_detail.get("image_list"):
        return dom_detail

    raise RemaxDetailScrapeError(
        f"Unable to extract property detail from {scrape_url} (id={remote_id})"
    )


def _merge_dom_contacts(detail: dict[str, Any], html: str) -> dict[str, Any]:
    """Fill missing phone/WhatsApp from DOM when JSON agent block is sparse."""
    if detail.get("agent_phone") and detail.get("whatsapp_link"):
        return detail
    dom = _extract_from_dom(html, detail["scrape_url"])
    if not detail.get("agent_phone") and dom.get("agent_phone"):
        detail["agent_phone"] = dom["agent_phone"]
    if not detail.get("whatsapp_link") and dom.get("whatsapp_link"):
        detail["whatsapp_link"] = dom["whatsapp_link"]
    if not detail.get("agent_name") and dom.get("agent_name"):
        detail["agent_name"] = dom["agent_name"]
    if not detail.get("image_list") and dom.get("image_list"):
        detail["image_list"] = dom["image_list"]
    return detail
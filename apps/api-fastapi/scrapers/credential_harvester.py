import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from playwright.async_api import Request

from scrapers.adspower_client import AdsPowerBrowserSession

REMAX_API_HOST = "api.remaxrd.com"
REMAX_TRIGGER_URL = (
    "https://www.remaxrd.com/en/propiedades?businessTypes=rent&currencyType=us"
    "&locations[]=id-1%26description-SANTO%20DOMINGO%20DE%20GUZM%C3%81N%26"
)
HARVEST_TIMEOUT_SECONDS = 45.0


@dataclass(frozen=True)
class HarvestedCredentials:
    headers: Dict[str, str]
    cookies: Dict[str, str]

    def as_curl_headers(self) -> Dict[str, str]:
        merged = dict(self.headers)
        if self.cookies:
            cookie_header = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
            if cookie_header:
                merged["Cookie"] = cookie_header
        merged.setdefault("Accept", "application/json, text/plain, */*")
        merged.setdefault("Referer", "https://www.remaxrd.com/")
        merged.setdefault("Origin", "https://www.remaxrd.com")
        return merged


class RemaxCredentialHarvester:
    """Uses AdsPower exactly once to capture live api.remaxrd.com request credentials."""

    async def harvest(self) -> HarvestedCredentials:
        captured_request: Dict[str, Any] = {}
        capture_event = asyncio.Event()

        async def on_request(request: Request) -> None:
            if capture_event.is_set():
                return
            parsed = urlparse(request.url)
            if parsed.netloc != REMAX_API_HOST:
                return
            if "/v2/realestates" not in parsed.path:
                return
            captured_request["headers"] = {
                k.lower(): v
                for k, v in request.headers.items()
            }
            capture_event.set()

        async with AdsPowerBrowserSession() as (_, browser):
            contexts = browser.contexts
            context = contexts[0] if contexts else await browser.new_context()
            page = await context.new_page()
            page.on("request", on_request)

            print(f"[Credential Harvester] Navigating trigger URL: {REMAX_TRIGGER_URL}")
            await page.goto(REMAX_TRIGGER_URL, wait_until="domcontentloaded", timeout=60000)

            try:
                await asyncio.wait_for(capture_event.wait(), timeout=HARVEST_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                print(
                    "[Credential Harvester] Network intercept missed; probing API directly from browser..."
                )
                await page.evaluate(
                    """async () => {
                        await fetch('https://api.remaxrd.com/v2/realestates?city=1&page=1', {
                            credentials: 'include',
                            headers: { 'Accept': 'application/json' }
                        });
                    }"""
                )
                await asyncio.wait_for(capture_event.wait(), timeout=15.0)

            cookies_list = await context.cookies()
            await page.close()

        if not captured_request.get("headers"):
            raise RuntimeError(
                "Failed to harvest api.remaxrd.com credentials from AdsPower browser session."
            )

        cookie_map = {c["name"]: c["value"] for c in cookies_list if c.get("name")}
        normalized_headers = _normalize_harvested_headers(captured_request["headers"])

        print(
            f"[Credential Harvester] Captured {len(normalized_headers)} headers "
            f"and {len(cookie_map)} cookies. Closing browser."
        )
        return HarvestedCredentials(headers=normalized_headers, cookies=cookie_map)


def _normalize_harvested_headers(raw_headers: Dict[str, str]) -> Dict[str, str]:
    allowed_prefixes = (
        "accept",
        "accept-language",
        "authorization",
        "user-agent",
        "sec-ch-ua",
        "sec-ch-ua-mobile",
        "sec-ch-ua-platform",
        "sec-fetch-dest",
        "sec-fetch-mode",
        "sec-fetch-site",
        "x-",
    )
    normalized: Dict[str, str] = {}
    for key, value in raw_headers.items():
        lower_key = key.lower()
        if lower_key in ("host", "content-length", "connection", "cookie"):
            continue
        if any(lower_key.startswith(prefix) for prefix in allowed_prefixes):
            normalized[lower_key] = value
    return normalized
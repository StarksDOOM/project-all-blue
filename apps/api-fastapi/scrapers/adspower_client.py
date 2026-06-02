import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import aiohttp
from dotenv import load_dotenv
from playwright.async_api import Browser, Playwright, async_playwright

load_dotenv()


@dataclass(frozen=True)
class AdsPowerConfig:
    profile_id: str
    api_base: str
    api_key: Optional[str]

    @classmethod
    def from_env(cls) -> "AdsPowerConfig":
        profile_id = os.getenv("ADSPOWER_PROFILE")
        if not profile_id:
            raise ValueError("Critical config failure: ADSPOWER_PROFILE missing from .env")
        return cls(
            profile_id=profile_id,
            api_base=os.getenv(
                "ADSPOWER_API_URL",
                "http://local.adspower.net:50325/api/v1/browser",
            ),
            api_key=os.getenv("ADSPOWER_API_KEY"),
        )

    @property
    def auth_headers(self) -> Dict[str, str]:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}


class AdsPowerBrowserSession:
    """Starts AdsPower once, yields a Playwright CDP browser, then stops the profile."""

    def __init__(self, config: Optional[AdsPowerConfig] = None):
        self.config = config or AdsPowerConfig.from_env()

    async def _resolve_ws_endpoint(self, http_session: aiohttp.ClientSession) -> str:
        start_url = f"{self.config.api_base}/start?user_id={self.config.profile_id}"
        start_timeout = aiohttp.ClientTimeout(total=120)
        async with http_session.get(start_url, timeout=start_timeout) as response:
            if response.status != 200:
                raw_err = await response.text()
                raise RuntimeError(
                    f"AdsPower rejected connection (Status {response.status}): {raw_err}"
                )
            res_data = await response.json()
            if res_data.get("code") != 0:
                raise RuntimeError(f"AdsPower API Error: {res_data.get('msg')}")

            ws_data = res_data.get("data", {}).get("ws", {})
            if "playwright" in ws_data:
                return ws_data["playwright"]
            if "puppeteer" in ws_data:
                return ws_data["puppeteer"]
            raise KeyError(
                "Could not locate a valid 'playwright' or 'puppeteer' WebSocket path in AdsPower response."
            )

    async def __aenter__(self) -> tuple[Playwright, Browser]:
        async with aiohttp.ClientSession(headers=self.config.auth_headers) as http_session:
            print(
                f"[AdsPower CDP] Requesting profile initialization for profile: {self.config.profile_id}"
            )
            self._ws_endpoint = await self._resolve_ws_endpoint(http_session)
            self._http_session = http_session

        print("[Playwright] Handshake accepted. Connecting to remote browser socket...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(self._ws_endpoint)
        return self._playwright, self._browser

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if getattr(self, "_browser", None):
            await self._browser.close()
        if getattr(self, "_playwright", None):
            await self._playwright.stop()

        stop_url = f"{self.config.api_base}/stop?user_id={self.config.profile_id}"
        async with aiohttp.ClientSession(headers=self.config.auth_headers) as http_session:
            await http_session.get(stop_url)
        print("[AdsPower CDP] Connection lifecycle clean shutdown completed.")
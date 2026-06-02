import os
import asyncio
import random
import aiohttp
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from playwright.async_api import async_playwright
from sqlmodel import Session, select
from database import engine, get_current_timestamp_ms
from models import PropertyListing
from dotenv import load_dotenv

load_dotenv()

class BaseScraperDriver(ABC):
    def __init__(self, source_portal: str):
        self.source_portal = source_portal
        
        # Load profile context and credentials globally
        self.profile_id = os.getenv("ADSPOWER_PROFILE")
        self.api_key = os.getenv("ADSPOWER_API_KEY")
        self.adspower_api = os.getenv("ADSPOWER_API_URL", "http://local.adspower.net:50325/api/v1/browser")
        
        if not self.profile_id:
            raise ValueError("Critical config failure: ADSPOWER_PROFILE missing from .env")
            
        # Build the authorization headers if an API Key is defined
        self.headers = {}
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    @abstractmethod
    async def extract_listings(self, html_content: str) -> List[Dict[str, Any]]:
        pass

    async def fetch_page_content(self, url: str, backoff_base: float = 3.0) -> str:
        start_url = f"{self.adspower_api}/start?user_id={self.profile_id}"
        stop_url = f"{self.adspower_api}/stop?user_id={self.profile_id}"
        
        async with aiohttp.ClientSession(headers=self.headers) as http_session:
            print(f"[AdsPower CDP] Requesting profile initialization for profile: {self.profile_id}")
            async with http_session.get(start_url) as response:
                if response.status != 200:
                    raw_err = await response.text()
                    raise RuntimeError(f"AdsPower rejected connection (Status {response.status}): {raw_err}")
                
                res_data = await response.json()
                if res_data.get("code") != 0:
                    raise RuntimeError(f"AdsPower API Error: {res_data.get('msg')}")
                
                # Check different possible structures for the WebSocket endpoint
                ws_data = res_data.get("data", {}).get("ws", {})
                
                if "playwright" in ws_data:
                    ws_endpoint = ws_data["playwright"]
                elif "puppeteer" in ws_data:
                    # Often Playwright can connect cleanly over the puppeteer debugger endpoint string as well
                    ws_endpoint = ws_data["puppeteer"]
                else:
                    # Print out the exact structure so we can target it accurately if it's completely custom
                    print(f"\n[AdsPower Debug] Unexpected JSON payload format from AdsPower API:\n{res_data}\n")
                    raise KeyError("Could not locate a valid 'playwright' or 'puppeteer' WebSocket debug path in the AdsPower response.")

        print("[Playwright] Handshake accepted. Connecting to remote browser socket...")
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(ws_endpoint)
            contexts = browser.contexts
            page = await contexts[0].new_page() if contexts else await browser.new_page()
            
            print(f"[Stealth Navigation] Routing context to target: {url}")
            # Change wait_until to networkidle so Next.js hydration fully completes
            await page.goto(url, wait_until="networkidle")
            
            # Keep the random backoff delay intact to mimic human interaction
            delay = backoff_base + random.uniform(1.0, 3.0)
            await asyncio.sleep(delay)
            
            content = await page.content()
            await page.close()
            await browser.close()
            
        async with aiohttp.ClientSession(headers=self.headers) as http_session:
            await http_session.get(stop_url)
            print("[AdsPower CDP] Connection lifecycle clean shutdown completed.")
            
        return content

    def upsert_listings(self, listings_data: List[Dict[str, Any]]) -> None:
        with Session(engine) as session:
            for data in listings_data:
                statement = select(PropertyListing).where(
                    PropertyListing.source_portal == self.source_portal,
                    PropertyListing.remote_id == str(data["remote_id"])
                )
                existing = session.exec(statement).first()
                
                if existing:
                    for key, val in data.items():
                        setattr(existing, key, val)
                    existing.last_modified = get_current_timestamp_ms()
                    existing.server_version += 1
                else:
                    new_listing = PropertyListing(**data)
                    new_listing.source_portal = self.source_portal
                    session.add(new_listing)
                    
            session.commit()
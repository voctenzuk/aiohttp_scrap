import asyncio
import logging

import aiohttp
from aiohttp_scraper import Proxies, ScraperSession
from tortoise import Tortoise

from utils import config

logging.basicConfig(
    format="%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d:%H:%M",
    level=logging.INFO,
)
proxy_map = {"Adidas": [config.proxy[0]], "Reebok": [config.proxy[1]]}


class BaseScraper:
    def __init__(self, *sections, maxtasks=2, limit=2, brand=""):
        self.todo = set()
        self.busy = set()
        self.done = {}
        self.tasks = set()
        self.sem = asyncio.Semaphore(maxtasks)
        self.retries = 3
        self.sections = sections
        self.section_url = ""
        self.good_url = ""
        self.brand = brand

        # connector stores cookies between requests and uses connection pool
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.72 Safari/537.36"
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Language": "ru",
        }
        if self.brand in ["Adidas", "Reebok"]:
            proxy = Proxies(
                proxies=proxy_map[self.brand],
                redis_uri=f"redis://{config.REDIS_IP}:6379",
                window_size_in_minutes=5,
                max_requests_per_window=300,
                redis_kwargs={},
            )
        else:
            proxy = None

        self.session = ScraperSession(
            headers=self.headers,
            connector=aiohttp.TCPConnector(limit=limit),
            proxies=proxy,
        )
        # self.session = aiohttp.ClientSession(headers=self.headers, connector=aiohttp.TCPConnector(limit=limit))

    async def run(self):
        logging.info("%s starting", self.brand)

        await self._prepare_writer()

        t = asyncio.ensure_future(
            self.addurls(
                [self.section_url.format(section) for section in self.sections]
            )
        )
        await asyncio.sleep(1)
        while self.busy:
            await asyncio.sleep(1)

        await t
        # await asyncio.sleep(2)
        await self.session.close()
        await Tortoise.close_connections()
        logging.info("%s scraped: %s items", self.brand, len(self.done))

    async def addurls(self, urls):
        for url in urls:
            if url not in self.busy and url not in self.done and url not in self.todo:
                self.todo.add(url)
                await self.sem.acquire()

                task = asyncio.ensure_future(self.process(url))
                task.add_done_callback(lambda t: self.sem.release())
                task.add_done_callback(self.tasks.remove)
                self.tasks.add(task)

    async def process(self, url):
        pass

    def select_type(self, url):
        pass

    def get_pages_count(self, data):
        pass

    async def parse_good(self, good_data, good_availability_data):
        pass

    async def _prepare_writer(self):
        await Tortoise.init(
            db_url=config.POSTGRES_URI,
            modules={"models": ["utils.models"]},
        )
        await Tortoise.generate_schemas()

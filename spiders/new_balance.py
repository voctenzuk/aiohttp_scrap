import asyncio
import json
import logging
import re

from base_scraper import BaseScraper
from utils.models import Item


def discount_find(standard_price, sale_price):
    discount = int((1 - sale_price / float(standard_price)) * 100)
    return discount


def select_type(url):
    if "/catalog/" in url:
        return "good"
    return "section"


class NBScraper(BaseScraper):
    def __init__(self, *sections, brand="New Balance"):
        super().__init__(*sections, brand=brand)

        self.section_url = "https://newbalance.ru/sale/?sort=default&arrCatalogFilter_220_435051366=Y&arrCatalogFilter_220_2162625244=Y&arrCatalogFilter_221_1734289371=Y&set_filter=%D0%9F%D0%BE%D0%BA%D0%B0%D0%B7%D0%B0%D1%82%D1%8C&PAGEN_1={}"
        self.good_url = "https://newbalance.ru"
        self.referal_url = "https://ad.admitad.com/g/8ab5faeed78ecf81d4cf19fa6a3a8a/?i=5&f_id=14129&ulp="
        self.oversale = 1

    async def process(self, url):
        self.todo.remove(url)
        self.busy.add(url)

        try:
            html = await self.session.get_html(url, retries=self.retries)
            json_text = re.findall(r'{"version".+}', html)[0]
            data = json.loads(json_text)

        except Exception as exc:
            logging.warning("%s : %s", url, exc)
            self.done[url] = False
        else:
            url_type = select_type(url)
            if url.endswith("PAGEN_1=1") and url_type == "section":
                pages_count = data["listing"]["pagesCount"]

                section_urls = [
                    self.section_url.format(page) for page in range(2, pages_count + 1)
                ]
                asyncio.Task(self.addurls((u for u in section_urls)))

            if url_type == "section":
                good_urls = [
                    self.good_url + good["url"] for good in data["listing"]["items"]
                ]
                asyncio.Task(self.addurls((u for u in good_urls)))

            elif url_type == "good":
                try:
                    await self.parse_good(data)
                except Exception as e:
                    logging.debug("%s : %s", url.split("&")[0], e)

            self.done[url] = True

        self.busy.remove(url)

        if len(self.done) % 100 == 0:
            logging.info(
                "%s completed tasks, %s still pending, todo %s",
                len(self.done),
                len(self.tasks),
                len(self.todo),
            )

    async def parse_good(self, data):
        discount = discount_find(
            data["product"]["unitPrice"], data["product"]["unitSalePrice"]
        )
        sizes = self.parse_sizes(data)[0]
        good = {
            "url": self.referal_url + self.good_url + data["product"]["url"],
            "name": data["product"]["name"],
            "brand": self.brand.title(),
            "vendor_code": data["product"]["url"].split("/")[-2],
            "image": self.good_url + data["product"]["imageUrl"],
            "gender": self.parse_info(data)[0],
            "category": self.parse_info(data)[1],
            "subcategory": self.parse_info(data)[2],
            "standard_price": data["product"]["unitPrice"],
            "sale_price": data["product"]["unitSalePrice"],
            "discount": discount if discount else None,
            "available_sizes": sizes if sizes else None,
            "size_label": self.parse_sizes(data)[1],
            "color": data["product"]["color"],
        }

        result = await Item.get_or_none(url=good["url"])

        if result:
            result = result.update_from_dict(good)
        else:
            result = Item(**good)
        await result.save()

    @staticmethod
    def parse_info(data):
        subcat_map = {
            "Трейловый бег": "Бег",
            "running": "Бег",
            "lifestyle": "Повседневная",
            "basketball": "Баскетбол",
        }
        gender_map = {"Мужчины": "Men", "Женщины": "Women"}

        if not (meta := data["product"].get("category")) or len(meta) < 3:
            url_data = data["product"]["url"].split("/")
            if len(url_data) >= 7:
                gender = url_data[2].title()
                category = url_data[3].split("_")[-1].title()
                subcategory = subcat_map[url_data[4].split("_")[-1]]
                meta = gender, category, subcategory

        gender = g if (g := gender_map.get(meta[0])) else meta[0]
        category = meta[1] if meta[1] != "Shoes" else "Обувь"
        subcategory = "Кроссовки;" + meta[2]

        return gender, category, subcategory

    @staticmethod
    def parse_sizes(data):
        sizes = ";".join([var["size"] for var in data["product"]["variations"]])
        label = "RU"
        return sizes, label

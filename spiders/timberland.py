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
    if "PAGEN_1" not in url:
        return "good"
    return "section"


def select_subcategory(name):
    sub_map = {
        "Мокасины": "Туфли",
        "Сандалии": "Летняя",
    }
    for cat in sub_map:
        if name.startswith(cat):
            return sub_map[cat]
    return name.split(" ")[0]


class TimberlandScraper(BaseScraper):
    def __init__(self, *sections, brand="Timberland"):
        super().__init__(*sections, brand=brand)

        self.section_url = (
            "https://timberland.ru/sale/filter/product_type-is-obuv/apply/?PAGEN_1={}"
        )
        self.good_url = "https://timberland.ru"
        self.referal_url = "https://ad.admitad.com/g/8tmmgnpezp8ecf81d4cf0358bd08b2/?i=5&f_id=15074&ulp="
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
            if url.endswith("PAGEN_1=1"):
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
                json_sizes = re.findall(r"JS_OBJ = ({.+})", html)[0]
                data_sizes = json.loads(json_sizes)["sizes"]
                try:
                    await self.parse_good(data, data_sizes)
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

    async def parse_good(self, data, data_sizes):
        discount = discount_find(
            data["product"]["unitPrice"], data["product"]["unitSalePrice"]
        )
        sizes = self.parse_sizes(data_sizes)[0]
        if not (img_end := data["product"]["imageUrl"]):
            img_end = re.findall(r'data-background="(.*.jpg)"')[0]
        good = {
            "url": self.referal_url + self.good_url + data["product"]["url"],
            "name": data["product"]["name"],
            "brand": self.brand.title(),
            "image": self.good_url + img_end,
            "gender": self.parse_info(data)[0],
            "category": self.parse_info(data)[1],
            "subcategory": self.parse_info(data)[2],
            "standard_price": data["product"]["unitPrice"],
            "sale_price": data["product"]["unitSalePrice"],
            "discount": discount if discount else None,
            "available_sizes": sizes if sizes else None,
            "size_label": self.parse_sizes(data_sizes)[1],
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
        gender_map = {"Мужчины": "Men", "Женщины": "Women"}

        url_data = data["product"]["url"].split("/")
        if len(url_data) >= 7:
            name = data["product"]["name"]

            subcategory = select_subcategory(name)

            gender = url_data[2].title()
            gender = gender_map[gender] if gender_map.get(gender) else gender
            category = url_data[3].split("_")[-1].title()
            meta = gender, category, subcategory

            category = meta[1] if meta[1] != "Obuv" else "Обувь"
            subcategory = meta[2]

        return gender, category, subcategory

    @staticmethod
    def parse_sizes(data_sizes):
        sizes = []
        for size in data_sizes:
            if size.get("rus") and size.get("can_buy") == "Y":
                sizes.append(size["rus"])
        sizes = ";".join(sizes)
        label = "RU"
        return sizes, label

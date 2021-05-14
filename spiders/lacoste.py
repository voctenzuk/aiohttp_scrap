import asyncio
import json
import logging
import re

from base_scraper import BaseScraper
from utils.models import Item


def parse_prices(data):
    standard = int(re.findall(r"\d+", data["prices"]["old"].replace(" ", ""))[0])
    sale = int(re.findall(r"\d+", data["prices"]["current"].replace(" ", ""))[0])
    discount = discount_find(standard, sale)
    return standard, sale, discount


def discount_find(standard_price, sale_price):
    discount = int((1 - sale_price / float(standard_price)) * 100)
    return discount


def select_type(url):
    if "/sales/" in url:
        return "section"
    return "good"


def pages_count(data):
    goods_count = data["count"]
    goods_per_page = data["perPage"]
    pages_count = goods_count // goods_per_page + 1
    return pages_count


class LacosteScraper(BaseScraper):
    def __init__(self, *sections, brand="Lacoste"):
        super().__init__(*sections, brand=brand)

        self.section_url = "https://lacoste.ru/catalog/sales/?set_filter=Y&arrFilter_123_2371150305=Y&arrFilter_123_3839122159=Y&arrFilter_123_1358442632=Y&arrFilter_123_3861158667=Y&arrFilter_123_1536390870=Y&arrFilter_123_2083355641=Y&arrFilter_123_3349330188=Y&arrFilter_123_1401442843=Y&arrFilter_187_3563192455=Y&arrFilter_187_1298878781=Y&PAGEN_1={}"
        self.good_url = "https://lacoste.ru/catalog/"
        self.referal_url = "https://ad.admitad.com/g/f446ccbb458ecf81d4cfd5f2d2f9d4/?i=5&f_id=7775&ulp="
        self.oversale = 1

    async def process(self, url):
        self.todo.remove(url)
        self.busy.add(url)

        try:
            html = await self.session.get_html(url, retries=self.retries)
            json_text = re.findall(r"__NUXT__=({.+})", html)[0]
            data = json.loads(json_text)["data"][0]["catalogData"]

        except Exception as exc:
            logging.warning("%s : %s", url.split("&")[0], exc)
            self.done[url] = False
        else:
            if url.endswith("PAGEN_1=1"):
                pages_count = self.pages_count(data["info"])
                section_urls = [
                    self.section_url.format(page) for page in range(2, pages_count + 1)
                ]
                asyncio.Task(self.addurls((u for u in section_urls)))

            for good in data["list"]:
                try:
                    await self.parse_good(good)
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
        good = {
            "url": self.referal_url + self.make_good_url(data),
            "name": data["name"],
            "brand": self.brand.title(),
            "image": "https:" + data["images"][0],
            "gender": self.parse_info(data["sec_code"])[0],
            "category": self.parse_info(data["sec_code"])[1],
            "subcategory": self.parse_info(data["sec_code"])[2],
            "standard_price": parse_prices(data)[0],
            "sale_price": parse_prices(data)[1],
            "discount": d if (d := parse_prices(data)[2]) else None,
            "available_sizes": s if (s := self.parse_sizes(data)[0]) else None,
            "size_label": self.parse_sizes(data)[1],
        }

        result = await Item.get_or_none(url=good["url"])

        if result:
            result = result.update_from_dict(good)
        else:
            result = Item(**good)
            await result.save()

    @staticmethod
    def parse_info(data):
        gender_map = {"muzhchiny": "Men", "zhenshchiny": "Women"}
        subcat_map = {
            "krossovki": "Кроссовки;Повседневная",
            "botinki": "Ботинки",
            "sapogi": "Ботинки",
            "kedy": "Кеды",
            "casual": "Летняя",
        }

        code = data.split("-")
        gender = g if (g := gender_map.get(code[-1])) else code[-1]
        category = "Обувь"
        subcategory = sc if (sc := subcat_map.get(code[0])) else code[0]
        return gender, category, subcategory

    def make_good_url(self, data):
        sec_code = s if (s := data.get("sec_code")) else "deti"
        url = self.good_url + sec_code + "/" + data["code"] + "/"
        return url

    @staticmethod
    def parse_sizes(data):
        sizes = ";".join([var["SIZE"].replace(",", ".") for var in data["offer"]])
        label = "RU"
        return sizes, label

    @staticmethod
    def pages_count(data):
        goods_count = data["count"]
        goods_per_page = data["perPage"]
        pages_count = goods_count // goods_per_page + 1
        return pages_count

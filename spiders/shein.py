import asyncio
import json
import logging
import re

from base_scraper import BaseScraper
from utils.models import Item


def discount_find(standard_price, sale_price):
    if not standard_price or not sale_price:
        return None
    discount = int((1 - sale_price / float(standard_price)) * 100)
    return discount


def select_type(url):
    if "/sale/" in url:
        return "section"
    return "good"


class SheinScraper(BaseScraper):
    def __init__(self, *sections, brand="Shein"):
        super().__init__(*sections, brand=brand)
        self.sections = [
            "RU-Shoes-On-Sale-sc-00509628",
            "Shoes-On-Sale-sc-00505720",
            "Men-Shoes-Bags-On-Sale-sc-00511774",
        ]
        self.section_url = "https://ru.shein.com/sale/{}.html"

        self.good_url = "https://ru.shein.com"
        self.referal_url = "https://ad.admitad.com/g/1kjlqr06u08ecf81d4cff0af71e07a/?i=5&f_id=18877&ulp="
        self.oversale = 1

    async def process(self, url):
        self.todo.remove(url)
        self.busy.add(url)

        try:
            html = await self.session.get_html(url, retries=self.retries)

        except Exception as exc:
            logging.warning("%s : %s", url, exc)
            self.done[url] = False
        else:
            url_type = select_type(url)
            if "page" not in url and url_type == "section":
                goods_count = int(re.findall(r'"top-info__title-sum">(\d+)', html)[0])
                pages_count = goods_count // 120 + 1

                new_url = url + "?page={}"
                section_urls = [
                    new_url.format(page) for page in range(2, pages_count + 1)
                ]

                asyncio.Task(self.addurls((u for u in section_urls)))

            if url_type == "section":
                links = re.findall(r'<a href="([\w.\/-]*)"', html)
                asyncio.Task(self.addurls((self.good_url + u for u in links)))

            elif url_type == "good":
                try:
                    json_text = re.findall(r"productIntroData: ({.+})", html)[0]
                    data = json.loads(json_text)
                    await self.parse_good(url, data)
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

    async def parse_good(self, url, data):
        standard_price_data = data["detail"].get("retailPrice")
        standard_price = int(pr) if (pr := standard_price_data.get("amount")) else None

        sale_price_data = data["detail"].get("salePrice")
        sale_price = int(pr) if (pr := sale_price_data.get("amount")) else None

        discount = discount_find(standard_price, sale_price)

        good = {
            "url": self.referal_url + url,
            "name": data["detail"].get("goods_name"),
            "brand": self.brand.title(),
            "image": "https:" + data["detail"].get("goods_img"),
            "gender": self.parse_info(data)[0],
            "category": self.parse_info(data)[1],
            "subcategory": self.parse_info(data)[2],
            "standard_price": standard_price,
            "sale_price": sale_price,
            "discount": discount,
            "available_sizes": self.parse_sizes(data)[0],
            "size_label": self.parse_sizes(data)[1],
            "color": self.parse_color(data),
        }
        result = await Item.get_or_none(url=good["url"])

        if result:
            result = result.update_from_dict(good)
        else:
            result = Item(**good)
        await result.save()

    @staticmethod
    def parse_color(data):
        prod_details = data["detail"].get("productDetails")
        for detail in prod_details:
            det_name = detail.get("attr_name_en")
            if det_name == "Color" and (color := detail.get("attr_value")):
                return color

    def parse_info(self, data):
        if not (gender_data := data.get("parentCats")):
            return None, None, None
        gender, categories_data = self.parse_gender(gender_data)
        category, subcategories_datas = self.parse_category(categories_data)
        subcategory = self.parse_subcategory(subcategories_datas)

        return gender, category, subcategory

    @staticmethod
    def parse_gender(data):
        gender = data.get("cat_url_name")
        next_data = data.get("children")
        return gender, next_data

    @staticmethod
    def parse_category(data):
        categories = []
        next_datas = []
        for category_data in data:
            ru_category = category_data.get("multi")
            if ru_category and ru_category.get("language_flag") == "ru":
                categories.append(ru_category["cat_name"])
            elif (en_category := category_data.get("cat_url_name")) :
                categories.append(en_category)
            if (next_data := category_data.get("children")) :
                next_datas += next_data

        categories = ";".join(categories) if categories else None
        return categories, next_datas

    @staticmethod
    def parse_subcategory(data):
        subcategories = []
        for subcategory_data in data:
            ru_subcategory = subcategory_data.get("multi")
            if ru_subcategory and ru_subcategory.get("language_flag") == "ru":
                subcategories.append(ru_subcategory["cat_name"])
            elif (en_subcategory := subcategory_data.get("cat_url_name")) :
                subcategories.append(en_subcategory)
        subcategories = ";".join(subcategories) if subcategories else None
        return subcategories

    @staticmethod
    def parse_sizes(data):
        multi_local_size = data.get("multiLocalSize")
        size_rule = multi_local_size.get("size_rule_list")
        eu_rules = size_rule.get("EU")
        sizes = []
        # if not eu_rule:
        size_list = data.get("attrSizeList")
        for size_data in size_list:
            if (s := size_data.get("attr_value")) and int(size_data.get("stock")) > 0:
                if not eu_rules:
                    sizes.append(s.removeprefix("EUR"))
                else:
                    for rule in eu_rules:
                        rule_data = eu_rules[rule]
                        if s == rule_data.get("name") and rule_data.get("correspond"):
                            sizes.append(rule_data.get("correspond"))
        sizes = ";".join(sizes) if sizes else None
        label = "EUR"
        return sizes, label

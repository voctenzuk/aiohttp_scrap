import asyncio
import logging
import re

from base_scraper import BaseScraper
from utils.models import Item


class AdidasScraper(BaseScraper):
    def __init__(self, *sections, maxtasks=2, limit=2, brand="Adidas"):
        super().__init__(*sections, maxtasks=maxtasks, limit=limit, brand=brand)

        if len(sections) == 1 and sections[0] == "all":
            self.sections = [
                "muzhchiny-obuv-outlet",
                "zhenshchiny-obuv-outlet",
                "muzhchiny-obuv",
                "zhenshchiny-obuv",
            ]

        self.section_url = "https://www.adidas.ru/api/plp/content-engine?query={}"
        self.good_url = "https://www.adidas.ru/api/products/"
        self.referal_url = "https://ad.admitad.com/g/ztm2nafuyh8ecf81d4cf0056221306/?i=5&f_id=14299&ulp="

        self.oversale = 1

    async def process(self, url):
        self.todo.remove(url)
        self.busy.add(url)

        try:
            data = await self.session.get_json(url, retries=self.retries)

            url_type = self.select_type(url)
            if url_type == "section":
                pass

            elif url_type == "good":
                data_availab = await self.session.get_json(
                    url + "/availability", retries=self.retries
                )

        except Exception as exc:
            logging.warning("%s : %s", url.split("&")[0], exc)
            self.done[url] = False
        else:
            if (url_type == "section") and "&start" not in url:
                pages_count = self.get_pages_count(data)

                category_id = url.split("query=")[-1]
                logging.info(
                    "category %s goods count %s", category_id, pages_count * 48
                )

                urls = [url + f"&start={page*48}" for page in range(1, pages_count)]
                goods = data["raw"]["itemList"]["items"]
                goods_urls = [self.good_url + product["productId"] for product in goods]
                asyncio.Task(self.addurls((u for u in urls)))
                asyncio.Task(self.addurls((u for u in goods_urls)))

            elif url_type == "section":
                goods = data["raw"]["itemList"]["items"]
                urls = [self.good_url + product["productId"] for product in goods]
                asyncio.Task(self.addurls((u for u in urls)))

            elif url_type == "good":
                try:
                    await self.parse_good(data, data_availab)
                except ValueError as e:
                    logging.debug("%s : %s", url, e)

            self.done[url] = True

        self.busy.remove(url)

        if len(self.done) % 100 == 0:
            logging.info(
                "%s completed tasks, %s still pending, todo %s",
                len(self.done),
                len(self.tasks),
                len(self.todo),
            )

    @staticmethod
    def select_type(url):
        if "/api/plp/content-engine" in url:
            return "section"
        elif "/api/products" in url:
            return "good"

    @staticmethod
    def get_pages_count(data):
        goods_count = data["raw"]["itemList"]["count"]
        pages_count = goods_count // 48 + 1

        return pages_count

    async def parse_good(self, good_data, good_availability_data):
        split_url = good_data["meta_data"]["canonical"].split("/")
        good = {
            "url": self.referal_url + "https://" + split_url[-3] + "/" + split_url[-1],
            "name": good_data["name"],
            "vendor_code": good_data.get("id"),
            "brand": self.brand.title(),
            "image": self.parse_image(good_data),
            "gender": self.parse_gender(good_data),
            "category": self.parse_category(good_data)["category"],
            "subcategory": self.parse_category(good_data)["subcategory"],
            "standard_price": self.parse_price(good_data)[0],
            "sale_price": self.parse_price(good_data)[1],
            "discount": self.parse_price(good_data)[2],
            "available_sizes": self.parse_sizes(good_availability_data)[0],
            "size_label": self.parse_sizes(good_availability_data)[1],
            "color": good_data["attribute_list"]["search_color_raw"],
        }

        result = await Item.get_or_none(url=good["url"])

        if result:
            result = result.update_from_dict(good)
        else:
            result = Item(**good)
        await result.save()

    def parse_category(self, data):
        cat_map = {
            "Оbuv": "Обувь",
            "Оdezhda": "Одежда",
            "Аksessuary": "Аксессуары",
        }
        subcat_map = {
            "Футбольные бутсы": "Кроссовки",
            "Сандалии и шлепанцы": "Летняя",
            "Lifestyle": "Повседневная",
        }
        category = data["attribute_list"]["category"]
        subactaegories = []
        for subcat in data["attribute_list"]["productType"]:
            subactaegories.append(s if (s := subcat_map.get(subcat)) else subcat)

        if "кеды" in data["name"].lower():
            subactaegories.append("Кеды")
            if "Кроссовки" in subactaegories:
                subactaegories.remove("Кроссовки")

        styles = []
        for style in data["attribute_list"]["sport"]:
            styles.append(s if (s := subcat_map.get(style)) else style)

        if "Кроссовки" in subactaegories:
            subactaegories += styles

        return {
            "category": cat_map[category],
            "subcategory": ";".join(subactaegories),
        }

    @staticmethod
    def parse_gender(data):
        gender = data["attribute_list"]["gender"]
        if gender in ["Женщины", "W"]:
            return "Women"
        elif gender in ["Мужчины", "M"]:
            return "Men"
        elif gender in ["Унисекс", "U"]:
            return "Unisex"
        elif gender == "Дети":
            return "Child"

    @staticmethod
    def parse_sizes(av_data):
        sizes = {}
        pattern = r"(?i)(.+) (\w+)"

        var_list = av_data.get("variation_list")
        if (
            not (av := av_data.get("availability_status"))
            or av != "IN_STOCK"
            or not var_list
        ):
            return None, None
        for var in var_list:
            if var.get("availability_status") == "IN_STOCK":
                size, label = re.findall(pattern, var.get("size"))[0]
                sizes[label] = sizes.get(label, []) + [size]

        if len(sizes) > 1:
            print(sizes)
        return ";".join(list(sizes.values())[0]), list(sizes.keys())[0].upper()

    def parse_price(self, data):
        pricing_information = data.get("pricing_information")

        if pricing_information is not None:
            standard_price = pricing_information.get("standard_price")
            sale_price = pricing_information.get("sale_price", standard_price)

            try:
                callout = data["callouts"]["callout_top_stack"][0]["title"]
                sale = float(re.findall(r"-(\d+)[\s]*%", callout)[0])
                self.oversale = 1 - round(sale / 100, 2)
            except BaseException:
                self.oversale = 1

            sale_price = float(sale_price) * self.oversale
            discount = int((1 - sale_price / float(standard_price)) * 100)

            if discount == 0:
                return None, None, None
            return standard_price, sale_price, discount

    @staticmethod
    def parse_image(data):
        image = data["product_description"]["description_assets"].get("image_url")
        if not image and len(data["view_list"]) > 0:
            image = data["view_list"][0]["image_url"]
        return image

from spiders.adidas import AdidasScraper


class ReebokScraper(AdidasScraper):
    def __init__(self, *sections, brand="Reebok"):
        super().__init__(*sections, brand=brand)

        self.section_url = "https://www.reebok.ru/api/plp/content-engine?query={}"
        self.good_url = "https://www.reebok.ru/api/products/"
        self.referal_url = "https://ad.admitad.com/g/fodzfl8hru8ecf81d4cfb092a65bb6/?i=5&f_id=15558&ulp="

        if len(sections) == 1 and sections[0] == "all":
            self.sections = [
                "muzhchiny-obuv-outlet",
                "zhenshchiny-obuv-outlet",
                "muzhchiny-obuv",
                "zhenshchiny-obuv",
            ]

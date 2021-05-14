import asyncio
import logging
import sys

from spiders import adidas, lacoste, new_balance, reebok, shein, timberland

logging.basicConfig(level=logging.INFO)


CRAWLER_SELECT = {
    "adidas": adidas.AdidasScraper,
    "reebok": reebok.ReebokScraper,
    "lacoste": lacoste.LacosteScraper,
    "nb": new_balance.NBScraper,
    "timberland": timberland.TimberlandScraper,
    "shein": shein.SheinScraper,
}


def main():
    loop = asyncio.get_event_loop()

    c = CRAWLER_SELECT[sys.argv[1]](*sys.argv[2:])
    loop.run_until_complete(c.run())


if __name__ == "__main__":
    if "--iocp" in sys.argv:
        from asyncio import events, windows_events

        sys.argv.remove("--iocp")
        logging.info("using iocp")
        el = windows_events.ProactorEventLoop()
        events.set_event_loop(el)

    main()

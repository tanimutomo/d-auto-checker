# coding: utf-8
import argparse
import asyncio
import collections
import json
import os
from time import sleep

from dotenv import load_dotenv
import moment
from pyppeteer import launch
import slackweb


URL = ""
SLACK_WEBHOOK_URL = ""
NOT_AVAILABLE = "現在、販売していません"
TICKET_ALLDAY = "１デーパスポート"
TICKET_ELEVEN = "入園時間指定パスポート（午前11時～）"
TICKET_FOURTEEN = "入園時間指定パスポート（午後2時～）"


async def check_all():
    browser = await launch(headless=False)
    page = await browser.newPage()
    await page.goto(URL)

    today_month = moment.now().month
    today_day = moment.now().day

    date_status = dict()
    for m in range(today_month, today_month+2):
        for x in range(1, 8):
            for y in range(1, 6):
                date_selector = get_date_selector(x, y)

                date_e = await page.J(date_selector + " > span")
                date = await page.evaluate("e => e.innerHTML", date_e)

                try:
                    date = int(date)
                except:
                    continue

                if m == today_month and date < today_day:
                    continue

                print("date:", date)

                date_selector = get_date_selector(x, y)
                availables = await getAvailableDates(page, date_selector)
                date_status[f"{m:02}/{date:02}"] = availables

        sleep(1)
        await page.click("#searchCalendar > div > div > ul > button.slick-next.slick-arrow")
        sleep(1)

    date_status = json.dumps(
        date_status,
        sort_keys=True,
        indent=5,
        separators=(", ", ": "),
        ensure_ascii=False,
    )
    print(date_status)
    send_to_slack(date_status)

    await browser.close()
    return


async def check_one(n :int, x :int, y :int):
    browser = await launch(
        headless=False,
        defaultViewport={"width": 1200, "height": 1000},
    )
    page = await browser.newPage()
    await page.goto(URL)

    today_month = moment.now().month
    today_day = moment.now().day

    for i in range(n):
        sleep(1)
        await page.click("#searchCalendar > div > div > ul > button.slick-next.slick-arrow")
        sleep(1)

    date_status = dict()
    date_selector = get_date_selector(x, y)

    date_e = await page.J(date_selector + " > span")
    date = await page.evaluate("e => e.innerHTML", date_e)

    try:
        date = int(date)
    except:
        return

    print("date:", date)
    date_selector = get_date_selector(x, y)
    availables = await getAvailableDates(page, date_selector)
    date_status[f"{today_month+n:02}/{date:02}"] = availables

    if not availables:
        return

    date_status = json.dumps(
        date_status,
        sort_keys=True,
        indent=5,
        separators=(", ", ": "),
        ensure_ascii=False,
    )
    print(date_status)
    send_to_slack(date_status)

    if TICKET_ELEVEN in availables:
        await goto_procedure(page, 2)
    elif TICKET_ALLDAY in availables:
        await goto_procedure(page, 1)
    elif TICKET_FOURTEEN in availables:
        await goto_procedure(page, 3)

    sleep(60*5)

    # await browser.close()
    # return


async def getAvailableDates(page, date_selector :str) -> list:
    await page.hover(date_selector)
    sleep(1)
    await page.click(date_selector)
    sleep(1)
    await page.click("#searchEticket")
    sleep(5)

    tickets = await page.JJ("#searchResultList > ul > li > div")
    availables = list()
    for ticket in tickets:
        name_e = await ticket.J("h4")
        name = await page.evaluate("e => e.innerHTML", name_e)

        ps = await ticket.JJ("p")
        is_available = True
        for p in ps:
            p_text = await page.evaluate("e => e.innerHTML", p)
            if p_text == NOT_AVAILABLE:
                is_available = False
        
        if is_available:
            availables.append(name)
    
    return availables


async def goto_procedure(page, n :int):
    await page.hover(f"#searchResultList > ul > li:nth-child({n}) > div")
    await page.click(f"#searchResultList > ul > li:nth-child({n}) > div")

    sleep(3)

    # select park
    land_desc = await page.J("#search-ticket-group > div > section > section.search-select-park-view.section-module.elm-progressive-reveal.is-visible > div > div.search-1day.elm-progressive-reveal.is-visible > div > ul > li:nth-child(1) > span")
    land_desc_text = await page.evaluate("e => e.innerHTML", land_desc)
    if land_desc_text != NOT_AVAILABLE:
        await page.click("#search-ticket-group > div > section > section.search-select-park-view.section-module.elm-progressive-reveal.is-visible > div > div.search-1day.elm-progressive-reveal.is-visible > div > ul > li:nth-child(1) > button")
    else:
        await page.click("#search-ticket-group > div > section > section.search-select-park-view.section-module.elm-progressive-reveal.is-visible > div > div.search-1day.elm-progressive-reveal.is-visible > div > ul > li:nth-child(2) > button")

    sleep(1)

    # push add button
    await page.click("#search-ticket-group > div > section > section.search-ticketnum-view.section-module.elm-progressive-reveal.is-visible > div > dl.select-ticket-num.search-adult > dd > ul > li:nth-child(3) > button")

    # push button to go to procedure
    await page.click("#search-ticket-group > div > section > section.section-module.section-append > div > ul > li > button")
    
    sleep(2)

    # # scroll down checks
    # checker = await page.J("body > div.new-ui-theme > div > div > div")
    # await page.evaluate("_ => { window.scrollBy(0, 100); }", checker)

    # # push confirm button
    # await page.click("body > div.new-ui-theme > div > div > ul > li > button")

    return


def get_date_selector(x :int, y :int) -> str:
    return f"#searchCalendar > div > div > ul > div > div > li.js-nc-mark-child.slick-slide.slick-current.slick-active > div > table > tbody > tr:nth-child({y}) > td:nth-child({x}) > a"


def init():
    load_dotenv()

    global URL
    global SLACK_WEBHOOK_URL

    URL = os.getenv("TARGET_URL")
    SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

    if not URL:
        EnvironmentError("URL is not defined.")
    if not SLACK_WEBHOOK_URL:
        EnvironmentError("SLACK_WEBHOOK_URL is not defined.")


def send_to_slack(text):
    slack = slackweb.Slack(url=SLACK_WEBHOOK_URL)
    slack.notify(text=text)


if __name__ == "__main__":
    init()

    parser = argparse.ArgumentParser()
    parser.add_argument("mode", type=str, choices=["all", "one"])
    parser.add_argument("--n", type=int)
    parser.add_argument("--x", type=int)
    parser.add_argument("--y", type=int)
    args = parser.parse_args()

    if args.mode == "all":
        asyncio.get_event_loop().run_until_complete(check_all())
    elif args.mode == "one":
        asyncio.get_event_loop().run_until_complete(
            check_one(args.n, args.x, args.y),
        )

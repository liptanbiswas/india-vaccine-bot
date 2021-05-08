#!/usr/bin/env python3

import datetime
import json
import logging
import os
import requests
import time
import traceback
from pathlib import Path

from TwitterAPI import TwitterAPI, TwitterError

sleep_between_runs = 300
sleep_between_configs = 15

configs = [
    {
        "name": "Pune",
        "state": "maharashtra",
        "districts": ["Pune"],
        "alert_channel": "C020LSC1NFQ",
        "min_age_limit": 18,
        "min_pincode": 411000,
        "max_pincode": 412308,
        "post_to_twitter": True,
    },
    {
        "name": "Bangalore",
        "state": "karnataka",
        "districts": ["Bangalore Rural", "Bangalore Urban"],
        "alert_channel": "C0216DGJBCH",
        "post_to_twitter": True,
    },
    {
        "name": "Delhi",
        "state": "delhi",
        "alert_channel": "C020QLZ56UV",
        "post_to_twitter": True,
    },
    {
        "name": "East Singhbhum",
        "state": "jharkhand",
        "districts": ["East Singhbhum"],
        "alert_channel": "C020RTE9S2K",
        "post_to_twitter": True,
    },
    {
        "name": "Faridabad",
        "state": "haryana",
        "districts": ["Faridabad"],
        "alert_channel": "C021MQQCYGY",
        "post_to_twitter": True,
    },
    {
        "name": "Gurugram",
        "state": "haryana",
        "districts": ["Gurgaon"],
        "alert_channel": "C020QKJASNR",
        "post_to_twitter": True,
    },
    {
        "name": "Hyderabad",
        "state": "telangana",
        "districts": ["Hyderabad"],
        "alert_channel": "C021JPGHMR6",
        "post_to_twitter": True,
    },
    {
        "name": "Hyderabad",
        "state": "telangana",
        "districts": ["Hyderabad"],
        "alert_channel": "C0217J5B8NM",
        "min_age_limit": 45,
    },
    {
        "name": "Jaipur",
        "state": "rajasthan",
        "districts": ["Jaipur I", "Jaipur II"],
        "alert_channel": "C021927JUKU",
        "post_to_twitter": True,
    },
    {
        "name": "Kolkata",
        "state": "west_bengal",
        "districts": ["Kolkata"],
        "alert_channel": "C0216NTVB1Q",
        "post_to_twitter": True,
    },
    {
        "name": "Kolkata",
        "state": "west_bengal",
        "districts": ["Kolkata"],
        "alert_channel": "C0216P680AW",
        "min_age_limit": 45,
    },
    {
        "name": "Mumbai",
        "state": "maharashtra",
        "districts": ["Mumbai"],
        "alert_channel": "C020U1L01FD",
        "post_to_twitter": True,
    },
]


# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
)

logger = logging.getLogger("india-vaccine-bot")


# Load all districts
p = Path(__file__).with_name("districts.json")
with p.open() as fh:
    all_districts = json.load(fh)


# post_webhook()
# _________________________________________________________________________________________
def post_webhook(data, config):
    webhook_url = os.environ.get("WEBHOOK_URL")
    if webhook_url is None:
        logger.error("WEBHOOK_URL env var is not set")
        return

    response = requests.post(
        webhook_url, data=json.dumps(data), headers={"Content-Type": "application/json"}
    )
    print(response)


# get_twitter_keys()
# _________________________________________________________________________________________
def get_twitter_keys(city, config):
    if city == "default":
        return (
            os.environ.get("TWITTER_API_KEY"),
            os.environ.get("TWITTER_API_SECRET"),
            os.environ.get("TWITTER_ACCESS_TOKEN"),
            os.environ.get("TWITTER_ACCESS_SECRET")
        )
    else:
        city = city.upper()
        api_key = "TWITTER_API_KEY_{city}"
        api_secret = "TWITTER_API_SECRET_{city}"
        access_token = "TWITTER_ACCESS_TOKEN_{city}"
        access_secret = "TWITTER_ACCESS_SECRET_{city}"

        min_age_limit = config.get("min_age_limit", 18)
        if min_age_limit == 45:
            api_key += "_45"
            api_secret += "_45"
            access_token += "_45"
            access_secret += "_45"

        return (
            api_key,
            api_secret,
            access_token,
            access_secret
        )



# post_twitter()
# _________________________________________________________________________________________
def post_twitter(msg, config, city):
    if not config.get("post_to_twitter", False):
        return

    api_key, api_secret, access_token, access_secret = get_twitter_keys(city, config)

    if api_key is None:
        logger.error(f"Twitter API key env vars not set for {city}")
        return

    twitter = TwitterAPI(
        api_key, api_secret, access_token, access_secret
    )
    try:
        logger.info(f"Posting to {city} twitter")
        r = twitter.request("statuses/update",
                            {"status": msg})
        logger.info(f"Twitter response: {r.status_code} {r.text}")
    except TwitterError.TwitterConnectionError as e:
        logger.error(f"Twitter error for {city}: {e}")

    if city == "default":
        time.sleep(10) # avoid twitter ratelimit


# report_availability()
# _________________________________________________________________________________________
def report_availability(slots_by_date_pincode, config):
    keys = list(slots_by_date_pincode.keys())
    keys.sort()
    most_recent = keys[0]

    slots_by_pincode = slots_by_date_pincode[most_recent]

    num_slots = 0
    fields = []
    pincodes = []
    centers = []
    for pincode, slots in slots_by_pincode.items():
        print(pincode, slots)
        num_slots += slots["available_capacity"]
        num_centers = len(slots["centers"])
        pincodes.append(str(pincode))
        centers += slots["centers"]

        if num_centers == 1:
            center_txt = slots["centers"][0]
        else:
            center_txt = f"{num_centers} centers"

        if slots["available_capacity"] == 1:
            num_txt = "One slot was found"
        else:
            num_txt = f"{slots['available_capacity']} slots were found"
        fields.append(
            {
                "value": f"{num_txt} in pincode {pincode} at {center_txt}.",
                "short": False,
            }
        )

    min_age_limit = config.get("min_age_limit", 18)

    pretext = f"{num_slots} appointment slots for {min_age_limit}+ found in {config['name']} on {most_recent.strftime('%b %d, %Y')}!"
    twitter_text = f"{num_slots} slots for {min_age_limit}+ found in {config['name']}"
    if len(centers) == 1:
        twitter_text += f" at {centers[0]}"
    elif len(pincodes) == 1:
        twitter_text += f" (pincode {pincodes[0]})"
    else:
        pincode_text = f" (pincodes {', '.join(pincodes)})"
        if len(twitter_text) + len(pincode_text) < 100:
            twitter_text += pincode_text
    twitter_text += f" on {most_recent.strftime('%b %d')}!"

    data = {
        "username": "VaxBot",
        "attachments": [
            {
                "pretext": pretext,
                "fields": fields,
            }
        ],
    }

    if "alert_channel" in config:
        data["channel"] = config["alert_channel"]

    print(data)
    post_webhook(data, config)
    post_twitter(twitter_text, config, "default")
    post_twitter(twitter_text, config, config["name"])


# get_day_for_week()
# _________________________________________________________________________________________
def get_day_for_week(week):
    day = datetime.date.today() + datetime.timedelta(weeks=week)
    return day.strftime("%d-%m-%Y")


# check_district()
# _________________________________________________________________________________________
def check_district(d, week, config):
    params = {"district_id": d["district_id"], "date": get_day_for_week(week)}

    headers = {
        'user-agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
    }

    url = "https://cdn-api.co-vin.in/api/v2/appointment/sessions/public/calendarByDistrict"
    r = requests.get(url, params=params, headers=headers)
    data = r.json()

    print("district config is {d}", d)
    print("params", params)

    min_age_limit = config.get("min_age_limit", 18)

    slots_by_date_pincode = {}
    slots_found = False
    for center in data["centers"]:
        for session in center["sessions"]:
            # print(session)
            if session["min_age_limit"] > min_age_limit:
                continue

            if session["available_capacity"] == 0:
                continue

            if "min_pincode" in config:
                if center["pincode"] < config["min_pincode"]:
                    continue
            if "max_pincode" in config:
                if center["pincode"] > config["max_pincode"]:
                    continue

            slots_found = True
            date = datetime.datetime.strptime(session["date"], "%d-%m-%Y")

            slots_by_pincode = slots_by_date_pincode.get(date, {})
            slots = slots_by_pincode.get(center["pincode"], {})

            slots["available_capacity"] = (
                slots.get("available_capacity", 0) + session["available_capacity"]
            )
            slots["centers"] = slots.get("centers", []) + [center["name"]]

            slots_by_pincode[center["pincode"]] = slots
            slots_by_date_pincode[date] = slots_by_pincode

    # print(slots_by_date_pincode)
    return slots_found, slots_by_date_pincode


# check_availability()
# _________________________________________________________________________________________
def check_availability(config):
    state = config["state"]
    districts = config.get("districts")

    logger.info(f"Checking {state} {districts=}")

    if districts is None:
        districts_to_check = all_districts[state]["districts"]
    else:
        districts_to_check = [
            x
            for x in all_districts[state]["districts"]
            if x["district_name"] in districts
        ]

    for d in districts_to_check:
        for week in range(0, 2):
            slots_found, slots_by_date_pincode = check_district(d, week, config)
            if slots_found:
                report_availability(slots_by_date_pincode, config)
                return
            time.sleep(sleep_between_configs)


logger.info("Starting VaxBot")

while True:
    for config in configs:
        try:
            check_availability(config)
        except Exception as e:
            logger.error(f"failed with exception {e}, {traceback.format_exc()}")
            time.sleep(120)
            continue

        time.sleep(sleep_between_configs)
    time.sleep(sleep_between_runs)

#!/usr/bin/env python3

import datetime
import json
import logging
import os
import requests
import time
import traceback
from pathlib import Path

sleep_between_runs = 300

configs = [
    {
        "name": "Kozhikode",
        "state": "kerala",
        "districts": ["Kozhikode"],
        "min_age_limit": 18,
    }
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


# post_alert()
# _____________________________________________________________________________
def post_alert(data):
    routing_key = os.environ.get("ROUTING_KEY")
    if routing_key is None:
        logger.error("ROUTING_KEY env var is required")
        return

    headers = {
        "Content-Type": "application/json"
    }

    data['routing_key'] = routing_key
    data['event_action'] = "trigger"
    
    response = requests.post(
        "https://events.pagerduty.com/v2/enqueue", data=json.dumps(data), headers=headers
    )
    print(response)


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

    for date in keys:
        slots_by_pincode = slots_by_date_pincode[date]
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
            fields.append(f"{date.strftime('%b %d, %Y')}: {num_txt} in pincode {pincode} at {center_txt}.")

    min_age_limit = config.get("min_age_limit", 18)

    pretext = f"{num_slots} appointment slots for {min_age_limit}+ found in {config['name']} on {most_recent.strftime('%b %d, %Y')}!"

    data = {
        "payload": {
            "summary": pretext,
            "source": "vaxbot",
            "severity": "critical",
            "custom_details": fields
        }
    }

    logger.info(f"webhook {data}")
    post_alert(data)


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
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
    }

    url = "https://cdn-api.co-vin.in/api/v2/appointment/sessions/public/calendarByDistrict"
    r = requests.get(url, params=params, headers=headers)
    data = r.json()

    logger.info(f"district config is {d}", d)
    logger.info(f"{params}")
    logger.info(f"{data}")

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
                slots.get("available_capacity", 0) +
                session["available_capacity"]
            )
            slots["centers"] = slots.get("centers", []) + [center["name"]]

            slots_by_pincode[center["pincode"]] = slots
            slots_by_date_pincode[date] = slots_by_pincode

    # We've built the slots_by_date_pincode map. Now remove all dates with
    # only one slot available to prevent noise
    logger.info(f"Found slots: {slots_by_date_pincode}")
    # return slots_found, slots_by_date_pincode
    dates_to_remove = []
    for date, slots_by_pincode in slots_by_date_pincode.items():
        pincodes = list(slots_by_pincode.keys())
        if len(pincodes) == 1:
            slots = slots_by_pincode[pincodes[0]]
            if slots["available_capacity"] == 1:
                dates_to_remove.append(date)
    for date in dates_to_remove:
        del(slots_by_date_pincode[date])

    logger.info(f"Slots after removing noise: {slots_by_date_pincode}")
    slots_found = True
    if slots_by_date_pincode == {}:
        slots_found = False
    return slots_found, slots_by_date_pincode


# check_availability()
# _________________________________________________________________________________________
def check_availability(config):
    state = config["state"]
    districts = config.get("districts")

    logger.info(f"Checking {state} {districts}")

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
            slots_found, slots_by_date_pincode = check_district(
                d, week, config)
            if slots_found:
                report_availability(slots_by_date_pincode, config)
                return


logger.info("Starting VaxBot")

while True:
    for config in configs:
        try:
            check_availability(config)
        except Exception as e:
            logger.error(
                f"failed with exception {e}, {traceback.format_exc()}")
            time.sleep(120)
            continue

    time.sleep(sleep_between_runs)

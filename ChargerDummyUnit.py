# importing the requests library
import requests
import random
import uuid
from datetime import datetime, timezone
import sched, time
# defining the api-endpoint
API_ENDPOINT = "http://127.0.0.1:5000/api/telemetry"
charger_id = "0646b3a8-8e0d-46fb-bffe-429c31cbf16b"
time_seconds = 5

def generate_and_send_telemetry(charger_id, scheduler):
    scheduler.enter(time_seconds, 1, generate_and_send_telemetry, (charger_id, scheduler))
    # 80% normale målinger
    # 8% overtemperatur
    # 7% ingen strøm
    # 5% ledningsskade
    scenario = random.choices(
        ["normal", "over_temp", "no_power", "cable_defect"],
        weights=[80, 8, 7, 5]
    )[0]

    if scenario == "normal":
        power_kw = round(random.uniform(3.0, 22.0), 2)
        voltage = round(random.uniform(220.0, 240.0), 2)
        current_a = round(random.uniform(10.0, 32.0), 2)
        temperature = round(random.uniform(15.0, 60.0), 2)
        error_code = None

    elif scenario == "over_temp":
        power_kw = round(random.uniform(0.0, 5.0), 2)
        voltage = round(random.uniform(220.0, 240.0), 2)
        current_a = round(random.uniform(0.0, 5.0), 2)
        temperature = round(random.uniform(81.0, 110.0), 2)
        error_code = "OVER_TEMPERATURE"

    elif scenario == "no_power":
        power_kw = 0.0
        voltage = round(random.uniform(0.0, 150.0), 2)
        current_a = 0.0
        temperature = round(random.uniform(15.0, 40.0), 2)
        error_code = "NO_POWER"

    else:  # cable_defect
        power_kw = 0.0
        voltage = round(random.uniform(220.0, 240.0), 2)
        current_a = 0.0
        temperature = round(random.uniform(15.0, 60.0), 2)
        error_code = "CABLE_DEFECT"
    temp_id = str(uuid.uuid4())

    # data to be sent to api
    data = {
        "id": temp_id,
        "charger_id": charger_id,
        "power_kw": power_kw,
        "voltage": voltage,
        "current_a": current_a,
        "temperature": temperature,
        "recorded_at": datetime.now(timezone.utc).isoformat()
    }

    # sending post request and saving response as response object
    r = requests.post(url=API_ENDPOINT, json=data)

    # extracting response text
    pastebin_url = r.text
    print("The pastebin URL is:%s" % pastebin_url)
    print(temp_id)

s = sched.scheduler(time.time, time.sleep)
s.enter(time_seconds, 1, generate_and_send_telemetry, (charger_id, s))
s.run()

import mysql.connector
import os
import uuid
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)
cursor = conn.cursor()

# ---------- LOKATIONER ----------
locations = [
    "København - Rådhuspladsen",
    "København - Nørreport",
    "København - Christianshavn",
    "Aarhus - Banegårdspladsen",
    "Aarhus - Universitetsparken",
    "Odense - Flakhaven",
    "Odense - Rosengårdscentret",
    "Aalborg - Budolfi Plads",
    "Aalborg - Kennedy Arkaden",
    "Esbjerg - Torvet",
    "Roskilde - Stændertorvet",
    "Helsingør - Kulturværftet",
    "Vejle - Spinderihallerne",
    "Horsens - Sundparken",
    "Silkeborg - Papirfabrikken"
]

vendors = ["ABB", "Siemens", "Schneider", "Easee", "Zaptec"]
models = ["Terra 54", "VersiCharge", "EVlink", "Home", "Pro"]
firmwares = ["1.2.3", "2.0.1", "1.5.0", "2.1.0", "3.0.2"]

# ---------- GENERER 1000 LADESTANDERE ----------
print("Genererer 1000 ladestandere...")
charger_ids = []

for i in range(1000):
    charger_id = str(uuid.uuid4())
    charger_ids.append(charger_id)
    location = random.choice(locations)
    vendor = random.choice(vendors)
    model = random.choice(models)
    firmware = random.choice(firmwares)
    status = random.choices(
        ["available", "occupied", "faulted"],
        weights=[70, 20, 10]  # 70% available, 20% occupied, 10% faulted
    )[0]

    cursor.execute(
        """INSERT INTO charger (id, location, vendor, model, firmware, status) 
        VALUES (%s, %s, %s, %s, %s, %s)""",
        (charger_id, location, vendor, model, firmware, status)
    )

conn.commit()
print(f"✅ 1000 ladestandere oprettet")

# ---------- GENERER TELEMETRI DATA ----------
print("Genererer telemetri målinger...")

total_readings = 0
for charger_id in charger_ids:
    # Hver ladestander får 10-20 målinger
    num_readings = random.randint(10, 20)
    
    for j in range(num_readings):
        reading_id = str(uuid.uuid4())
        recorded_at = datetime.now() - timedelta(hours=random.randint(0, 72))

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

        cursor.execute(
            """INSERT INTO telemetry_reading 
            (id, charger_id, power_kw, voltage, current_a, temperature, error_code, recorded_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (reading_id, charger_id, power_kw, voltage, current_a, temperature, error_code, recorded_at)
        )
        total_readings += 1

conn.commit()
print(f"✅ {total_readings} telemetri målinger oprettet")
print(f"✅ Data generering færdig!")

cursor.close()
conn.close()

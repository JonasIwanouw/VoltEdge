import requests
import random
import time

tekniker = "tech-001"

# Hent alle assignments for teknikeren
r_get_assignments = requests.get(f"http://127.0.0.1:5000/api/assignments/{tekniker}")
json_assignments = r_get_assignments.json()

if not json_assignments:
    print("Ingen assignments fundet for tekniker")
else:
    # Vælg en random assignment
    random_assignment = random.choice(json_assignments)
    assignment_id = random_assignment["id"]
    incident_id = random_assignment["incident_id"]

    print(f"Valgt assignment: {assignment_id}")
    print(f"Incident type: {random_assignment['incident_type']}")
    print(f"Lokation: {random_assignment['location']}")

    # Accepter opgaven
    r_respond = requests.put(
        f"http://127.0.0.1:5000/api/assignments/{assignment_id}/respond",
        json={"accept": True}
    )
    print(f"Accepteret: {r_respond.json()}")

    # Vent X sekunder — simulerer at teknikeren kører ud og løser problemet
    ventetid = 10
    print(f"Tekniker er på vej... venter {ventetid} sekunder")
    time.sleep(ventetid)

    # Resolver incident
    r_resolve = requests.put(
        f"http://127.0.0.1:5000/api/incidents/{incident_id}/resolve"
    )
    print(f"Løst: {r_resolve.json()}")
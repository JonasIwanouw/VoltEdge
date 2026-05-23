import requests
import random
import uuid

r_get_incidents = requests.get("http://localhost:5000/api/incidents")
print(r_get_incidents.json())
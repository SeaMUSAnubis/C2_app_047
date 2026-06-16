from fastapi.testclient import TestClient
from src.main import app
from src.api.routes import get_current_account
import json

client = TestClient(app)
app.dependency_overrides[get_current_account] = lambda: {"id": 1, "role": "admin"}

SCENARIOS = [
  {
    "id": 1,
    "user_id": "MOH0273",
    "events": [
      { "event_type": "logon", "timestamp": "2010-05-12T08:15:00Z", "pc": "PC-1234" },
      { "event_type": "email", "timestamp": "2010-05-12T09:30:00Z", "to": "boss@dtaa.com" },
      { "event_type": "http", "timestamp": "2010-05-12T10:00:00Z", "url": "http://news.com" }
    ]
  },
  {
    "id": 2,
    "user_id": "JXD0123",
    "events": [
      { "event_type": "logon", "timestamp": "2010-05-12T23:15:00Z", "pc": "PC-9999" },
      { "event_type": "device", "timestamp": "2010-05-12T23:20:00Z", "activity": "Connect" },
      { "event_type": "http", "timestamp": "2010-05-12T23:25:00Z", "url": "http://wikileaks.org/upload" },
      { "event_type": "file", "timestamp": "2010-05-12T23:30:00Z", "filename": "confidential.zip" }
    ]
  },
  {
    "id": 3,
    "user_id": "HSB0196",
    "events": [
      { "event_type": "logon", "timestamp": "2010-01-02T09:00:00Z", "pc": "PC-8001" },
      { "event_type": "file", "timestamp": "2010-01-02T09:49:30Z", "filename": "RJGC8XX5.exe" }
    ]
  },
  {
    "id": 4,
    "user_id": "ABC0999",
    "events": [
      { "event_type": "http", "timestamp": "2010-08-15T14:00:00Z", "url": "http://indeed.com/jobs" },
      { "event_type": "http", "timestamp": "2010-08-15T14:10:00Z", "url": "http://monster.com" },
      { "event_type": "device", "timestamp": "2010-08-15T16:00:00Z", "activity": "Connect" },
      { "event_type": "file", "timestamp": "2010-08-15T16:05:00Z", "filename": "source_code.zip" }
    ]
  },
  {
    "id": 5,
    "user_id": "ITAdmin01",
    "events": [
      { "event_type": "http", "timestamp": "2011-02-10T11:00:00Z", "url": "http://hacker-tools.com/keylog.exe" },
      { "event_type": "file", "timestamp": "2011-02-10T11:05:00Z", "filename": "keylogger.exe" },
      { "event_type": "device", "timestamp": "2011-02-10T11:10:00Z", "activity": "Connect" }
    ]
  }
]

for s in SCENARIOS:
    print(f"--- SCENARIO {s['id']} ---")
    response = client.post(
        "/api/demo/analyze",
        json={"user_id": s["user_id"], "events": s["events"]}
    )
    print("Status:", response.status_code)
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)

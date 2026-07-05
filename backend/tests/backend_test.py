"""Backend tests for Ajay Haircut barber shop."""
import os
from datetime import datetime, timedelta
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fade-master-49.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def future_date(days=5):
    return (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# Health / root
class TestHealth:
    def test_root(self, session):
        r = session.get(f"{API}/")
        assert r.status_code == 200
        assert "Ajay Haircut" in r.json().get("message", "")


# Availability endpoint
class TestAvailability:
    def test_availability_returns_11_slots(self, session):
        d = future_date(3)
        r = session.get(f"{API}/bookings/availability", params={"date": d})
        assert r.status_code == 200
        data = r.json()
        assert data["date"] == d
        assert isinstance(data["slots"], list)
        assert len(data["slots"]) == 11
        for slot in data["slots"]:
            assert "time" in slot and "available" in slot


# Booking creation + persistence + availability update
class TestBookings:
    def test_create_and_reflect_in_availability_and_list(self, session):
        d = future_date(7)
        time_slot = "11:00 AM"

        # Pre-check: slot available
        avail = session.get(f"{API}/bookings/availability", params={"date": d}).json()
        pre_slot = next(s for s in avail["slots"] if s["time"] == time_slot)
        assert pre_slot["available"] is True

        payload = {
            "service": "Skin Fades",
            "date": d,
            "time": time_slot,
            "name": "TEST_User Booking",
            "email": "delivered@resend.dev",
            "phone": "+17783442550",
            "notes": "TEST booking",
        }
        r = session.post(f"{API}/bookings", json=payload)
        assert r.status_code == 200, f"Create booking failed: {r.status_code} {r.text}"
        booking = r.json()
        assert "id" in booking and isinstance(booking["id"], str) and len(booking["id"]) > 0
        assert booking["status"] == "confirmed"
        assert booking["service"] == payload["service"]
        assert booking["date"] == payload["date"]
        assert booking["time"] == payload["time"]
        assert booking["email"] == payload["email"]

        # Availability should show that slot as unavailable now
        avail2 = session.get(f"{API}/bookings/availability", params={"date": d}).json()
        post_slot = next(s for s in avail2["slots"] if s["time"] == time_slot)
        assert post_slot["available"] is False, "Slot should be marked unavailable after booking"

        # GET /api/bookings should include this booking
        listing = session.get(f"{API}/bookings")
        assert listing.status_code == 200
        bookings = listing.json()
        assert isinstance(bookings, list)
        assert any(b["id"] == booking["id"] for b in bookings)

    def test_invalid_email_rejected(self, session):
        payload = {
            "service": "Skin Fades",
            "date": future_date(2),
            "time": "10:00 AM",
            "name": "TEST_BadEmail",
            "email": "not-an-email",
            "phone": "+17783442550",
        }
        r = session.post(f"{API}/bookings", json=payload)
        assert r.status_code == 422


# Contact endpoint
class TestContact:
    def test_contact_ok(self, session):
        payload = {
            "name": "TEST_Contact",
            "email": "delivered@resend.dev",
            "message": "Hello from tests",
        }
        r = session.post(f"{API}/contact", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        assert "message" in data

    def test_contact_invalid_email(self, session):
        r = session.post(f"{API}/contact", json={
            "name": "TEST_Bad",
            "email": "bad",
            "message": "hi",
        })
        assert r.status_code == 422

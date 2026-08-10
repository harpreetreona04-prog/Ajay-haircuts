"""Backend tests for Ajay Haircut barber shop."""
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fade-master-49.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
BUSINESS_TZ = ZoneInfo("America/Vancouver")


def future_date(days=5):
    d = datetime.utcnow() + timedelta(days=days)
    # skip Tuesdays (closed) so booking succeeds
    while d.weekday() == 1:
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")


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
    def test_availability_default_duration(self, session):
        d = future_date(3)
        r = session.get(f"{API}/bookings/availability", params={"date": d})
        assert r.status_code == 200
        data = r.json()
        assert data["date"] == d
        assert isinstance(data["slots"], list)
        assert len(data["slots"]) > 0
        for slot in data["slots"]:
            assert "time" in slot and "available" in slot

    def test_longer_service_has_fewer_slots(self, session):
        # A 45-min service (Haircut & Beard) must finish by closing time,
        # so it has fewer possible start times than a 30-min service.
        d = future_date(4)
        short = session.get(f"{API}/bookings/availability", params={"date": d, "service": "Skin Fades"}).json()
        longer = session.get(f"{API}/bookings/availability", params={"date": d, "service": "Haircut & Beard"}).json()
        assert len(longer["slots"]) < len(short["slots"])

    def test_todays_past_slots_are_unavailable(self, session):
        today = datetime.now(BUSINESS_TZ).strftime("%Y-%m-%d")
        if datetime.now(BUSINESS_TZ).weekday() == 1:
            pytest.skip("Shop is closed today (Tuesday); nothing meaningful to assert.")
        avail = session.get(f"{API}/bookings/availability", params={"date": today, "service": "Skin Fades"}).json()
        if avail.get("closed"):
            pytest.skip("Shop reported closed for today.")
        now_clock = datetime.now(BUSINESS_TZ)
        for slot in avail["slots"]:
            slot_dt = datetime.strptime(slot["time"], "%I:%M %p").replace(
                year=now_clock.year, month=now_clock.month, day=now_clock.day, tzinfo=BUSINESS_TZ
            )
            if slot_dt <= now_clock:
                assert slot["available"] is False, f"{slot['time']} is in the past but marked available"

    def test_cannot_book_a_past_time_today(self, session):
        now = datetime.now(BUSINESS_TZ)
        if now.weekday() == 1:
            pytest.skip("Shop is closed today (Tuesday).")
        past_time = (now - timedelta(hours=2)).strftime("%I:%M %p")
        payload = {
            "service": "Skin Fades",
            "date": now.strftime("%Y-%m-%d"),
            "time": past_time,
            "name": "TEST_PastTime",
            "email": "delivered@resend.dev",
            "phone": "+17783442550",
        }
        r = session.post(f"{API}/bookings", json=payload)
        assert r.status_code == 400

    def test_booking_blocks_overlapping_slots_not_just_exact_match(self, session):
        # Book a 45-min "Haircut & Beard" at 10:00 AM -> occupies 10:00-10:45.
        # A 30-min service slot at 10:15 or 10:30 should now be blocked even
        # though neither matches the booked start time exactly.
        d = future_date(20)
        payload = {
            "service": "Haircut & Beard",
            "date": d,
            "time": "10:00 AM",
            "name": "TEST_Overlap Booking",
            "email": "delivered@resend.dev",
            "phone": "+17783442550",
        }
        r = session.post(f"{API}/bookings", json=payload)
        assert r.status_code == 200, r.text

        avail = session.get(f"{API}/bookings/availability", params={"date": d, "service": "Skin Fades"}).json()
        by_time = {s["time"]: s["available"] for s in avail["slots"]}
        assert by_time.get("10:00 AM") is False
        assert by_time.get("10:15 AM") is False  # overlaps 10:00-10:45
        assert by_time.get("10:30 AM") is False  # overlaps 10:00-10:45
        assert by_time.get("09:30 AM") is True   # finishes by 10:00, no overlap
        assert by_time.get("10:45 AM") is True   # starts right when the booking ends


# Booking creation + persistence + availability update
class TestBookings:
    def test_create_and_reflect_in_availability_and_list(self, session):
        d = future_date(45)
        time_slot = "04:00 PM"

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

    def test_overlapping_booking_rejected_with_409(self, session):
        d = future_date(21)
        payload = {
            "service": "Haircut & Beard",
            "date": d,
            "time": "02:00 PM",
            "name": "TEST_Conflict A",
            "email": "delivered@resend.dev",
            "phone": "+17783442550",
        }
        r1 = session.post(f"{API}/bookings", json=payload)
        assert r1.status_code == 200

        conflicting = dict(payload, time="02:15 PM", name="TEST_Conflict B")
        r2 = session.post(f"{API}/bookings", json=conflicting)
        assert r2.status_code == 409


# Admin endpoints — walk-in bookings, blocking, editing, cancel/unblock
class TestAdminBookings:
    def test_admin_create_walkin_booking(self, session):
        d = future_date(22)
        payload = {
            "service": "Skin Fades",
            "date": d,
            "time": "11:00 AM",
            "name": "TEST_Walkin Customer",
            "phone": "+17783442550",
        }
        r = session.post(f"{API}/admin/bookings", json=payload)
        assert r.status_code == 200, r.text
        booking = r.json()
        assert booking["status"] == "confirmed"
        assert booking["duration_minutes"] == 30

    def test_admin_block_time_with_custom_duration(self, session):
        d = future_date(23)
        payload = {
            "date": d,
            "time": "03:00 PM",
            "duration_minutes": 60,
            "name": "Lunch break",
            "is_block": True,
        }
        r = session.post(f"{API}/admin/bookings", json=payload)
        assert r.status_code == 200, r.text
        booking = r.json()
        assert booking["status"] == "blocked"
        assert booking["duration_minutes"] == 60

        # A 30-min slot inside the block (e.g. 3:15) should now be unavailable
        avail = session.get(f"{API}/bookings/availability", params={"date": d, "service": "Skin Fades"}).json()
        by_time = {s["time"]: s["available"] for s in avail["slots"]}
        assert by_time.get("03:15 PM") is False

    def test_admin_edit_booking_reschedules_it(self, session):
        d = future_date(24)
        create = session.post(f"{API}/admin/bookings", json={
            "service": "Skin Fades",
            "date": d,
            "time": "09:00 AM",
            "name": "TEST_Reschedule Me",
        })
        assert create.status_code == 200
        booking_id = create.json()["id"]

        edit = session.patch(f"{API}/admin/bookings/{booking_id}", json={"time": "10:00 AM"})
        assert edit.status_code == 200, edit.text
        assert edit.json()["time"] == "10:00 AM"

    def test_admin_cancel_booking(self, session):
        d = future_date(25)
        create = session.post(f"{API}/admin/bookings", json={
            "service": "Skin Fades",
            "date": d,
            "time": "01:00 PM",
            "name": "TEST_Cancel Me",
        })
        booking_id = create.json()["id"]

        delete = session.delete(f"{API}/admin/bookings/{booking_id}")
        assert delete.status_code == 200
        assert delete.json()["action"] == "cancelled"

        # Soft-cancel: the booking still exists in the listing...
        listing = session.get(f"{API}/bookings").json()
        cancelled_entry = next((b for b in listing if b["id"] == booking_id), None)
        assert cancelled_entry is not None
        assert cancelled_entry["status"] == "cancelled"

        # ...but its slot is freed up for someone else to book.
        avail = session.get(f"{API}/bookings/availability", params={"date": d, "service": "Skin Fades"}).json()
        by_time = {s["time"]: s["available"] for s in avail["slots"]}
        assert by_time.get("01:00 PM") is True

    def test_admin_unblock_removes_block_entirely(self, session):
        d = future_date(26)
        create = session.post(f"{API}/admin/bookings", json={
            "date": d,
            "time": "04:00 PM",
            "name": "Break",
            "is_block": True,
        })
        block_id = create.json()["id"]

        delete = session.delete(f"{API}/admin/bookings/{block_id}")
        assert delete.status_code == 200
        assert delete.json()["action"] == "unblocked"

        listing = session.get(f"{API}/bookings").json()
        assert not any(b["id"] == block_id for b in listing)


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

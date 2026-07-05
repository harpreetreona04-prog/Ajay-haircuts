"""Backend tests for Stripe deposit checkout flow."""
import os
from datetime import datetime, timedelta
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


def _future_non_tuesday(days=3):
    d = datetime.utcnow() + timedelta(days=days)
    # weekday(): Mon=0, Tue=1
    while d.weekday() == 1:
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def _next_tuesday():
    d = datetime.utcnow()
    while d.weekday() != 1:
        d += timedelta(days=1)
    # ensure future
    if d.date() <= datetime.utcnow().date():
        d += timedelta(days=7)
    return d.strftime("%Y-%m-%d")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _booking_payload(date, time_slot, email="TEST_deposit@resend.dev"):
    return {
        "origin_url": BASE_URL,
        "booking": {
            "service": "Skin Fades",
            "date": date,
            "time": time_slot,
            "name": "TEST_Deposit Buyer",
            "email": email,
            "phone": "+17783442550",
            "notes": "TEST deposit checkout",
        },
    }


# --- Checkout session creation ---
class TestCheckoutCreation:
    def test_checkout_returns_url_and_session_id(self, session):
        date = _future_non_tuesday(4)
        payload = _booking_payload(date, "09:00 AM")
        r = session.post(f"{API}/bookings/checkout", json=payload)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert "url" in data and data["url"].startswith("https://")
        assert "checkout.stripe.com" in data["url"]
        assert "session_id" in data and isinstance(data["session_id"], str) and len(data["session_id"]) > 0

        # No booking created yet (unpaid)
        listing = session.get(f"{API}/bookings").json()
        assert not any(b["date"] == date and b["time"] == "09:00 AM" and b["name"] == "TEST_Deposit Buyer"
                       for b in listing), "Booking must not exist before payment"

        # Status endpoint returns unpaid + no booking
        s_id = data["session_id"]
        st = session.get(f"{API}/payments/checkout/status/{s_id}")
        assert st.status_code == 200
        sd = st.json()
        assert sd["payment_status"] in ("unpaid", "no_payment_required")
        assert sd["booking"] is None
        assert sd["amount_total"] == 1200
        assert sd["currency"] == "cad"

    def test_checkout_tuesday_rejected(self, session):
        date = _next_tuesday()
        payload = _booking_payload(date, "10:00 AM")
        r = session.post(f"{API}/bookings/checkout", json=payload)
        assert r.status_code == 400
        assert "tuesday" in r.json().get("detail", "").lower()

    def test_checkout_conflict_when_slot_taken(self, session):
        # Book a slot directly via /bookings (bypasses payment for test setup)
        date = _future_non_tuesday(10)
        time_slot = "07:00 PM"
        pre = session.post(f"{API}/bookings", json={
            "service": "Skin Fades", "date": date, "time": time_slot,
            "name": "TEST_Blocker", "email": "delivered@resend.dev",
            "phone": "+1", "notes": "TEST",
        })
        assert pre.status_code == 200

        # Now try to checkout the same date/time
        r = session.post(f"{API}/bookings/checkout", json=_booking_payload(date, time_slot))
        assert r.status_code == 409
        assert "just booked" in r.json().get("detail", "").lower() or "booked" in r.json().get("detail", "").lower()

    def test_checkout_invalid_time_slot(self, session):
        date = _future_non_tuesday(6)
        r = session.post(f"{API}/bookings/checkout", json=_booking_payload(date, "13:00 XX"))
        assert r.status_code == 400


# --- Status polling & idempotency (unpaid session) ---
class TestCheckoutStatus:
    def test_status_multiple_polls_no_duplicate_bookings(self, session):
        date = _future_non_tuesday(8)
        time_slot = "08:00 PM"
        r = session.post(f"{API}/bookings/checkout", json=_booking_payload(date, time_slot))
        assert r.status_code == 200
        s_id = r.json()["session_id"]

        # Poll status 3 times; all should be unpaid + no booking, no dup created
        for _ in range(3):
            st = session.get(f"{API}/payments/checkout/status/{s_id}").json()
            assert st["payment_status"] in ("unpaid", "no_payment_required")
            assert st["booking"] is None

        listing = session.get(f"{API}/bookings").json()
        matches = [b for b in listing if b["date"] == date and b["time"] == time_slot]
        assert len(matches) == 0, "No booking should exist for an unpaid session"


# --- Regression: non-payment endpoints still work ---
class TestRegression:
    def test_root(self, session):
        r = session.get(f"{API}/")
        assert r.status_code == 200
        assert "Ajay Haircut" in r.json().get("message", "")

    def test_availability_and_direct_booking(self, session):
        d = _future_non_tuesday(12)
        av = session.get(f"{API}/bookings/availability", params={"date": d}).json()
        assert av["closed"] is False and len(av["slots"]) == 12

    def test_contact_ok(self, session):
        r = session.post(f"{API}/contact", json={
            "name": "TEST_ContactDep", "email": "delivered@resend.dev", "message": "hi"
        })
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

from fastapi import FastAPI, APIRouter, HTTPException, Header
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timedelta, timezone
import resend

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
OWNER_EMAIL = os.environ.get('OWNER_EMAIL')
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

# Optional shared secret for admin-only endpoints. If unset, admin endpoints
# are open (fine for local testing, not recommended for production) — set
# this in the backend .env and send the same value from the admin dashboard
# as the X-Admin-Key header.
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY')


def _require_admin(x_admin_key: Optional[str]):
    if ADMIN_API_KEY and x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


BUSINESS = {
    "name": "Ajay Haircut",
    "phone": "(778) 344-2550",
    "location": "Surrey, BC, Canada",
}

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Business hours: first appointment can start at OPEN_TIME; every appointment
# must finish by CLOSE_TIME.
OPEN_TIME = "09:00 AM"
CLOSE_TIME = "09:00 PM"
SLOT_INTERVAL_MINUTES = 15  # spacing between selectable start times

# Duration (in minutes) per service. Anything not listed falls back to
# DEFAULT_DURATION_MINUTES.
SERVICE_DURATIONS = {
    "Haircut & Beard": 45,
}
DEFAULT_DURATION_MINUTES = 30
WALKIN_SERVICE = "Phone / Walk-in"


class BookingCreate(BaseModel):
    service: str
    date: str
    time: str
    name: str
    email: EmailStr
    phone: str
    notes: Optional[str] = ""


class Booking(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    date: str
    time: str
    name: str
    email: EmailStr
    phone: str
    notes: Optional[str] = ""
    duration_minutes: int = DEFAULT_DURATION_MINUTES
    status: str = "confirmed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContactCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = ""
    message: str


class AdminBookingCreate(BaseModel):
    """Used by the owner dashboard to add a phone/walk-in booking, or to
    block off time with no customer attached (is_block=True).
    duration_minutes overrides the service-based lookup when set, which lets
    the owner block an arbitrary-length window."""
    service: str = WALKIN_SERVICE
    date: str
    time: str
    duration_minutes: Optional[int] = None
    name: str
    phone: Optional[str] = "N/A"
    email: Optional[EmailStr] = None
    notes: Optional[str] = ""
    is_block: bool = False


class AdminBookingUpdate(BaseModel):
    """All fields optional — only send what you want to change."""
    service: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    duration_minutes: Optional[int] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


def _duration_for_service(service: str) -> int:
    return SERVICE_DURATIONS.get(service, DEFAULT_DURATION_MINUTES)


def _is_tuesday(date: str) -> bool:
    try:
        return datetime.strptime(date, "%Y-%m-%d").weekday() == 1
    except ValueError:
        return False


def _parse_clock(t: str) -> datetime:
    # Parsed onto an arbitrary fixed date so we can do arithmetic/comparisons
    # on time-of-day only.
    return datetime.strptime(t, "%I:%M %p")


def _format_clock(dt: datetime) -> str:
    return dt.strftime("%I:%M %p")


def _generate_slot_times(duration_minutes: int) -> List[str]:
    """All possible start times for a service of this length that still
    finish by closing time."""
    cur = _parse_clock(OPEN_TIME)
    close = _parse_clock(CLOSE_TIME)
    slots = []
    while cur + timedelta(minutes=duration_minutes) <= close:
        slots.append(_format_clock(cur))
        cur += timedelta(minutes=SLOT_INTERVAL_MINUTES)
    return slots


def _ranges_overlap(start_a: datetime, duration_a: int, start_b: datetime, duration_b: int) -> bool:
    end_a = start_a + timedelta(minutes=duration_a)
    end_b = start_b + timedelta(minutes=duration_b)
    return start_a < end_b and start_b < end_a


async def _booked_intervals(date: str, exclude_id: Optional[str] = None):
    """Return [(start_datetime, duration_minutes), ...] for every existing
    booking on this date, optionally excluding one booking by id (used when
    editing that booking so it doesn't block its own current slot)."""
    query = {"date": date}
    if exclude_id:
        query["id"] = {"$ne": exclude_id}
    docs = await db.bookings.find(
        query, {"_id": 0, "time": 1, "service": 1, "duration_minutes": 1}
    ).to_list(1000)
    intervals = []
    for d in docs:
        start = _parse_clock(d["time"])
        duration = d.get("duration_minutes") or _duration_for_service(d.get("service", ""))
        intervals.append((start, duration))
    return intervals


def _confirmation_html(b: Booking) -> str:
    return f"""
    <div style="font-family: Arial, Helvetica, sans-serif; background:#FAFAFA; padding:32px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #E5E7EB;">
        <tr><td style="background:#111827;padding:28px 32px;">
          <span style="color:#C5A059;font-size:22px;font-weight:700;letter-spacing:1px;">AJAY HAIRCUT</span>
          <div style="color:#9CA3AF;font-size:12px;letter-spacing:3px;margin-top:4px;">SURREY, BC</div>
        </td></tr>
        <tr><td style="padding:32px;">
          <h1 style="color:#111827;font-size:24px;margin:0 0 8px;">Booking Confirmed</h1>
          <p style="color:#4B5563;font-size:15px;margin:0 0 24px;">Hi {b.name}, your appointment is booked. We look forward to seeing you.</p>
          <table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #E5E7EB;">
            <tr><td style="padding:14px 0;color:#6B7280;font-size:13px;text-transform:uppercase;letter-spacing:1px;">Service</td><td style="padding:14px 0;color:#111827;font-size:15px;font-weight:600;text-align:right;">{b.service}</td></tr>
            <tr><td style="padding:14px 0;border-top:1px solid #F3F4F6;color:#6B7280;font-size:13px;text-transform:uppercase;letter-spacing:1px;">Date</td><td style="padding:14px 0;border-top:1px solid #F3F4F6;color:#111827;font-size:15px;font-weight:600;text-align:right;">{b.date}</td></tr>
            <tr><td style="padding:14px 0;border-top:1px solid #F3F4F6;color:#6B7280;font-size:13px;text-transform:uppercase;letter-spacing:1px;">Time</td><td style="padding:14px 0;border-top:1px solid #F3F4F6;color:#111827;font-size:15px;font-weight:600;text-align:right;">{b.time}</td></tr>
          </table>
          <div style="margin-top:28px;padding:20px;background:#FAFAFA;border:1px solid #E5E7EB;">
            <p style="margin:0;color:#111827;font-size:14px;"><strong>{BUSINESS['name']}</strong></p>
            <p style="margin:6px 0 0;color:#4B5563;font-size:14px;">{BUSINESS['location']}</p>
            <p style="margin:6px 0 0;color:#C5A059;font-size:14px;font-weight:600;">{BUSINESS['phone']}</p>
          </div>
          <p style="color:#9CA3AF;font-size:12px;margin-top:24px;">Need to reschedule? Call us at {BUSINESS['phone']}.</p>
        </td></tr>
      </table>
    </div>
    """


def _owner_html(b: Booking) -> str:
    notes_block = f'<div style="margin-top:20px;padding:16px;background:#FAFAFA;border:1px solid #E5E7EB;color:#4B5563;font-size:14px;"><strong>Notes:</strong> {b.notes}</div>' if b.notes else ''
    return f"""
    <div style="font-family: Arial, Helvetica, sans-serif; background:#FAFAFA; padding:32px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #E5E7EB;">
        <tr><td style="background:#111827;padding:24px 32px;">
          <span style="color:#C5A059;font-size:13px;letter-spacing:2px;text-transform:uppercase;font-weight:700;">New Appointment</span>
          <h1 style="color:#ffffff;font-size:22px;margin:6px 0 0;">You have a new booking</h1>
        </td></tr>
        <tr><td style="padding:32px;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr><td style="padding:12px 0;color:#6B7280;font-size:13px;">Service</td><td style="padding:12px 0;color:#111827;font-size:15px;font-weight:600;text-align:right;">{b.service}</td></tr>
            <tr><td style="padding:12px 0;border-top:1px solid #F3F4F6;color:#6B7280;font-size:13px;">Date</td><td style="padding:12px 0;border-top:1px solid #F3F4F6;color:#111827;font-size:15px;font-weight:600;text-align:right;">{b.date}</td></tr>
            <tr><td style="padding:12px 0;border-top:1px solid #F3F4F6;color:#6B7280;font-size:13px;">Time</td><td style="padding:12px 0;border-top:1px solid #F3F4F6;color:#111827;font-size:15px;font-weight:600;text-align:right;">{b.time}</td></tr>
            <tr><td style="padding:12px 0;border-top:1px solid #F3F4F6;color:#6B7280;font-size:13px;">Customer</td><td style="padding:12px 0;border-top:1px solid #F3F4F6;color:#111827;font-size:15px;font-weight:600;text-align:right;">{b.name}</td></tr>
            <tr><td style="padding:12px 0;border-top:1px solid #F3F4F6;color:#6B7280;font-size:13px;">Phone</td><td style="padding:12px 0;border-top:1px solid #F3F4F6;color:#111827;font-size:15px;font-weight:600;text-align:right;"><a href="tel:{b.phone}" style="color:#C5A059;text-decoration:none;">{b.phone}</a></td></tr>
            <tr><td style="padding:12px 0;border-top:1px solid #F3F4F6;color:#6B7280;font-size:13px;">Email</td><td style="padding:12px 0;border-top:1px solid #F3F4F6;color:#111827;font-size:15px;font-weight:600;text-align:right;">{b.email}</td></tr>
          </table>
          {notes_block}
        </td></tr>
      </table>
    </div>
    """


async def _send_confirmation(b: Booking):
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set; skipping email")
        return
    params = {
        "from": f"Ajay Haircut <{SENDER_EMAIL}>",
        "to": [b.email],
        "subject": f"Your booking is confirmed — {b.date} at {b.time}",
        "html": _confirmation_html(b),
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Confirmation email sent to {b.email}")
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {e}")

    if OWNER_EMAIL:
        owner_params = {
            "from": f"Ajay Haircut Bookings <{SENDER_EMAIL}>",
            "to": [OWNER_EMAIL],
            "subject": f"New Booking: {b.service} — {b.date} {b.time}",
            "html": _owner_html(b),
        }
        try:
            await asyncio.to_thread(resend.Emails.send, owner_params)
            logger.info(f"Owner notification sent to {OWNER_EMAIL}")
        except Exception as e:
            logger.error(f"Failed to send owner notification: {e}")


@api_router.get("/")
async def root():
    return {"message": "Ajay Haircut API"}


@api_router.post("/bookings", response_model=Booking)
async def create_booking(payload: BookingCreate):
    if _is_tuesday(payload.date):
        raise HTTPException(status_code=400, detail="We are closed on Tuesdays. Please choose another day.")

    duration = _duration_for_service(payload.service)
    try:
        new_start = _parse_clock(payload.time)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format.")

    existing = await _booked_intervals(payload.date)
    if any(_ranges_overlap(new_start, duration, b_start, b_dur) for b_start, b_dur in existing):
        raise HTTPException(status_code=409, detail="That time is no longer available. Please choose another slot.")

    booking = Booking(**payload.model_dump(), duration_minutes=duration)
    doc = booking.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.bookings.insert_one(doc)
    asyncio.create_task(_send_confirmation(booking))
    return booking


@api_router.get("/bookings", response_model=List[Booking])
async def list_bookings(date: Optional[str] = None):
    query = {"date": date} if date else {}
    docs = await db.bookings.find(query, {"_id": 0}).sort([("date", 1), ("time", 1)]).to_list(1000)
    for d in docs:
        if isinstance(d.get('created_at'), str):
            d['created_at'] = datetime.fromisoformat(d['created_at'])
    return docs


@api_router.get("/bookings/availability")
async def availability(date: str, service: Optional[str] = None, ignore_closed: bool = False, exclude_id: Optional[str] = None):
    duration = _duration_for_service(service) if service else DEFAULT_DURATION_MINUTES
    candidate_times = _generate_slot_times(duration)

    if _is_tuesday(date) and not ignore_closed:
        return {"date": date, "closed": True, "slots": [{"time": s, "available": False} for s in candidate_times]}

    booked = await _booked_intervals(date, exclude_id=exclude_id)
    slots = []
    for s in candidate_times:
        s_start = _parse_clock(s)
        available = not any(_ranges_overlap(s_start, duration, b_start, b_dur) for b_start, b_dur in booked)
        slots.append({"time": s, "available": available})

    return {"date": date, "closed": False, "slots": slots}


@api_router.post("/admin/bookings", response_model=Booking)
async def admin_create_booking(payload: AdminBookingCreate, x_admin_key: Optional[str] = Header(None)):
    """Owner-only: add a phone/walk-in booking, or block off time with no
    customer attached (is_block=True). Ignores the Tuesday-closed rule since
    the owner may legitimately want to note something on a closed day."""
    _require_admin(x_admin_key)

    duration = payload.duration_minutes or _duration_for_service(payload.service)
    try:
        new_start = _parse_clock(payload.time)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format.")

    existing = await _booked_intervals(payload.date)
    if any(_ranges_overlap(new_start, duration, b_start, b_dur) for b_start, b_dur in existing):
        raise HTTPException(status_code=409, detail="That time overlaps an existing booking.")

    booking = Booking(
        service=payload.service,
        date=payload.date,
        time=payload.time,
        name=payload.name,
        email=payload.email or "owner@ajayhaircut.com",
        phone=payload.phone or "N/A",
        notes=payload.notes or "",
        duration_minutes=duration,
        status="blocked" if payload.is_block else "confirmed",
    )
    doc = booking.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.bookings.insert_one(doc)
    if not payload.is_block:
        asyncio.create_task(_send_confirmation(booking))
    return booking


@api_router.patch("/admin/bookings/{booking_id}", response_model=Booking)
async def admin_update_booking(booking_id: str, payload: AdminBookingUpdate, x_admin_key: Optional[str] = Header(None)):
    """Owner-only: edit, reschedule, cancel-and-rebook, or convert a booking
    to/from a block."""
    _require_admin(x_admin_key)

    existing_doc = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not existing_doc:
        raise HTTPException(status_code=404, detail="Booking not found.")

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    merged = {**existing_doc, **updates}

    if payload.duration_minutes is not None:
        new_duration = payload.duration_minutes
    elif payload.service is not None:
        new_duration = _duration_for_service(payload.service)
    else:
        new_duration = existing_doc.get('duration_minutes') or _duration_for_service(existing_doc.get('service', ''))

    try:
        new_start = _parse_clock(merged['time'])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format.")

    others_docs = await db.bookings.find(
        {"date": merged['date'], "id": {"$ne": booking_id}},
        {"_id": 0, "time": 1, "service": 1, "duration_minutes": 1},
    ).to_list(1000)
    other_intervals = [
        (_parse_clock(o['time']), o.get('duration_minutes') or _duration_for_service(o.get('service', '')))
        for o in others_docs
    ]
    if any(_ranges_overlap(new_start, new_duration, s, d) for s, d in other_intervals):
        raise HTTPException(status_code=409, detail="That time overlaps another booking.")

    merged['duration_minutes'] = new_duration
    merged.pop('_id', None)
    await db.bookings.update_one({"id": booking_id}, {"$set": merged})

    if isinstance(merged.get('created_at'), str):
        merged['created_at'] = datetime.fromisoformat(merged['created_at'])
    return Booking(**merged)


@api_router.delete("/admin/bookings/{booking_id}")
async def admin_delete_booking(booking_id: str, x_admin_key: Optional[str] = Header(None)):
    """Owner-only: cancel a customer booking, or unblock a previously
    blocked time slot — both are just row deletions."""
    _require_admin(x_admin_key)
    result = await db.bookings.delete_one({"id": booking_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Booking not found.")
    return {"status": "ok"}


@api_router.post("/contact")
async def contact(payload: ContactCreate):
    doc = payload.model_dump()
    doc['id'] = str(uuid.uuid4())
    doc['created_at'] = datetime.now(timezone.utc).isoformat()
    await db.contacts.insert_one(doc)
    return {"status": "ok", "message": "Thanks for reaching out. We'll be in touch soon."}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

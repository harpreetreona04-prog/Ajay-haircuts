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
from zoneinfo import ZoneInfo
import resend

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
OWNER_EMAIL = os.environ.get('OWNER_EMAIL')
# Supports one or more addresses in OWNER_EMAIL, comma-separated, e.g.
# OWNER_EMAIL=ajay@example.com,harpreetreona04@gmail.com,other@example.com
OWNER_EMAILS = [e.strip() for e in OWNER_EMAIL.split(',')] if OWNER_EMAIL else []
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
    "location": "Unit 102, 9385 120 St, Surrey, BC",
}

# Surrey, BC is in the Pacific timezone. Used so "is this slot already in
# the past?" is judged by the shop's local clock, not the server's.
BUSINESS_TZ = ZoneInfo("America/Vancouver")


def _now_local() -> datetime:
    return datetime.now(BUSINESS_TZ)


def _today_str() -> str:
    return _now_local().strftime("%Y-%m-%d")

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Business hours: first appointment can start at OPEN_TIME; every appointment
# must finish by CLOSE_TIME. This is what customers see on the public site.
OPEN_TIME = "09:00 AM"
CLOSE_TIME = "09:00 PM"
SLOT_INTERVAL_MINUTES = 15  # spacing between selectable start times

# The owner can log an earlier walk-in/phone appointment (e.g. someone asks
# for 7 or 8 AM) directly in the admin dashboard, without that early slot
# ever being offered to customers on the public booking page.
ADMIN_OPEN_TIME = os.environ.get("ADMIN_OPEN_TIME", "07:00 AM")

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


class ClosedDateCreate(BaseModel):
    date: str
    reason: Optional[str] = ""


def _duration_for_service(service: str) -> int:
    return SERVICE_DURATIONS.get(service, DEFAULT_DURATION_MINUTES)


def _is_tuesday(date: str) -> bool:
    try:
        return datetime.strptime(date, "%Y-%m-%d").weekday() == 1
    except ValueError:
        return False


async def _closed_date_doc(date: str):
    """Returns the closure document for this date if the owner has manually
    blocked the whole day off (e.g. shop closed for a trip), else None."""
    return await db.closed_dates.find_one({"date": date}, {"_id": 0})


def _parse_clock(t: str) -> datetime:
    # Parsed onto an arbitrary fixed date so we can do arithmetic/comparisons
    # on time-of-day only.
    return datetime.strptime(t, "%I:%M %p")


def _format_clock(dt: datetime) -> str:
    return dt.strftime("%I:%M %p")


def _generate_slot_times(duration_minutes: int, open_time: str = OPEN_TIME) -> List[str]:
    """All possible start times for a service of this length that still
    finish by closing time."""
    cur = _parse_clock(open_time)
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
    """Return [(start_datetime, duration_minutes), ...] for every ACTIVE
    booking on this date (cancelled bookings don't occupy the slot anymore),
    optionally excluding one booking by id (used when editing that booking
    so it doesn't block its own current slot)."""
    query = {"date": date, "status": {"$ne": "cancelled"}}
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


def _rescheduled_html(b: Booking) -> str:
    return f"""
    <div style="font-family: Arial, Helvetica, sans-serif; background:#FAFAFA; padding:32px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #E5E7EB;">
        <tr><td style="background:#111827;padding:28px 32px;">
          <span style="color:#C5A059;font-size:22px;font-weight:700;letter-spacing:1px;">AJAY HAIRCUT</span>
          <div style="color:#9CA3AF;font-size:12px;letter-spacing:3px;margin-top:4px;">SURREY, BC</div>
        </td></tr>
        <tr><td style="padding:32px;">
          <h1 style="color:#111827;font-size:24px;margin:0 0 8px;">Booking Updated</h1>
          <p style="color:#4B5563;font-size:15px;margin:0 0 24px;">Hi {b.name}, your appointment details have changed. Here's your updated booking:</p>
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
          <p style="color:#9CA3AF;font-size:12px;margin-top:24px;">Questions? Call us at {BUSINESS['phone']}.</p>
        </td></tr>
      </table>
    </div>
    """


def _cancellation_html(b: Booking) -> str:
    return f"""
    <div style="font-family: Arial, Helvetica, sans-serif; background:#FAFAFA; padding:32px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #E5E7EB;">
        <tr><td style="background:#111827;padding:28px 32px;">
          <span style="color:#C5A059;font-size:22px;font-weight:700;letter-spacing:1px;">AJAY HAIRCUT</span>
          <div style="color:#9CA3AF;font-size:12px;letter-spacing:3px;margin-top:4px;">SURREY, BC</div>
        </td></tr>
        <tr><td style="padding:32px;">
          <h1 style="color:#111827;font-size:24px;margin:0 0 8px;">Booking Cancelled</h1>
          <p style="color:#4B5563;font-size:15px;margin:0 0 24px;">Hi {b.name}, your appointment below has been cancelled.</p>
          <table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #E5E7EB;">
            <tr><td style="padding:14px 0;color:#6B7280;font-size:13px;text-transform:uppercase;letter-spacing:1px;">Service</td><td style="padding:14px 0;color:#111827;font-size:15px;font-weight:600;text-align:right;text-decoration:line-through;">{b.service}</td></tr>
            <tr><td style="padding:14px 0;border-top:1px solid #F3F4F6;color:#6B7280;font-size:13px;text-transform:uppercase;letter-spacing:1px;">Date</td><td style="padding:14px 0;border-top:1px solid #F3F4F6;color:#111827;font-size:15px;font-weight:600;text-align:right;text-decoration:line-through;">{b.date}</td></tr>
            <tr><td style="padding:14px 0;border-top:1px solid #F3F4F6;color:#6B7280;font-size:13px;text-transform:uppercase;letter-spacing:1px;">Time</td><td style="padding:14px 0;border-top:1px solid #F3F4F6;color:#111827;font-size:15px;font-weight:600;text-align:right;text-decoration:line-through;">{b.time}</td></tr>
          </table>
          <p style="color:#4B5563;font-size:14px;margin-top:24px;">Want to book another time? We'd love to see you.</p>
          <div style="margin-top:20px;padding:20px;background:#FAFAFA;border:1px solid #E5E7EB;">
            <p style="margin:0;color:#111827;font-size:14px;"><strong>{BUSINESS['name']}</strong></p>
            <p style="margin:6px 0 0;color:#4B5563;font-size:14px;">{BUSINESS['location']}</p>
            <p style="margin:6px 0 0;color:#C5A059;font-size:14px;font-weight:600;">{BUSINESS['phone']}</p>
          </div>
        </td></tr>
      </table>
    </div>
    """


async def _send_email(to_email: str, subject: str, html: str):
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set; skipping email")
        return
    params = {
        "from": f"Ajay Haircut <{SENDER_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "html": html,
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email sent to {to_email}: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")


async def _send_confirmation(b: Booking):
    await _send_email(b.email, f"Your booking is confirmed — {b.date} at {b.time}", _confirmation_html(b))

    if OWNER_EMAILS:
        owner_params = {
            "from": f"Ajay Haircut Bookings <{SENDER_EMAIL}>",
            "to": OWNER_EMAILS,
            "subject": f"New Booking: {b.service} — {b.date} {b.time}",
            "html": _owner_html(b),
        }
        try:
            await asyncio.to_thread(resend.Emails.send, owner_params)
            logger.info(f"Owner notification sent to {OWNER_EMAILS}")
        except Exception as e:
            logger.error(f"Failed to send owner notification: {e}")


async def _send_reschedule_notification(b: Booking):
    await _send_email(b.email, f"Your booking has been updated — {b.date} at {b.time}", _rescheduled_html(b))


async def _send_cancellation_notification(b: Booking):
    await _send_email(b.email, f"Your booking on {b.date} has been cancelled", _cancellation_html(b))


@api_router.get("/")
async def root():
    return {"message": "Ajay Haircut API"}


@api_router.post("/bookings", response_model=Booking)
async def create_booking(payload: BookingCreate):
    if _is_tuesday(payload.date):
        raise HTTPException(status_code=400, detail="We are closed on Tuesdays. Please choose another day.")

    closed_doc = await _closed_date_doc(payload.date)
    if closed_doc:
        raise HTTPException(status_code=400, detail="We're closed that day. Please choose another date.")

    duration = _duration_for_service(payload.service)
    try:
        new_start = _parse_clock(payload.time)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format.")

    if payload.date == _today_str():
        now_clock = _parse_clock(_now_local().strftime("%I:%M %p"))
        if new_start <= now_clock:
            raise HTTPException(status_code=400, detail="That time has already passed today. Please choose a later time.")

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
async def availability(date: str, service: Optional[str] = None, ignore_closed: bool = False, exclude_id: Optional[str] = None, admin: bool = False):
    duration = _duration_for_service(service) if service else DEFAULT_DURATION_MINUTES
    # Only the admin dashboard passes admin=true, so only the owner ever
    # sees/can pick a time earlier than the public site's opening time.
    open_time = ADMIN_OPEN_TIME if admin else OPEN_TIME
    candidate_times = _generate_slot_times(duration, open_time=open_time)

    if not ignore_closed:
        closed_doc = await _closed_date_doc(date)
        if _is_tuesday(date) or closed_doc:
            return {"date": date, "closed": True, "slots": [{"time": s, "available": False} for s in candidate_times]}

    booked = await _booked_intervals(date, exclude_id=exclude_id)

    # If the requested date is today, anything at or before the current
    # time (shop's local clock) is no longer bookable.
    is_today = date == _today_str()
    now_clock = _parse_clock(_now_local().strftime("%I:%M %p")) if is_today else None

    slots = []
    for s in candidate_times:
        s_start = _parse_clock(s)
        available = not any(_ranges_overlap(s_start, duration, b_start, b_dur) for b_start, b_dur in booked)
        if is_today and s_start <= now_clock:
            available = False
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
    # No customer email for manual/phone entries — these are logged by the
    # owner after the call, not booked by the customer themselves.
    return booking


@api_router.patch("/admin/bookings/{booking_id}", response_model=Booking)
async def admin_update_booking(booking_id: str, payload: AdminBookingUpdate, x_admin_key: Optional[str] = Header(None)):
    """Owner-only: edit, reschedule, cancel-and-rebook, or convert a booking
    to/from a block. Notifies the customer by email when a real (non-block)
    booking changes."""
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
        {"date": merged['date'], "id": {"$ne": booking_id}, "status": {"$ne": "cancelled"}},
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
    updated = Booking(**merged)

    # Only send a "your booking has changed" email for real reschedule/
    # detail changes — not for a plain status update like marking a
    # booking "completed" (that's an internal record-keeping action, not
    # something the customer needs to be told about).
    is_reschedule = any(
        getattr(payload, field) is not None
        for field in ("date", "time", "service", "duration_minutes")
    )
    if is_reschedule and updated.status != "blocked" and updated.email and updated.email != "owner@ajayhaircut.com":
        asyncio.create_task(_send_reschedule_notification(updated))

    return updated


@api_router.delete("/admin/bookings/{booking_id}")
async def admin_delete_booking(booking_id: str, x_admin_key: Optional[str] = Header(None)):
    """Owner-only: cancel a customer booking, or unblock a previously
    blocked time slot.

    A blocked slot (no customer attached) is removed entirely — there's
    nothing to keep a record of. A real customer booking is instead marked
    'cancelled' and kept in the database so it still shows up in the admin
    dashboard's history and frees up its time slot for new bookings; the
    customer is emailed that it was cancelled.
    """
    _require_admin(x_admin_key)

    existing_doc = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not existing_doc:
        raise HTTPException(status_code=404, detail="Booking not found.")

    if existing_doc.get('status') == 'blocked':
        await db.bookings.delete_one({"id": booking_id})
        return {"status": "ok", "action": "unblocked"}

    await db.bookings.update_one({"id": booking_id}, {"$set": {"status": "cancelled"}})

    if isinstance(existing_doc.get('created_at'), str):
        existing_doc['created_at'] = datetime.fromisoformat(existing_doc['created_at'])
    existing_doc['status'] = 'cancelled'
    cancelled = Booking(**existing_doc)

    if cancelled.email and cancelled.email != "owner@ajayhaircut.com":
        asyncio.create_task(_send_cancellation_notification(cancelled))

    return {"status": "ok", "action": "cancelled"}


@api_router.get("/closed-dates")
async def list_closed_dates():
    """Public — used by both the customer site and the admin calendar to
    mark manually-closed days (e.g. shop closed for a trip)."""
    docs = await db.closed_dates.find({}, {"_id": 0}).to_list(1000)
    return docs


@api_router.post("/admin/closed-dates")
async def admin_close_date(payload: ClosedDateCreate, x_admin_key: Optional[str] = Header(None)):
    """Owner-only: block off an entire day — no customer can book any time
    on it, regardless of what's otherwise open. Existing bookings already on
    that day are left untouched; cancel them separately if needed."""
    _require_admin(x_admin_key)
    await db.closed_dates.update_one(
        {"date": payload.date},
        {"$set": {"date": payload.date, "reason": payload.reason or ""}},
        upsert=True,
    )
    return {"status": "ok", "date": payload.date}


@api_router.delete("/admin/closed-dates/{date}")
async def admin_open_date(date: str, x_admin_key: Optional[str] = Header(None)):
    """Owner-only: undo a whole-day closure, making that date bookable
    again (subject to the normal Tuesday-closed rule)."""
    _require_admin(x_admin_key)
    result = await db.closed_dates.delete_one({"date": date})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="That date wasn't marked closed.")
    return {"status": "ok", "date": date}


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

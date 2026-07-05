from fastapi import FastAPI, APIRouter, HTTPException, Request
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
from datetime import datetime, timezone
import resend
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest,
)

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

STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
DEPOSIT_AMOUNT = 12.00
DEPOSIT_CURRENCY = "cad"

BUSINESS = {
    "name": "Ajay Haircut",
    "phone": "(778) 344-2550",
    "location": "Surrey, BC, Canada",
}

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
    status: str = "confirmed"
    deposit_paid: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContactCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = ""
    message: str


class CheckoutRequest(BaseModel):
    booking: BookingCreate
    origin_url: str


SLOTS = ["09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "01:00 PM",
         "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM",
         "07:00 PM", "08:00 PM"]


def _is_tuesday(date: str) -> bool:
    try:
        return datetime.strptime(date, "%Y-%m-%d").weekday() == 1
    except ValueError:
        return False


async def _slot_taken(date: str, time: str) -> bool:
    existing = await db.bookings.find_one({"date": date, "time": time})
    return existing is not None


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
    # Customer confirmation
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

    # Owner notification
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


async def _finalize_booking(data: dict) -> Booking:
    fields = ("service", "date", "time", "name", "email", "phone", "notes", "deposit_paid")
    booking = Booking(**{k: data[k] for k in fields if k in data})
    doc = booking.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.bookings.insert_one(doc)
    asyncio.create_task(_send_confirmation(booking))
    return booking


@api_router.post("/bookings", response_model=Booking)
async def create_booking(payload: BookingCreate):
    return await _finalize_booking(payload.model_dump())


@api_router.post("/bookings/checkout")
async def bookings_checkout(payload: CheckoutRequest, request: Request):
    b = payload.booking
    if _is_tuesday(b.date):
        raise HTTPException(status_code=400, detail="We are closed on Tuesdays. Please choose another day.")
    if b.time not in SLOTS:
        raise HTTPException(status_code=400, detail="Invalid time slot.")
    if await _slot_taken(b.date, b.time):
        raise HTTPException(status_code=409, detail="That time slot was just booked. Please pick another.")
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Payments are not configured.")

    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    origin = payload.origin_url.rstrip("/")
    success_url = f"{origin}/?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/"

    metadata = {"type": "booking_deposit", "service": b.service, "date": b.date, "time": b.time, "email": b.email}
    req = CheckoutSessionRequest(
        amount=DEPOSIT_AMOUNT,
        currency=DEPOSIT_CURRENCY,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(req)

    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "amount": DEPOSIT_AMOUNT,
        "currency": DEPOSIT_CURRENCY,
        "payment_status": "initiated",
        "status": "initiated",
        "processed": False,
        "booking": b.model_dump(),
        "booking_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"url": session.url, "session_id": session.session_id}


async def _process_paid_session(session_id: str) -> Optional[dict]:
    """Finalize a booking once its deposit is paid. Idempotent per session."""
    txn = await db.payment_transactions.find_one({"session_id": session_id})
    if not txn or txn.get("processed"):
        return txn.get("booking_id_data") if txn else None
    booking_data = dict(txn["booking"])
    booking_data["deposit_paid"] = DEPOSIT_AMOUNT
    booking = await _finalize_booking(booking_data)
    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {"processed": True, "booking_id": booking.id, "booking_id_data": booking.model_dump(mode="json")}},
    )
    return booking.model_dump(mode="json")


@api_router.get("/payments/checkout/status/{session_id}")
async def checkout_status(session_id: str, request: Request):
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Payments are not configured.")
    host_url = str(request.base_url)
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=f"{host_url}api/webhook/stripe")
    status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(session_id)

    update = {"status": status.status, "payment_status": status.payment_status}
    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": update})

    booking = None
    if status.payment_status == "paid":
        booking = await _process_paid_session(session_id)
    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency,
        "booking": booking,
    }


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Payments are not configured.")
    host_url = str(request.base_url)
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=f"{host_url}api/webhook/stripe")
    body = await request.body()
    sig = request.headers.get("Stripe-Signature")
    try:
        event = await stripe_checkout.handle_webhook(body, sig)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook")
    if event.payment_status == "paid" and event.session_id:
        await db.payment_transactions.update_one(
            {"session_id": event.session_id},
            {"$set": {"payment_status": "paid", "status": "complete"}},
        )
        await _process_paid_session(event.session_id)
    return {"received": True}


@api_router.get("/bookings", response_model=List[Booking])
async def list_bookings():
    docs = await db.bookings.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for d in docs:
        if isinstance(d.get('created_at'), str):
            d['created_at'] = datetime.fromisoformat(d['created_at'])
    return docs


@api_router.get("/bookings/availability")
async def availability(date: str):
    slots = ["09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "01:00 PM",
             "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM",
             "07:00 PM", "08:00 PM"]
    # Closed on Tuesdays
    try:
        is_tuesday = datetime.strptime(date, "%Y-%m-%d").weekday() == 1
    except ValueError:
        is_tuesday = False
    if is_tuesday:
        return {"date": date, "closed": True, "slots": [{"time": s, "available": False} for s in slots]}
    taken = await db.bookings.find({"date": date}, {"_id": 0, "time": 1}).to_list(1000)
    taken_times = {t['time'] for t in taken}
    return {"date": date, "closed": False, "slots": [{"time": s, "available": s not in taken_times} for s in slots]}


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

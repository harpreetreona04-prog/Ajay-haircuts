from fastapi import FastAPI, APIRouter, HTTPException
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContactCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = ""
    message: str


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


@api_router.get("/")
async def root():
    return {"message": "Ajay Haircut API"}


@api_router.post("/bookings", response_model=Booking)
async def create_booking(payload: BookingCreate):
    booking = Booking(**payload.model_dump())
    doc = booking.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.bookings.insert_one(doc)
    asyncio.create_task(_send_confirmation(booking))
    return booking


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
             "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM", "07:00 PM"]
    taken = await db.bookings.find({"date": date}, {"_id": 0, "time": 1}).to_list(1000)
    taken_times = {t['time'] for t in taken}
    return {"date": date, "slots": [{"time": s, "available": s not in taken_times} for s in slots]}


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

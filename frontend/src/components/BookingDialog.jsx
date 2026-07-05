import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "./ui/dialog";
import { Check, ChevronRight, ChevronLeft, CalendarDays, Clock, Scissors, Loader2, PartyPopper, ShieldCheck, CreditCard, XCircle } from "lucide-react";
import { SERVICES, BUSINESS } from "../data/site";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const DEPOSIT = "$12";

const STEPS = ["Service", "Date & Time", "Your Info", "Deposit"];
const todayStr = () => new Date().toISOString().split("T")[0];

export const BookingDialog = ({ open, onOpenChange, defaultService, resumeSessionId }) => {
  const [step, setStep] = useState(0);
  const [service, setService] = useState(defaultService || "");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [slots, setSlots] = useState([]);
  const [closed, setClosed] = useState(false);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [info, setInfo] = useState({ name: "", email: "", phone: "", notes: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  // Payment-return state
  const [payState, setPayState] = useState("idle"); // idle | polling | paid | failed
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (open && !resumeSessionId) {
      setStep(0); setService(defaultService || ""); setDate(""); setTime("");
      setInfo({ name: "", email: "", phone: "", notes: "" }); setError("");
      setPayState("idle"); setResult(null);
    }
  }, [open, defaultService, resumeSessionId]);

  const pollStatus = useCallback(async (sessionId, attempt = 0) => {
    if (attempt >= 8) { setPayState("failed"); setError("Payment is taking longer than expected. Please check your email."); return; }
    try {
      const { data } = await axios.get(`${API}/payments/checkout/status/${sessionId}`);
      if (data.payment_status === "paid") {
        setResult(data.booking); setPayState("paid"); return;
      }
      if (data.status === "expired") { setPayState("failed"); setError("Payment session expired. Please try booking again."); return; }
      setTimeout(() => pollStatus(sessionId, attempt + 1), 2000);
    } catch (e) {
      setTimeout(() => pollStatus(sessionId, attempt + 1), 2000);
    }
  }, []);

  useEffect(() => {
    if (open && resumeSessionId) {
      setPayState("polling"); setResult(null); setError("");
      pollStatus(resumeSessionId);
    }
  }, [open, resumeSessionId, pollStatus]);

  useEffect(() => {
    if (!date) { setSlots([]); return; }
    setSlotsLoading(true); setTime("");
    axios.get(`${API}/bookings/availability`, { params: { date } })
      .then(({ data }) => { setSlots(data.slots); setClosed(!!data.closed); })
      .catch(() => { setSlots([]); setClosed(false); })
      .finally(() => setSlotsLoading(false));
  }, [date]);

  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const back = () => setStep((s) => Math.max(s - 1, 0));

  const payAndBook = async () => {
    setSubmitting(true); setError("");
    try {
      const { data } = await axios.post(`${API}/bookings/checkout`, {
        origin_url: window.location.origin,
        booking: { service, date, time, ...info },
      });
      window.location.href = data.url; // redirect to Stripe
    } catch (e) {
      const msg = e?.response?.data?.detail || "We couldn't start the payment. Please try again or call us.";
      setError(msg); setSubmitting(false);
    }
  };

  const canNext =
    (step === 0 && service) ||
    (step === 1 && date && time) ||
    (step === 2 && info.name && info.email && info.phone);

  const showConfirmation = payState === "paid" || payState === "polling" || payState === "failed";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg p-0 gap-0 overflow-hidden border-0 bg-white rounded-none" data-testid="booking-dialog">
        <DialogTitle className="sr-only">Book an Appointment at Ajay Haircut</DialogTitle>
        <DialogDescription className="sr-only">Choose a service, pick a date and time, enter your details, and pay a $12 deposit to confirm.</DialogDescription>
        <div className="bg-[#111827] px-6 py-5">
          <p className="text-[#C5A059] text-[10px] uppercase tracking-[0.3em] font-bold">Ajay Haircut · Surrey BC</p>
          <h2 className="text-white font-display text-2xl font-bold mt-1">Book an Appointment</h2>
          {!showConfirmation && (
            <div className="flex items-center gap-2 mt-4">
              {STEPS.map((s, i) => (
                <div key={s} className="flex items-center gap-2 flex-1">
                  <div className={`w-6 h-6 flex items-center justify-center text-[11px] font-bold rounded-full transition-colors ${
                    i <= step ? "bg-[#C5A059] text-[#111827]" : "bg-white/10 text-white/50"
                  }`}>
                    {i < step ? <Check size={13} /> : i + 1}
                  </div>
                  {i < STEPS.length - 1 && <div className={`h-px flex-1 ${i < step ? "bg-[#C5A059]" : "bg-white/15"}`} />}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="px-6 py-6 max-h-[62vh] overflow-y-auto">
          {!showConfirmation && step === 0 && (
            <div className="space-y-2" data-testid="booking-step-service">
              <p className="text-xs uppercase tracking-widest text-gray-400 font-semibold mb-3">Choose a service</p>
              {SERVICES.map((s) => (
                <button key={s.title} onClick={() => setService(s.title)} data-testid={`select-service-${s.title}`}
                  className={`w-full flex items-center justify-between px-4 py-3 border text-left transition-colors ${
                    service === s.title ? "border-[#C5A059] bg-[#C5A059]/5" : "border-gray-200 hover:border-gray-300"
                  }`}>
                  <span className="flex items-center gap-3">
                    <Scissors size={16} className="text-[#C5A059]" />
                    <span className="font-medium text-[#111827] text-sm">{s.title}</span>
                  </span>
                  <span className="text-[#C5A059] text-sm font-semibold">{s.price}</span>
                </button>
              ))}
            </div>
          )}

          {!showConfirmation && step === 1 && (
            <div data-testid="booking-step-datetime">
              <label className="flex items-center gap-2 text-xs uppercase tracking-widest text-gray-400 font-semibold mb-2">
                <CalendarDays size={14} /> Select date
              </label>
              <input type="date" min={todayStr()} value={date} onChange={(e) => setDate(e.target.value)} data-testid="booking-date"
                className="w-full border border-gray-200 px-4 py-3 focus:border-[#C5A059] focus:outline-none text-[#111827]" />

              <label className="flex items-center gap-2 text-xs uppercase tracking-widest text-gray-400 font-semibold mt-6 mb-2">
                <Clock size={14} /> Select time
              </label>
              {!date && <p className="text-sm text-gray-400">Pick a date to see available times.</p>}
              {slotsLoading && <p className="text-sm text-gray-400 flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Loading slots…</p>}
              {date && !slotsLoading && closed && (
                <p className="text-sm text-red-600 font-medium" data-testid="booking-closed">We're closed on Tuesdays — please pick another day.</p>
              )}
              {date && !slotsLoading && !closed && (
                <div className="grid grid-cols-3 gap-2">
                  {slots.map((s) => (
                    <button key={s.time} disabled={!s.available} onClick={() => setTime(s.time)} data-testid={`slot-${s.time}`}
                      className={`py-2 text-sm border transition-colors ${
                        time === s.time ? "border-[#C5A059] bg-[#C5A059] text-white"
                        : s.available ? "border-gray-200 text-[#111827] hover:border-[#C5A059]"
                        : "border-gray-100 text-gray-300 line-through cursor-not-allowed"
                      }`}>
                      {s.time}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {!showConfirmation && step === 2 && (
            <div className="space-y-4" data-testid="booking-step-info">
              <div>
                <label className="text-xs uppercase tracking-widest text-gray-400 font-semibold">Full name</label>
                <input value={info.name} onChange={(e) => setInfo({ ...info, name: e.target.value })} data-testid="booking-name"
                  className="w-full border-b border-gray-300 py-2.5 focus:border-[#C5A059] focus:outline-none text-lg transition-colors" />
              </div>
              <div>
                <label className="text-xs uppercase tracking-widest text-gray-400 font-semibold">Email</label>
                <input type="email" value={info.email} onChange={(e) => setInfo({ ...info, email: e.target.value })} data-testid="booking-email"
                  className="w-full border-b border-gray-300 py-2.5 focus:border-[#C5A059] focus:outline-none text-lg transition-colors" />
                <p className="text-[11px] text-gray-400 mt-1">Your confirmation will be emailed here.</p>
              </div>
              <div>
                <label className="text-xs uppercase tracking-widest text-gray-400 font-semibold">Phone</label>
                <input value={info.phone} onChange={(e) => setInfo({ ...info, phone: e.target.value })} data-testid="booking-phone"
                  className="w-full border-b border-gray-300 py-2.5 focus:border-[#C5A059] focus:outline-none text-lg transition-colors" />
              </div>
              <div>
                <label className="text-xs uppercase tracking-widest text-gray-400 font-semibold">Notes (optional)</label>
                <textarea rows={2} value={info.notes} onChange={(e) => setInfo({ ...info, notes: e.target.value })} data-testid="booking-notes"
                  className="w-full border-b border-gray-300 py-2.5 focus:border-[#C5A059] focus:outline-none resize-none transition-colors" />
              </div>
            </div>
          )}

          {!showConfirmation && step === 3 && (
            <div data-testid="booking-step-deposit">
              <div className="bg-[#FAFAFA] border border-gray-100 p-5 text-sm">
                <p className="text-gray-500 uppercase tracking-widest text-xs font-semibold mb-3">Appointment Summary</p>
                <div className="flex justify-between py-1.5"><span className="text-gray-500">Service</span><span className="font-semibold text-[#111827]">{service}</span></div>
                <div className="flex justify-between py-1.5 border-t border-gray-100"><span className="text-gray-500">Date</span><span className="font-semibold text-[#111827]">{date}</span></div>
                <div className="flex justify-between py-1.5 border-t border-gray-100"><span className="text-gray-500">Time</span><span className="font-semibold text-[#111827]">{time}</span></div>
                <div className="flex justify-between py-1.5 border-t border-gray-100"><span className="text-gray-500">Name</span><span className="font-semibold text-[#111827]">{info.name}</span></div>
              </div>

              <div className="mt-5 border border-[#C5A059]/40 bg-[#C5A059]/5 p-5">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-[#111827] font-semibold"><ShieldCheck size={18} className="text-[#C5A059]" /> Booking Deposit</span>
                  <span className="font-display text-2xl font-extrabold text-[#111827]">{DEPOSIT} CAD</span>
                </div>
                <p className="text-sm text-gray-500 mt-3">
                  A {DEPOSIT} deposit secures your appointment and is applied toward your service total on the day of your visit.
                </p>
                <p className="text-xs text-gray-400 mt-3 flex items-center gap-2">
                  <CreditCard size={14} /> Pay securely with card, Apple Pay or Google Pay via Stripe.
                </p>
              </div>
              {error && <p className="text-red-600 text-sm mt-4" data-testid="booking-error">{error}</p>}
            </div>
          )}

          {/* Payment return / confirmation */}
          {showConfirmation && payState === "polling" && (
            <div className="text-center py-10" data-testid="booking-processing">
              <Loader2 size={40} className="text-[#C5A059] animate-spin mx-auto" />
              <h3 className="font-display text-xl font-bold text-[#111827] mt-5">Confirming your payment…</h3>
              <p className="text-gray-500 mt-2 text-sm">Please wait a moment while we secure your appointment.</p>
            </div>
          )}

          {showConfirmation && payState === "failed" && (
            <div className="text-center py-8" data-testid="booking-failed">
              <XCircle size={44} className="text-red-500 mx-auto" />
              <h3 className="font-display text-2xl font-bold text-[#111827] mt-4">Payment not completed</h3>
              <p className="text-gray-500 mt-2 text-sm">{error || "Your deposit wasn't completed."}</p>
              <button onClick={() => onOpenChange(false)} data-testid="booking-failed-close"
                className="mt-6 bg-[#111827] text-white hover:bg-[#C5A059] transition-colors px-8 py-3 text-xs uppercase tracking-widest font-bold w-full">
                Close
              </button>
            </div>
          )}

          {showConfirmation && payState === "paid" && (
            <div className="text-center py-6" data-testid="booking-confirmation">
              <div className="w-16 h-16 bg-[#C5A059]/15 rounded-full flex items-center justify-center mx-auto">
                <PartyPopper size={30} className="text-[#C5A059]" />
              </div>
              <h3 className="font-display text-2xl font-bold text-[#111827] mt-5">Booking Confirmed!</h3>
              <p className="text-gray-500 mt-2 text-sm">
                Your {DEPOSIT} deposit was received{result?.name ? `, ${result.name.split(" ")[0]}` : ""}. A confirmation has been emailed to you.
              </p>
              <div className="bg-[#FAFAFA] border border-gray-100 p-5 mt-6 text-left">
                <div className="flex justify-between py-1.5 text-sm"><span className="text-gray-500">Service</span><span className="font-semibold text-[#111827]">{result?.service || service}</span></div>
                <div className="flex justify-between py-1.5 text-sm border-t border-gray-100"><span className="text-gray-500">Date</span><span className="font-semibold text-[#111827]">{result?.date || date}</span></div>
                <div className="flex justify-between py-1.5 text-sm border-t border-gray-100"><span className="text-gray-500">Time</span><span className="font-semibold text-[#111827]">{result?.time || time}</span></div>
                <div className="flex justify-between py-1.5 text-sm border-t border-gray-100"><span className="text-gray-500">Deposit paid</span><span className="font-semibold text-[#C5A059]">{DEPOSIT} CAD</span></div>
              </div>
              <p className="text-xs text-gray-400 mt-4">Need to reschedule? Call {BUSINESS.phone}</p>
              <button onClick={() => onOpenChange(false)} data-testid="booking-close"
                className="mt-6 bg-[#111827] text-white hover:bg-[#C5A059] transition-colors px-8 py-3 text-xs uppercase tracking-widest font-bold w-full">
                Done
              </button>
            </div>
          )}
        </div>

        {!showConfirmation && (
          <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-between">
            <button onClick={back} disabled={step === 0} data-testid="booking-back"
              className="flex items-center gap-1 text-sm font-semibold text-gray-500 hover:text-[#111827] disabled:opacity-0 transition-colors">
              <ChevronLeft size={16} /> Back
            </button>
            {step < 3 ? (
              <button onClick={next} disabled={!canNext} data-testid="booking-next"
                className="btn-shine flex items-center gap-1 bg-[#111827] text-white hover:bg-[#C5A059] transition-colors px-6 py-3 text-xs uppercase tracking-widest font-bold disabled:opacity-40 disabled:cursor-not-allowed">
                Continue <ChevronRight size={16} />
              </button>
            ) : (
              <button onClick={payAndBook} disabled={submitting} data-testid="booking-pay"
                className="btn-shine flex items-center gap-2 bg-[#C5A059] text-[#111827] hover:bg-[#111827] hover:text-white transition-colors px-6 py-3 text-xs uppercase tracking-widest font-bold disabled:opacity-40 disabled:cursor-not-allowed">
                {submitting ? <><Loader2 size={16} className="animate-spin" /> Redirecting…</> : <>Pay {DEPOSIT} Deposit</>}
              </button>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

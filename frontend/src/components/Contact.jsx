import { useState } from "react";
import axios from "axios";
import { Phone, MapPin, Clock, Send, Instagram } from "lucide-react";
import { toast } from "sonner";
import { BUSINESS, HOURS } from "../data/site";
import { useReveal } from "../hooks/useReveal";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const Contact = ({ onBook }) => {
  const ref = useReveal();
  const [form, setForm] = useState({ name: "", email: "", phone: "", message: "" });
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await axios.post(`${API}/contact`, form);
      toast.success(data.message || "Message sent!");
      setForm({ name: "", email: "", phone: "", message: "" });
    } catch (err) {
      toast.error("Something went wrong. Please call us instead.");
    } finally {
      setLoading(false);
    }
  };

  const upd = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <section id="contact" className="py-24 md:py-32 bg-white" data-testid="contact">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="max-w-2xl mb-14">
          <p className="overline mb-4">Get In Touch</p>
          <h2 className="font-display text-4xl md:text-5xl font-extrabold text-[#111827] tracking-tight leading-tight">
            Visit us in Surrey, BC
          </h2>
        </div>

        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16">
          <div ref={ref} className="reveal space-y-8">
            <div className="space-y-6">
              <div className="flex items-start gap-4">
                <div className="w-11 h-11 bg-[#FAFAFA] border border-[#C5A059]/30 flex items-center justify-center shrink-0">
                  <MapPin size={18} className="text-[#C5A059]" />
                </div>
                <div>
                  <p className="text-xs uppercase tracking-widest text-gray-400 font-semibold">Location</p>
                  <p className="text-[#111827] font-semibold mt-1">{BUSINESS.name}</p>
                  <p className="text-gray-500">{BUSINESS.location}</p>
                </div>
              </div>

              <a href={BUSINESS.phoneHref} className="flex items-start gap-4 group" data-testid="contact-call">
                <div className="w-11 h-11 bg-[#FAFAFA] border border-[#C5A059]/30 flex items-center justify-center shrink-0">
                  <Phone size={18} className="text-[#C5A059]" />
                </div>
                <div>
                  <p className="text-xs uppercase tracking-widest text-gray-400 font-semibold">Phone</p>
                  <p className="text-[#111827] font-semibold mt-1 group-hover:text-[#C5A059] transition-colors">{BUSINESS.phone}</p>
                  <p className="text-gray-500 text-sm">Tap to call · click-to-call enabled</p>
                </div>
              </a>

              <div className="flex items-start gap-4">
                <div className="w-11 h-11 bg-[#FAFAFA] border border-[#C5A059]/30 flex items-center justify-center shrink-0">
                  <Clock size={18} className="text-[#C5A059]" />
                </div>
                <div>
                  <p className="text-xs uppercase tracking-widest text-gray-400 font-semibold">Business Hours</p>
                  {HOURS.map((h) => (
                    <p key={h.day} className="text-gray-600 mt-1 text-sm flex justify-between gap-6 max-w-xs">
                      <span className="text-[#111827] font-medium">{h.day}</span><span>{h.time}</span>
                    </p>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-3 pt-2">
                <a href={BUSINESS.socials.instagram} target="_blank" rel="noreferrer" data-testid="contact-instagram"
                  className="w-11 h-11 bg-[#111827] text-white flex items-center justify-center hover:bg-[#C5A059] transition-colors">
                  <Instagram size={18} />
                </a>
                <a href={BUSINESS.socials.tiktok} target="_blank" rel="noreferrer" data-testid="contact-tiktok"
                  className="w-11 h-11 bg-[#111827] text-white flex items-center justify-center hover:bg-[#C5A059] transition-colors font-bold text-xs">
                  TikTok
                </a>
              </div>
            </div>

            <div className="border border-gray-200 overflow-hidden h-64">
              <iframe
                title="Ajay Haircut location map — Surrey BC"
                src="https://www.google.com/maps?q=Surrey,British+Columbia,Canada&output=embed"
                className="w-full h-full grayscale hover:grayscale-0 transition-all duration-500"
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
              />
            </div>
          </div>

          <div className="bg-[#FAFAFA] border border-gray-100 p-8 md:p-10">
            <h3 className="font-display text-2xl font-bold text-[#111827]">Send us a message</h3>
            <p className="text-gray-500 text-sm mt-2">Questions about a service? Drop us a line or book directly.</p>
            <form onSubmit={submit} className="mt-8 space-y-6" data-testid="contact-form">
              <div>
                <label className="text-xs text-gray-500 font-semibold tracking-wide uppercase">Name</label>
                <input required value={form.name} onChange={upd("name")} data-testid="contact-name"
                  className="w-full border-b border-gray-300 bg-transparent py-3 focus:border-[#C5A059] focus:outline-none text-lg transition-colors" />
              </div>
              <div className="grid sm:grid-cols-2 gap-6">
                <div>
                  <label className="text-xs text-gray-500 font-semibold tracking-wide uppercase">Email</label>
                  <input required type="email" value={form.email} onChange={upd("email")} data-testid="contact-email"
                    className="w-full border-b border-gray-300 bg-transparent py-3 focus:border-[#C5A059] focus:outline-none text-lg transition-colors" />
                </div>
                <div>
                  <label className="text-xs text-gray-500 font-semibold tracking-wide uppercase">Phone</label>
                  <input value={form.phone} onChange={upd("phone")} data-testid="contact-phone"
                    className="w-full border-b border-gray-300 bg-transparent py-3 focus:border-[#C5A059] focus:outline-none text-lg transition-colors" />
                </div>
              </div>
              <div>
                <label className="text-xs text-gray-500 font-semibold tracking-wide uppercase">Message</label>
                <textarea required rows={3} value={form.message} onChange={upd("message")} data-testid="contact-message"
                  className="w-full border-b border-gray-300 bg-transparent py-3 focus:border-[#C5A059] focus:outline-none text-lg resize-none transition-colors" />
              </div>
              <button type="submit" disabled={loading} data-testid="contact-submit"
                className="btn-shine w-full bg-[#111827] text-white hover:bg-[#C5A059] transition-colors duration-300 px-8 py-4 font-bold uppercase tracking-widest text-sm flex items-center justify-center gap-2 disabled:opacity-60">
                {loading ? "Sending..." : <>Send Message <Send size={16} /></>}
              </button>
            </form>
          </div>
        </div>
      </div>
    </section>
  );
};

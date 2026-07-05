import { Phone, Instagram, MapPin } from "lucide-react";
import { BUSINESS } from "../data/site";

const QUICK = [
  { label: "Services", href: "#services" },
  { label: "About", href: "#about" },
  { label: "Gallery", href: "#gallery" },
  { label: "Reviews", href: "#reviews" },
  { label: "Contact", href: "#contact" },
];

const SERVICE_LINKS = ["Men's Haircuts", "Skin Fades", "Beard Trimming", "Hair & Beard Perms", "Men's Facials"];

export const Footer = ({ onBook }) => {
  return (
    <footer className="bg-[#0B0F17] text-white" data-testid="footer">
      <div className="max-w-7xl mx-auto px-6 md:px-12 py-16 grid gap-12 md:grid-cols-2 lg:grid-cols-4">
        <div>
          <span className="font-display text-2xl font-extrabold">Ajay<span className="text-[#C5A059]">.</span>Haircut</span>
          <p className="text-white/50 text-sm mt-4 leading-relaxed max-w-xs">
            Premium men's grooming in Surrey, BC. 11+ years of precision haircuts, beard styling, perms & facials.
          </p>
          <div className="flex items-center gap-3 mt-6">
            <a href={BUSINESS.socials.instagram} target="_blank" rel="noreferrer" data-testid="footer-instagram"
              className="w-10 h-10 border border-white/15 flex items-center justify-center hover:bg-[#C5A059] hover:border-[#C5A059] transition-colors">
              <Instagram size={17} />
            </a>
            <a href={BUSINESS.socials.tiktok} target="_blank" rel="noreferrer" data-testid="footer-tiktok"
              className="w-10 h-10 border border-white/15 flex items-center justify-center hover:bg-[#C5A059] hover:border-[#C5A059] transition-colors text-xs font-bold">
              TT
            </a>
          </div>
        </div>

        <div>
          <h4 className="text-xs uppercase tracking-[0.25em] text-[#C5A059] font-bold mb-5">Quick Links</h4>
          <ul className="space-y-3">
            {QUICK.map((q) => (
              <li key={q.href}><a href={q.href} className="text-white/60 hover:text-white text-sm transition-colors">{q.label}</a></li>
            ))}
          </ul>
        </div>

        <div>
          <h4 className="text-xs uppercase tracking-[0.25em] text-[#C5A059] font-bold mb-5">Services</h4>
          <ul className="space-y-3">
            {SERVICE_LINKS.map((s) => (
              <li key={s}><a href="#services" className="text-white/60 hover:text-white text-sm transition-colors">{s}</a></li>
            ))}
          </ul>
        </div>

        <div>
          <h4 className="text-xs uppercase tracking-[0.25em] text-[#C5A059] font-bold mb-5">Book Appointment</h4>
          <a href={BUSINESS.phoneHref} className="flex items-center gap-2 text-white/70 hover:text-white text-sm mb-3 transition-colors">
            <Phone size={15} className="text-[#C5A059]" /> {BUSINESS.phone}
          </a>
          <p className="flex items-center gap-2 text-white/60 text-sm mb-6">
            <MapPin size={15} className="text-[#C5A059]" /> {BUSINESS.location}
          </p>
          <button onClick={onBook} data-testid="footer-book-btn"
            className="btn-shine bg-[#C5A059] text-[#111827] hover:bg-white transition-colors duration-300 px-6 py-3 text-xs uppercase tracking-widest font-bold w-full">
            Book Now
          </button>
        </div>
      </div>

      <div className="border-t border-white/10">
        <div className="max-w-7xl mx-auto px-6 md:px-12 py-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-white/40 text-xs">
          <p>© {new Date().getFullYear()} Ajay Haircut. All rights reserved.</p>
          <div className="flex items-center gap-6">
            <a href="#" className="hover:text-white transition-colors" data-testid="footer-privacy">Privacy Policy</a>
            <a href="#" className="hover:text-white transition-colors" data-testid="footer-terms">Terms of Service</a>
          </div>
        </div>
      </div>
    </footer>
  );
};

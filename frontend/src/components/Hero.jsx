import { Phone, Star, ArrowRight } from "lucide-react";
import { BUSINESS, IMAGES } from "../data/site";

export const Hero = ({ onBook }) => {
  return (
    <section id="home" className="relative min-h-screen flex items-center overflow-hidden" data-testid="hero">
      <div className="absolute inset-0">
        <img
          src={IMAGES.hero}
          alt="Professional barber cutting a client's hair at Ajay Haircut in Surrey"
          className="w-full h-full object-cover kenburns"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/60 to-black/20" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6 md:px-12 w-full pt-28 pb-20">
        <div className="max-w-2xl">
          <div className="flex items-center gap-3 mb-6 reveal in-view">
            <div className="flex text-[#C5A059]">
              {[...Array(5)].map((_, i) => <Star key={i} size={16} fill="#C5A059" strokeWidth={0} />)}
            </div>
            <span className="text-white/80 text-xs uppercase tracking-[0.25em] font-semibold">
              {BUSINESS.experience} of Experience
            </span>
          </div>

          <p className="overline mb-4">Premium Men's Grooming · Surrey, BC</p>

          <h1 className="font-display text-white text-5xl md:text-6xl lg:text-7xl font-extrabold leading-[1.02] tracking-tight">
            Premium Men's Haircuts & Beard Grooming in Surrey
          </h1>

          <p className="text-white/80 text-base md:text-lg mt-7 max-w-xl leading-relaxed">
            11+ years of experience delivering precision haircuts, beard styling, perms & men's facials —
            crafted for the modern gentleman.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 mt-10">
            <button
              onClick={onBook}
              data-testid="hero-book-btn"
              className="btn-shine group bg-[#C5A059] text-[#111827] hover:bg-white transition-colors duration-300 px-8 py-4 font-bold uppercase tracking-widest text-sm flex items-center justify-center gap-2"
            >
              Book Appointment
              <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
            </button>
            <a
              href={BUSINESS.phoneHref}
              data-testid="hero-call-btn"
              className="border border-white/40 text-white hover:bg-white hover:text-[#111827] transition-colors duration-300 px-8 py-4 font-bold uppercase tracking-widest text-sm flex items-center justify-center gap-2"
            >
              <Phone size={18} /> Call Now
            </a>
          </div>
        </div>
      </div>

      <div className="absolute bottom-0 inset-x-0 z-10 bg-black/40 backdrop-blur-sm border-t border-white/10">
        <div className="max-w-7xl mx-auto px-6 md:px-12 py-4 flex flex-wrap items-center justify-between gap-4 text-white/85 text-sm">
          <span className="flex items-center gap-2"><Phone size={15} className="text-[#C5A059]" /> {BUSINESS.phone}</span>
          <span className="hidden md:block h-4 w-px bg-white/20" />
          <span>Open Daily 9AM – 9PM · Closed Tuesdays</span>
          <span className="hidden md:block h-4 w-px bg-white/20" />
          <span className="text-[#C5A059] font-semibold uppercase tracking-widest text-xs">Walk-ins Welcome</span>
        </div>
      </div>
    </section>
  );
};

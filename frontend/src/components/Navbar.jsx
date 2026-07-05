import { useEffect, useState } from "react";
import { Menu, X, Phone } from "lucide-react";
import { BUSINESS } from "../data/site";

const LINKS = [
  { label: "Services", href: "#services" },
  { label: "About", href: "#about" },
  { label: "Gallery", href: "#gallery" },
  { label: "Reviews", href: "#reviews" },
  { label: "Contact", href: "#contact" },
];

export const Navbar = ({ onBook }) => {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      data-testid="navbar"
      className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${
        scrolled ? "bg-white/85 backdrop-blur-xl border-b border-black/5 shadow-sm" : "bg-transparent"
      }`}
    >
      <nav className="max-w-7xl mx-auto px-6 md:px-12 h-[72px] flex items-center justify-between">
        <a href="#home" data-testid="logo" className="flex flex-col leading-none">
          <span className={`font-display text-2xl font-extrabold tracking-tight ${scrolled ? "text-[#111827]" : "text-white"}`}>
            Ajay<span className="text-[#C5A059]">.</span>Haircut
          </span>
          <span className={`text-[10px] tracking-[0.35em] uppercase mt-1 ${scrolled ? "text-gray-400" : "text-white/70"}`}>
            Surrey · BC
          </span>
        </a>

        <div className="hidden lg:flex items-center gap-9">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              data-testid={`nav-${l.label.toLowerCase()}`}
              className={`text-xs uppercase tracking-widest font-semibold transition-colors hover:text-[#C5A059] ${
                scrolled ? "text-gray-700" : "text-white/90"
              }`}
            >
              {l.label}
            </a>
          ))}
        </div>

        <div className="hidden lg:flex items-center gap-3">
          <a
            href={BUSINESS.phoneHref}
            data-testid="nav-call"
            className={`flex items-center gap-2 text-sm font-semibold transition-colors hover:text-[#C5A059] ${
              scrolled ? "text-[#111827]" : "text-white"
            }`}
          >
            <Phone size={16} strokeWidth={2} /> {BUSINESS.phone}
          </a>
          <button
            onClick={onBook}
            data-testid="nav-book-btn"
            className="btn-shine bg-[#111827] text-white hover:bg-[#C5A059] transition-colors duration-300 px-6 py-3 text-xs uppercase tracking-widest font-bold"
          >
            Book Now
          </button>
        </div>

        <button
          className={`lg:hidden ${scrolled || open ? "text-[#111827]" : "text-white"}`}
          onClick={() => setOpen((v) => !v)}
          data-testid="mobile-menu-toggle"
          aria-label="Toggle menu"
        >
          {open ? <X size={26} /> : <Menu size={26} />}
        </button>
      </nav>

      {open && (
        <div className="lg:hidden bg-white border-t border-black/5 px-6 py-6 flex flex-col gap-5" data-testid="mobile-menu">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className="text-sm uppercase tracking-widest font-semibold text-gray-800"
            >
              {l.label}
            </a>
          ))}
          <a href={BUSINESS.phoneHref} className="flex items-center gap-2 text-sm font-semibold text-[#111827]">
            <Phone size={16} /> {BUSINESS.phone}
          </a>
          <button
            onClick={() => { setOpen(false); onBook(); }}
            data-testid="mobile-book-btn"
            className="bg-[#111827] text-white px-6 py-3 text-xs uppercase tracking-widest font-bold"
          >
            Book Now
          </button>
        </div>
      )}
    </header>
  );
};

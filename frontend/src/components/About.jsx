import { Award, Users, Clock, ArrowRight } from "lucide-react";
import { BUSINESS, IMAGES } from "../data/site";
import { useReveal } from "../hooks/useReveal";

const STATS = [
  { icon: Clock, value: "11+", label: "Years Experience" },
  { icon: Users, value: "5,000+", label: "Happy Clients" },
  { icon: Award, value: "5.0", label: "Average Rating" },
];

export const About = ({ onBook }) => {
  const ref = useReveal();
  return (
    <section id="about" className="py-24 md:py-32 bg-white overflow-hidden" data-testid="about">
      <div className="max-w-7xl mx-auto px-6 md:px-12 grid lg:grid-cols-2 gap-14 lg:gap-20 items-center">
        <div ref={ref} className="reveal relative">
          <div className="relative">
            <img src={IMAGES.aboutInterior} alt="Ajay Haircut barbershop interior in Surrey" className="w-full h-[520px] object-cover" />
            <div className="absolute -bottom-8 -right-4 md:-right-8 bg-[#111827] text-white p-8 max-w-[220px]">
              <p className="font-display text-4xl font-extrabold text-[#C5A059]">{BUSINESS.experience}</p>
              <p className="text-sm text-white/70 mt-2 uppercase tracking-widest">Of master barbering in Surrey</p>
            </div>
          </div>
        </div>

        <div>
          <p className="overline mb-4">Our Story</p>
          <h2 className="font-display text-4xl md:text-5xl font-extrabold text-[#111827] tracking-tight leading-tight">
            A tradition of precision & personal care
          </h2>
          <div className="text-gray-500 mt-6 space-y-4 text-base md:text-lg leading-relaxed">
            <p>
              For over 11 years, <span className="text-[#111827] font-semibold">Ajay Haircut</span> has been Surrey's
              trusted destination for premium men's grooming. What began with a pair of scissors and a passion for
              detail has grown into a reputation built on skill, consistency and genuine care.
            </p>
            <p>
              Every client receives personalized service in a welcoming, professional environment — whether it's a
              classic cut, a sharp skin fade, a beard sculpt or a refreshing men's facial. We take the time to get it
              right, every single visit.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-4 mt-10">
            {STATS.map((st) => (
              <div key={st.label} className="border-l-2 border-[#C5A059] pl-4">
                <st.icon size={20} className="text-[#C5A059] mb-2" strokeWidth={1.5} />
                <p className="font-display text-2xl md:text-3xl font-extrabold text-[#111827]">{st.value}</p>
                <p className="text-xs text-gray-500 mt-1 uppercase tracking-wide">{st.label}</p>
              </div>
            ))}
          </div>

          <button
            onClick={onBook}
            data-testid="about-book-btn"
            className="btn-shine group mt-10 inline-flex items-center gap-2 bg-[#111827] text-white hover:bg-[#C5A059] transition-colors duration-300 px-8 py-4 font-bold uppercase tracking-widest text-sm"
          >
            Book Your Visit <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
          </button>
        </div>
      </div>
    </section>
  );
};

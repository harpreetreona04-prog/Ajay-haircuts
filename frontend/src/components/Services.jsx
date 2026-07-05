import { Scissors, Sparkles, Wind, Waves, Leaf, Brush, Baby, Droplets, ArrowUpRight } from "lucide-react";
import { SERVICES } from "../data/site";
import { useReveal } from "../hooks/useReveal";

const ICONS = { Scissors, Sparkles, Wind, Waves, Leaf, Brush, Baby, Droplets };

const ServiceCard = ({ s, onBook, index }) => {
  const ref = useReveal();
  const Icon = ICONS[s.icon] || Scissors;
  return (
    <div
      ref={ref}
      className="reveal group bg-white border border-gray-100 hover:border-[#C5A059]/40 shadow-sm hover:shadow-xl transition-all duration-500 hover:-translate-y-1"
      style={{ animationDelay: `${(index % 4) * 90}ms` }}
      data-testid={`service-card-${index}`}
    >
      <div className="relative h-52 overflow-hidden">
        <img src={s.img} alt={s.title} className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent" />
        <div className="absolute top-4 left-4 w-11 h-11 bg-white/95 backdrop-blur flex items-center justify-center">
          <Icon size={20} strokeWidth={1.5} className="text-[#C5A059]" />
        </div>
      </div>
      <div className="p-7">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-display text-xl font-bold text-[#111827] leading-snug">{s.title}</h3>
          <span className="text-[#C5A059] font-bold text-sm whitespace-nowrap mt-1">{s.price}</span>
        </div>
        <p className="text-gray-500 text-sm mt-3 leading-relaxed">{s.desc}</p>
        <button
          onClick={onBook}
          data-testid={`service-book-${index}`}
          className="mt-5 flex items-center gap-1.5 text-xs uppercase tracking-widest font-bold text-[#111827] hover:text-[#C5A059] transition-colors"
        >
          Book This <ArrowUpRight size={15} className="group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
        </button>
      </div>
    </div>
  );
};

export const Services = ({ onBook }) => {
  return (
    <section id="services" className="py-24 md:py-32 bg-[#FAFAFA]" data-testid="services">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="max-w-2xl mb-14">
          <p className="overline mb-4">What We Do</p>
          <h2 className="font-display text-4xl md:text-5xl font-extrabold text-[#111827] tracking-tight leading-tight">
            Grooming services crafted for the modern man
          </h2>
          <p className="text-gray-500 mt-5 text-base md:text-lg">
            From razor-sharp skin fades to relaxing men's facials — every service is delivered with
            precision and care. <span className="text-[#111827] font-semibold">All facial treatments are for men only.</span>
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {SERVICES.map((s, i) => (
            <ServiceCard key={s.title} s={s} onBook={onBook} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
};

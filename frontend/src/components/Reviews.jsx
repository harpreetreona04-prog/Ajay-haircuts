import { Star, Quote } from "lucide-react";
import { REVIEWS, IMAGES } from "../data/site";
import { useReveal } from "../hooks/useReveal";

const ReviewCard = ({ r, index }) => {
  const ref = useReveal();
  return (
    <div
      ref={ref}
      className="reveal bg-white/95 backdrop-blur p-8 md:p-10 border border-[#C5A059]/20"
      style={{ animationDelay: `${index * 120}ms` }}
      data-testid={`review-${index}`}
    >
      <Quote size={32} className="text-[#C5A059]" fill="#C5A059" />
      <div className="flex text-[#C5A059] mt-5 mb-4">
        {[...Array(5)].map((_, i) => <Star key={i} size={16} fill="#C5A059" strokeWidth={0} />)}
      </div>
      <p className="font-display text-lg md:text-xl text-[#111827] leading-relaxed">"{r.text}"</p>
      <p className="text-sm text-gray-500 mt-6 uppercase tracking-widest font-semibold">— {r.author}</p>
    </div>
  );
};

export const Reviews = () => {
  return (
    <section id="reviews" className="relative py-24 md:py-32 overflow-hidden" data-testid="reviews">
      <div className="absolute inset-0">
        <img src={IMAGES.ctaInterior} alt="" className="w-full h-full object-cover" />
        <div className="absolute inset-0 bg-[#111827]/92" />
      </div>
      <div className="relative z-10 max-w-7xl mx-auto px-6 md:px-12">
        <div className="text-center max-w-2xl mx-auto mb-14">
          <p className="overline mb-4">Client Reviews</p>
          <h2 className="font-display text-4xl md:text-5xl font-extrabold text-white tracking-tight leading-tight">
            Trusted by gentlemen across Surrey
          </h2>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {REVIEWS.map((r, i) => <ReviewCard key={i} r={r} index={i} />)}
        </div>
      </div>
    </section>
  );
};

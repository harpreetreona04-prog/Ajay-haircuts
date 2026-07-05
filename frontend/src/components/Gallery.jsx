import { GALLERY } from "../data/site";
import { useReveal } from "../hooks/useReveal";

const GalleryItem = ({ item, index, className }) => {
  const ref = useReveal();
  return (
    <div
      ref={ref}
      className={`reveal group relative overflow-hidden cursor-pointer ${className}`}
      style={{ animationDelay: `${(index % 4) * 80}ms` }}
      data-testid={`gallery-item-${index}`}
    >
      <img src={item.img} alt={item.label} className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" />
      <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent opacity-80 group-hover:opacity-95 transition-opacity" />
      <div className="absolute bottom-0 left-0 p-6">
        <span className="text-[#C5A059] text-[10px] uppercase tracking-[0.25em] font-bold">Ajay Haircut</span>
        <h3 className="text-white font-display text-xl md:text-2xl font-bold mt-1">{item.label}</h3>
      </div>
    </div>
  );
};

export const Gallery = () => {
  // Bento layout spans
  const spans = [
    "sm:col-span-2 sm:row-span-2 h-64 sm:h-full",
    "h-64",
    "h-64",
    "h-64",
    "h-64",
    "sm:col-span-2 h-64",
    "h-64",
  ];
  return (
    <section id="gallery" className="py-24 md:py-32 bg-[#FAFAFA]" data-testid="gallery">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6 mb-14">
          <div className="max-w-xl">
            <p className="overline mb-4">The Work</p>
            <h2 className="font-display text-4xl md:text-5xl font-extrabold text-[#111827] tracking-tight leading-tight">
              A gallery of clean cuts & craftsmanship
            </h2>
          </div>
          <p className="text-gray-500 text-sm md:text-base max-w-sm">
            Skin fades, classic cuts, beard trims, perms, men's facials and our shop interior — see the results
            for yourself.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 auto-rows-[16rem]">
          {GALLERY.map((item, i) => (
            <GalleryItem key={item.label} item={item} index={i} className={spans[i]} />
          ))}
        </div>
      </div>
    </section>
  );
};

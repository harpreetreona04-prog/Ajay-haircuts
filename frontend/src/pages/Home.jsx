import { useState } from "react";
import { Navbar } from "../components/Navbar";
import { Hero } from "../components/Hero";
import { Services } from "../components/Services";
import { About } from "../components/About";
import { Gallery } from "../components/Gallery";
import { Reviews } from "../components/Reviews";
import { Contact } from "../components/Contact";
import { Footer } from "../components/Footer";
import { BookingDialog } from "../components/BookingDialog";
import { Toaster } from "../components/ui/sonner";
import { CalendarCheck } from "lucide-react";

export default function Home() {
  const [bookOpen, setBookOpen] = useState(false);
  const openBook = () => setBookOpen(true);

  return (
    <div className="bg-[#FAFAFA] min-h-screen">
      <Navbar onBook={openBook} />
      <main>
        <Hero onBook={openBook} />
        <Services onBook={openBook} />
        <About onBook={openBook} />
        <Gallery />
        <Reviews />
        <Contact onBook={openBook} />
      </main>
      <Footer onBook={openBook} />

      {/* Floating mobile Book button */}
      <button
        onClick={openBook}
        data-testid="floating-book-btn"
        className="lg:hidden fixed bottom-5 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 bg-[#C5A059] text-[#111827] px-7 py-4 font-bold uppercase tracking-widest text-xs shadow-2xl"
      >
        <CalendarCheck size={16} /> Book Now
      </button>

      <BookingDialog open={bookOpen} onOpenChange={setBookOpen} />
      <Toaster position="top-center" richColors />
    </div>
  );
}

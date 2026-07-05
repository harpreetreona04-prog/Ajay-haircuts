# PRD — Ajay Haircut (Premium Men's Barber Landing Page)

## Original Problem Statement
Modern, premium, mobile-first website for a men's barber shop "Ajay Haircut" (Surrey, BC, phone (778) 344-2550, 11+ years experience). Services, online booking (service → date/time → info → confirmation), gallery, reviews, contact w/ Google map, social links, footer, SEO + local business schema. Payments requested but user chose to SKIP (booking only). Confirmation emails via Resend.

## User Choices
- Theme: Light with gold accents (#C5A059 accent, #111827 ink, #FAFAFA bg)
- Payments: SKIPPED (booking only)
- Booking confirmation email: YES (Resend)
- Map: Surrey, BC placeholder embed
- Logo: text-based gold "Ajay.Haircut"

## Architecture
- Frontend: React (CRA/craco), Tailwind, shadcn/ui, framer-motion available, lucide-react icons, Playfair Display + Manrope fonts. Single-page anchored sections.
- Backend: FastAPI + MongoDB (motor). Routes prefixed /api.
- Email: Resend SDK (async via asyncio.to_thread), sends confirmation on booking create.

## Implemented (2026-07)
- Hero (ken-burns bg, dual CTAs, hours bar), Services grid (8 services, men-only facial note), About (stats), Bento Gallery (7 categories), Reviews (3 testimonials), Contact (form + tel + Google map iframe + socials), Footer (quick links, services, legal).
- Sticky glass navbar, floating mobile Book button, smooth scroll.
- Booking: multi-step dialog (service → date/time w/ live availability → info → confirmation). Backend: POST/GET /api/bookings, GET /api/bookings/availability, POST /api/contact.
- SEO: meta title/description/keywords, OG + Twitter tags, HairSalon LocalBusiness JSON-LD.
- Tested end-to-end: backend 100%, frontend 100% (iteration_1.json).

## Backlog / Next
- Payments: REMOVED per user (booking-only, no deposit). Stripe deposit flow was built then reverted on user request.
- P1: Verify a domain in Resend to email real customers (sandbox only sends to verified/owner addresses).
- P2: Admin dashboard to view/manage bookings; slot-collision uniqueness guard on (date,time).
- P2: Real business address + precise map pin; gallery lightbox.

## Email
- Customer confirmation + owner notification (harpreetreona04@gmail.com) sent via Resend on each booking. Sandbox delivers only to verified owner until a domain is verified.

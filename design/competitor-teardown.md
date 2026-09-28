# Competitor & reference-site teardown (design)

Date: 2026-09-26. Method: I downloaded each homepage's raw HTML with curl and, where available, its main stylesheets. A Python script then extracted the title, meta description, h1/h2, the most frequent hex colours, `font-family` / `@font-face` names, script hosts and framework markers. For the qualitative read (section order, CTAs, tone) I also used WebFetch on 8 sites. Everything below is grade D (marketing pages, observed directly), and every URL was actually fetched. Hex values are **the most frequent colours in the HTML/CSS**, not official brand palettes. "n/o" means not observable, usually because the site is a JS-rendered SPA or builder output.

## A. BCI / neurotech (12)

| Site | Layout / hero (observed) | Palette (top observed hex) | Type | Imagery / 3D | Tone | Conversion | Stack clues |
|---|---|---|---|---|---|---|---|
| neuralink.com | SPA shell. Title "Pioneering Brain Computer Interfaces". Meta: "restore autonomy... unlock human potential" | theme-color #000000 (dark) | n/o (SPA) | n/o in HTML (SPA; swiper.css present) | Visionary, medical mission | n/o | Vite-style `/assets/static/index.*.css` SPA, GTM |
| synchron.com | h1 **"Still you."** Sub "implantable BCIs to protect what makes you human". Hero, then procedure, "meet the users", product | #FCFCF7, #F1F2EE, #13452A, #25593B, #09341E, #E3F3E8 (off-white + deep green) | **interphases** + interphasesMono (display light weight) | User photos, YouTube, SVG ripple | Humane, minimal, calm | "See if you're eligible", "Explore the technology", "Join our study" | Next.js, Sanity CMS |
| paradromics.com | h1 "Some of the most important breakthroughs / Start with a simple act of connection". Sections: vision, NYT press, Connexus product, CEO quote, clinical study | #06080C (near black), #F2EDE6 (warm cream) | n/o (custom WP theme) | Lottie + GSAP, video, brain graphic | Aspirational ("human possibility") | Learn more, Clinical study, community signup | WordPress, GSAP, Lottie, jsDelivr |
| precisionneuro.io | h1 "The brain-computer interface that will change everything". Then applications, patients, vision, 15+ clinical partner logos, stats, news, newsletter | #F3F3F3, #E1E1E1, #49555C, #5D676D, #D7E2E9, accent #CD3824 (red), #EBE66C | **FFF Acid Grotesk**, **Immortel Colera** (display), **ABC Monument Grotesk Mono** | Hero photo/render, video, logo carousel | Bold, confident, clinical credibility | "Partner with us", "Get in touch", newsletter | Next.js, Sanity |
| blackrockneurotech.com | h1 **"Empowered by thought"**. Video hero, stats band, capabilities, institutions, **For Researchers / For Patients dual cards**, newsletter | theme #fff, accent #C89A74 (bronze), #32373C | **GT Super Display** (serif display) + **Apercu Pro** | Hero video, WebGL/canvas markers | Inspirational and clinical | Dual audience CTAs, newsletter | WordPress, GTM |
| openbci.com | SPA. Docs site: top nav + left sidebar (Getting Started, Cyton, Ganglion, Software, For Developers, FAQ) | #011326 (navy), #F98025 (orange), #030A12, #102337, #9AADCE | **Montserrat**, Fira Code | GUI GIF with real EEG | Community, open-source, welcoming | Shop, forum, GitHub | Vite SPA, Zendesk |
| emotiv.com | h1 "Meet EPOC X PRO / The Leader in Real-World Neuroscience" (hero carousel) | #09153B (deep navy, dominant), #ECEEF6, #5A6BA3, #3363FF (blue) | **Google Sans Flex**, Fragment Mono | Product renders, video | Product/consumer-research, superlative | Shop, HubSpot forms | Framer, HubSpot |
| neurable.com | h1 "The Mind. Unlocked" / "Enabling Everyday Devices with Neurotechnology". As Seen In, mission, vision | #0A0A0B, cream #F6F3EC, coral **#E45A47**, #181E25 | **Matter SQ**, Lato | Video, GSAP | Consumer lifestyle, mission-driven | Shopify store, Klaviyo | Webflow, GSAP, Shopify |
| kernel.com | h1 "Defining the future of brain health". Principles, "From brain data to insight", longitudinal tracking, products, research | #2D2F5F (indigo), **#997AE4** (lavender), #8B8DA7, #F9F9F9 | **Inter**, monospace | SVG, data-report visuals (no heavy 3D) | Evidence-based wellness | "Participate today", "Book a scan"; nav splits **For Clinics / For Developers** | Gatsby |
| gtec.at | h2-led, ALL-CAPS: "BUILDING THE GLOBAL PLATFORM FOR BCIs", trusted by institutions, global network, "proven at scale", 50,000+ community CTA | theme **#005284** (corporate blue), #2563EB, #6B7280 | **Oswald** + **Lato** (Google Fonts) | Product photos, video (Plyr), maps | Corporate/industrial, scale claims | Newsletter, shop (WooCommerce) | WordPress + WooCommerce, HubSpot |
| neuroelectrics.com | Title "Revolutionazing Brain Therapy" (sic). Featured projects, partners, contact | #000000, greys #8C8C91/#525258, accent **#1A6AFF**, #F7F6F5 | Roboto, Madefor, custom webfont | Lottie, GSAP, WebGL, video | Therapeutic mission | Contact forms | Wix |
| brainflow.org | h1 "BrainFlow". Key Features, Community, Latest News | Bootstrap defaults | **Lora** + **Open Sans** | Minimal | Open-source, practical | GitHub, docs | Static site + Bootstrap, Font Awesome |

## B. Developer infrastructure / data platforms (6)

| Site | Layout / hero | Palette | Type | Imagery | Tone | Conversion | Stack |
|---|---|---|---|---|---|---|---|
| stripe.com | h1 "Financial infrastructure to grow your revenue". Animated gradient-wave hero, logo carousel, product cards, scale stats, enterprise/startup case studies, developer section, news | **#533AFD** (indigo), #F5A623, #FB76FA, #424770, dark #181818 | **Söhne** (sohne-var), Source Code Pro | Animated gradient/canvas, product UI | Confident, precise, scale | "Get started", "Sign up with Google", "Contact sales" | Next.js, Contentful |
| vercel.com | h1 "Agentic Infrastructure". Sections: agents, apps, platforms, recently shipped, Agent Stack, Core Platform, **Security** | #FAFAFA, #EAEAEA, #1F1F1F, **#0070F3** | **Geist Sans / Geist Mono** (+ Geist Pixel) | Monochrome diagrams, product UI | Terse and technical | Deploy / Get a demo | Next.js, Tailwind |
| supabase.com | h1 "Build in a weekend / Scale to millions". Product grid (DB, Auth, Edge Functions, Storage, Realtime, Vector), "Open source from day one", SOC 2 mention | dark #1C1C1C, **#3ECF8E** (green), #BDA4FF, #6B35DC, #FFCDA1 | **Inter**, Manrope, Source Code Pro, Departure Mono | Product UI, code | Friendly dev, open-source | "Start your project", free tier | Next.js, Tailwind |
| snowflake.com | h1 animated "Code / Work". Simplify data+AI, architecture, customers, ecosystem, news | #042130 (deep teal), #D4F0FA, #C6EDF1, #249EDC, #E59DBC | **Texta**, Lato, **Space Mono** | Lottie, GSAP, illustration | Enterprise, benefit-led | Start trial, demo | Adobe EDS (hlx), Lottie |
| databricks.com | h1 "One database for AI, apps and agents". Build/run, customer wins, analyst recognition, spotlight | #1B3139 (dark teal), **#FF3621** (red), #F9F7F4 (warm paper), #DCE0E2 | **DM Sans**, **DM Mono**, Merriweather | Product UI, illustration | Enterprise, confident | Try free, demo | Gatsby, Tailwind |
| benchling.com | h1 "AI for every scientist. Breakthroughs for all." Logo carousel, value props, 6 product areas, modalities, services, testimonials with metrics, demo CTA | **#000650** (deep navy, dominant), #000DB5 | **Graphik** + GT America Mono | Product UI screenshots, Lottie, Wistia | Science-forward, professional | "Request a demo" | Next.js, Contentful |

## C. Patterns observed

1. **Two design families in neurotech.** (a) *Clinical-humane*: light or cream backgrounds, green/neutral palettes, light-weight display type, human stories (Synchron, Precision, Blackrock, Kernel). (b) *Dark-tech*: near-black or navy with one electric accent (Neuralink #000, Emotiv #09153B, OpenBCI #011326 plus orange, Paradromics #06080C plus cream).
2. **Warm cream is a recurring "humanising" neutral.** Paradromics #F2EDE6, Neurable #F6F3EC, Synchron #FCFCF7, Databricks #F9F7F4.
3. **Neurotech sites sell to patients and clinicians. None sells a data platform.** Kernel's "For Developers" and Blackrock's "For Researchers" come closest. The B2B-infrastructure voice (Stripe, Vercel, Supabase) is **absent from the BCI sector**, which is a positioning gap for us.
4. **Audience split is standard.** Blackrock (Researchers/Patients), Kernel (Clinics/Developers) and Precision (For Clinicians) all use it. Our Researchers / Hardware companies split fits the sector.
5. **Grotesk plus mono is the house style of infra.** Söhne + Source Code Pro, Geist + Geist Mono, Inter + Source Code Pro, DM Sans + DM Mono, Graphik + GT America Mono. Neurotech adds a serif display for gravitas: GT Super (Blackrock), Immortel Colera (Precision).
6. **Trust signals.** Infra sites use scale stats and customer logos. We have **neither**, and the brief forbids inventing them. Substitute transparent roadmaps, open methods, public benchmarks with code, and an honest compliance status board.
7. **Motion.** GSAP and Lottie are common (Paradromics, Neurable, Snowflake, Neuroelectrics). Real WebGL is rare (Blackrock, Neuroelectrics). A tasteful 3D or live-signal hero would stand out.
8. **Stack.** Next.js with a headless CMS (Sanity/Contentful) dominates the better sites. WordPress, Wix and Webflow sit at the long tail.

## D. Borrow / avoid

**Borrow**
- Stripe/Vercel: one-sentence infra headline plus a code sample in the hero area, and a dedicated Security section.
- Supabase: free tier up front ("Start free"), product-grid storytelling, open-source goodwill.
- Benchling: science-first voice, product UI as imagery.
- Blackrock/Kernel: explicit audience split cards.
- Synchron: restraint and calm. One strong line beats five claims.
- Databricks/Paradromics: warm paper neutral (#F9F7F4 / #F2EDE6) to soften a technical brand.
- OpenBCI docs: sidebar docs IA for the eventual Docs site.

**Avoid**
- Patient-outcome and therapy language ("restore", "therapy", "revolutionising"). It is out of scope and a regulatory risk for a data platform.
- Unverifiable superlatives ("highest performing", "the leader", "will change everything").
- Fake logo walls and stats. Use "early-access" and "design partner" framing until real.
- Heavy video heroes and builder bloat. Emotiv (~1.8 MB HTML) and Neuroelectrics (~3 MB HTML, Wix) are slow.
- ALL-CAPS corporate headings (g.tec), which read dated.
- Typos in headings: Neuroelectrics' title reads "Revolutionazing".

## E. Sources (fetched 2026-09-26)
https://neuralink.com · https://neuralink.com/blog/ · https://synchron.com · https://www.paradromics.com · https://precisionneuro.io · https://blackrockneurotech.com · https://openbci.com · https://docs.openbci.com · https://www.emotiv.com · https://www.neurable.com · https://www.kernel.com · https://www.gtec.at · https://www.neuroelectrics.com · https://brainflow.org · https://stripe.com · https://vercel.com · https://supabase.com · https://www.snowflake.com · https://www.databricks.com · https://www.benchling.com
Stylesheets fetched for: neuralink, openbci, stripe, vercel, supabase, synchron, precisionneuro, neurable. The extraction scripts and raw HTML are in the session scratchpad and were not kept in the project.

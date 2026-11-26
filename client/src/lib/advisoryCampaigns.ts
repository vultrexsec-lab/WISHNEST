/**
 * WishNest × ArrowX — campaign-configurable advisory landing content.
 * Add variants without rewriting the page shell.
 */

export type AdvisoryTopic =
  | "land"
  | "hospitality"
  | "reimagined"
  | "second-homes"
  | "architecture";

export type PresentationItem = {
  id: string;
  title: string;
  cover: string;
  /** Optional real media — when set, opens protected full viewer instead of slide deck */
  mediaType?: "pdf" | "video";
  mediaSrc?: string;
  subtitle?: string;
  slides: { title: string; body: string; image?: string }[];
};

export type ProjectItem = {
  id: string;
  name: string;
  location?: string;
  category: string;
  status: "completed" | "ongoing" | "concept";
  image: string;
  images?: string[];
  description: string;
};

export type AdvisoryCampaign = {
  topic: AdvisoryTopic;
  path: string;
  metaTitle: string;
  metaDescription: string;
  headline: string;
  support: string;
  heroImage: string;
  heroVideo?: string;
  aiOpening: string;
  whatsappPrefill: string;
  presentations: PresentationItem[];
  projects: ProjectItem[];
  calendarUrl?: string;
};

const img = {
  land: "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=1600&q=80",
  land2: "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=1200&q=80",
  land3: "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=1200&q=80",
  hospitality: "https://images.unsplash.com/photo-1582719508461-905c673771fd?w=1600&q=80",
  hospitality2: "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=1200&q=80",
  hospitality3: "https://images.unsplash.com/photo-1571896349842-33c89424de2d?w=1200&q=80",
  reimagined: "https://images.unsplash.com/photo-1613490493576-7fde63acd811?w=1600&q=80",
  reimagined2: "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=1200&q=80",
  second: "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=1600&q=80",
  second2: "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=1200&q=80",
  arch: "https://images.unsplash.com/photo-1600585154526-990dced4db0d?w=1600&q=80",
  arch2: "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=1200&q=80",
  arch3: "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=1200&q=80",
};

export const ADVISORY_CAMPAIGNS: Record<AdvisoryTopic, AdvisoryCampaign> = {
  land: {
    topic: "land",
    path: "/advisory/land",
    metaTitle: "What could your land become? | WishNest × ArrowX",
    metaDescription:
      "Explore your land's development potential with WishNest and the architectural expertise of ArrowX.",
    headline: "Your land could be worth ₹100+ Crore.",
    support: "Not because of where it is. Because of what it can become. Luxury villa communities · Boutique resorts · Wellness retreats.",
    heroImage: "/advisory/images/bridge-house-render.png",
    heroVideo: "/advisory/videos/land-potential.mp4",
    aiOpening:
      "You've been exploring how land can become a high-value hospitality destination. I'm here to continue that conversation — no forms, just clarity on what is possible with your site.",
    whatsappPrefill:
      "Hi ArrowX, I was looking at the land potential work on WishNest. I'd like to explore what is possible with my land.",
    presentations: [
      {
        id: "land-potential-film",
        title: "Your land could be worth ₹100+ Crore",
        subtitle: "How premium land + ₹5 Cr becomes a ₹100 Cr+ destination",
        cover: "/advisory/covers/land-film.jpg",
        mediaType: "video",
        mediaSrc: "/advisory/videos/land-potential.mp4",
        slides: [{ title: "Land as hospitality asset", body: "Luxury villa communities, boutique resorts, wellness retreats." }],
      },
      {
        id: "your-house-hills",
        title: "Your House + The Hills",
        subtitle: "Hill homes that work with nature",
        cover: "/advisory/covers/your-house-01.jpg",
        mediaType: "pdf",
        mediaSrc: "/advisory/pdfs/your-house-the-hills.pdf",
        slides: [{ title: "Work with the mountain", body: "Renovation that respects slopes, water paths and stone foundations." }],
      },
      {
        id: "tons-river",
        title: "Tons River Private Retreat",
        subtitle: "Purkul – Dehradun · Architectural Concept",
        cover: "/advisory/covers/tons-01.jpg",
        mediaType: "pdf",
        mediaSrc: "/advisory/pdfs/tons-river-private-retreat.pdf",
        slides: [{ title: "Tons River", body: "Private retreat concept on the Tons corridor." }],
      },
      {
        id: "tehri-pine",
        title: "Lake-Facing Terraced Villa Community",
        subtitle: "Tehri Lake · Signature Hillside Development",
        cover: "/advisory/covers/tehri-01.jpg",
        mediaType: "pdf",
        mediaSrc: "/advisory/pdfs/tehri-lake-pine-cone.pdf",
        slides: [{ title: "Tehri Lake", body: "Lake-facing terraced villa community." }],
      },
      {
        id: "satva",
        title: "SATVA — Himalayan Village Rehabilitation",
        subtitle: "Regenerative Tourism + Wellness Cluster",
        cover: "/advisory/covers/satva-01.jpg",
        mediaType: "pdf",
        mediaSrc: "/advisory/pdfs/satva.pdf",
        slides: [{ title: "SATVA", body: "Sustainable Architecture for Transformative Village Acceleration." }],
      },
      {
        id: "modular-village",
        title: "Modular Village Vision",
        subtitle: "Future-ready hillside living",
        cover: "/advisory/covers/modular.jpg",
        mediaType: "video",
        mediaSrc: "/advisory/videos/modular-village.mp4",
        slides: [{ title: "Modular living", body: "Solar modular homes and regenerative infrastructure." }],
      },
      {
        id: "forest-valley",
        title: "Forest Valley Wellness Villas",
        subtitle: "Mussoorie · Wellness-led hillside community",
        cover: "/advisory/covers/forest-01.jpg",
        mediaType: "pdf",
        mediaSrc: "/advisory/pdfs/forest-valley-wellness.pdf",
        slides: [{ title: "Forest Valley", body: "Senior-friendly wellness villas with circular utilities." }],
      },
      {
        id: "breaking-cover",
        title: "Breaking Cover — Ancestral Home",
        subtitle: "Pauri Garhwal · Reimagining heritage",
        cover: "/advisory/covers/breaking-01.jpg",
        mediaType: "pdf",
        mediaSrc: "/advisory/pdfs/breaking-cover.pdf",
        slides: [{ title: "Breaking Cover", body: "Strategic rupture — preserving the past while projecting into the future." }],
      },
      {
        id: "majkhali",
        title: "Majkhali 2-Acre Community",
        subtitle: "Uttarakhand · Curated villa development",
        cover: "/advisory/covers/majkhali-01.jpg",
        mediaType: "pdf",
        mediaSrc: "/advisory/pdfs/majkhali-community.pdf",
        slides: [{ title: "Majkhali", body: "Luxury sustainable hill community on 2 acres." }],
      },
      {
        id: "khaniyara",
        title: "Khaniyara Riverfront Sky Villa",
        subtitle: "Kangra, Himachal · Building with the mountain",
        cover: "/advisory/covers/khaniyara-01.jpg",
        mediaType: "pdf",
        mediaSrc: "/advisory/pdfs/khaniyara-sky-villa.pdf",
        slides: [{ title: "Khaniyara", body: "Luxury hillside residence & boutique hospitality concept." }],
      },
      {
        id: "proposed-villa",
        title: "Proposed Villa & Resort",
        subtitle: "Arrow Design · Concept presentation",
        cover: "/advisory/covers/proposed-01.jpg",
        mediaType: "pdf",
        mediaSrc: "/advisory/pdfs/proposed-villa-resort.pdf",
        slides: [{ title: "Proposed Villa & Resort", body: "Architectural concept by Arrow Design." }],
      },
      {
        id: "hilltop",
        title: "Hilltop Horizon Estate",
        subtitle: "Private residence · ArrowX Architecture",
        cover: "/advisory/covers/hilltop-01.jpg",
        mediaType: "pdf",
        mediaSrc: "/advisory/pdfs/hilltop-horizon-estate.pdf",
        slides: [{ title: "Hilltop Horizon", body: "Private residence design study." }],
      },
      {
        id: "52-acre",
        title: "52-Acre Terrain Villa Community",
        subtitle: "Mangaon, Maharashtra",
        cover: "/advisory/covers/fiftytwo-01.jpg",
        mediaType: "pdf",
        mediaSrc: "/advisory/pdfs/52-acre-terrain.pdf",
        slides: [{ title: "52 Acre Community", body: "Strategic development proposal for terrain villa community." }],
      },
      {
        id: "garisen",
        title: "Garisen Future City",
        subtitle: "AI-powered content city concept (VIREXA)",
        cover: "/advisory/covers/garisen-01.jpg",
        mediaType: "pdf",
        mediaSrc: "/advisory/pdfs/garisen-future-city.pdf",
        slides: [{ title: "Garisen", body: "Representational concept — not proposed for the hills." }],
      },
      {
        id: "bridge-diagram",
        title: "Bridge House — Terrain Response",
        subtitle: "Extreme water & debris flow design",
        cover: "/advisory/images/bridge-house-diagram.png",
        mediaType: "pdf",
        mediaSrc: "/advisory/pdfs/your-house-the-hills.pdf",
        slides: [{ title: "Bridge House", body: "Raised contour roads and wire-net barriers." }],
      },
    ],
    projects: [
      {
        id: "bridge-house",
        name: "Bridge House",
        location: "Mountain stream crossing",
        category: "Extreme terrain architecture",
        status: "concept",
        image: "/advisory/images/bridge-house-render.png",
        images: [
          "/advisory/images/bridge-house-render.png",
          "/advisory/images/bridge-house-diagram.png",
        ],
        description:
          "A precision-engineered residence that spans a live water course. Raised contour roads, wire-net debris barriers and extreme-flow design allow the house to coexist with seasonal torrents.",
      },
      {
        id: "p-ridge",
        name: "Ridge Retreat Studies",
        location: "Himalayan foothills",
        category: "Land & hospitality",
        status: "concept",
        image: img.land2,
        description:
          "Landscape-led studies exploring low-impact hospitality clusters along ridgelines and terraces.",
      },
      {
        id: "p-valley",
        name: "Valley Estate Framework",
        location: "Western Ghats",
        category: "Master planning",
        status: "ongoing",
        image: img.land3,
        description:
          "A phased framework balancing conservation buffers with selective residential and retreat parcels.",
      },
      {
        id: "p-coast",
        name: "Coastal Parcel Options",
        category: "Feasibility",
        status: "concept",
        image: img.hospitality2,
        description:
          "Comparative massing and experience options for a coastal landholding under environmental constraints.",
      },
    ],
  },
  hospitality: {
    topic: "hospitality",
    path: "/advisory/hospitality",
    metaTitle: "Create a destination. Not just a hotel. | WishNest × ArrowX",
    metaDescription:
      "Explore distinctive hospitality concepts, architecture and development possibilities with WishNest and ArrowX.",
    headline: "Create a destination. Not just a hotel.",
    support: "Explore distinctive hospitality concepts, architecture and development possibilities.",
    heroImage: img.hospitality,
    aiOpening:
      "Hello. Tell me about the hospitality project you're exploring. I'd be happy to help you take the next step.",
    whatsappPrefill:
      "Hello WishNest, I would like to discuss a hospitality development project.",
    presentations: [
      {
        id: "hosp-dest",
        title: "Developing a distinctive hospitality destination",
        cover: img.hospitality2,
        slides: [
          {
            title: "Beyond keys and occupancy",
            body: "Memorable destinations are defined by place, ritual, and architectural clarity.",
            image: img.hospitality2,
          },
          {
            title: "Concept before construction",
            body: "Positioning and guest journey decisions should precede detailed design.",
          },
        ],
      },
      {
        id: "hosp-position",
        title: "Hospitality concepts and positioning",
        cover: img.hospitality3,
        slides: [
          {
            title: "Who is it for?",
            body: "Clear guest intent guides scale, amenities, and the architecture of arrival.",
            image: img.hospitality3,
          },
        ],
      },
      {
        id: "hosp-arch",
        title: "Architecture and guest experience",
        cover: img.arch2,
        slides: [
          {
            title: "Spatial narrative",
            body: "ArrowX designs sequences of space that feel inevitable in the landscape.",
            image: img.arch2,
          },
        ],
      },
    ],
    projects: [
      {
        id: "h1",
        name: "Courtyard Hotel Concept",
        location: "Rajasthan",
        category: "Boutique hotel",
        status: "concept",
        image: img.hospitality2,
        description: "A courtyard-centred hospitality scheme rooted in regional craft and climate response.",
      },
      {
        id: "h2",
        name: "Forest Pavilion Resort",
        category: "Resort",
        status: "ongoing",
        image: img.hospitality3,
        description: "Dispersed pavilions prioritising canopy, privacy, and low visual impact.",
      },
      {
        id: "h3",
        name: "Urban Boutique Study",
        category: "Hotel",
        status: "completed",
        image: img.arch3,
        description: "Compact urban hospitality with a strong public room and restrained guest floors.",
      },
    ],
  },
  reimagined: {
    topic: "reimagined",
    path: "/advisory/reimagined",
    metaTitle: "See your property differently. | WishNest Reimagined™ × ArrowX",
    metaDescription:
      "Reimagine your existing hospitality property through architecture, repositioning and renewed guest experiences.",
    headline: "See your property differently.",
    support:
      "Reimagine your existing hospitality property through architecture, repositioning and renewed guest experiences.",
    heroImage: img.reimagined,
    aiOpening: "Hello. What would you like to change or improve about your existing property?",
    whatsappPrefill:
      "Hello WishNest, I would like to discuss reimagining my existing hotel or resort.",
    presentations: [
      {
        id: "re-1",
        title: "Reimagining existing hospitality properties",
        cover: img.reimagined2,
        slides: [
          {
            title: "What already works",
            body: "Repositioning starts with honest appraisal of structure, location, and guest perception.",
            image: img.reimagined2,
          },
        ],
      },
      {
        id: "re-2",
        title: "Property repositioning",
        cover: img.hospitality,
        slides: [
          {
            title: "Signal and substance",
            body: "Design updates must match the story you want the market to believe.",
          },
        ],
      },
      {
        id: "re-3",
        title: "Transformation through design",
        cover: img.arch3,
        slides: [
          {
            title: "Selective intervention",
            body: "High-impact zones — arrival, rooms, F&B — often unlock more value than full rebuilds.",
            image: img.arch3,
          },
        ],
      },
    ],
    projects: [
      {
        id: "r1",
        name: "Lobby & Room Refresh Study",
        category: "Reimagined™",
        status: "concept",
        image: img.reimagined2,
        description: "Targeted spatial and material upgrades for a mid-scale resort seeking premium perception.",
      },
      {
        id: "r2",
        name: "Wing Repositioning",
        category: "Hospitality",
        status: "ongoing",
        image: img.hospitality,
        description: "Phased renovation strategy for an operational property with limited closure windows.",
      },
      {
        id: "r3",
        name: "Arrival Sequence Redesign",
        category: "Architecture",
        status: "completed",
        image: img.arch2,
        description: "A clearer arrival narrative and landscape edge for an established hill property.",
      },
    ],
  },
  "second-homes": {
    topic: "second-homes",
    path: "/advisory/second-homes",
    metaTitle: "A home away from the ordinary. | WishNest × ArrowX",
    metaDescription:
      "Explore distinctive private residences shaped by their landscapes and the way you wish to live.",
    headline: "A home away from the ordinary.",
    support: "Explore distinctive private residences shaped by their landscapes and the way you wish to live.",
    heroImage: img.second,
    aiOpening: "Hello. Tell me a little about the home or private retreat you have been imagining.",
    whatsappPrefill: "Hello WishNest, I would like to discuss a second home or private retreat.",
    presentations: [
      {
        id: "sh-1",
        title: "The second-home journey",
        cover: img.second2,
        slides: [
          {
            title: "How you will live there",
            body: "Seasonality, privacy, and ease of arrival matter as much as square footage.",
            image: img.second2,
          },
        ],
      },
      {
        id: "sh-2",
        title: "Designing with the landscape",
        cover: img.land2,
        slides: [
          {
            title: "Site first",
            body: "Orientation, views, and environmental response define the dwelling.",
            image: img.land2,
          },
        ],
      },
      {
        id: "sh-3",
        title: "Private residences and retreats",
        cover: img.arch3,
        slides: [
          {
            title: "Quiet luxury",
            body: "Restraint in form and material often reads as greater quality than excess.",
          },
        ],
      },
    ],
    projects: [
      {
        id: "s1",
        name: "Hillside Pavilion Home",
        location: "Nilgiris",
        category: "Residence",
        status: "concept",
        image: img.second2,
        description: "A light-touch residence organised around terraces and monsoon-aware detailing.",
      },
      {
        id: "s2",
        name: "Courtyard Family Retreat",
        category: "Second home",
        status: "ongoing",
        image: img.second,
        description: "Inward-looking privacy with selective landscape openings.",
      },
      {
        id: "s3",
        name: "Lake Edge Studio",
        category: "Retreat",
        status: "completed",
        image: img.arch,
        description: "A compact lakeside structure for intermittent occupation and quiet work.",
      },
    ],
  },
  architecture: {
    topic: "architecture",
    path: "/advisory/architecture",
    metaTitle: "Architecture begins with a vision. | ArrowX × WishNest",
    metaDescription:
      "Translate your aspirations into thoughtful architecture with ArrowX, supported by WishNest advisory.",
    headline: "Architecture begins with a vision.",
    support: "Translate your aspirations into thoughtful architecture with ArrowX.",
    heroImage: img.arch,
    aiOpening:
      "Hello. Tell me about the project you would like to create, and I'll help you connect with the appropriate team.",
    whatsappPrefill: "Hello WishNest, I would like to discuss an architectural project with ArrowX.",
    presentations: [
      {
        id: "a-1",
        title: "ArrowX design philosophy",
        cover: img.arch2,
        slides: [
          {
            title: "Clarity over novelty",
            body: "Architecture that endures prioritises structure, light, and place over fashion.",
            image: img.arch2,
          },
        ],
      },
      {
        id: "a-2",
        title: "Integrated architecture and master planning",
        cover: img.arch3,
        slides: [
          {
            title: "One continuum",
            body: "Site strategy and building design are developed together, not in sequence of isolation.",
          },
        ],
      },
      {
        id: "a-3",
        title: "From vision to architecture",
        cover: img.hospitality2,
        slides: [
          {
            title: "Process",
            body: "Briefing, options, and refinement — with the client present at each meaningful decision.",
            image: img.hospitality2,
          },
        ],
      },
    ],
    projects: [
      {
        id: "a1",
        name: "Stone & Timber Residence",
        category: "Architecture",
        status: "completed",
        image: img.arch2,
        description: "A material-honest dwelling with deep eaves and a strong relationship to ground.",
      },
      {
        id: "a2",
        name: "Cultural Pavilion",
        category: "Public",
        status: "concept",
        image: img.arch3,
        description: "A flexible pavilion for gathering, exhibition, and landscape events.",
      },
      {
        id: "a3",
        name: "Campus Planning Study",
        category: "Master planning",
        status: "ongoing",
        image: img.arch,
        description: "Organisational diagrams for a multi-building site with shared landscape cores.",
      },
    ],
  },
};

export function getCampaign(topic: string | undefined): AdvisoryCampaign {
  const key = (topic || "land") as AdvisoryTopic;
  return ADVISORY_CAMPAIGNS[key] || ADVISORY_CAMPAIGNS.land;
}

export const ADVISORY_TOPICS: AdvisoryTopic[] = [
  "land",
  "hospitality",
  "reimagined",
  "second-homes",
  "architecture",
];

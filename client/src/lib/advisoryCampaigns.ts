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
    headline: "What could your land become?",
    support: "Explore its potential with WishNest and the architectural expertise of ArrowX.",
    heroImage: img.land,
    aiOpening:
      "Hello, I'm WishNest's AI project assistant. Tell me a little about your land and what you have in mind. You don't need to prepare anything in advance.",
    whatsappPrefill:
      "Hello WishNest, I would like to discuss the development potential of my land.",
    presentations: [
      {
        id: "land-potential",
        title: "Understanding your land's potential",
        cover: img.land2,
        slides: [
          {
            title: "Site as opportunity",
            body: "Every parcel carries constraints and possibilities — topography, access, climate, and context shape what it can become.",
            image: img.land2,
          },
          {
            title: "From vision to framework",
            body: "A clear development brief aligns landowners, designers, and partners before commitments are made.",
            image: img.land3,
          },
          {
            title: "Next conversations",
            body: "We help you frame options — retreat, hospitality, residential, or mixed — without forcing a single path.",
          },
        ],
      },
      {
        id: "land-destination",
        title: "From land to destination",
        cover: img.land3,
        slides: [
          {
            title: "Place-led development",
            body: "Destinations grow from landscape character, not imported templates.",
            image: img.land3,
          },
          {
            title: "Phasing and feasibility",
            body: "Thoughtful sequencing protects capital while testing demand and design quality.",
          },
        ],
      },
      {
        id: "land-masterplan",
        title: "Development possibilities & master planning",
        cover: img.arch,
        slides: [
          {
            title: "Master planning lens",
            body: "Circulation, open space, and building footprints set the long-term value of the site.",
            image: img.arch,
          },
          {
            title: "Architecture as continuity",
            body: "ArrowX integrates architecture with planning so early decisions support later detail.",
          },
        ],
      },
    ],
    projects: [
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

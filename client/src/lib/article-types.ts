export type ArticleType = "standard" | "review";

// Category slugs that indicate a destination/landmark article (place guide, best-of
// roundup) rather than a single property review.  Must stay in sync with the backend
// _LANDMARK_CATEGORIES frozenset in image_service.py.
export const DESTINATION_CATEGORIES: ReadonlySet<string> = new Set([
  "destinations",
  "destination",
  "best places & destinations",
  "best-of-destinations",
]);

/** True when the article describes a geographic destination rather than a specific property. */
export function isDestinationArticle(article: Article): boolean {
  if (!article.category) return false;
  return DESTINATION_CATEGORIES.has(article.category.trim().toLowerCase());
}

export type ArticleStatus = "draft" | "approved" | "scheduled" | "published";

export type Grade =
  | "A+"
  | "A"
  | "A-"
  | "B+"
  | "B"
  | "B-"
  | "C+"
  | "C"
  | "C-"
  | "D+"
  | "D";

export interface FaqItem {
  question: string;
  answer: string;
}

export interface InternalLink {
  anchor_text: string;
  target_page: string;
  context: string;
  seo_reason: string;
}

export interface Article {
  id: string;
  article_type: ArticleType;
  status: ArticleStatus;
  is_trash: boolean;
  category: string | null;

  headline: string;
  subtitle: string | null;
  full_article: string | null;
  executive_summary: string | null;
  pull_quotes: string[] | null;
  faq_section: FaqItem[] | null;

  seo_title: string | null;
  meta_description: string | null;
  focus_keyword: string | null;
  keywords: string[] | null;
  source_urls: string[] | null;
  image_credits: string[] | null;
  captions: string[] | null;
  alt_text: string[] | null;
  internal_links: InternalLink[] | null;
  hero_image_url: string | null;
  section_image_urls: string[] | null;

  property_snapshot: Record<string, unknown> | null;
  best_for: string[] | null;
  not_ideal_for: string[] | null;
  price_band: string | null;
  location: string | null;
  accessibility: string | null;

  architecture_grade: Grade | null;
  landscape_grade: Grade | null;
  connectivity_grade: Grade | null;
  delight_grade: Grade | null;
  eat_explore_grade: Grade | null;
  // Numeric scores 1.0–10.0 (LLM-generated; power the public score-card UI)
  architecture_score: number | null;
  landscape_score: number | null;
  connectivity_score: number | null;
  delight_score: number | null;
  eat_explore_score: number | null;
  // Server-computed overall ABCDE™ grade (e.g. "A", "B+")
  abcde_overall: string | null;
  developer_lessons: string[] | null;
  key_takeaways: string[] | null;
  wishnest_verdict: string | null;

  linkedin_variations: string[] | null;
  facebook_variations: string[] | null;
  twitter_thread: string[] | null;
  newsletter_summary: string | null;
  suggested_hashtags: string[] | null;
  cta: string | null;

  scheduled_at: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export const ABCDE_GRADES: { key: keyof Article; letter: string; title: string }[] = [
  { key: "architecture_grade", letter: "A", title: "Architecture" },
  { key: "landscape_grade", letter: "B", title: "Biophilic & Landscape & Sustainability" },
  { key: "connectivity_grade", letter: "C", title: "Connectivity & Access" },
  { key: "delight_grade", letter: "D", title: "Delight / Guest Experience" },
  { key: "eat_explore_grade", letter: "E", title: "Eat & Explore" },
];

/** Numeric score dimensions — power the public progress-bar score card. */
export const ABCDE_SCORES: {
  scoreKey: keyof Article;
  gradeKey: keyof Article;
  letter: string;
  title: string;
}[] = [
  { scoreKey: "architecture_score", gradeKey: "architecture_grade", letter: "A", title: "Architecture" },
  { scoreKey: "landscape_score",    gradeKey: "landscape_grade",    letter: "B", title: "Biophilic & Landscape & Sustainability" },
  { scoreKey: "connectivity_score", gradeKey: "connectivity_grade", letter: "C", title: "Connectivity & Access" },
  { scoreKey: "delight_score",      gradeKey: "delight_grade",      letter: "D", title: "Delight / Guest Experience" },
  { scoreKey: "eat_explore_score",  gradeKey: "eat_explore_grade",  letter: "E", title: "Eat & Explore" },
];

const GRADE_ORDER: Record<string, number> = {
  "A+": 12, A: 11, "A-": 10,
  "B+": 9, B: 8, "B-": 7,
  "C+": 6, C: 5, "C-": 4,
  "D+": 3, D: 2,
};

export function overallGrade(article: Article): string | null {
  const grades = [
    article.architecture_grade,
    article.landscape_grade,
    article.connectivity_grade,
    article.delight_grade,
    article.eat_explore_grade,
  ].filter(Boolean) as string[];
  if (grades.length === 0) return null;
  const avg =
    grades.reduce((sum, g) => sum + (GRADE_ORDER[g] ?? 0), 0) / grades.length;
  const rounded = Math.round(avg);
  const entry = Object.entries(GRADE_ORDER).find(([, v]) => v === rounded);
  return entry ? entry[0] : grades[0];
}

export function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-IN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export interface ConciergeThemeOption {
  id: string;
  label: string;
  description: string;
}

export interface ConciergeIntentResult {
  selectedThemeIds: string[];
  matchedLabels: string[];
  summary: string;
  confidence: "clear" | "guided" | "fallback";
}

const KEYWORD_HINTS: Record<string, string[]> = {
  underground_dance: ["dance", "techno", "rave", "club", "warehouse", "dj", "electronic", "edm"],
  indie_live_music: ["indie", "band", "live music", "concert", "gig", "show", "alt", "guitar"],
  gallery_nights: ["gallery", "art", "arty", "opening", "museum", "installation", "exhibit"],
  jazz_intimate_shows: ["jazz", "listening", "intimate", "date", "quiet", "sax", "piano"],
  hiphop_rap_shows: ["hip hop", "hip-hop", "rap", "beats", "mc"],
  comedy_nights: ["comedy", "standup", "stand-up", "funny", "laugh"],
  dive_bar_scene: ["dive", "bar", "low key", "low-key", "casual", "beer"],
  rooftop_lounges: ["rooftop", "lounge", "upscale", "views", "cocktail", "dress"],
  late_night_food: ["food", "bite", "dinner", "restaurant", "popup", "pop-up", "late night", "hungry"],
  queer_nightlife: ["queer", "drag", "lgbtq", "inclusive", "gay"],
  collector_marketplaces: ["market", "swap", "vintage", "records", "collector", "thrift"],
  student_intellectual_scene: ["talk", "reading", "campus", "lecture", "book", "ideas"],
  ambitious_professional_scene: ["networking", "founder", "career", "professional", "industry"],
  style_design_shopping: ["style", "design", "shopping", "menswear", "fashion", "retail"],
  creative_meetups: ["meetup", "workshop", "creative", "maker", "founder", "community"],
};

const BUDGET_HINTS = ["cheap", "free", "under $30", "budget", "low cost", "affordable"];
const LATE_HINTS = ["late", "after hours", "after-hours", "midnight", "tonight"];

function normalizeText(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

function labelMatchesText(option: ConciergeThemeOption, normalizedText: string) {
  const label = normalizeText(option.label);
  const description = normalizeText(option.description);
  return label
    .split(/[^a-z0-9]+/)
    .filter(Boolean)
    .some((word) => normalizedText.includes(word)) || description.includes(normalizedText);
}

export function parseConciergeIntent(
  text: string,
  options: ConciergeThemeOption[],
  quickThemeIds: string[] = [],
): ConciergeIntentResult {
  const normalizedText = normalizeText(text);
  const selected = new Set(quickThemeIds);

  if (normalizedText) {
    for (const option of options) {
      const hints = KEYWORD_HINTS[option.id] ?? [];
      if (labelMatchesText(option, normalizedText) || hints.some((hint) => normalizedText.includes(hint))) {
        selected.add(option.id);
      }
    }
  }

  if (normalizedText && BUDGET_HINTS.some((hint) => normalizedText.includes(hint))) {
    selected.add("dive_bar_scene");
    selected.add("late_night_food");
  }

  if (normalizedText && LATE_HINTS.some((hint) => normalizedText.includes(hint))) {
    selected.add("underground_dance");
    selected.add("late_night_food");
  }

  const selectedThemeIds = [...selected].filter((id) => options.some((option) => option.id === id)).slice(0, 5);
  const matchedLabels = selectedThemeIds
    .map((id) => options.find((option) => option.id === id)?.label)
    .filter((label): label is string => Boolean(label));

  if (matchedLabels.length) {
    return {
      selectedThemeIds,
      matchedLabels,
      summary: `Pulse will steer this run toward ${matchedLabels.slice(0, 3).join(", ")}.`,
      confidence: normalizedText ? "clear" : "guided",
    };
  }

  return {
    selectedThemeIds: [],
    matchedLabels: [],
    summary: "Tell Pulse the vibe first, or pick one of the quick intents.",
    confidence: "fallback",
  };
}

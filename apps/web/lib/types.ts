export type ScoreBand = "high" | "medium" | "low";

export interface InterestTopic {
  id: string;
  label: string;
  confidence: number;
  sourceSignals: string[];
  boosted: boolean;
  muted: boolean;
}

export interface UserConstraint {
  city: string;
  neighborhood?: string | null;
  zipCode?: string | null;
  radiusMiles: number;
  budgetLevel: "free" | "under_30" | "under_75" | "flexible";
  preferredDays: string[];
  socialMode: "solo" | "group" | "either";
}

export interface RecommendationReason {
  title: string;
  detail: string;
}

export interface RecommendationFreshness {
  discoveredAt?: string | null;
  lastVerifiedAt?: string | null;
  freshnessLabel: string;
}

export interface RecommendationProvenance {
  sourceName: string;
  sourceKind: string;
  sourceConfidence: number;
  sourceConfidenceLabel: string;
  sourceBaseUrl?: string | null;
  hasTicketUrl: boolean;
}

export interface RecommendationScoreBreakdownItem {
  key: string;
  label: string;
  impactLabel: string;
  detail: string;
  contribution: number;
  direction: "positive" | "negative";
}

export interface TravelEstimate {
  mode: "walk" | "transit";
  label: string;
  minutes: number;
}

export interface VenueRecommendationCard {
  venueId: string;
  venueName: string;
  neighborhood: string;
  address: string;
  eventTitle: string;
  eventId: string;
  startsAt: string;
  priceLabel: string;
  scoreBand: ScoreBand;
  score: number;
  travel: TravelEstimate[];
  reasons: RecommendationReason[];
  freshness: RecommendationFreshness;
  provenance: RecommendationProvenance;
  scoreSummary?: string | null;
  scoreBreakdown: RecommendationScoreBreakdownItem[];
  secondaryEvents: Array<{
    eventId: string;
    title: string;
    startsAt: string;
  }>;
}

export interface MapVenuePin {
  venueId: string;
  venueName: string;
  latitude: number;
  longitude: number;
  scoreBand: ScoreBand;
  selected: boolean;
}

export interface MapViewport {
  latitude: number;
  longitude: number;
  latitudeDelta: number;
  longitudeDelta: number;
}

export interface MapContext {
  serviceArea: string;
  activeAnchorLabel: string;
  activeAnchorSource: string;
  requestedAnchorLabel?: string | null;
  requestedAnchorSource?: string | null;
  requestedAnchorWithinServiceArea: boolean;
  usedFallbackAnchor: boolean;
  fallbackReason?: string | null;
}

export interface FeedbackReason {
  key: string;
  label: string;
}

export interface AuthViewer {
  userId: string;
  email: string;
  displayName?: string | null;
  isAuthenticated: boolean;
  isDemo: boolean;
  authMethod: "demo" | "supabase" | "pulse_session" | "email_header";
  redditConnected: boolean;
  redditConnectionMode: "none" | "live" | "sample";
  spotifyConnected: boolean;
}

export interface ThemeEvidenceCount {
  key: string;
  count: number;
}

export interface ThemeEvidenceSnippet {
  type: string;
  subreddit?: string | null;
  snippet: string;
  permalink?: string | null;
}

export interface ThemeEvidence {
  matchedSubreddits: ThemeEvidenceCount[];
  matchedKeywords: ThemeEvidenceCount[];
  topExamples: ThemeEvidenceSnippet[];
  providerNotes: string[];
}

export interface TasteTheme {
  id: string;
  label: string;
  confidence: number;
  confidenceLabel: string;
  evidence: ThemeEvidence;
}

export interface TasteProfileResponse {
  source: string;
  sourceKey: string;
  username?: string | null;
  generatedAt: string;
  themes: TasteTheme[];
  unmatchedActivity: Record<string, unknown>;
}

export interface RecommendationsMapResponse {
  viewport: MapViewport;
  pins: MapVenuePin[];
  cards: Record<string, VenueRecommendationCard>;
  generatedAt: string;
  displayTimezone: string;
  userConstraint: UserConstraint;
  mapContext: MapContext;
}

export interface RecommendationDriverSummary {
  key: string;
  label: string;
  impactLabel: string;
  averageContribution: number;
  venueCount: number;
  topVenues: string[];
}

export interface RecommendationFeedbackReasonSummary {
  key: string;
  label: string;
  count: number;
  weightedStrength: number;
}

export interface RecommendationDebugVenue {
  rank: number;
  venueId: string;
  venueName: string;
  score: number;
  scoreBand: ScoreBand;
  scoreSummary?: string | null;
  topDrivers: RecommendationScoreBreakdownItem[];
}

export interface RecommendationDebugSummary {
  runId?: string | null;
  generatedAt?: string | null;
  rankingModel?: string | null;
  contextHash?: string | null;
  shortlistSize: number;
  summary?: string | null;
  mapContext: MapContext;
  activeTopics: string[];
  mutedTopics: string[];
  topSaveReasons: RecommendationFeedbackReasonSummary[];
  topDismissReasons: RecommendationFeedbackReasonSummary[];
  topPositiveDrivers: RecommendationDriverSummary[];
  topNegativeDrivers: RecommendationDriverSummary[];
  venues: RecommendationDebugVenue[];
}

export interface RecommendationRunComparisonItem {
  venueId: string;
  venueName: string;
  neighborhood: string;
  currentRank?: number | null;
  previousRank?: number | null;
  rankDelta?: number | null;
  currentScore?: number | null;
  previousScore?: number | null;
  scoreDelta?: number | null;
  scoreBand?: ScoreBand | null;
  scoreSummary?: string | null;
  movement: "new" | "dropped" | "up" | "down" | "steady";
}

export interface RecommendationRunComparison {
  currentRunId?: string | null;
  previousRunId?: string | null;
  currentGeneratedAt?: string | null;
  previousGeneratedAt?: string | null;
  currentContextHash?: string | null;
  previousContextHash?: string | null;
  summary?: string | null;
  shortlistSize: number;
  comparableVenueCount: number;
  newEntrants: RecommendationRunComparisonItem[];
  droppedVenues: RecommendationRunComparisonItem[];
  movers: RecommendationRunComparisonItem[];
  steadyLeaders: RecommendationRunComparisonItem[];
}

export interface ArchiveSnapshot {
  runId: string;
  kind: "live" | "preview" | "scheduled" | "snapshot";
  title: string;
  generatedAt: string;
  deliveredAt?: string | null;
  items: VenueRecommendationCard[];
}

export interface ArchiveResponse {
  items: VenueRecommendationCard[];
  displayTimezone: string;
  history: ArchiveSnapshot[];
}

export interface LocationAnchorPayload {
  neighborhood?: string;
  zipCode?: string;
  latitude?: number;
  longitude?: number;
  source: "live" | "zip" | "neighborhood";
}

export interface AnchorSaveResponse {
  ok: boolean;
  mapContext: MapContext;
}

export interface SupplySyncResponse {
  ok: boolean;
  candidateCount: number;
  accepted: number;
  sourcesCreated: number;
  venuesCreated: number;
  eventsCreated: number;
  occurrencesCreated: number;
  status: string;
}

export interface DigestPreviewResponse {
  recipientEmail: string;
  subject: string;
  preheader: string;
  html: string;
  text: string;
  generatedAt: string;
  items: VenueRecommendationCard[];
}

export interface DigestSendResponse {
  ok: boolean;
  recipientEmail: string;
  provider: string;
  status: string;
}

export interface EmailPreferences {
  weeklyDigestEnabled: boolean;
  digestDay: string;
  digestTimeLocal: string;
  timezone: string;
}

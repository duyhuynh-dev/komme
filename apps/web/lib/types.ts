export type ScoreBand = "high" | "medium" | "low";

export interface InterestTopic {
  id: string;
  label: string;
  confidence: number;
  sourceProvider?: string;
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

export interface RecommendationPersonalizationSource {
  sourceProvider: string;
  label: string;
  influence: "supporting" | "reducing" | "suppressed" | string;
  topicLabels: string[];
  detail?: string | null;
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
  ticketUrl?: string | null;
  scoreBand: ScoreBand;
  score: number;
  travel: TravelEstimate[];
  reasons: RecommendationReason[];
  freshness: RecommendationFreshness;
  provenance: RecommendationProvenance;
  scoreSummary?: string | null;
  scoreBreakdown: RecommendationScoreBreakdownItem[];
  personalizationProvenance: RecommendationPersonalizationSource[];
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

export interface TonightPlannerFallbackOption {
  venueId: string;
  venueName: string;
  eventId: string;
  eventTitle: string;
  neighborhood: string;
  startsAt: string;
  priceLabel: string;
  scoreBand: ScoreBand;
  sourceConfidence?: number;
  hopLabel?: string | null;
  fallbackReason: string;
  selected: boolean;
}

export interface TonightPlannerRerouteOption {
  venueId: string;
  venueName: string;
  eventId: string;
  eventTitle: string;
  neighborhood: string;
  startsAt: string;
  priceLabel: string;
  scoreBand: ScoreBand;
  sourceConfidence?: number;
  hopLabel?: string | null;
  roleLabel?: string | null;
  sourceKind: "fallback" | "next_stop";
  rerouteReason: string;
}

export interface TonightPlannerStop {
  role: "pregame" | "main_event" | "late_option" | "backup";
  roleLabel: string;
  venueId: string;
  venueName: string;
  eventId: string;
  eventTitle: string;
  neighborhood: string;
  startsAt: string;
  priceLabel: string;
  scoreBand: ScoreBand;
  sourceConfidence?: number;
  hopLabel?: string | null;
  roleReason: string;
  confidence: "high" | "medium" | "watch";
  confidenceLabel: string;
  confidenceReason: string;
  selected: boolean;
  fallbacks: TonightPlannerFallbackOption[];
}

export interface TonightPlannerResponse {
  status: "ready" | "limited" | "empty";
  title: string;
  summary?: string | null;
  planningNote?: string | null;
  planWindowStart?: string | null;
  planWindowEnd?: string | null;
  planWindowLabel?: string | null;
  executionStatus: "idle" | "locked" | "swapped";
  executionNote?: string | null;
  activeTargetEventId?: string | null;
  activeTargetVenueName?: string | null;
  outcomeStatus: "idle" | "pending" | "attended" | "skipped";
  outcomeNote?: string | null;
  rerouteStatus: "idle" | "available" | "unavailable";
  rerouteNote?: string | null;
  rerouteOption?: TonightPlannerRerouteOption | null;
  sessionId?: string | null;
  sessionStatus?: "active" | "completed" | "expired" | string | null;
  activeStop?: TonightPlannerStop | null;
  remainingStops: TonightPlannerStop[];
  droppedStops: TonightPlannerStop[];
  recompositionReason?: string | null;
  lastRecomputedAt?: string | null;
  lifecycleReason?: string | null;
  createdFreshBecauseStale?: boolean;
  lastEventAt?: string | null;
  stops: TonightPlannerStop[];
}

export type EventPlanFallbackOption = TonightPlannerFallbackOption;
export type EventPlanRerouteOption = TonightPlannerRerouteOption;
export type EventPlanStop = TonightPlannerStop;
export type EventPlanResponse = TonightPlannerResponse;

export interface FeedbackReason {
  key: string;
  label: string;
}

export interface ConnectedSourceHealth {
  provider: string;
  connected: boolean;
  latestRunStatus?: string | null;
  latestRunAt?: string | null;
  stale: boolean;
  currentlyInfluencingRanking: boolean;
  confidenceState: "healthy" | "degraded" | "inactive" | "disconnected" | "unknown" | string;
  healthReason?: string | null;
  debugReason?: string | null;
}

export interface ThemeCatalogItem {
  id: string;
  label: string;
  description: string;
}

export interface AuthViewer {
  userId: string;
  email: string;
  displayName?: string | null;
  isAuthenticated: boolean;
  isDemo: boolean;
  authMethod: "demo" | "supabase" | "pulse_session" | "email_header";
  spotifyConnected: boolean;
  spotifyTasteHealth: ConnectedSourceHealth;
  connectedSources: ConnectedSourceHealth[];
}

export interface ThemeEvidenceCount {
  key: string;
  count: number;
}

export interface ThemeEvidenceSnippet {
  type: string;
  snippet: string;
  permalink?: string | null;
}

export interface ThemeEvidence {
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
  tonightPlanner: TonightPlannerResponse;
  eventPlan?: EventPlanResponse;
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

export interface RecommendationOutcomeAttribution {
  action: string;
  source: "feedback" | "planner" | "digest" | string;
  venueId?: string | null;
  venueName?: string | null;
  eventId?: string | null;
  eventTitle?: string | null;
  topicKeys: string[];
  reasonKeys: string[];
  recencyLabel: string;
  direction: "positive" | "negative" | "neutral" | string;
  explanation: string;
}

export interface RecommendationTopicSourceSummary {
  sourceProvider: string;
  label: string;
  topicCount: number;
  averageConfidence: number;
  topTopics: string[];
  connected: boolean;
  latestRunStatus?: string | null;
  latestRunAt?: string | null;
  stale: boolean;
  currentlyInfluencingRanking: boolean;
  confidenceState: string;
  healthReason?: string | null;
  debugReason?: string | null;
}

export interface RecommendationMovementCue {
  key: string;
  label: string;
  delta: number;
  direction: "positive" | "negative";
}

export interface RecommendationMovementExplanation {
  title: string;
  detail: string;
  direction: "positive" | "negative" | "neutral" | string;
  source: "feedback" | "planner" | "source_health" | "profile" | "score" | string;
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

export interface RecommendationSupplyQualityRollup {
  sourceName: string;
  sourceKind: string;
  recommendationCount: number;
  eventCount: number;
  staleVerificationCount: number;
  weakSourceConfidenceCount: number;
  missingTicketUrlCount: number;
  missingSourceUrlCount: number;
  averageRawSourceConfidence: number;
  averageEffectiveSourceConfidence: number;
  topTrustReasons: string[];
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
  activeTopicSources: RecommendationTopicSourceSummary[];
  supplyQualityRollups: RecommendationSupplyQualityRollup[];
  topSaveReasons: RecommendationFeedbackReasonSummary[];
  topConfirmedSaveReasons: RecommendationFeedbackReasonSummary[];
  topDismissReasons: RecommendationFeedbackReasonSummary[];
  outcomeAttributions: RecommendationOutcomeAttribution[];
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
  movementCues: RecommendationMovementCue[];
  movementExplanation: RecommendationMovementExplanation[];
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

export interface PlannerSessionDebugEvent {
  eventId: string;
  eventType: string;
  recommendationId?: string | null;
  createdAt: string;
  metadata: Record<string, unknown>;
}

export interface PlannerSessionDebugStopScore {
  eventId: string;
  venueName: string;
  role: string;
  score: number;
  reasons: string[];
}

export interface PlannerSessionDebugItem {
  sessionId: string;
  sessionStatus: string;
  recommendationRunId?: string | null;
  contextHash?: string | null;
  activeStopEventId?: string | null;
  budgetLevel: string;
  timezone: string;
  createdAt: string;
  updatedAt: string;
  initialStopCount: number;
  remainingStopCount: number;
  droppedStopCount: number;
  recompositionReason?: string | null;
  lifecycleReason?: string | null;
  createdFreshBecauseStale: boolean;
  replacedSessionId?: string | null;
  recompositionScores: PlannerSessionDebugStopScore[];
  events: PlannerSessionDebugEvent[];
}

export interface PlannerSessionDebugResponse {
  sessions: PlannerSessionDebugItem[];
}

export type EventPlanSessionDebugEvent = PlannerSessionDebugEvent;
export type EventPlanSessionDebugStopScore = PlannerSessionDebugStopScore;
export type EventPlanSessionDebugItem = PlannerSessionDebugItem;
export type EventPlanSessionDebugResponse = PlannerSessionDebugResponse;

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

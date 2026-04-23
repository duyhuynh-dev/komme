from app.taste.errors import InvalidManualSelectionError, UnknownThemeError
from app.taste.profile_contracts import TasteProfile, TasteTheme, ThemeEvidence, ThemeEvidenceSnippet
from app.taste.theme_catalog import THEME_CATALOG, THEME_CATALOG_BY_ID


class ManualThemeProvider:
    source_name = "manual"

    def available_themes(self):
        return list(THEME_CATALOG)

    async def build_profile(self, selected_theme_ids: list[str]) -> TasteProfile:
        deduped_ids = list(dict.fromkeys(selected_theme_ids))
        if not deduped_ids:
            raise InvalidManualSelectionError("Pick at least one theme to build a manual taste profile.")

        unknown_ids = [theme_id for theme_id in deduped_ids if theme_id not in THEME_CATALOG_BY_ID]
        if unknown_ids:
            raise UnknownThemeError(f"Unknown theme selection: {', '.join(unknown_ids)}")

        themes = []
        for theme_id in deduped_ids:
            item = THEME_CATALOG_BY_ID[theme_id]
            themes.append(
                TasteTheme(
                    id=item.id,
                    label=item.label,
                    confidence=48,
                    confidence_label="Emerging",
                    evidence=ThemeEvidence(
                        provider_notes=["Selected manually during onboarding."],
                        top_examples=[
                            ThemeEvidenceSnippet(
                                type="manual",
                                snippet=f"User selected {item.label.lower()} as a taste signal.",
                            )
                        ],
                    ),
                )
            )

        return TasteProfile(
            source="manual",
            source_key="manual-selection",
            themes=themes,
            unmatched_activity={},
        )

# Internationalization and multilingual support

## Product requirement

NEXUS AI TRADER must be designed for users worldwide. The application should be localization-ready for any language for which a reviewed translation catalog can be supplied. Do not claim that every world language is already translated; language coverage grows through translation packs.

## Requirements

1. **Complete UI localization:** navigation, page titles, labels, buttons, tooltips, validation messages, errors, notifications, charts, tables, reports, onboarding, and help text must use translation keys rather than hard-coded user-facing strings.
2. **Language selection:** provide an explicit language selector and persist the user's preference. Automatic browser-language detection may suggest an initial language, but must never prevent manual override.
3. **Fallback behavior:** resolve missing translations through a documented fallback chain (user language, configured fallback such as English). Never show a missing key or crash because a translation is absent.
4. **RTL and LTR:** support right-to-left layout and text direction for Persian, Arabic, Urdu, Hebrew, and other RTL languages, while preserving left-to-right rendering for code, wallet addresses, token symbols, hashes, and URLs.
5. **Locale-aware formatting:** format dates, times, numbers, decimal/group separators, percentages, and currencies according to locale. Keep raw numeric values and machine-readable timestamps independent of display formatting.
6. **Financial correctness:** never translate or mutate ticker symbols, chain names, contract addresses, wallet addresses, API fields, or canonical market identifiers. Localize their descriptions only.
7. **Translation quality:** use reviewed translation catalogs for trading, risk, and financial terminology. Machine translation may be a draft, not an authority for safety-critical warnings or financial meaning.
8. **Extensible catalogs:** adding or updating a language must not require changing strategy, market-data, backtest, or order-execution logic.
9. **Accessibility and layout:** test long translated strings, font fallback, mobile layouts, keyboard navigation, and screen-reader labels.
10. **Tests:** add automated tests for translation-key completeness, fallback behavior, RTL/LTR isolation, locale formatting, and rendering of critical risk warnings in each supported catalog.

## Rollout

- Establish a localization framework and remove hard-coded UI strings.
- Start with Persian and English, then add further language packs in prioritized batches.
- Publish a language as supported only after its critical trading/risk strings and UI flows pass review and tests.
- Keep language coverage and translation-review status visible in project documentation.

## Acceptance criteria

A user can select a supported language and use every implemented screen without untranslated UI fragments (except intentionally language-neutral identifiers). Switching language must not change calculations, signals, prices, backtests, or trading behavior. RTL languages must render correctly on desktop and mobile.

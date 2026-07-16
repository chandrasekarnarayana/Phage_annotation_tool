# Assisted Review

Assisted review helps prioritize likely points while keeping the user in control
of final annotation decisions.

## Suggestion generation

Suggestion models produce `PointSuggestion` rows with image position, score,
label, source model, source modality, density context, uncertainty reason, and
optional multi-modality evidence.

## Review queue

The review queue ranks suggestions by uncertainty and confidence. Reviewers can
accept, reject, skip, filter, and revisit candidates without leaving the
keyboard.

## Keyboard cadence

Common review keys:

- `A`: accept current suggestion;
- `R`: reject current suggestion;
- `N`: next suggestion;
- `P`: previous suggestion;
- `Shift+A`: accept focused suggestion only.

## Stale suggestion guard

The controller can reject acceptance of stale suggestions when the model context
has changed. This protects against applying decisions to candidates generated
under outdated thresholds, ROI state, or annotation context.

## Learning feedback

Accepted and rejected decisions can be routed into interactive learning and
rescore paths. Those updates are kept outside direct GUI rendering so the
interface stays responsive.

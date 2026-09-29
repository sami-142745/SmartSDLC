import { SCORE_TONE_COLOR, scoreTone } from '../ui/ScoreGauge';

/**
 * Rail colour for a file's change bar: heavily deletion-weighted files read as
 * a risk, pure additions read as healthy, everything else stays neutral-green.
 *
 * Lives outside `MonacoDiff` so `DiffViewer` can import it without pulling the
 * editor into the main bundle.
 */
export function diffAccentColor(additions: number, deletions: number) {
  if (additions === 0 && deletions === 0) return '#52525b';
  const total = additions + deletions;
  if (deletions / total > 0.6) return SCORE_TONE_COLOR[scoreTone(45)];
  if (additions / total > 0.6) return SCORE_TONE_COLOR[scoreTone(78)];
  return SCORE_TONE_COLOR[scoreTone(96)];
}

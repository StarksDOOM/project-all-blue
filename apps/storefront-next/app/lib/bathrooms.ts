/**
 * Client-side bath KPI fallback when API returns bathrooms=0 but description has counts.
 * Mirrors backend parse order: structured field first, then prose in raw_description.
 */

export function parseBathroomsFromDescription(text: string): number {
  if (!text.trim()) {
    return 0;
  }

  const normalized = text
    .replace(/\u00a0/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();

  let total = 0;

  const medioMatches = [...normalized.matchAll(/(?:(\d+)\s*)?medio\s*ba[ñn]o/g)];
  for (const match of medioMatches) {
    const count = match[1] ? Number.parseInt(match[1], 10) : 1;
    total += 0.5 * (Number.isFinite(count) ? count : 1);
  }

  const completeMatches = [
    ...normalized.matchAll(/(\d+(?:[.,]\d+)?)\s*ba[ñn]os?\s+complet/g),
  ];
  if (completeMatches.length > 0) {
    const values = completeMatches.map((m) =>
      Number.parseFloat(m[1].replace(",", "."))
    );
    total += Math.max(...values);
  } else {
    const genericMatches = [
      ...normalized.matchAll(
        /(\d+(?:[.,]\d+)?)\s*ba[ñn]os?(?!\s+complet)(?!\s*medio)/g
      ),
    ];
    if (genericMatches.length > 0) {
      const values = genericMatches.map((m) =>
        Number.parseFloat(m[1].replace(",", "."))
      );
      total += Math.max(...values);
    }
  }

  const labeled = normalized.match(/ba[ñn]os?\s*[:=]\s*(\d+(?:[.,]\d+)?)/);
  if (labeled && total === 0) {
    total += Number.parseFloat(labeled[1].replace(",", "."));
  }

  return Math.round(total * 100) / 100;
}

export function resolveBathsForDisplay(
  bathrooms: number,
  rawDescription: string
): number | null {
  if (bathrooms > 0) {
    return bathrooms;
  }
  const parsed = parseBathroomsFromDescription(rawDescription);
  return parsed > 0 ? parsed : null;
}
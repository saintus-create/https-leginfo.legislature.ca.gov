/**
 * Canonical citation and source-link helpers for California Legislative Information.
 *
 * Keep these helpers provider-independent: retrieval/AI code should pass section
 * metadata here rather than constructing leginfo URLs in prompts or UI code.
 */

export const LEGINFO_BASE = 'https://leginfo.legislature.ca.gov';
export const CODE_SECTION_PATH = '/faces/codes_displaySection.xhtml';

export interface LegislativeSectionRef {
  lawCode: string;
  sectionNum: string;
  subsection?: string;
}

export interface LegislativeCitation {
  label: string;
  lawCode: string;
  sectionNum: string;
  url: string;
  subsection?: string;
}

function cleanCode(value: string): string {
  return value.trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
}

function cleanSection(value: string): string {
  // LegInfo accepts section identifiers such as 432.5. Preserve the dot and
  // hyphen because some codes contain compound identifiers.
  return value.trim().replace(/[^A-Za-z0-9.\-]/g, '');
}

/** Build the official LegInfo URL for a code section. */
export function sectionUrl(ref: LegislativeSectionRef): string {
  const lawCode = cleanCode(ref.lawCode);
  const sectionNum = cleanSection(ref.sectionNum);

  if (!lawCode || !sectionNum) {
    throw new Error('Both lawCode and sectionNum are required.');
  }

  const params = new URLSearchParams({
    sectionNum: `${sectionNum}.`,
    lawCode,
  });

  const url = new URL(CODE_SECTION_PATH, LEGINFO_BASE);
  url.search = params.toString();

  if (ref.subsection?.trim()) {
    // Fragment identifiers are local UI navigation, not part of the legal
    // citation itself. Keep them optional and sanitized.
    const subsection = ref.subsection.trim().replace(/[^A-Za-z0-9().\-]/g, '');
    if (subsection) url.hash = subsection;
  }

  return url.toString();
}

/** Convert section metadata into a stable citation object for API/UI output. */
export function citationForSection(ref: LegislativeSectionRef): LegislativeCitation {
  const lawCode = cleanCode(ref.lawCode);
  const sectionNum = cleanSection(ref.sectionNum);
  const subsection = ref.subsection?.trim() || undefined;

  if (!lawCode || !sectionNum) {
    throw new Error('Both lawCode and sectionNum are required.');
  }

  return {
    label: `${lawCode} § ${sectionNum}`,
    lawCode,
    sectionNum,
    ...(subsection ? { subsection } : {}),
    url: sectionUrl({ lawCode, sectionNum, subsection }),
  };
}

/**
 * Best-effort extraction for the common internal UID forms used by the corpus.
 * Examples: FAM:432.5, FAM-432.5, FAM/432.5.
 * Returns null rather than inventing a citation when the UID is ambiguous.
 */
export function citationFromUid(uid: string): LegislativeCitation | null {
  const value = uid.trim();
  const match = /^(?<lawCode>[A-Za-z0-9]+)[:\/-](?<section>[A-Za-z0-9.\-]+)$/.exec(value);
  if (!match?.groups) return null;

  const { lawCode, section } = match.groups;
  return citationForSection({ lawCode, sectionNum: section });
}

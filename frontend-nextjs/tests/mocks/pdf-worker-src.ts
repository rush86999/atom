/**
 * Jest stub for lib/pdf-worker-src.ts (mapped via jest moduleNameMapper).
 * The real module uses webpack's `new URL(..., import.meta.url)`, which the
 * CJS test transform can't parse. Returning "" makes pdf.js fall back to its
 * main-thread fake worker in jsdom — irrelevant for the component tests,
 * which mock the API layer anyway.
 */
export function pdfWorkerSrc(): string {
    return "";
}

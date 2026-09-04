/**
 * PDF.js worker source for the browser bundle.
 *
 * Isolated from PdfFileCanvas so the webpack-only syntax lives in one
 * module: webpack 5 resolves `new URL(..., import.meta.url)` at build time
 * and emits the worker as an asset. Jest maps this module to
 * tests/mocks/pdf-worker-src.ts (import.meta can't be parsed under the CJS
 * transform), where pdf.js degrades to its main-thread fake worker.
 */
export function pdfWorkerSrc(): string {
    return new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
}

/**
 * PDF.js worker source for the browser bundle.
 *
 * WHY THIS IS A RELATIVE SPECIFIER (2026-09-28).
 *
 * The previous form was:
 *
 *     new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url)
 *
 * and it did not work. webpack 5 does not treat a BARE specifier inside
 * `new URL()` as a module request: it resolves it as a RELATIVE path against
 * the importing file, i.e. `<dir>/pdfjs-dist/build/pdf.worker.min.mjs`, which
 * does not exist. The compile then fails with
 *
 *     Module not found: ESM packages (pdfjs-dist/build/pdf.worker.min.mjs)
 *     need to be imported.
 *
 * That is a COMPILE error, so it is not confined to the PDF canvas: the import
 * chain is `pages/canvas/[id].tsx` -> `CanvasPanel` -> `PdfFileCanvas` ->
 * this module, and the failure took down the whole canvas route -- which is
 * also the only surface that attaches canvas context to a chat turn, so canvas
 * editing could not be exercised in a browser at all. Measured on an isolated
 * frontend: `/canvas/<id>` returned 500 with this line, and 200 after the fix.
 *
 * webpack 5 DOES emit an asset for a RELATIVE specifier in `new URL()`, and
 * that is what this uses. `../node_modules/...` resolves correctly both in the
 * checkout (`frontend-nextjs/node_modules`) and in an isolated preview farm
 * (which keeps its own `node_modules` beside its copied sources), so the
 * installed pdfjs-dist build is used rather than a vendored copy that could
 * drift from the pinned version.
 *
 * `pdfWorkerSrc()` returns the emitted asset URL. Jest cannot parse
 * `import.meta` under the CJS transform, so tests map this module to
 * `tests/mocks/pdf-worker-src.ts`, where pdf.js degrades to its main-thread
 * fake worker.
 */
export function pdfWorkerSrc(): string {
    return new URL(
        "../node_modules/pdfjs-dist/build/pdf.worker.min.mjs",
        import.meta.url,
    ).toString();
}

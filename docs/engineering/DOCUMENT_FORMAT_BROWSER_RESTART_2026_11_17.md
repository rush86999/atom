# Common-format documents through the browser and a full restart

Qualified runtime source: `8c142c1019785e0a21b14bda6505bd04a475934e`.
PR [#978](https://github.com/rush86999/atom/pull/978) merged the same tree
`24a6c7d2b81be204c4cfb5f8c6b66f9001277052` as
`02c9b16744e4fc9cfe7c81dce2ebf82cac7bf909`. The runtime reported the PR
head, not the later merge identifier. The original 143 claims / 18 goals and
`app_complete: false` remain unchanged.

Normal browser sign-in, file-chooser upload, detail open/reload, and actual
Text/Markdown/JSON downloads passed for one synthetic DOCX, PDF and CSV.
Each export matched the complete stored extraction, its known synthetic
marker, its response bytes, content hash and extraction revision. Unsigned
access was refused. Native delete controls and actual confirmations returned
verified receipts for the same document; library reloads excluded it, and
stale tabs received 404 with no download and a visible error.

A separate DOCX remained available across a full backend-and-frontend restart
of the same isolated world. Both process IDs changed. Normal browser sign-in
after restart exported the same document ID, extraction identity and exact
three downloaded byte sequences. The three earlier deleted documents still
returned 404 through their normal browser routes, with export controls absent.
The retained DOCX was then deleted through the UI and its stale-tab export was
refused. Both owned services were stopped and their ports refused connections.
An independent artifact check re-read all downloads and verified the hashes
and identical pre/post-restart artifacts.

The cached production frontend was reused: 2,005 tracked files were compared,
with identical web runtime, package and configuration inputs. Differences
were confined to coverage artifacts, generated ambient TypeScript declarations
and native Tauri generated/test fixtures. This is neither a new build nor an
identical-entire-tree claim. No auth injection, fake HTTP, request interception,
provider call or active-app data was used.

Earlier verifier failures remain retained: a missing download folder stopped
before browser activity; the first DOCX run uploaded successfully but assumed
identical API/browser filenames. The API retains `.docx.txt` while the browser
uses `.txt`. The corrected verifier continued that existing upload without
repeating it. A stopped-port probe required explicit network permission; the
read-only retry passed. None was promoted into a product-defect claim.

Limits: small synthetic files and stored-text exports, not original binaries,
all parser variants, cross-user browser breadth, live WorkDrive, generative
model quality or whole Goal 3. Expected extraction text came from the parser
plus an independent fixed marker; this is not a parser-accuracy benchmark.
Cross-surface search remains deferred in the core profile and was not enabled.
The separate authenticated search API evidence retains its original source.
[Filtered browser/restart result](evidence/document_format_browser_restart_20261117/result.json).

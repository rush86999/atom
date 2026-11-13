"""Bounded openpyxl compatibility for out-of-range font family ids.

openpyxl 3.1 validates font family ids as ``0 <= family <= 14`` in two
independent readers, both of which run before any worksheet row is read:

* the shared-string reader always materialises rich-text run properties
  through :class:`openpyxl.cell.rich_text.InlineFont`, even when the workbook
  is opened with ``rich_text=False`` (and even under
  ``read_only=True, data_only=True``), so ``<rPr><family val="...">`` with a
  larger id raises ``ValueError: Max value is 14``;
* the stylesheet reader materialises the workbook font table through
  :class:`openpyxl.styles.fonts.Font`, so a direct
  ``<fonts><font><family val="...">`` with a larger id raises the same error
  (the outer message is ``could not read stylesheet``).

A producer may legally write another font family id in either place. The
package itself is well-formed. The compatibility step below rebuilds an
in-memory copy of the package whose ONLY differences are out-of-range font
family ids (clamped into openpyxl's accepted range). It touches only the exact
``xl/sharedStrings.xml`` and ``xl/styles.xml`` parts, and only
SpreadsheetML-namespaced elements:

* ``sst/si/r/rPr/family`` (shared-string rich-text runs); and
* the direct ``styleSheet/fonts/font/family`` path in the font table.

Same-named parts, roots, or elements in another namespace, a case-variant part
path, and nested font elements (for example ``styleSheet/dxfs``) are left
untouched. It never mutates the caller's bytes, so the caller's provider
digest / byte length / lineage stay bound to the original download. Parsing is
bounded: each inspected part and the uncompressed package size are capped, and
the package is copied as a stream rather than expanded into one giant object.

No monkeypatch is installed; callers hand the returned copy to openpyxl and
keep using the original bytes for identity and evidence.
"""
from __future__ import annotations

import io
import logging
import shutil
import zipfile
from typing import Callable, Dict, Iterable, Optional

logger = logging.getLogger(__name__)

SHARED_STRINGS_PART = "xl/sharedStrings.xml"
STYLES_PART = "xl/styles.xml"
SPREADSHEETML_NAMESPACE = (
    "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
)
_SHARED_STRINGS_ROOT = f"{{{SPREADSHEETML_NAMESPACE}}}sst"
_STYLESHEET_ROOT = f"{{{SPREADSHEETML_NAMESPACE}}}styleSheet"
_RICH_TEXT_RUN_PROPERTIES = f"{{{SPREADSHEETML_NAMESPACE}}}rPr"
_STYLE_FONTS = f"{{{SPREADSHEETML_NAMESPACE}}}fonts"
_STYLE_FONT = f"{{{SPREADSHEETML_NAMESPACE}}}font"
_FONT_FAMILY = f"{{{SPREADSHEETML_NAMESPACE}}}family"

# Cost guards. A workbook whose inspected part exceeds this cannot be checked
# for the font quirk without unbounded memory; the caller then keeps its
# existing failure path (explicit incomplete read, never a fabricated one).
MAX_SHARED_STRINGS_BYTES = 64 * 1024 * 1024
MAX_STYLESHEET_BYTES = 64 * 1024 * 1024
MAX_PACKAGE_UNCOMPRESSED_BYTES = 512 * 1024 * 1024

FAMILY_MIN = 0
FAMILY_MAX = 14  # openpyxl's InlineFont/Font family constraint


def _read_part_bounded(
    archive: zipfile.ZipFile, name: str, limit: int,
) -> Optional[bytes]:
    """Read one zip member, refusing to exceed ``limit`` uncompressed bytes."""
    try:
        info = archive.getinfo(name)
    except KeyError:
        return None
    if info.file_size > limit:
        logger.debug(
            "xlsx compat: %s is %s bytes (cap %s); skipping font "
            "normalisation", name, info.file_size, limit,
        )
        return None
    with archive.open(info, "r") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        logger.debug(
            "xlsx compat: %s exceeded the %s-byte read cap; skipping",
            name, limit,
        )
        return None
    return data


def _clamp_family(element) -> bool:
    """Clamp one ``family`` element into openpyxl's accepted range."""
    raw = element.get("val")
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return False
    if FAMILY_MIN <= value <= FAMILY_MAX:
        return False
    # The numeric id is presentation metadata; dropping it would change the
    # element shape, so clamp to the accepted minimum.
    element.set("val", str(FAMILY_MIN))
    return True


def _shared_string_families(root) -> Iterable:
    """Yield ``rPr/family`` elements from the SpreadsheetML shared-string sst.

    Matches the existing rich-text contract exactly: every
    SpreadsheetML-namespaced ``rPr`` under the exact ``sst`` root, and only its
    direct SpreadsheetML-namespaced ``family`` children.
    """
    for rpr in root.iter(_RICH_TEXT_RUN_PROPERTIES):
        for child in list(rpr):
            if child.tag == _FONT_FAMILY:
                yield child


def _stylesheet_families(root) -> Iterable:
    """Yield only direct ``styleSheet/fonts/font/family`` elements.

    The path is matched element by element, so ``dxfs/dxf/font/family`` or
    elements in another namespace are never eligible.
    """
    for fonts in list(root):
        if fonts.tag != _STYLE_FONTS:
            continue
        for font in list(fonts):
            if font.tag != _STYLE_FONT:
                continue
            for child in list(font):
                if child.tag == _FONT_FAMILY:
                    yield child


def _normalise_part(
    xml_bytes: bytes,
    *,
    expected_root: str,
    family_elements: Callable[[object], Iterable],
    label: str,
) -> tuple[bool, Optional[bytes]]:
    """Clamp out-of-range family ids in one SpreadsheetML part.

    Returns ``(True, None)`` when the part is eligible but needs no change,
    ``(True, rewritten_bytes)`` when it was changed, and ``(False, None)`` when
    the part could not be parsed safely or is not the exact expected root.
    Cell text, values, formulas, and cached formula results live in other
    elements and are copied verbatim.

    Parsing is defusedxml-only. If it is unavailable the copy is declined
    rather than silently falling back to the stdlib parser (which would open
    the DTD/entity path). DTDs and entities are always rejected.
    """
    try:
        from defusedxml import ElementTree as SafeET
    except Exception as exc:  # noqa: BLE001 — no unsafe fallback by design
        logger.warning(
            "xlsx compat: defusedxml unavailable (%s); declining %s "
            "normalisation", exc, label,
        )
        return False, None

    try:
        root = SafeET.fromstring(
            xml_bytes,
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
    except Exception as exc:  # noqa: BLE001 — malformed/unsafe: leave error
        logger.debug(
            "xlsx compat: %s could not be parsed safely: %s", label, exc)
        return False, None

    # Exact OOXML part contents: only the expected SpreadsheetML root is
    # eligible. A same-named element in another namespace, or a different part
    # that happens to contain the same local names, is left untouched.
    if root.tag != expected_root:
        logger.debug(
            "xlsx compat: %s root %r is not the OOXML namespace; declining "
            "normalisation", label, root.tag,
        )
        return False, None

    changed = False
    for element in family_elements(root):
        if _clamp_family(element):
            changed = True

    if not changed:
        return True, None

    # Serialise with the stdlib writer but do NOT call register_namespace:
    # ElementTree may emit generated ns0-style prefixes, which are
    # semantically identical to the original default namespace and avoids
    # process-global namespace state mutation.
    import xml.etree.ElementTree as ET

    try:
        return True, ET.tostring(
            root, encoding="utf-8", xml_declaration=True,
        )
    except Exception as exc:  # noqa: BLE001 — no copy, no compatibility claim
        logger.debug("xlsx compat: %s could not be serialised: %s", label, exc)
        return False, None


def _rebuild_package(
    content: bytes, replacements: Dict[str, bytes],
) -> Optional[bytes]:
    """Copy the package to memory with the given members replaced.

    Every other member is streamed through unchanged (including compression
    type and metadata), so the copy openpyxl receives is the provider's
    package apart from the normalised font metadata.
    """
    output = io.BytesIO()
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as source, zipfile.ZipFile(
            output, "w", allowZip64=True,
        ) as target:
            target.comment = source.comment
            for info in source.infolist():
                if info.filename in replacements:
                    target.writestr(info, replacements[info.filename])
                elif info.is_dir():
                    target.writestr(info, b"")
                else:
                    with source.open(info, "r") as reader, target.open(
                        info, "w",
                    ) as writer:
                        shutil.copyfileobj(reader, writer, 1024 * 1024)
    except Exception as exc:  # noqa: BLE001 — keep the caller's original error
        logger.debug("xlsx compat: package copy failed: %s", exc)
        return None
    return output.getvalue()


def openpyxl_compatible_bytes(
    content: bytes,
    *,
    max_shared_strings_bytes: int = MAX_SHARED_STRINGS_BYTES,
    max_stylesheet_bytes: int = MAX_STYLESHEET_BYTES,
    max_package_uncompressed_bytes: int = MAX_PACKAGE_UNCOMPRESSED_BYTES,
) -> Optional[bytes]:
    """Return a package copy openpyxl can read, or ``None`` when not needed.

    ``None`` means either the workbook has no out-of-range font family id in
    an eligible part (the original bytes are already usable) or a bounded
    check declined (the caller then keeps its normal parse-failure handling).
    The input bytes are never modified.
    """
    if not content:
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            try:
                total_uncompressed = sum(
                    max(0, int(info.file_size or 0))
                    for info in archive.infolist()
                )
            except Exception:  # noqa: BLE001 — malformed package
                return None
            if total_uncompressed > max_package_uncompressed_bytes:
                logger.debug(
                    "xlsx compat: package expands to %s bytes (cap %s); "
                    "skipping normalisation",
                    total_uncompressed, max_package_uncompressed_bytes,
                )
                return None

            present_parts = {
                info.filename for info in archive.infolist()
            }
            part_rules = (
                (
                    SHARED_STRINGS_PART,
                    max_shared_strings_bytes,
                    _SHARED_STRINGS_ROOT,
                    _shared_string_families,
                    "sharedStrings",
                ),
                (
                    STYLES_PART,
                    max_stylesheet_bytes,
                    _STYLESHEET_ROOT,
                    _stylesheet_families,
                    "stylesheet",
                ),
            )
            replacements: Dict[str, bytes] = {}
            for (
                part_name, byte_limit, expected_root, family_elements, label,
            ) in part_rules:
                # A missing part is normal (inline-string workbooks have no
                # sharedStrings table); only an exact-name member is eligible.
                if part_name not in present_parts:
                    continue
                part = _read_part_bounded(archive, part_name, byte_limit)
                if part is None:
                    return None
                accepted, normalised = _normalise_part(
                    part,
                    expected_root=expected_root,
                    family_elements=family_elements,
                    label=label,
                )
                if not accepted:
                    return None
                if normalised is not None:
                    replacements[part_name] = normalised
            if not replacements:
                return None
    except Exception as exc:  # noqa: BLE001 — not a zip / not readable
        logger.debug("xlsx compat: package could not be opened: %s", exc)
        return None

    return _rebuild_package(content, replacements)

"""Data-driven repair of the tenant's identity cluster in the workspace
graph — the ontology half of the outbound-identity contract
(core/outbound_identity.py).

Failure class being repaired (live 2026-09-02): the owner's identity sat in
the graph as three disconnected Person nodes and the company itself existed
as a misparsed Person at an external org, so GraphRAG retrieval over the
cluster could not return one authoritative "our member / our company"
answer — a draft even got signed with a lead's name.

Everything here is resolved PER INSTALL from tenant data; no member or
company names appear in code:

  1. Member identities come from the users table plus the installation
     profile (``identity`` + ``people`` sections). Profile people are
     classified team/external by their own role ("dealer", "vendor" …) or
     email domain — external contacts are NEVER merged or touched.
  2. Person nodes whose name alias-matches a member (token-subset with
     initials: "R. Ma…" ⊆ full name) merge into one canonical node per
     member (exact-name node preferred, else the most connected); edges
     retarget; canonical properties are repaired. Ambiguous fragments that
     match two different members are left alone.
  3. Person nodes alias-matching the company name (the company misparsed
     as a person out of an external signature block) merge into the
     matching Organization node, or are retyped in place when no
     Organization node exists yet.

Idempotent: canonical nodes are flagged (``identity_canonical``) and
re-runs find nothing to do. ``--dry-run`` prints without writing.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import SessionLocal  # noqa: E402
from core.models import GraphEdge, GraphNode, InstallationProfile, User  # noqa: E402
from core.outbound_identity import classify_person_role, _email_domain  # noqa: E402

_STRIP = ".,'-–—’"


def _tokens(name: str) -> list:
    out = []
    for tok in str(name or "").replace(".", " ").split():
        tok = tok.strip(_STRIP).lower()
        if tok:
            out.append(tok)
    return out


def _alias_matches(node_name: str, full_name: str) -> bool:
    """True when the node's name is the full name or a fragment of it
    ("Rish" ⊆ "Rish Maniar", "R. Maniar" ⊆, "Rish M." ⊆)."""
    a, b = _tokens(node_name), _tokens(full_name)
    if not a or not b or len(a) > len(b):
        return False
    if a == b:
        return True
    b_pool = list(b)
    for tok in a:
        hit = None
        for cand in b_pool:
            if tok == cand:
                hit = cand
                break
            if len(tok) <= 2 and cand.startswith(tok[0]):
                hit = cand
                break
        if hit is None:
            return False
        b_pool.remove(hit)
    return True


def _member_identities(db, tenant_id: str):
    """[(name, email)] — tenant users + profile sender + internal people."""
    members: dict = {}

    def _add(name, email, role=None):
        name = str(name or "").strip()
        email = str(email or "").strip()
        if not name:
            return
        key = name.lower()
        if key not in members:
            members[key] = {"name": name, "email": email}
        elif email and not members[key]["email"]:
            members[key]["email"] = email

    users = db.query(User).filter(User.tenant_id == tenant_id).all()
    if not users:
        users = db.query(User).filter(User.tenant_id.is_(None)).all()
    for u in users:
        if getattr(u, "is_active", True):
            _add(
                " ".join(p for p in (u.first_name, u.last_name) if p),
                u.email,
            )

    profile = (
        db.query(InstallationProfile)
        .filter(InstallationProfile.tenant_id == tenant_id)
        .first()
    )
    profile = profile or (
        db.query(InstallationProfile)
        .filter(InstallationProfile.tenant_id == "default")
        .first()
    )
    ident = (profile.identity if profile else None) or {}
    company_name = str(ident.get("company_name") or "").strip()
    _add(ident.get("sender_name"), ident.get("sender_email"))

    sender_email = str(ident.get("sender_email") or "")
    owner_domain = _email_domain(sender_email) or _email_domain(
        next(iter(members.values()), {}).get("email") or ""
    )
    for person in (profile.people if profile else None) or []:
        if not isinstance(person, dict):
            continue
        email = str(person.get("email") or "")
        if classify_person_role(person.get("role"), email, owner_domain) == "team":
            _add(person.get("name"), email, person.get("role"))
    return list(members.values()), company_name


def _edge_count(db, node_id: str) -> int:
    return (
        db.query(GraphEdge)
        .filter(
            (GraphEdge.source_node_id == node_id)
            | (GraphEdge.target_node_id == node_id)
        )
        .count()
    )


def _retarget(db, old_id, new_id) -> int:
    moved = 0
    moved += (
        db.query(GraphEdge)
        .filter(GraphEdge.source_node_id == old_id)
        .update({"source_node_id": new_id})
    )
    moved += (
        db.query(GraphEdge)
        .filter(GraphEdge.target_node_id == old_id)
        .update({"target_node_id": new_id})
    )
    return moved


def repair_member_clusters(db, members) -> int:
    changes = 0
    # A fragment matching TWO different members (two "Rish" members) is
    # ambiguous — left alone rather than guessed.
    claim_counts: dict = {}
    for member in members:
        for n in db.query(GraphNode).filter(
            GraphNode.type == "Person",
            GraphNode.name.isnot(None),
        ).all():
            if n.name and _alias_matches(n.name, member["name"]):
                claim_counts[n.id] = claim_counts.get(n.id, 0) + 1
    for member in members:
        full_name = member["name"]
        matches = [
            n
            for n in db.query(GraphNode).filter(
                GraphNode.type == "Person",
                GraphNode.name.isnot(None),
            ).all()
            if n.name and _alias_matches(n.name, full_name)
            and claim_counts.get(n.id, 0) == 1
        ]
        if not matches:
            continue
        # Prefer the exact-name node; drop ambiguous sets spanning distinct
        # member spellings only when they cannot be ordered deterministically
        # (exact name or connectivity always breaks ties here).
        exact = [n for n in matches if _tokens(n.name) == _tokens(full_name)]
        canonical = (
            sorted(exact, key=lambda n: _edge_count(db, n.id), reverse=True)[0]
            if exact
            else sorted(
                matches,
                key=lambda n: (_edge_count(db, n.id), str(n.created_at)),
                reverse=True,
            )[0]
        )
        props = dict(canonical.properties or {})
        if not props.get("identity_canonical") or props.get("name") != full_name:
            props.update(
                {
                    "name": full_name,
                    "identity_canonical": True,
                    "member_email": member["email"],
                }
            )
            canonical.properties = props
            changes += 1
            print(
                f"canonical member node {canonical.id} -> {full_name} "
                f"({len(matches)} alias node(s) in cluster)"
            )
        for frag in matches:
            if frag.id == canonical.id:
                continue
            moved = _retarget(db, frag.id, canonical.id)
            db.delete(frag)
            changes += 1
            print(
                f"merging fragment '{frag.name}' ({frag.id}) into "
                f"canonical {canonical.id} ({moved} edge(s) retargeted)"
            )
    return changes


def repair_company_misparses(db, company_name) -> int:
    if not company_name:
        return 0
    company_persons = [
        n
        for n in db.query(GraphNode).filter(
            GraphNode.type == "Person",
            GraphNode.name.isnot(None),
        ).all()
        if n.name and _alias_matches(n.name, company_name)
    ]
    if not company_persons:
        return 0
    org = (
        db.query(GraphNode)
        .filter(GraphNode.type == "Organization")
        .all()
    )
    org_match = next(
        (o for o in org if _alias_matches(o.name, company_name)
         and _tokens(o.name) == _tokens(company_name)),
        None,
    )
    changes = 0
    for node in company_persons:
        if org_match is not None and org_match.id != node.id:
            moved = _retarget(db, node.id, org_match.id)
            db.delete(node)
            changes += 1
            print(
                f"removing misparsed Person '{node.name}' ({node.id}): "
                f"{moved} edge(s) retargeted to Organization "
                f"'{org_match.name}' ({org_match.id})"
            )
        else:
            # No Organization to merge into: retype in place rather than
            # leave the company typed as a person.
            node.type = "Organization"
            node.name = company_name
            changes += 1
            print(
                f"retyped misparse '{node.name}' ({node.id}) to Organization "
                f"'{company_name}'"
            )
    return changes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tenant", default="default")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    db = SessionLocal()
    try:
        members, company_name = _member_identities(db, args.tenant)
        print(
            f"tenant {args.tenant}: {len(members)} member identity(ies) "
            f"resolved from users + installation profile"
        )
        changes = repair_member_clusters(db, members)
        changes += repair_company_misparses(db, company_name)
        if not changes:
            print("graph identity cluster already clean — nothing to do")
        if args.dry_run:
            db.rollback()
            print("dry-run: rolled back")
        else:
            db.commit()
            print("committed")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

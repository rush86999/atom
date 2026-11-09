# Web Projects: authoritative workspace scope

Product source: e51546f13. PR797 successor; single-tenant Personal Edition remains the deployment model.

Independent real public-router/SQLite controls reproduced three scope failures on predecessor6132395cd: a real tenant with missing or contradictory default workspace could list another scope's default project (two cases), or create a project there (one case). The retained baseline has3failed17passed. The last three zero-effect consumer controls were added after that baseline; they are not represented as previously executed negatives.

The repair loads the authoritative existing Workspace and compares its canonical tenant with the actor using the established personal_scope resolver. Missing/mismatching workspaces refuse404 before project reads, writes, or task references. HTTPException remains a typed refusal through existing database error handling. Legitimate legacy actor-null/workspace-null defaults and raw Workspace tenant null/default positive twins pass. No global resolver, schema, release profile, or authentication policy is replaced.

Final gate:50passed onPython3.11 and3.14:23 actual public-router/SQLite Task/Project controls plus27CI lane-preservation controls. Authentication dependency is controlled in this test fixture; it is not ordinary login/browser evidence. Original7anonymous Next controls, HTTP/restart packet,127component controls, and safe core-fallback packet keep their original attribution.

General transactional authority/target CAS, mutation operation receipts, full main-app/profile browser CRUD, and whole-app completion remain unqualified. No model/provider/account external effects, deployment, live database, or mobile work. Local pre-existing diagnostic warnings are retained in logs.

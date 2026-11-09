# Editable presentation join repair

Frozen product/test source: `03beb72e8e966ffbb1a271646e833e0d56d54dae`. The earlier producer repair at `780fc9ab1` persisted only audits. Its real presentation-to-authenticated-HTTP-edit join failed 3/3 with missing Canvas resources. That negative is retained, not rewritten as a pass.

The successor creates the existing Canvas and CanvasAudit atomically under authoritative active-user and workspace claims. Trusted receipt fields override business metadata; current actor IDs govern stored ownership and broadcast recipients. Inactive/foreign/moved scopes refuse; Personal Edition NULL/empty/default compatibility has explicit twins. No new persistence engine or authority is introduced.

The exact frozen gate passes 63 controls, including all three presentation types followed by authenticated API edits, actor and workspace races, native content, no-effect and uncertainty contracts. The earlier wider run passed 82/89; its seven form-governance fixture failures exactly match the frozen 21/28 baseline. That wider run predates two final Personal Edition test parameters and is not relabelled as a final-source run.

Frontend evidence is reused at source780 because the entire frontend tree is byte-identical: 287 controls and TypeScript exit0. Existing browser evidence remains at its original source. No fresh browser or general long-running-task qualification follows.

Independent read-only DeepSeek Flash review prompted metadata isolation, canonical identity and cleanup checks. Root added the actual HTTP join, workspace claim and forced authority-race tests. Review output is advisory, not acceptance.

Remaining: legacy update_canvas still needs to use the existing verified writer, and full web application goals remain open. Mobile remains deferred.

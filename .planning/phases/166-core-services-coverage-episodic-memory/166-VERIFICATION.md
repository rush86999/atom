---
phase: 166-core-services-coverage-episodic-memory
title: "Phase 166 Verification Template"
status: template
last_updated: 2026-03-11

verification_results:
  requirement: CORE-03
  target: "Team can test episodic memory services (segmentation, retrieval modes, lifecycle) at 80%+ line coverage"

services:
  - service: episode_segmentation_service
    file: backend/core/episode_segmentation_service.py
    target_percent: 80
    target_lines: 591
    baseline_percent: 27.4
    baseline_lines: 162
    final_percent: TBD
    final_lines: TBD
    status: pending

  - service: episode_retrieval_service
    file: backend/core/episode_retrieval_service.py
    target_percent: 80
    target_lines: 1077
    baseline_percent: TBD
    baseline_lines: TBD
    final_percent: TBD
    final_lines: TBD
    status: pending

  - service: episode_lifecycle_service
    file: backend/core/episode_lifecycle_service.py
    target_percent: 80
    target_lines: 422
    baseline_percent: TBD
    baseline_lines: TBD
    final_percent: TBD
    final_lines: TBD
    status: pending

success_criteria:
  - criterion: "Episode segmentation (time gaps >30min, topic changes <0.75) achieves 80%+ coverage"
    status: pending

  - criterion: "All four retrieval modes (temporal, semantic, sequential, contextual) are tested"
    status: pending

  - criterion: "Episode lifecycle operations (decay, consolidation, archival) are tested"
    status: pending

  - criterion: "Canvas and feedback integration with episodic memory is tested"
    status: pending

test_files_created: []
test_files_modified: []

known_issues: []
recommendations: []

commits: []
---

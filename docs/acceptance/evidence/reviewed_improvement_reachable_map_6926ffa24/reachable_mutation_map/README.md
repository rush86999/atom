# Reachable mutation map — active core profile

API: `http://127.0.0.1:8100`

- OpenAPI paths: **1605**
- Mutation-shaped mounted routes: **821**
- Bypass candidates (direct service / unknown): **693**

## Effect classification

- mutation_shaped: 411
- unknown_effect: 326
- read_only_likely: 84

## Dispatch classification

- direct_or_unknown: 530
- direct_provider_service: 168
- direct_canvas_service: 69
- shared_action_registry: 25
- assignment_executor: 16
- direct_goal_service: 9
- oracle_consumer: 4

## Families with bypass candidates

- `other`: 544 mutation-shaped, 475 bypass candidates; dispatch={'direct_or_unknown': 397, 'oracle_consumer': 4, 'direct_provider_service': 121, 'direct_canvas_service': 20, 'shared_action_registry': 2}
- `canvas`: 77 mutation-shaped, 60 bypass candidates; dispatch={'direct_canvas_service': 41, 'direct_or_unknown': 20, 'assignment_executor': 16}
- `agents`: 50 mutation-shaped, 36 bypass candidates; dispatch={'direct_or_unknown': 37, 'shared_action_registry': 12, 'direct_provider_service': 1}
- `admin`: 27 mutation-shaped, 25 bypass candidates; dispatch={'direct_or_unknown': 27}
- `auth`: 21 mutation-shaped, 21 bypass candidates; dispatch={'direct_or_unknown': 10, 'direct_provider_service': 11}
- `provider_outlook`: 28 mutation-shaped, 14 bypass candidates; dispatch={'direct_provider_service': 28}
- `memory`: 12 mutation-shaped, 12 bypass candidates; dispatch={'direct_or_unknown': 12}
- `documents`: 10 mutation-shaped, 10 bypass candidates; dispatch={'direct_or_unknown': 9, 'direct_provider_service': 1}
- `chat`: 8 mutation-shaped, 8 bypass candidates; dispatch={'direct_canvas_service': 8}
- `goal_runs`: 8 mutation-shaped, 8 bypass candidates; dispatch={'direct_goal_service': 8}
- `evolution_review`: 5 mutation-shaped, 5 bypass candidates; dispatch={'direct_or_unknown': 5}
- `skills`: 5 mutation-shaped, 5 bypass candidates; dispatch={'direct_or_unknown': 5}
- `workflows`: 5 mutation-shaped, 5 bypass candidates; dispatch={'direct_or_unknown': 1, 'direct_provider_service': 4}
- `provider_integrations`: 4 mutation-shaped, 4 bypass candidates; dispatch={'direct_provider_service': 2, 'direct_or_unknown': 2}
- `marketplace`: 5 mutation-shaped, 4 bypass candidates; dispatch={'direct_or_unknown': 5}

## Boundary

This is a reachability/dispatch map, not runtime coverage proof. Direct-service routes still need family-level postcondition controls; the complete row list is in `reachable_mutation_map.json`.

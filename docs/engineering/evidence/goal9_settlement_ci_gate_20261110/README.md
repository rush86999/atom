# Durable settlement CI follow-through

The settlement and old-database upgrade controls were not selected by the normal CI workflow. Add one backend-core step through the existing additive manifest. All existing parsed jobs and steps are preserved; the immutable baseline is unchanged.

The CI lane contract plus settlement and upgrade selection passed 56 tests. Product remains the frozen df3b7747b source; this follow-up changes CI selection only. Existing model-free observers must bind the new head; earlier green does not transfer. Atomic concurrent cap reservation remains a separate open goal.

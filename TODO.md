# TODO: Add Optimistic Updates to useCache Hook

- [x] Add 'optimisticUpdate' option to the hook's options type
- [x] Add previousDataRef to track data for reversion
- [x] Modify fetchData to apply optimistic update before fetching fresh data
- [x] Modify catch block in fetchData to revert data on error
- [ ] Test the implementation

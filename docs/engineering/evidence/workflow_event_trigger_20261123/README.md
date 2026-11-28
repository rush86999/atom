# Durable event trigger execution

Registered event trigger nodes consume the persisted admitted event; they never invoke a connector to reconstruct it. The runner verifies the selected node, receipt source and identity, payload digest and frozen execution owner before dispatch. Run-local graph projection includes only the admitted root and its reachable actions, excluding unrelated roots and alternative event branches. The saved receipt graph remains unchanged.

Both graph and linear dispatch use the same trigger consumer. Ordinary action dispatch remains on its existing executor. Legacy unregistered trigger behavior is preserved. Manual invocation cannot invent an admitted event for a registered source trigger.

Design reference: [Home Assistant trigger data](https://www.home-assistant.io/docs/automation/trigger-data/) and [trigger identity](https://www.home-assistant.io/docs/automation/trigger/). These establish the mature pattern of exposing the triggering event and identifying which trigger started a run. Atom retains its existing durable reservation/receipt mechanism rather than adding an event queue.

Qualification remains controlled: scratch databases, actual reserved graph runner and state manager, final synthetic action transport doubled. No live provider, browser, deployment or merge qualification is claimed. Web source authoring and authenticated source intake remain open.

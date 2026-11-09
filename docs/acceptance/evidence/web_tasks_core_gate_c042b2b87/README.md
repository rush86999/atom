# Core fallback boundary, not Tasks journey acceptance

At source `c042b2b87`, routine UI sign-in with the disposable scratch account returned to `/tasks` and rendered the safe core deferred screen. No task form was exposed or forced on; no task CRUD was exercised through the browser.

The controlled backend fixture mounts auth and task/project routers, not the profile endpoint. That endpoint returned404, so the UI used its core fallback. This proves fallback safety only, not Tasks browser CRUD, a loaded backend profile, or full main_api_app. The earlier HTTP/restart packet remains at source8b3ca2671.

No passwords or session tokens are included. The visible example.invalid account identifier is a disposable fixture, not customer data. No score changes or gate broadening follow. Next ordinary-user work must use supported core surfaces and the full-app profile boundary, rather than forcing a gate on to obtain a pass.

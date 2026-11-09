# Normal-app recovery request browser boundary

The ordinary web page, configured frontend proxy, real main app and normal registry-mounted auth were exercised at b21402964 (product4fe092905). A synthetic member was registered via the public scratch API. Only SMTP delivery was replaced with a local captured-message function; route selection, database, token issuance and UI were real.

Known and unknown addresses displayed the same accepted-request message. Exactly one message and one unused token exist for the one synthetic member; the captured link points to the implemented /auth/reset-password page on the configured frontend. An invalid link displays Invalid Reset Link. Browser observations are transcribed from CUA; counts were independently read from retained scratch SQLite. Raw tokens, mail, launch environment and credentials remain private. No screenshot file is claimed in this packet.

This is deliberately not a complete browser password-reset episode: no credential was changed through the browser, and the final credential-changing step requires user handoff under the browser control policy. Backend/API controls separately cover atomic reset and subsequent login. Existing bearer-session invalidation remains open. Both owned server handles terminated after capture; no existing world was reset or deleted.

# OpenCode Go vs OpenCode Zen endpoint defaults

`opencode-go` and `opencode` are distinct provider ids. The default base URLs
are intentionally different:

| Provider id | Product | Default base URL |
| --- | --- | --- |
| `opencode-go` | OpenCode Go subscription | `https://opencode.ai/inference/go/openai/v1` |
| `opencode` | OpenCode Zen catalog | `https://opencode.ai/zen/v1` |

`OPENCODE_BASE_URL` remains an explicit operator override for both ids (used by
custom gateways and loopback tests). When unset, each id uses its own default;
do not point a Go key at the Zen default or a Zen key at the Go default.

The Go product documentation names DeepSeek V4.1 Flash and the Go
OpenAI-compatible chat endpoint:
<https://opencode.ai/docs/console/go/#endpoints>. The same documentation
requires a stable per-conversation session and the caller's own User-Agent,
which the existing client already sends (`atom-agent/1.0`,
`x-opencode-session: atom-<workspace>`). SDK retries remain zero.

This is a configuration/default repair. It does not prove live authentication,
served model identity, quality or billing.

## Settings/UI note

`OPENCODE_BASE_URL` is an **explicit shared override** for both provider ids,
not the Go product default. The Settings catalog keeps its existing default
value unchanged to avoid silently rerouting the Zen id; when the setting is
unset, each provider uses its own default above. The label/help now names the
override and both defaults so the two products are not conflated.

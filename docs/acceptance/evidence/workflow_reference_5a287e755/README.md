# Workflow reference accuracy checkpoint

Source `5a287e755`, compared with main `dd2610502`. No workflow or executable
Python statement changes. The previous reference described removed deploy/LanceDB
pipelines and job dependencies absent from current YAML. Preserve that original
reference in Git history; the replacement is current-source reference, not a claim
that the old examples ever ran.

The source map was parsed from actual YAML with js-yaml. The diagram semantic
check compares all nine CI job labels and every needs edge exactly. Docker step
order, push:false, final smoke assertions and success-path cleanup were manually
traced to the writer. Both editable diagrams rendered as SVG with Mermaid CLI
12.2.0 and existing Chrome. PNG visual review is recorded separately.

Public-source Flash review used the already configured OpenCode Go route with
all tools denied, two-step bound and no app/private inputs. Root independently
reviewed its findings. An initial CLI launch refused its normal local log access;
the separately recorded authorized invocation completed. No hidden model retry or
provider substitution was used.

Python 3.14.7 primary implementation and official docs contradict two original
comments: default policy loop storage is strong, and asyncio.iscoroutinefunction
is deprecated rather than removed in3.14. Compare executable AST excluding module
documentation: identical. This does not reopen accepted worker runtime evidence.

This checkpoint covers the workflow reference and its two diagrams, not every
reference in the repository. DOCS-REF-01 remains open. No app run, deployment,
provider/business send, account/credential operation or historical claim change.

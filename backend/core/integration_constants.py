# Communication channels supporting multi-entity extraction
COMMUNICATION_INTEGRATIONS = ["outlook", "gmail", "slack", "whatsapp", "teams", "hubspot"]

# Document channels supporting multi-entity extraction
DOCUMENT_INTEGRATIONS = ["document"]

# Combined: all integrations with multi-entity support
MULTI_ENTITY_INTEGRATIONS = COMMUNICATION_INTEGRATIONS + DOCUMENT_INTEGRATIONS

# Integrations where text contains quoted/forwarded replies to strip before
# LLM extraction. Email-like integrations thread via "On X wrote:" and "> ".
# Chat integrations (Slack, Teams) and non-messaging (Salesforce, Notion) don"t.
EMAIL_THREAD_INTEGRATIONS = ["outlook", "gmail"]

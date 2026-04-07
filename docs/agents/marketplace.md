# Agent Marketplace & Federation Guide

The ATOM platform's Marketplace has evolved from merely sharing individual "Skills" to sharing complete, autonomous **Agents**. 

This guide explains how the Agent Marketplace operates, how agents are packaged, and how ATOM federates these packages across multiple self-hosted instances.

## Core Concepts

### 1. Agent Templates
An `AgentTemplate` is the core distributable unit in the Marketplace. It represents a fully configured agent, packaged and redacted so that it can be installed by any other tenant or organization.

A published Agent Template encapsulates:
- **Agent Capability**: Unstructured complex task definitions, including system prompts, agent-level constraints, and tool combinations.
- **Canvas UIs**: Attached custom UI layouts/Canvas components that the agent uses to interact or present findings.
- **Experience Memory**: A curated, anonymized bundle of "learned heuristics" (e.g., successful error-resolution paths, execution graphs) so the agent is highly capable immediately upon installation.

### 2. Hybrid Anonymization Strategy
When an agent is published to the Marketplace, its existing memory and operational history often contain sensitive business information or Personally Identifiable Information (PII). 

ATOM employs a **Hybrid Anonymization Strategy**:
1. **Deterministic Redaction**: A pass using regex and rule-based filters strips out known formats like emails, SSNs, phone numbers, exact tenant UUIDs, and common internal domain patterns.
2. **LLM Representation**: A secondary pass uses a Large Language Model to semantically rewrite and redact any remaining edge-case business context from the memory bundle, producing generic, generalized heuristics.
3. **Manual Review**: The publisher reviews the resulting memory bundle before giving final approval for it to enter the Marketplace.

### 3. Accelerated Maturity Transfer
Agents installed from the Marketplace begin at the `INTERN` maturity level. However, because they are pre-loaded with successful heuristics (via their anonymized experience memory), they benefit from a massively accelerated learning curve. They can prove themselves autonomously much faster without blindly bypassing organizational safety protocols.

## Multi-Node Federation (API)

To support the open-source community and enterprise deployments, the ATOM marketplace operates as a **Federated System**. 

A self-hosted instance of ATOM can query and install `AgentTemplates` from the primary SaaS marketplace API or connect to other peer nodes via an Inter-Node API.

### Federation Endpoints

Federation connections are authenticated via a pre-shared key (e.g., `x-federation-key` header). Self-hosted nodes expose two primary routes under `/api/federation`:

- `GET /api/federation/agents`
  Lists all public, approved `AgentTemplate` records available on the node.
- `GET /api/federation/agents/{template_id}`
  Retrieves the full JSON bundle for a specific agent template, allowing the requesting node to instantiate an imported agent locally using the bundled configuration, capabilities, and anonymized memory.

Ultimately, this allows self-hosted clusters to share capabilities without ever exposing internal operational data.

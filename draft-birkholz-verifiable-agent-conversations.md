---
v: 3

title: "Verifiable Agent Conversations"
abbrev: "RATS CMW"
docname: draft-birkholz-verifiable-agent-conversations-latest
category: std
consensus: true
submissionType: IETF

ipr: trust200902
area: "Security"
keyword: [ verifiable, evidence, transparency, compliance, auditability ]

stand_alone: yes
smart_quotes: no
pi: [toc, sortrefs, symrefs]

author:
 - name: Henk Birkholz
   email: henk.birkholz@ietf.contact
 - name: Tobias Heldt
   email: tobias@xor.tech

normative:
  RFC4648: base64
  RFC5280: pkix
  RFC7252: coap
  RFC7515: jws
  RFC7519: jwt
  STD90:
    -: json
    =: RFC8259
  RFC8610: cddl
  STD94:
    -: cbor
    =: RFC8949
  IANA.cwt:
  IANA.jwt:
  BCP26:
    -: ianacons
    =: RFC8126

informative:
  STD96:
    -: cose
    =: RFC9052
  RFC9334: rats-arch
  I-D.ietf-scitt-architecture: scitt-arch

entity:
  SELF: "RFCthis"

--- abstract

Abstract

--- middle

# Introduction

The question of whether the recorded output of an autonomous agent faithfully represents an agent's actual behavior has found new urgency as the number of consequential tasks that are delegated to agent increases rapidly.
Autonomous Agents--typically workload instances of agentic artificial intelligence (AI) based on large language models (LLM)--interact with other actors by design.
This creates an interconnected web of agent interactions and conversations that is currently rarely supervised in a systemic manner.
In essence, the two main types of actors interacting with autonomous agents are humans and machines (e.g., other autonomous agents), or a mix of them.
In agentic AI systems, machine actors interact with other machine actors.
The number of interaction between machine actors grows significantly more than the number of interactions between human actors and machine actors.
While the responsible parties for agent actions ultimately are humans--whether a natural legal entity or an organization--agents act on behalf of humans and on behalf of other agents.
To demonstrate due diligence, responsible human parties require records of agent behavior to demonstrate policy compliant behavior for agents acting under their authority.
These increasingly complex interactions between multiple actors that can also be triggered by machines (recursively) increase the need to understand decision making and the chain of thoughts of autonomous agents, retroactively.

The verifiable records of agent conversations that are specified in this document provide an essential basis for operators to detect divergences between intended and actual agent behavior after the interaction has concluded.

For example:

*  An agent authorized to read files might invoke tools to modify production systems or exfiltrate sensitive data beyond its authorization scope.

*  An agent's visible chain-of-thought output might diverge from the reasoning that actually produced its actions.

*  An agent might deliberately underperform during capability evaluations while performing at full capacity during deployment.

This document defines conversation records representing activities of autonomous agents such that long-term preservation of the evidentiary value of these records across chains of custody is possible.
The first goal is to assure that the recording of an agent conversation (a distinct segment of the interaction with an autonomous agent) being proffered is the same as the agent conversation that actually occurred.
The second goal is to provide a general structure of agent conversations that can represent most common types of agent conversation frames, is extensible, and allows for future evolution of agent conversation complexity and corresponding actor interaction.
The third goal is to use existing IETF building blocks to present believable evidence about how an agent conversation is recorded utilizing Evidence generation as laid out in the Remote ATtestation ProcedureS architecture {{-rats-arch}}.
The fourth goal is to use existing IETF building blocks to render conversation records auditable after the fact and enable non-repudiation as laid out in the Supply Chain Integrity, Transparency, and Trust architecture {{-scitt-arch}}.
The fifth goal is to enable detection of behavioral anomalies in agent interactions, including unauthorized tool invocations, inconsistencies between reasoning traces and actions, and performance modulation across evaluation and deployment contexts, through structured, comparable conversation records.
The sixth goal is to enable cross-vendor interoperability by defining a common representation for agent conversations that can be translated from multiple existing agent implementations with distinct native formats.
The seventh goal is to produce records suitable for demonstrating compliance with emerging regulatory requirements for AI system documentation, traceability, and human oversight.

Most agent conversations today are represented in "human-readable" text formats.
For example, {{STD90}} is considered to be "human-readable" as it can be presented to humans in human-computer-interfaces (HCI) via off-the-shelf tools, e.g., pre-installed text editors that allow such data to be consumed or modified by humans.
The Concise Binary Object Representation (CBOR {{STD94}}) is used as the primary representation next to the established representation that is JSON.

## Conventions and Definitions

{::boilerplate bcp14-tagged}

In this document, CDDL {{-cddl}} is used to describe the data formats.

The reader is assumed to be familiar with the vocabulary and concepts defined in {{-rats-arch}} and {{-scitt-arch}}.

# Agent Conversations

Content

~~~ cddl
{::include agent-conversation.cddl}
~~~
{: #fig-cddl-record artwork-align="left"
   title="CDDL definition of an Agent Conversation"}

--- back

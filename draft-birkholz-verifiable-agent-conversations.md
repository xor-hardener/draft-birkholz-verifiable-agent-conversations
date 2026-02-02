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

Autonomous Agents--typically workload instances of agentic artificial intelligence (AI) based on large language models (LLM)--interact with other actors by design.
The two main types of actors interacting with autonomous agents are humans and machines (e.g., other autonomous), or a mix of them.
In agentic AI systems, machine actors interact with other machine actors.
While the responsible parties ultimately are humans (e.g., a natural legal entity or an organization), agents do not only act on behalf of humans they can also act on behalf of other agents.
These increasingly complex interactions between multiple actors that can also be triggered by machines (recursively) increases the need to understand decision making and the chain of thoughts of autonomous agents, retroactively.

This document defines conversation records representing activities of autonomous agents such that long-term preservation of the evidentiary value of these records across chains of custody is possible.
The first goal is to assure that the recording of an agent conversation (a distinct segment of the interaction with an autonomous agent) being proffered is the same as the agent conversation that actually occurred.
The second goal is to provide a general structure of agent conversations that can represent most common types of agent conversation frames, is extensible, and allows for future evolution of agent conversation complexity and corresponding actor interaction.
The third goal is to use existing IETF building blocks to present believable evidence about how an agent conversation is recorded utilizing Evidence generation as laid out in the Remote ATtestation ProcedureS architecture {-rats-arch}.
The fourth goal is to use existing IETF building blocks to render conversation records auditable after the fact and enable non-repudiation as laid out in the Supply Chain Integrity, Transparency, and Trust architecture {-scitt-architecture).

Most agent conversations today are represented in "human-readable" text formats.
For example, {{STD90}} is considered to be "human-readable" as it can be presented to humans in human-computer-interfaces (HCI) via off-the-shelf tools, e.g., pre-installed text editors that allow such data to be consumed or modified by humans.
The Concise Binary Object Representation (CBOR {{STD94}}) is used as the primary representation next to the established representation that is JSON.

## Conventions and Definitions

{::boilerplate bcp14-tagged}

In this document, CDDL {{-cddl}} is used to describe the data formats.

The reader is assumed to be familiar with the vocabulary and concepts defined in {{-rats-arch}} and {{-scitt-arch}}.

# Agent Conversations

Content 

--- back

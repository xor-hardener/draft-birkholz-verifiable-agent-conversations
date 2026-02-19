# Compliance Research Resources

This folder contains source documents analyzed for the compliance requirements intersection.

## Downloaded Documents

PDFs are excluded from git (`.gitignore`). Download links provided for reference.

| Document | Source URL | Description |
|----------|-----------|-------------|
| ETSI TS 104 223 | https://www.etsi.org/deliver/etsi_ts/104200_104299/104223/01.01.01_60/ts_104223v010101p.pdf | Baseline Cyber Security Requirements for AI Models and Systems |
| NIST AI 100-2 | https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-2e2025.pdf | Adversarial Machine Learning Taxonomy |
| BSI AI Finance | https://www.bsi.bund.de/SharedDocs/Downloads/EN/BSI/KI/AI-Finance_Test-Criteria.pdf | AI Finance Test Criteria |
| Anthropic Research | https://www.anthropic.com/research/emergent-misalignment-reward-hacking | Emergent Misalignment and Reward Hacking |

## Framework Analysis Summary

### Frameworks Analyzed

1. **EU AI Act** (Regulation 2024/1689) - Articles 12, 19
2. **Cyber Resilience Act** (CRA) - Vulnerability handling, SBOM requirements
3. **NIS2 Directive** - Incident reporting (24h/72h/1mo)
4. **ETSI TS 104 223** - AI-specific security provisions (13 principles)
5. **SOC 2** - Trust Services Criteria (Security, Processing Integrity)
6. **FedRAMP Rev. 5** - AU-2, AU-6, AU-12, M-21-31
7. **PCI DSS v4.0** - Requirement 10, AI-specific guidance
8. **ISO/IEC 42001:2023** - A.6.2.8 Event Logging
9. **FFIEC IT Handbook** - VII.D AI/ML, VI.B.7 Log Management

### Key Finding: Universal Requirements

All frameworks require these capabilities for AI system logging:

1. **Automatic event logging** - System-generated, not manual
2. **Timestamps** - Precise temporal ordering
3. **Actor identification** - Who performed the action
4. **Action recording** - What was done
5. **Tamper-evidence** - Integrity protection
6. **Incident support** - Enable investigation
7. **Anomaly detection** - Support risk identification
8. **Traceability** - Reconstruct behavior

### AI-Specific Requirements (subset of frameworks)

These appear in AI-focused regulations:

1. **Input/output recording** - Prompts and responses
2. **Reasoning capture** - Chain-of-thought where available
3. **Human oversight** - Enable review of AI decisions
4. **Model versioning** - Track which model produced outputs

## Research Date

Analysis conducted: 2026-02-18

## Sources Consulted (Web)

- https://artificialintelligenceact.eu/article/12/
- https://artificialintelligenceact.eu/article/19/
- https://ithandbook.ffiec.gov/it-booklets/architecture-infrastructure-and-operations/
- https://ithandbook.ffiec.gov/it-booklets/architecture-infrastructure-and-operations/vii-evolving-technologies/viid-artificial-intelligence-and-machine-learning/
- https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act
- https://www.nis-2-directive.com/
- https://blog.pcisecuritystandards.org/ai-principles-securing-the-use-of-ai-in-payment-environments
- https://www.iso.org/standard/42001
- https://www.isms.online/iso-42001/annex-a-controls/a-6-ai-system-life-cycle/a-6-2-8-ai-system-recording-of-event-logs/

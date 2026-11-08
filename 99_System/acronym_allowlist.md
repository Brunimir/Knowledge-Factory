---
allowlist:
  - AI
  - VM
  - IT
  - OS
  - JSON
  - SQL
  - REST
  - AWS
  - CLI
  - PIN
  - GRS
  - LRS
  - ZRS
  - GZRS
  - SMART
  - ID
  - IP
  - ARM
  - CPU
  - AKS
  - MECE
  - API
  - CEO
  - GPU
  - ROI
  - UI
  - VRAM
  - TCP
  - RAID
  - SLA
  - RAM
  - GC
  - GDP
  - USD
  - HK
  - KFC
  - DB
  - DAG
  - DNA
  - EU
  - ISO
  - KPI
  - AAC
  - AD
  - AES
  - ATO
  - AV
  - BCP
  - BEC
  - BYOD
  - CA
  - CASB
  - CD
  - CDE
  - CIA
  - CIAM
  - CID
  - CIS
  - CRM
  - CVE
  - DES
  - DID
  - DIF
  - DLP
  - DNS
  - DR
  - DSI
  - DSPM
  - EDM
  - EDR
  - ESI
  - FDG
  - FQDN
  - GCP
  - GDPR
  - GRC
  - HR
  - HSM
  - HTTPS
  - IEC
  - IRM
  - ITDR
  - JEA
  - JIT
  - JML
  - KQL
  - LLM
  - MCP
  - MFA
  - MITM
  - MITRE
  - ML
  - MOC
  - NAC
  - NDA
  - NL
  - OCR
  - OTP
  - PDF
  - PIM
  - PKI
  - POLP
  - QR
  - ROM
  - RSA
  - SAP
  - SCIM
  - SCU
  - SFA
  - SHA
  - SIEM
  - SIT
  - SMS
  - SOAR
  - SOC
  - SSE
  - SSID
  - SSO
  - SSPM
  - SSPR
  - STIG
  - STP
  - TAP
  - TI
  - TLS
  - TOU
  - UDSP
  - UEBA
  - UK
  - URL
  - US
  - USB
  - VISA
  - VPN
  - WHOIS
  - WPA
  - XDR
  - ZAP
  - ZTNA
  - MBA
  - SDK
  - OTLP
  - SRE
  - SLO
  - RPC
  - CI
  - QA
  - PII
  - YAML
  - RAG
  - GPT
  - HIPAA
  - JDBC
  - GB
  - IO
  - BI
  - TB
  - AM
  - ETL
  - POS
  - ZIP
  - LSM
  - HTML
  - CCPA
  - CSV
  - ELT
  - XML
  - POSIX
  - CRUD
  - ANSI
  - GET
---

# Acronym Allowlist

Acronyms atomic enough that they neither need inline expansion in concept
notes nor a vault concept of their own. Read by:

- `pkm-ingestion` Phase 2 audit — suppresses the unflagged-acronym warning
- `pkm-review` Review 6 vault gap scan — excludes from the gap report

## Inclusion rule (all three must hold)

1. The term is universally understood in tech / business contexts and reading the bare acronym does not slow a competent reader down.
2. It does NOT represent a discrete mechanism worth its own concept note. (If you could write a Core Idea + Mechanism + Boundary condition + Application for it, it's not atomic — it should be a vault concept.)
3. Expanding it inline every single time would feel pedantic to the writer and the reader.

If unsure, **do not add**. Better to flag the acronym once during audit and decide each time than to silently lose a real vault gap. **Every wrongful entry permanently mutes the gap scan** for that token — which is exactly the failure mode this file exists to prevent.

## How to add an entry

Edit the `allowlist:` list in the frontmatter above. One acronym per line, uppercase, no quotes:

```yaml
allowlist:
  - API
  - CPU
  - RAM
```

The allowlist is **populated as the ingestion audit and Review 6 surface
acronyms you decide are genuinely atomic for your domains** — it is not empty.
Keep it pruned against the three-part inclusion rule above; remove any entry
that turns out to be a real concept or extraction-markup shrapnel.

## What does NOT belong here

- Anything you'd want a flashcard for → vault concept, not allowlist
- Anything domain-specific to one MOC (e.g. `RBAC`, `IAM`, `NFS`) → vault concept (these were removed from the list above for this reason)
- Extraction-markup shrapnel — confidence/label tokens like `HIGH`, `MEDIUM`, `NONE`, `NOT`, `ALL`, or fragments of multi-part names (`ATT`/`CK` from `ATT&CK`, `RA` from `RA-GRS`). These must be stripped at Phase-3 note build (see `docs/inbox-pipeline.md`), never allowlisted — allowlisting them silently mutes real gaps. They were removed from the list above.
- Brand names (`Azure`, `AWS`, `Obsidian`) → not acronyms in the audit sense; these don't match `\b[A-Z]{2,}\b` if used in CamelCase / mixed-case form
- Standards / protocols (`HTTP`, `TLS`, `SMTP`) → judgment call. Default: vault concept. Override to allowlist only if you genuinely don't want to learn or teach them.

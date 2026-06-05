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
  - RA
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
  - DB
  - DAG
  - DNA
  - EU
  - ISO
  - KPI
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

If unsure, **do not add**. Better to flag the acronym once during audit and decide each time than to silently lose a real vault gap.

## How to add an entry

Edit the `allowlist:` list in the frontmatter above. One acronym per line, uppercase, no quotes:

```yaml
allowlist:
  - API
  - CPU
  - RAM
```

The allowlist is intentionally seeded empty — populate it as the ingestion audit and Review 6 surface acronyms you decide are genuinely atomic for your domains.

## What does NOT belong here

- Anything you'd want a flashcard for → vault concept, not allowlist
- Anything domain-specific to one MOC (e.g. `RBAC`, `IAM`, `NFS`) → vault concept
- Brand names (`Azure`, `AWS`, `Obsidian`) → not acronyms in the audit sense; these don't match `\b[A-Z]{2,}\b` if used in CamelCase / mixed-case form
- Standards / protocols (`HTTP`, `TLS`, `SMTP`) → judgment call. Default: vault concept. Override to allowlist only if you genuinely don't want to learn or teach them.

# ── Portable vault root ─────────────────────────────────────────────
# Set VAULT_ROOT in your environment, or this falls back to the
# directory the script lives in.
$VaultRoot = if ($env:VAULT_ROOT) { $env:VAULT_ROOT } else {
    Split-Path -Parent $MyInvocation.MyCommand.Path
}
# ────────────────────────────────────────────────────────────────────
Set-Location $VaultRoot

$notes = [System.IO.Directory]::GetFiles(
    (Join-Path $VaultRoot "00_Inbox\Note Pipe"), "*.md")

if ($notes.Count -eq 0) {
    Write-Host "Note Pipe is empty - nothing to process." -ForegroundColor Yellow
    exit 0
}

Write-Host "Found $($notes.Count) note(s) in Note Pipe. Regenerating vault index..." -ForegroundColor Cyan
python generate_index.py

# GATE-KF-13 - BLOCKING, and deliberately BEFORE the agent. Every other gate
# inspects artefact shape after the fact; this one opens the cited document and
# checks that each `quote:` in the capture is really in it. Measured 2026-08-15:
# 18.3% of all checkable quotes were fabricated, carrying `confidence: HIGH`.
# The quotes never reach a note (no quote field in the schema) but the EDGES they
# justify do - so the vault ends up holding relationships whose only evidence was
# invented and then discarded. Blocking here means a capture with fabricated
# evidence never becomes notes at all; catching it afterwards is far more
# expensive, because status:final notes are locked by Safety Rule 6.
# Silent on captures whose source was not retained - that gap is provenance_pct.
Write-Host "`nGATE-KF-13 quote fidelity..." -ForegroundColor Cyan
python gate_quote_fidelity.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Capture cites the source for claims the source does not make." -ForegroundColor Red
    Write-Host "  Fix the extract (drop the quotation marks, or correct the quote)." -ForegroundColor Red
    exit 1
}

# GATE-KF-14 - BLOCKING, the judgement half of the same idea. KF-13 above proves
# quotations verbatim; it cannot judge whether a mechanism bullet, a boundary
# condition or a worked example is actually supported - that needs an agent that
# has read both sides. This gate refuses to process a capture whose CHECKABLE
# blocks carry no verdict, and refuses outright when one is `fabricated`.
# Blocks with no reachable source pass silently: that is provenance_pct, a
# capture-time problem, not something to fail a run over.
Write-Host "`nGATE-KF-14 capture fidelity..." -ForegroundColor Cyan
python capture_fidelity.py manifest | Out-Null

# Auto-review: the manifest above can carry unjudged checkable blocks. Before
# the gate checks for a verdict, a dedicated sonnet agent reads each unjudged
# checkable block against its frozen source in 30_Sources and writes
# faithful/drifted/fabricated/unverifiable back into the manifest. See
# 99_System\Claude\pkm-capture-verify\SKILL.md. Skipped entirely when nothing
# is unjudged, so a clean run pays nothing for this step.
$manifestPath = Join-Path $VaultRoot "00_Inbox\CAPTURE_FIDELITY.json"
$unjudgedCount = @((Get-Content $manifestPath -Raw | ConvertFrom-Json).blocks |
    Where-Object { $_.source.kind -ne "absent" -and -not $_.verdict }).Count
if ($unjudgedCount -gt 0) {
    Write-Host "  $unjudgedCount unjudged checkable block(s) - running capture fidelity review..." -ForegroundColor Cyan
    # -p/--print, NOT --remote-control: this step has no "STOP and wait for
    # human" branch (unlike the main process-inbox agent below, which
    # legitimately does for Overlap/Split) - it only judges and reports, so
    # it must run headless and exit on its own, or the script blocks forever
    # on an interactive session nobody is there to close.
    claude --model sonnet -p --permission-mode acceptEdits "verify-capture-fidelity"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Capture fidelity review agent exited $LASTEXITCODE - gate will re-check what it left." -ForegroundColor DarkYellow
    }
}

python capture_fidelity.py gate
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Verify the capture against its source before it becomes notes." -ForegroundColor Red
    Write-Host "  A fabrication costs one Note Pipe edit here; after promotion it" -ForegroundColor Red
    Write-Host "  costs a Decision, because Safety Rule 6 locks status:final notes." -ForegroundColor Red
    exit 1
}

# Overlap candidates: deterministic pre-computation, same pattern as
# extract_flashcard_candidates.ps1 - the agent reads the manifest, it does NOT
# roll its own similarity search.
Write-Host "Generating overlap candidates..." -ForegroundColor Cyan
python overlap_candidates.py generate

Write-Host "`nStarting PKM agent..." -ForegroundColor Green
claude --model opus --remote-control "PKM Process Inbox" process-inbox

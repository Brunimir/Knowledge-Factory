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
Write-Host "`nStarting PKM agent..." -ForegroundColor Green
claude --remote-control "PKM Process Inbox" process-inbox

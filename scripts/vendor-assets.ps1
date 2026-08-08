<#
.SYNOPSIS
    Downloads and vendors third-party frontend assets into portfolio/static/portfolio/vendor/.

.DESCRIPTION
    Fetches Bootstrap 5.3.3, Bootstrap Icons 1.11.3 (CSS + font files), Chart.js 4.4.4, and
    Space Grotesk / IBM Plex Mono (Latin subset, woff2) from their canonical CDNs, then writes
    a SHA256 lock file (scripts/vendor-assets.lock.json) so re-runs are idempotent and any drift
    (CDN serving different bytes) is caught instead of silently re-vendored.

    Run again any time to verify nothing has drifted; pass -Force after a deliberate version bump.

.PARAMETER VerifyOnly
    Do not download anything. Check vendored files on disk against the lock file and report
    missing/mismatched entries. Exits non-zero on any problem. Use on the Pi before deploying.

.PARAMETER Force
    Re-download every asset and overwrite the lock file, even if local files already match it.
    Use this after bumping a version in the manifest below.

.EXAMPLE
    powershell -File scripts/vendor-assets.ps1

.EXAMPLE
    powershell -File scripts/vendor-assets.ps1 -VerifyOnly
#>

param(
    [switch]$VerifyOnly,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$RepoRoot   = Split-Path -Parent $PSScriptRoot
$VendorRoot = Join-Path $RepoRoot 'portfolio\static\portfolio\vendor'
$LockPath   = Join-Path $PSScriptRoot 'vendor-assets.lock.json'

$ChromeUserAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

# ---- direct-download manifest (name -> source URL, dest path relative to $VendorRoot) ----
$DirectAssets = @(
    @{ Name = 'bootstrap.min.css';        Url = 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css';        Dest = 'bootstrap/bootstrap.min.css' }
    @{ Name = 'bootstrap.bundle.min.js';  Url = 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js';    Dest = 'bootstrap/bootstrap.bundle.min.js' }
    @{ Name = 'chart.umd.min.js';         Url = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js';              Dest = 'chartjs/chart.umd.min.js' }
)

$BootstrapIconsCssUrl  = 'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css'
$BootstrapIconsCssDest = 'bootstrap-icons/bootstrap-icons.min.css'

# Weights must cover every --weight-* token in tokens/typography.css; a weight
# that is requested but not vendored gets faux-bolded by the browser.
$GoogleFontsFamilies = 'family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap'
$GoogleFontsCssUrl    = "https://fonts.googleapis.com/css2?$GoogleFontsFamilies"
$LocalFontsCssDest    = 'fonts/fonts.css'

# ---------------------------------------------------------------------------

function Get-Sha256Hex {
    param([Parameter(Mandatory)][string]$Path)
    (Get-FileHash -Path $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function ConvertTo-LockKey {
    param([string]$RelPath)
    $RelPath -replace '\\', '/'
}

function Load-Lock {
    if (Test-Path $LockPath) {
        $raw = Get-Content -Path $LockPath -Raw | ConvertFrom-Json
        $table = @{}
        foreach ($prop in $raw.PSObject.Properties) {
            $table[$prop.Name] = @{
                url    = $prop.Value.url
                sha256 = $prop.Value.sha256
                bytes  = $prop.Value.bytes
            }
        }
        return $table
    }
    return @{}
}

function Save-Lock {
    param([hashtable]$Lock)
    $ordered = [ordered]@{}
    foreach ($key in ($Lock.Keys | Sort-Object)) {
        $ordered[$key] = $Lock[$key]
    }
    $ordered | ConvertTo-Json -Depth 5 | Set-Content -Path $LockPath -Encoding utf8
}

function Download-ToFile {
    param([string]$Url, [string]$DestPath, [string]$UserAgent)
    $parent = Split-Path -Parent $DestPath
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $tmp = "$DestPath.download"
    $headers = @{}
    if ($UserAgent) { $headers['User-Agent'] = $UserAgent }
    Invoke-WebRequest -Uri $Url -Headers $headers -UseBasicParsing -OutFile $tmp
    Move-Item -Path $tmp -Destination $DestPath -Force
}

# Fetches $Url, verifies/updates $Lock[$key], skips network call if already correct on disk.
function Sync-Asset {
    param(
        [string]$Url,
        [string]$RelDest,
        [hashtable]$Lock,
        [string]$UserAgent = $null
    )
    $key      = ConvertTo-LockKey $RelDest
    $destPath = Join-Path $VendorRoot $RelDest
    $existing = $Lock[$key]

    if (-not $Force -and $existing -and (Test-Path $destPath)) {
        $currentHash = Get-Sha256Hex -Path $destPath
        if ($currentHash -eq $existing.sha256) {
            Write-Host "  up to date  $key"
            return
        }
        Write-Warning "  drift detected on disk for $key (expected $($existing.sha256), found $currentHash) -- re-downloading"
    }

    Write-Host "  fetching    $key  <-  $Url"
    Download-ToFile -Url $Url -DestPath $destPath -UserAgent $UserAgent
    $newHash = Get-Sha256Hex -Path $destPath

    if (-not $Force -and $existing -and $existing.sha256 -ne $newHash) {
        throw "Checksum mismatch for $key`: locked hash $($existing.sha256) but CDN now serves $newHash. " +
              "If this is an intentional upstream update, re-run with -Force to relock."
    }

    $Lock[$key] = @{
        url    = $Url
        sha256 = $newHash
        bytes  = (Get-Item $destPath).Length
    }
}

# Django's ManifestStaticFilesStorage resolves sourceMappingURL comments during
# collectstatic and hard-fails if the .map is absent, so vendor those too.
function Sync-SourceMap {
    param([string]$SourceUrl, [string]$RelDest, [hashtable]$Lock)

    $destPath = Join-Path $VendorRoot $RelDest
    $text = Get-Content -Path $destPath -Raw
    $m = [regex]::Match($text, '(?m)^[/*]+#\s*sourceMappingURL=(\S+?)\s*(?:\*/)?$')
    if (-not $m.Success) { return }

    $mapRef = $m.Groups[1].Value
    if ($mapRef -like 'data:*') { return }

    $baseUrl  = $SourceUrl.Substring(0, $SourceUrl.LastIndexOf('/') + 1)
    $mapUrl   = [Uri]::new([Uri]$baseUrl, $mapRef).AbsoluteUri
    $destDir  = Split-Path -Parent $RelDest
    $mapDest  = if ($destDir) { "$destDir\$mapRef" } else { $mapRef }

    Sync-Asset -Url $mapUrl -RelDest ($mapDest -replace '/', '\') -Lock $Lock
}

function Sync-BootstrapIcons {
    param([hashtable]$Lock)

    $cssDestPath = Join-Path $VendorRoot $BootstrapIconsCssDest
    Sync-Asset -Url $BootstrapIconsCssUrl -RelDest $BootstrapIconsCssDest -Lock $Lock

    # Parse the CSS we just vendored for its own relative font references instead of
    # hardcoding fingerprinted filenames -- those change per release.
    $cssText  = Get-Content -Path $cssDestPath -Raw
    $baseUrl  = $BootstrapIconsCssUrl.Substring(0, $BootstrapIconsCssUrl.LastIndexOf('/') + 1)
    $cssDir   = Split-Path -Parent $BootstrapIconsCssDest

    $matches = [regex]::Matches($cssText, 'url\("?(?!https?://|data:|/)([^")?]+)(?:\?[^")]*)?"?\)')
    $seen = New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($m in $matches) {
        $relRef = $m.Groups[1].Value -replace '^\./', ''
        if (-not $seen.Add($relRef)) { continue }

        $fontUrl  = [Uri]::new([Uri]$baseUrl, $relRef).AbsoluteUri
        $fontDest = ($cssDir + '/' + $relRef) -replace '/', '\'
        Sync-Asset -Url $fontUrl -RelDest $fontDest -Lock $Lock
    }
}

function Sync-GoogleFonts {
    param([hashtable]$Lock)

    Write-Host "  fetching    google fonts css2 (latin subset only) <- $GoogleFontsCssUrl"
    $cssText = (Invoke-WebRequest -Uri $GoogleFontsCssUrl -UseBasicParsing -Headers @{ 'User-Agent' = $ChromeUserAgent }).Content

    # Google emits one @font-face block per subset, each preceded by a `/* subset */` comment.
    $blockPattern = [regex]'/\*\s*(?<subset>[a-z0-9-]+)\s*\*/\s*(?<face>@font-face\s*\{[^}]*\})'
    $blocks = [regex]::Matches($cssText, $blockPattern)

    $localRules = New-Object System.Collections.Generic.List[string]

    foreach ($b in $blocks) {
        if ($b.Groups['subset'].Value -ne 'latin') { continue }

        $face = $b.Groups['face'].Value
        $familyMatch = [regex]::Match($face, "font-family:\s*'([^']+)'")
        $weightMatch = [regex]::Match($face, 'font-weight:\s*(\d+)')
        $styleMatch  = [regex]::Match($face, 'font-style:\s*(\w+)')
        $srcMatch    = [regex]::Match($face, "url\((https://fonts\.gstatic\.com/[^)]+\.woff2)\)")

        if (-not $srcMatch.Success) { continue }

        $family = $familyMatch.Groups[1].Value
        $weight = $weightMatch.Groups[1].Value
        $style  = $styleMatch.Groups[1].Value
        $slug   = ($family -replace '\s+', '-').ToLowerInvariant()
        $fileName = "$slug-$weight-$style.woff2"
        $relDest = "fonts\$fileName"

        Sync-Asset -Url $srcMatch.Groups[1].Value -RelDest $relDest -Lock $Lock

        $localRules.Add(@"
@font-face {
  font-family: '$family';
  font-style: $style;
  font-weight: $weight;
  font-display: swap;
  src: url('$fileName') format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+2000-206F, U+2074, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}
"@)
    }

    if ($localRules.Count -eq 0) {
        throw "No latin @font-face blocks parsed from Google Fonts response -- CDN response format may have changed."
    }

    $cssDestPath = Join-Path $VendorRoot $LocalFontsCssDest
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $cssDestPath) | Out-Null
    ($localRules -join "`n`n") | Set-Content -Path $cssDestPath -Encoding utf8

    $key = ConvertTo-LockKey $LocalFontsCssDest
    $Lock[$key] = @{
        url    = $GoogleFontsCssUrl
        sha256 = Get-Sha256Hex -Path $cssDestPath
        bytes  = (Get-Item $cssDestPath).Length
    }
}

function Invoke-VerifyOnly {
    $lock = Load-Lock
    if ($lock.Count -eq 0) {
        Write-Error "No lock file at $LockPath -- run without -VerifyOnly first."
        exit 1
    }
    $problems = 0
    foreach ($key in ($lock.Keys | Sort-Object)) {
        $entry = $lock[$key]
        $path = Join-Path $VendorRoot ($key -replace '/', '\')
        if (-not (Test-Path $path)) {
            Write-Warning "MISSING  $key"
            $problems++
            continue
        }
        $hash = Get-Sha256Hex -Path $path
        if ($hash -ne $entry.sha256) {
            Write-Warning "MISMATCH $key (expected $($entry.sha256), found $hash)"
            $problems++
            continue
        }
        Write-Host "  ok          $key"
    }
    if ($problems -gt 0) {
        Write-Error "$problems vendored asset(s) missing or modified."
        exit 1
    }
    Write-Host "All $($lock.Count) vendored assets verified."
    exit 0
}

# ---------------------------------------------------------------------------

if ($VerifyOnly) {
    Invoke-VerifyOnly
}

New-Item -ItemType Directory -Force -Path $VendorRoot | Out-Null
$lock = Load-Lock

Write-Host "Vendoring frontend assets into $VendorRoot"

foreach ($asset in $DirectAssets) {
    Sync-Asset -Url $asset.Url -RelDest $asset.Dest -Lock $lock
    Sync-SourceMap -SourceUrl $asset.Url -RelDest $asset.Dest -Lock $lock
}

Sync-BootstrapIcons -Lock $lock
Sync-SourceMap -SourceUrl $BootstrapIconsCssUrl -RelDest $BootstrapIconsCssDest -Lock $lock
Sync-GoogleFonts -Lock $lock

Save-Lock -Lock $lock

Write-Host ""
Write-Host "Done. $($lock.Count) assets locked in $LockPath"
Write-Host "Re-run anytime to verify; pass -VerifyOnly for a read-only check (e.g. on the Pi before deploy)."

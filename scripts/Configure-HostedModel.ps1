[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$template = Join-Path $projectRoot '.env.example'
$environmentFile = Join-Path $projectRoot '.env'

if (-not (Test-Path -LiteralPath $template)) {
    throw "Cannot find .env.example in $projectRoot"
}

$endpoint = Read-Host 'OpenAI-compatible chat-completions URL (https://...)'
if (-not [Uri]::IsWellFormedUriString($endpoint, [UriKind]::Absolute) -or
    -not $endpoint.StartsWith('https://', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Use an HTTPS URL supplied by your model provider.'
}

$modelId = Read-Host 'Provider model ID'
if ([string]::IsNullOrWhiteSpace($modelId)) {
    throw 'A provider model ID is required.'
}

$secureKey = Read-Host 'API key (input is hidden)' -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
}
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw 'An API key is required for a hosted model.'
}

$inputPrice = Read-Host 'Input price USD per million tokens [0]'
if ([string]::IsNullOrWhiteSpace($inputPrice)) { $inputPrice = '0' }
$outputPrice = Read-Host 'Output price USD per million tokens [0]'
if ([string]::IsNullOrWhiteSpace($outputPrice)) { $outputPrice = '0' }
foreach ($price in @($inputPrice, $outputPrice)) {
    $number = 0.0
    if (-not [double]::TryParse($price, [Globalization.NumberStyles]::Float,
            [Globalization.CultureInfo]::InvariantCulture, [ref]$number) -or $number -lt 0) {
        throw 'Token prices must be non-negative numbers.'
    }
}

if (Test-Path -LiteralPath $environmentFile) {
    $lines = [Collections.Generic.List[string]](Get-Content -LiteralPath $environmentFile)
}
else {
    $lines = [Collections.Generic.List[string]](Get-Content -LiteralPath $template)
}

function Set-EnvironmentValue([string]$Name, [string]$Value) {
    $pattern = '^{0}=' -f [Regex]::Escape($Name)
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match $pattern) {
            $lines[$index] = "$Name=$Value"
            return
        }
    }
    $lines.Add("$Name=$Value")
}

Set-EnvironmentValue 'MODEL_MODE' 'live'
Set-EnvironmentValue 'MODEL_URL' $endpoint
Set-EnvironmentValue 'MODEL_ID' $modelId
Set-EnvironmentValue 'MODEL_API_KEY' $apiKey
Set-EnvironmentValue 'MODEL_TIMEOUT_SECONDS' '90'
Set-EnvironmentValue 'RUN_TIMEOUT_SECONDS' '360'
Set-EnvironmentValue 'INPUT_USD_PER_MILLION' $inputPrice
Set-EnvironmentValue 'OUTPUT_USD_PER_MILLION' $outputPrice

[IO.File]::WriteAllLines($environmentFile, $lines)
Write-Host 'Hosted-model configuration saved in .env.'
Write-Host 'The API key is local, ignored by Git, and was not printed.'

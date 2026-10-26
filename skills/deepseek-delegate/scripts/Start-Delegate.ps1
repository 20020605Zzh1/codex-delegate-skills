param(
    [Parameter(Mandatory=$true)][string]$TaskDirectory,
    [string]$PromptFile,
    [string]$BatchFile,
    [switch]$Serve,
    [string]$DshPath,
    [string]$PythonPath,
    [string]$SdkDepsPath,
    [string]$CredentialPath
)
$ErrorActionPreference='Stop'
if (-not $PythonPath) {
    $pythonCommand=Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) { throw 'Pass -PythonPath with an installed compatible Python executable.' }
    $PythonPath=$pythonCommand.Source
}
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw 'Python executable not found.' }
if (-not (Test-Path -LiteralPath (Join-Path $TaskDirectory 'task.json') -PathType Leaf)) { throw 'Prepare the project task first.' }
$previousCredential=$env:DEEPSEEK_API_KEY
$previousEncoding=$env:PYTHONIOENCODING
$previousSdkDeps=$env:DEEPSEEK_DELEGATE_SDK_DEPS
$secretPointer=[IntPtr]::Zero
$bridgeExitCode=1
try {
    if (-not $env:DEEPSEEK_API_KEY) {
        if (-not $CredentialPath -or -not (Test-Path -LiteralPath $CredentialPath -PathType Leaf)) { throw 'Set DEEPSEEK_API_KEY locally or pass -CredentialPath with your own DPAPI credential file.' }
        $secureCredential=(Get-Content -LiteralPath $CredentialPath -Raw).Trim() | ConvertTo-SecureString
        $secretPointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureCredential)
        $env:DEEPSEEK_API_KEY=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPointer)
    }
    $env:PYTHONIOENCODING='utf-8'
    if ($SdkDepsPath) { $env:DEEPSEEK_DELEGATE_SDK_DEPS=$SdkDepsPath }
    $bridgeArguments=@('-u',(Join-Path $PSScriptRoot 'bridge.py'),'--task-dir',$TaskDirectory)
    if ($DshPath) { $bridgeArguments+=@('--dsh-bin',$DshPath) }
    if ($Serve) { $bridgeArguments+='--serve' }
    elseif ($BatchFile) { $bridgeArguments+=@('--batch-file',$BatchFile) }
    elseif ($PromptFile) { $bridgeArguments+=@('--prompt-file',$PromptFile) }
    else { throw 'Use -Serve, -PromptFile, or -BatchFile.' }
    & $PythonPath @bridgeArguments
    $bridgeExitCode=$LASTEXITCODE
} finally {
    $env:DEEPSEEK_API_KEY=$previousCredential
    $env:PYTHONIOENCODING=$previousEncoding
    $env:DEEPSEEK_DELEGATE_SDK_DEPS=$previousSdkDeps
    if ($secretPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPointer) }
}
exit $bridgeExitCode

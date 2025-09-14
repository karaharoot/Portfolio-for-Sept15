param(
  [Parameter(Mandatory=$true)] [string]$ComputerListPath,
  [switch]$Install,
  [string]$OutPath = ".\patch_results.csv"
)
if (-not (Get-Module -ListAvailable PSWindowsUpdate)) { Install-Module PSWindowsUpdate -Force -Scope CurrentUser }
Import-Module PSWindowsUpdate
$computers = Get-Content $ComputerListPath
$cred = Get-Credential
$results = foreach ($c in $computers) {
  try {
    $session = New-PSSession -ComputerName $c -Credential $cred -ErrorAction Stop
    Invoke-Command -Session $session -ScriptBlock { Import-Module PSWindowsUpdate }
    $available = Invoke-Command -Session $session -ScriptBlock { Get-WindowsUpdate -MicrosoftUpdate -AcceptAll -IgnoreReboot }
    if ($Install) {
      Invoke-Command -Session $session -ScriptBlock { Install-WindowsUpdate -MicrosoftUpdate -AcceptAll -IgnoreReboot -AutoReboot:$false }
    }
    Remove-PSSession $session
    [pscustomobject]@{ Computer=$c; Count=$($available.Count); Titles=$($available.Title -join ';'); Installed=$Install.IsPresent }
  } catch {
    [pscustomobject]@{ Computer=$c; Count=$null; Titles=$null; Installed=$Install.IsPresent; Error=$_.Exception.Message }
  }
}
$results | Export-Csv -NoTypeInformation -Path $OutPath
Write-Host "Saved $OutPath"

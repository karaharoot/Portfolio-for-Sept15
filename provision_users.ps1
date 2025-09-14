param(
  [Parameter(Mandatory=$true)] [string]$CsvPath,
  [Parameter(Mandatory=$true)] [string]$OU,
  [Parameter(Mandatory=$true)] [securestring]$DefaultPassword,
  [string[]]$DefaultGroups = @()
)
Import-Module ActiveDirectory
$users = Import-Csv -Path $CsvPath
foreach ($u in $users) {
  $upn = "$($u.sAMAccountName)@$($u.domain)"
  if (-not (Get-ADUser -Filter "SamAccountName -eq '$($u.sAMAccountName)'" -ErrorAction SilentlyContinue)) {
    New-ADUser -Name $u.DisplayName -GivenName $u.GivenName -Surname $u.Surname `
      -SamAccountName $u.sAMAccountName -UserPrincipalName $upn -DisplayName $u.DisplayName `
      -EmailAddress $u.Email -Office $u.Office -Department $u.Department -Title $u.Title `
      -Path $OU -AccountPassword $DefaultPassword -Enabled $true -ChangePasswordAtLogon $true
  }
  $allGroups = @()
  if ($u.Groups) { $allGroups += ($u.Groups -split ';') }
  if ($DefaultGroups) { $allGroups += $DefaultGroups }
  foreach ($g in $allGroups) {
    if ([string]::IsNullOrWhiteSpace($g)) { continue }
    if (Get-ADGroup -Filter "Name -eq '$g'" -ErrorAction SilentlyContinue) {
      Add-ADGroupMember -Identity $g -Members $u.sAMAccountName -ErrorAction SilentlyContinue
    }
  }
}

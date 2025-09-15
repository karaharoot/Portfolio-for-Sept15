
# Haroutun Karakossian

This repo contains runnable scripts that mirror real work:
- **SIEM detections** (Splunk SPL Rules)
- **M365 user access automation** (role-based provisioning on mock directory data)
- **Infrastructure ops** (AD provisioning and patch scanning via PowerShell)

# Structure
- `siem/spl/*.spl` — Production-ready Splunk correlation searches
- `m365/user_access_automation.py` — Simulates RBAC provisioning from `sample_data/users.csv`
- `infra/*.ps1` — AD provisioning, compliance reporting, and patch scan scripts
- `sample_data/users.csv` — Mock directory entries with roles


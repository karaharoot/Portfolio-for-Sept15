
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

# Quick Start
```bash
# 1) Generate Sysmon-like logs
python3 siem/python/simulate_sysmon.py --out ./sysmon.jsonl --minutes 15 --rate 20

# 2) Paste SPL into Splunk Search and point to index of your test data
#    Or just sanity-check SPL logic by reading and filtering sysmon.jsonl.

# 3) Simulate M365 provisioning
python3 m365/user_access_automation.py --csv sample_data/users.csv --report out/provision_report.csv
```


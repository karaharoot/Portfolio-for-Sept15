#!/usr/bin/env python3
import argparse, csv, os, pathlib, json, datetime

ROLES = {
  "Engineer": ["MailUser","TeamsUser","SharePointReader"],
  "Analyst": ["MailUser","TeamsUser","SharePointContributor"],
  "Contractor": ["MailUser"],
  "Admin": ["MailUser","TeamsUser","SharePointAdmin","GlobalReader"]
}

def provision_user(u):
    roles = set()
    for r in u.get("Roles","").split(";"):
        r=r.strip()
        if r and r in ROLES: roles.update(ROLES[r])
    mailbox = f"{u['sam']}@example.corp"
    return {
        "sam": u["sam"],
        "display": u["DisplayName"],
        "email": mailbox,
        "assigned_roles": sorted(list(roles)),
        "status": "provisioned"
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--report", default="out/provision_report.csv")
    ap.add_argument("--json", default="out/provision_report.json")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    rows=[]
    with open(args.csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
              "sam": r["sAMAccountName"],
              "DisplayName": r["DisplayName"],
              "Roles": r.get("Roles","")
            })

    results=[provision_user(r) for r in rows]

    with open(args.report,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=["sam","display","email","assigned_roles","status"])
        w.writeheader()
        for r in results:
            r2=r.copy(); r2["assigned_roles"]=";".join(r["assigned_roles"])
            w.writerow(r2)

    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json,"w",encoding="utf-8") as jf:
        json.dump({"generated": datetime.datetime.utcnow().isoformat(), "results": results}, jf, indent=2)
    print(f"Wrote {args.report} and {args.json}")

if __name__=="__main__":
    main()

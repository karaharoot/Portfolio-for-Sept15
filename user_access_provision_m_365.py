import argparse
import csv
import datetime
import json
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

import requests
from msal import ConfidentialClientApplication
from dotenv import load_dotenv
import pandas as pd

# ---- Business role → entitlement mapping (customize to your policies) ---- #
ROLES = {
    "Engineer":   ["MailUser", "TeamsUser", "SharePointReader"],
    "Analyst":    ["MailUser", "TeamsUser", "SharePointContributor"],
    "Contractor": ["MailUser"],
    "Admin":      ["MailUser", "TeamsUser", "SharePointAdmin", "GlobalReader"],
}

# Optionally map entitlements to actual group display names in your tenant
ENTITLEMENT_GROUPS = {
    "MailUser":               ["All Mail Users"],
    "TeamsUser":              ["All Teams Users"],
    "SharePointReader":       ["SharePoint Readers"],
    "SharePointContributor":  ["SharePoint Contributors"],
    "SharePointAdmin":        ["SharePoint Admins"],
    "GlobalReader":           ["Global Readers"],
}

# Known SKU part numbers (examples). Extend as needed for your tenant.
# You can discover your org's SKUs via GET https://graph.microsoft.com/v1.0/subscribedSkus
KNOWN_SKUS = {
    "ENTERPRISEPACK": "Office 365 E3",
    "SPE_E5": "Microsoft 365 E5",
    "EMS": "Enterprise Mobility + Security E3/E5",
    "BUSINESS_PREMIUM": "Microsoft 365 Business Premium",
}

SCOPES = ["https://graph.microsoft.com/.default"]
GRAPH = "https://graph.microsoft.com/v1.0"

load_dotenv()
TENANT_ID = os.getenv("TENANT_ID", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
DEFAULT_USAGE_LOCATION = os.getenv("DEFAULT_USAGE_LOCATION", "US")
DEFAULT_DOMAIN = os.getenv("DEFAULT_DOMAIN", "example.corp")

if not (TENANT_ID and CLIENT_ID and CLIENT_SECRET):
    print("ERROR: TENANT_ID / CLIENT_ID / CLIENT_SECRET must be set (via .env or env vars).", file=sys.stderr)
    sys.exit(2)


def get_token() -> str:
    app = ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(SCOPES)
    if "access_token" not in result:
        raise RuntimeError(f"Token acquisition failed: {result}")
    return result["access_token"]


def graph_get(token: str, url: str, params: Optional[dict] = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, params=params)
    if r.status_code >= 400:
        raise RuntimeError(f"GET {url} failed: {r.status_code} {r.text}")
    return r.json()


def graph_post(token: str, url: str, body: dict, what_if: bool = False) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if what_if:
        return {"what_if": True, "url": url, "body": body}
    r = requests.post(url, headers=headers, json=body)
    if r.status_code >= 400:
        raise RuntimeError(f"POST {url} failed: {r.status_code} {r.text}")
    return r.json() if r.text else {}


def graph_patch(token: str, url: str, body: dict, what_if: bool = False) -> None:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if what_if:
        return
    r = requests.patch(url, headers=headers, json=body)
    if r.status_code >= 400:
        raise RuntimeError(f"PATCH {url} failed: {r.status_code} {r.text}")


def resolve_group_ids_by_name(token: str, names: List[str]) -> Dict[str, Optional[str]]:
    resolved = {}
    for name in names:
        if not name or name.strip() == "":
            resolved[name] = None
            continue
        data = graph_get(token, f"{GRAPH}/groups", params={"$filter": f"displayName eq '{name}'"})
        gid = data["value"][0]["id"] if data.get("value") else None
        resolved[name] = gid
    return resolved


def list_subscribed_skus(token: str) -> Dict[str, str]:
    data = graph_get(token, f"{GRAPH}/subscribedSkus")
    skus = {}
    for sku in data.get("value", []):
        # skuPartNumber like "ENTERPRISEPACK"
        skus[sku.get("skuPartNumber")] = sku.get("skuId")
    return skus


def ensure_user(token: str, user: dict, what_if: bool = False) -> Tuple[str, bool]:
    """Return (user_id, created_bool). If exists, returns existing id and created=False."""
    upn = user["userPrincipalName"]
    # Try to find existing user by UPN
    data = graph_get(token, f"{GRAPH}/users", params={"$filter": f"userPrincipalName eq '{upn}'"})
    if data.get("value"):
        return data["value"][0]["id"], False

    body = {
        "accountEnabled": True,
        "displayName": user["displayName"],
        "mailNickname": user["mailNickname"],
        "userPrincipalName": upn,
        "givenName": user.get("givenName", ""),
        "surname": user.get("surname", ""),
        "department": user.get("department", ""),
        "usageLocation": user.get("usageLocation") or DEFAULT_USAGE_LOCATION,
        "passwordProfile": {
            "forceChangePasswordNextSignIn": True,
            "password": user.get("tempPassword", "TempPass123!")
        }
    }
    created = graph_post(token, f"{GRAPH}/users", body, what_if=what_if)
    if what_if:
        # Simulate an ID for reporting purposes
        return f"whatif-{upn}", True
    return created.get("id"), True


def add_user_to_groups(token: str, user_id: str, group_ids: List[str], what_if: bool = False) -> List[str]:
    added = []
    for gid in group_ids:
        if not gid:
            continue
        url = f"{GRAPH}/groups/{gid}/members/$ref"
        body = {"@odata.id": f"{GRAPH}/directoryObjects/{user_id}"}
        try:
            graph_post(token, url, body, what_if=what_if)
            added.append(gid)
        except Exception as e:
            print(f"WARN: add to group {gid} failed: {e}")
    return added


def assign_licenses(token: str, user_id: str, sku_part_numbers: List[str], what_if: bool = False) -> List[str]:
    if not sku_part_numbers:
        return []
    # Map part numbers to skuIds
    existing = list_subscribed_skus(token)
    to_assign = []
    for pn in sku_part_numbers:
        sid = existing.get(pn)
        if sid:
            to_assign.append({"skuId": sid})
        else:
            print(f"WARN: SKU {pn} not found in tenant subscriptions")

    if not to_assign:
        return []

    url = f"{GRAPH}/users/{user_id}/assignLicense"
    body = {"addLicenses": to_assign, "removeLicenses": []}
    if what_if:
        graph_post(token, url, body, what_if=True)
        return sku_part_numbers

    r = graph_post(token, url, body, what_if=False)
    return [pn for pn in sku_part_numbers]


def expand_business_roles(raw_roles: str) -> List[str]:
    roles = set()
    for r in (raw_roles or "").split(";"):
        r = r.strip()
        if r and r in ROLES:
            roles.update(ROLES[r])
        elif r:
            print(f"WARN: Unknown business role '{r}' — skipping")
    return sorted(list(roles))


def parse_csv(path: str) -> List[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            sam = r.get("sAMAccountName") or r.get("sam") or ""
            display = r.get("DisplayName") or r.get("display") or ""
            given = r.get("GivenName") or r.get("given") or ""
            surname = r.get("Surname") or r.get("sn") or ""
            upn = r.get("UserPrincipalName") or r.get("UPN") or ""
            dept = r.get("Department") or ""
            usage = r.get("UsageLocation") or ""
            roles = r.get("Roles") or ""
            groups = r.get("Groups") or ""
            licenses = r.get("Licenses") or ""

            if not upn:
                if not sam:
                    print(f"ERROR: row missing both UPN and sAMAccountName: {r}")
                    continue
                upn = f"{sam}@{DEFAULT_DOMAIN}"

            mailnick = (sam or upn.split("@")[0]).lower()
            rows.append({
                "sAMAccountName": sam,
                "DisplayName": display,
                "GivenName": given,
                "Surname": surname,
                "UserPrincipalName": upn,
                "Department": dept,
                "UsageLocation": usage or DEFAULT_USAGE_LOCATION,
                "Roles": roles,
                "Groups": groups,
                "Licenses": licenses,
                "mailNickname": mailnick,
            })
    return rows


def ensure_output_dirs(report_path: str, json_path: str):
    rp = os.path.dirname(report_path)
    jp = os.path.dirname(json_path)
    if rp:
        os.makedirs(rp, exist_ok=True)
    if jp:
        os.makedirs(jp, exist_ok=True)


def main():
    ap = argparse.ArgumentParser(description="Provision Microsoft 365 users from CSV via Graph API")
    ap.add_argument("--csv", required=True, help="Input CSV path")
    ap.add_argument("--report", default="out/provision_report.csv", help="Output CSV report path")
    ap.add_argument("--json", default="out/provision_report.json", help="Output JSON report path")
    ap.add_argument("--what-if", action="store_true", help="Dry run — no changes, just simulate actions")
    args = ap.parse_args()

    ensure_output_dirs(args.report, args.json)

    token = get_token()
    rows = parse_csv(args.csv)

    # Resolve group names from explicit CSV + entitlements
    # Build a unique set of all group display names referenced
    all_group_names = set()
    for r in rows:
        # From entitlements
        for ent in expand_business_roles(r.get("Roles", "")):
            for g in ENTITLEMENT_GROUPS.get(ent, []):
                all_group_names.add(g)
        # From explicit CSV
        for g in (r.get("Groups") or "").split(";"):
            g = g.strip()
            if g:
                all_group_names.add(g)

    name_to_id = resolve_group_ids_by_name(token, sorted(list(all_group_names))) if all_group_names else {}

    results = []
    for r in rows:
        upn = r["UserPrincipalName"]
        entitlements = expand_business_roles(r.get("Roles", ""))
        explicit_groups = [g.strip() for g in (r.get("Groups") or "").split(";") if g.strip()]
        # Merge entitlement groups + explicit groups
        target_group_names = set(explicit_groups)
        for ent in entitlements:
            for g in ENTITLEMENT_GROUPS.get(ent, []):
                target_group_names.add(g)
        target_group_ids = [name_to_id.get(n) for n in target_group_names if n in name_to_id]

        sku_parts = [s.strip() for s in (r.get("Licenses") or "").split(";") if s.strip()]

        user_model = {
            "displayName": r["DisplayName"],
            "mailNickname": r["mailNickname"],
            "userPrincipalName": upn,
            "givenName": r.get("GivenName"),
            "surname": r.get("Surname"),
            "department": r.get("Department"),
            "usageLocation": r.get("UsageLocation") or DEFAULT_USAGE_LOCATION,
            "tempPassword": "TempPass123!",  # customize or pass in from a vault
        }

        record = {
            "upn": upn,
            "sam": r.get("sAMAccountName"),
            "display": r["DisplayName"],
            "created": False,
            "groups_added": [],
            "licenses_assigned": [],
            "what_if": args.what_if,
            "error": None,
        }

        try:
            uid, created = ensure_user(token, user_model, what_if=args.what_if)
            record["created"] = created
            if target_group_ids:
                added = add_user_to_groups(token, uid, target_group_ids, what_if=args.what_if)
                record["groups_added"] = added
            if sku_parts:
                assigned = assign_licenses(token, uid, sku_parts, what_if=args.what_if)
                record["licenses_assigned"] = assigned
        except Exception as e:
            record["error"] = str(e)
            print(f"ERROR processing {upn}: {e}")

        results.append(record)

    # Write CSV report
    df = pd.DataFrame(results)
    df.to_csv(args.report, index=False)

    # Write JSON report
    with open(args.json, "w", encoding="utf-8") as jf:
        json.dump({
            "generated": datetime.datetime.utcnow().isoformat(),
            "results": results
        }, jf, indent=2)

    print(f"\nDone. Report(s) written:\n  • {args.report}\n  • {args.json}")


if __name__ == "__main__":
    main()

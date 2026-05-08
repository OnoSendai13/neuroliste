#!/usr/bin/env python3
"""
Find missing addresses using adresse.data.gouv.fr API.
Usage: python find_addresses.py [limit]
"""
import os
import sys
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from models import Neurologue, SessionLocal

def search_address(nom, prenom, commune):
    """Search using adresse.data.gouv.fr API."""
    query = f"{prenom} {nom} {commune}"
    try:
        resp = requests.get(
            "https://api-adresse.data.gouv.fr/search/",
            params={"q": query, "limit": 5, "autocomplete": 0},
            timeout=10
        )
        data = resp.json()
        if data.get("features"):
            for feature in data["features"]:
                props = feature.get("properties", {})
                name = props.get("name", "").lower()
                if nom.lower() in name or prenom.lower() in name:
                    return {
                        "adresse": props.get("street", ""),
                        "code_postal": props.get("postcode", ""),
                        "commune": props.get("city", ""),
                        "score": props.get("score", 0)
                    }
    except Exception as e:
        print(f"Search error: {e}")
    return None

def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    db = SessionLocal()
    
    # Find doctors with empty address
    missing = db.query(Neurologue).filter(
        Neurologue.adresse == ' '
    ).limit(limit).all()
    
    found = 0
    for doc in missing:
        if not doc.adresse or doc.adresse == ' ':
            print(f"Searching for {doc.nom} {doc.prenom} in {doc.commune}...")
            result = search_address(doc.nom, doc.prenom, doc.commune)
            if result and result["score"] > 0.5:
                doc.adresse = f"{result['adresse']} {result['code_postal']} {result['commune']}".strip()
                if not doc.code_postal and result["code_postal"]:
                    doc.code_postal = result["code_postal"]
                found += 1
                print(f"  ✓ Found: {doc.adresse[:60]}")
            else:
                print(f"  ✗ Not found")
    
    db.commit()
    print(f"\nUpdated {found}/{len(missing)} addresses")
    db.close()

if __name__ == "__main__":
    main()
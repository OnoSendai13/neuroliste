#!/usr/bin/env python3
"""
Search for missing contact info using web search.
Usage: python search_missing.py
"""
import requests
from models import Neurologue, SessionLocal
import time

def search_doctor(name, commune):
    """Search for doctor info using DuckDuckGo Instant Answer API."""
    query = f"{name} {commune} neurologue cabinet"
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=10
        )
        data = resp.json()
        # Extract first result URL
        if data.get("AbstractURL"):
            return data["AbstractURL"]
        if data.get("RelatedTopics"):
            for topic in data["RelatedTopics"][:1]:
                if "FirstURL" in topic:
                    return topic["FirstURL"]
    except Exception as e:
        print(f"Search error: {e}")
    return None

def find_and_update():
    db = SessionLocal()
    
    # Find doctors with missing tel or mail
    missing = db.query(Neurologue).filter(
        Neurologue.tel.is_(None) | (Neurologue.tel == "")
    ).limit(10).all()
    
    for doc in missing:
        if not doc.tel:
            print(f"Searching for {doc.nom} {doc.prenom} in {doc.commune}...")
            url = search_doctor(f"{doc.nom} {doc.prenom}", doc.commune)
            if url:
                print(f"  Found: {url}")
                doc.tel = url  # Store URL temporarily
                db.commit()
        time.sleep(1)  # Rate limit
    
    db.close()

if __name__ == "__main__":
    find_and_update()
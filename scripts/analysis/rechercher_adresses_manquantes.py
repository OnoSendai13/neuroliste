#!/usr/bin/env python3
"""Recherche externe d’adresses pour les candidats, sans modifier la DB.

Ce script lit le CSV de candidats produit par generate_adresse_corrections.py,
interroge des sources publiques optionnelles, puis écrit un nouveau CSV enrichi
avec les adresses trouvées et une classification :

- certaine    : nom + profession + localité concordent fortement
- probable    : nom/profession concordent, localité partielle ou source fiable
- non_sure    : correspondance faible, localité absente ou candidats multiples
- non_trouve  : aucune source exploitable trouvée
- erreur_recherche : source indisponible ou erreur réseau

Aucune connexion SQLite n’est ouverte. Aucune écriture n’est faite dans
neurologues.db.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TextIO
from urllib.parse import parse_qs, unquote, urlparse

import requests


BASE_CANDIDATE_COLUMNS = [
    "id_ppss",
    "nom",
    "prenom",
    "code_mode_exercice",
    "categorie_audit",
    "adresse_current",
    "code_postal_current",
    "commune_current",
    "departement_current",
    "region_current",
    "correction_type",
    "suggested_adresse",
    "suggested_code_postal",
    "suggested_commune",
    "suggested_departement",
    "suggested_region",
    "confidence",
    "source",
    "source_url",
    "source_snippet",
    "search_query",
    "status",
    "notes",
]

SEARCH_COLUMNS = [
    "confidence_recherche",
    "score",
    "search_status",
    "search_provider",
    "source_nom",
    "source_adresse",
    "source_code_postal",
    "source_commune",
    "source_departement",
    "source_region",
    "source_siren",
    "source_activite",
    "source_rank",
    "source_match_reason",
]

OUTPUT_COLUMNS = BASE_CANDIDATE_COLUMNS + SEARCH_COLUMNS

ESANTE_BASE_URL = "https://annuaire.esante.gouv.fr"
ESANTE_SESSION: requests.Session | None = None

OFFICIAL_DOMAINS = [
    "doctolib.fr",
    "annuairesante.ameli.fr",
    "sante.fr",
    "conseil-national.medecin.fr",
    "ordre-medecins.fr",
    "service-public.fr",
    "data.gouv.fr",
]

PROFESSION_TERMS = [
    "neurologue",
    "neurologie",
    "médecin neurologue",
    "docteur",
    "cabinet médical",
    "cabinet de neurologie",
]

MEDICAL_ACTIVITY_TERMS = [
    "médecins spécialistes",
    "activité des médecins spécialistes",
    "pratique médicale spécialisée",
    "cabinet médical",
    "neurologie",
]


@dataclass(frozen=True)
class SearchResult:
    provider: str
    rank: int
    name: str
    address: str = ""
    postal_code: str = ""
    commune: str = ""
    department: str = ""
    region: str = ""
    url: str = ""
    snippet: str = ""
    siren: str = ""
    activity: str = ""
    raw: dict[str, object] | None = None


@dataclass(frozen=True)
class SearchDecision:
    confidence: str
    score: int
    status: str
    provider: str
    result: SearchResult | None
    reason: str


def normalize(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip()).lower()


def strip_html(value: str) -> str:
    return html.unescape(re.sub(r"<.*?>", "", value)).strip()


def truncate(value: str, limit: int = 800) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= limit else value[: limit - 3] + "..."


def build_suggested_address(address: str, postal_code: str, commune: str) -> str:
    address = re.sub(r"\s+", " ", address or "").strip(" .,-")
    postal_code = (postal_code or "").strip()
    commune = re.sub(r"\s+", " ", commune or "").strip(" .,-")

    if not address:
        return " ".join(part for part in [postal_code, commune] if part)

    if postal_code and postal_code not in address:
        if commune and commune not in address:
            return f"{address} {postal_code} {commune}"
        return f"{address} {postal_code}".strip()

    return address


def extract_address_from_text(text: str) -> tuple[str, str, str]:
    """Extrait une adresse lisible depuis un snippet DuckDuckGo.

    C’est volontairement conservateur : on ne remplit les suggestions que si un
    code postal français est présent. La commune est déduite avant ou après le
    code postal, en ignorant les artefacts de snippet comme “vues Adresse
    principale” ou “France Voir sur la carte”.
    """

    cleaned = html.unescape(re.sub(r"<.*?>", "", text))
    lowered = cleaned.lower()
    candidate = cleaned

    markers = ["adresse :", "address :", "à son cabinet", "au cabinet", "adresse principale"]
    for marker in markers:
        if marker in lowered:
            candidate = cleaned[lowered.index(marker) + len(marker) :]
            break

    candidate = re.sub(r"\s+", " ", candidate).strip(" .,-")
    candidate = re.sub(r"\b\d+\s+vues\b", "", candidate, flags=re.IGNORECASE).strip(" .,-")

    postal_matches = list(re.finditer(r"\b\d{5}\b", candidate))
    if not postal_matches:
        return "", "", ""

    postal_match = postal_matches[-1]
    postal = postal_match.group(0)
    before = candidate[max(0, postal_match.start() - 120) : postal_match.start()].strip(" .,-")
    after = candidate[postal_match.end() : postal_match.end() + 100].strip(" .,-")

    commune = extract_commune(before, after)
    street = clean_street(candidate[: postal_match.start()])
    return truncate(street, 180), postal, commune


def extract_commune(before: str, after: str) -> str:
    before_tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ’'\-]+", before)
    after_tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ’'\-]+", after)
    noise = {
        "bp",
        "boite",
        "boîte",
        "postale",
        "france",
        "voir",
        "sur",
        "la",
        "carte",
        "adresse",
        "principale",
        "vues",
        "neurologie",
        "neurologue",
        "rendez",
        "prenez",
        "decouvrez",
        "découvrez",
        "coordonnees",
        "coordonnées",
        "localisation",
        "confreres",
        "confrères",
        "proximite",
        "proximité",
        "trouvez",
        "trouver",
        "et",
        "promotions",
        "avec",
        "justacote",
        "justacoté",
        "avis",
        "telephone",
        "téléphone",
        "horaires",
        "plan",
    }

    def clean(tokens: list[str]) -> str:
        stop_indexes = [idx for idx, token in enumerate(tokens) if token.lower() in {"france", "voir", "la", "le", "les", "des", "du", "de", "neurologie", "cabinet"}]
        if stop_indexes:
            tokens = tokens[: stop_indexes[0]]
        tokens = [token for token in tokens if token.lower() not in noise and not token.isdigit()]
        if len(tokens) > 3:
            tokens = tokens[-3:]
        return " ".join(tokens).strip()

    commune = clean(after_tokens)
    if commune:
        return commune

    before_tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ’'\-]+", before)
    for marker in ["bp", "boite", "boîte", "postale", "rue", "avenue", "boulevard", "bd", "place", "allee", "allée", "chemin", "route", "impasse", "quai", "residence", "résidence", "clinique", "hopital", "hôpital", "cabinet", "chr"]:
        indexes = [idx for idx, token in enumerate(before_tokens) if token.lower() == marker]
        if indexes:
            before_tokens = before_tokens[indexes[-1] + 1 :]
            last = clean(before_tokens[-1:])
            return last or clean(before_tokens)

    for token in reversed(before_tokens):
        if token.lower() not in noise and not token.isdigit():
            return token

    return clean(before_tokens)


def clean_street(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" .,-")
    lowered = cleaned.lower()
    for marker in ["adresse principale", "adresse et téléphone", "adresse :", "address :", "situé au", "prenez rendez-vous"]:
        if marker in lowered:
            cleaned = cleaned[lowered.index(marker) + len(marker) :].strip(" .,:-")
            lowered = cleaned.lower()
            break
    cleaned = re.sub(r"\b\d+\s+vues\b", "", cleaned, flags=re.IGNORECASE)
    for suffix in [" France Voir sur la carte", " France", " Voir sur la carte", " La neurologie est", " La neurologie", " Neurologie", " Adresse et", " Prenez", " Découvrez", " Rendez"]:
        if suffix in cleaned:
            cleaned = cleaned.split(suffix, 1)[0].strip(" .,-")

    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ’'\-]+", cleaned)
    street_markers = {
        "rue",
        "avenue",
        "boulevard",
        "bd",
        "place",
        "allee",
        "allée",
        "chemin",
        "route",
        "impasse",
        "quai",
        "residence",
        "résidence",
        "clinique",
        "hopital",
        "hôpital",
        "cabinet",
        "chr",
        "centre",
        "maison",
        "médicale",
        "medicale",
    }
    leading_noise = {"neurologue", "docteur", "dr", "prends", "prenez", "rendez", "agenda"}
    if tokens and (tokens[0].lower() in leading_noise or len(tokens) <= 4) and not any(token.lower() in street_markers for token in tokens):
        return ""

    return cleaned.strip(" .,-")


def read_candidates(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV candidats introuvable : {path}")

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = set(BASE_CANDIDATE_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Colonnes manquantes dans le CSV candidats : {sorted(missing)}")
        return [{key: row.get(key, "").strip() for key in BASE_CANDIDATE_COLUMNS} for row in reader]


def build_query(row: dict[str, str], include_rpps: bool = False) -> str:
    name = " ".join(part for part in [row.get("nom", ""), row.get("prenom", "")] if part)
    locality = " ".join(part for part in [row.get("commune_current", ""), row.get("code_postal_current", ""), row.get("departement_current", "")] if part)
    rpps = row.get("numero_rpps") or row.get("id_ppss") or ""
    parts = [name, "neurologue", locality]
    if include_rpps and rpps:
        parts.insert(0, f"RPPS {rpps}")
    return " ".join(part for part in parts if part)


def search_duckduckgo(query: str, max_results: int, timeout: int, user_agent: str) -> list[SearchResult]:
    results: list[SearchResult] = []
    response = requests.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": user_agent},
        timeout=timeout,
    )
    response.raise_for_status()
    text = response.text

    title_pattern = re.compile(
        r'<a rel="nofollow" class="result__a" href="(?P<url>[^"]+)">(?P<title>.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    snippet_pattern = re.compile(
        r'<a class="result__snippet" href="[^"]*">(?P<snippet>.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    for index, match in enumerate(title_pattern.finditer(text), start=1):
        raw_url = html.unescape(match.group("url"))
        resolved_url = resolve_duckduckgo_url(raw_url)
        title = strip_html(match.group("title"))
        snippet_match = snippet_pattern.search(text[match.end() :])
        snippet = strip_html(snippet_match.group("snippet")) if snippet_match else ""
        results.append(
            SearchResult(
                provider="duckduckgo",
                rank=index,
                name=title,
                url=resolved_url,
                snippet=snippet,
                raw={"title": title, "snippet": snippet, "raw_url": raw_url},
            )
        )
        if len(results) >= max_results:
            break

    return results


def resolve_duckduckgo_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc.endswith("duckduckgo.com"):
        query = parse_qs(parsed.query)
        redirected = query.get("uddg", [""])[0]
        if redirected:
            return unquote(redirected)
    return url


def search_sirene(query: str, max_results: int, timeout: int, user_agent: str) -> list[SearchResult]:
    # DNS de l’API SIRENE peut être instable depuis certains environnements WSL.
    # Les erreurs sont capturées par le caller et marquées comme erreur_recherche.
    response = requests.get(
        "https://api.recherche-entreprises.sirene.gouv.fr/search",
        params={
            "q": query,
            "per_page": max_results,
            "convention_collective": "false",
        },
        headers={"User-Agent": user_agent},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()

    results: list[SearchResult] = []
    for index, item in enumerate(payload.get("results", []), start=1):
        unite = item.get("unite_legale", {}) or {}
        siege = item.get("siege", {}) or {}
        etablissements = item.get("matching_etablissements", []) or []
        commune = siege.get("commune") or unite.get("nom_commune") or ""
        postal = siege.get("code_postal") or ""
        department = siege.get("departement") or unite.get("departement_siege") or ""
        results.append(
            SearchResult(
                provider="sirene",
                rank=index,
                name=item.get("nom_complet") or unite.get("denomination") or unite.get("nom", ""),
                address=siege.get("voie") or "",
                postal_code=postal,
                commune=commune,
                department=department,
                region=siege.get("region") or "",
                url=item.get("link", ""),
                snippet=" | ".join(str(value) for value in [item.get("nom_complet"), siege.get("voie"), postal, commune, unite.get("libelle_activite_principale")] if value),
                siren=unite.get("siren", ""),
                activity=unite.get("libelle_activite_principale", ""),
                raw={"matching_etablissements": len(etablissements), "etat_administratif": unite.get("etat_administratif", "")},
            )
        )
    return results


def esante_payload(row: dict[str, str] | None = None) -> dict[str, object]:
    return {
        "identifiant": (row or {}).get("numero_rpps") or (row or {}).get("id_ppss") or "",
        "emailMss": "",
        "nomExercice": "",
        "prenomExercice": "",
        "codeCategoriePro": "",
        "codeFonction": "",
        "codeSaf": "",
        "codeTypeSaf": "",
        "numTypRueVoie": "",
        "codeProfession": "",
        "codePostal": "",
        "location": {"code": "", "type": ""},
        "raisonSociale": "",
        "enseigneCommerciale": "",
        "idStructure": "",
        "sirenSiret": "",
        "codeApeNaf": "",
        "codeSecteurActivite": "",
        "typeMss": "",
        "showOnlyPpWithMss": "",
    }


def esante_headers(user_agent: str) -> dict[str, str]:
    return {
        "User-Agent": user_agent,
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{ESANTE_BASE_URL}/",
        "Origin": ESANTE_BASE_URL,
        "Content-Type": "application/json",
    }


def esante_ensure_session(timeout: int, user_agent: str) -> requests.Session:
    global ESANTE_SESSION
    if ESANTE_SESSION is None:
        ESANTE_SESSION = requests.Session()
        ESANTE_SESSION.post(
            f"{ESANTE_BASE_URL}/api/search/pp",
            json=esante_payload(),
            headers=esante_headers(user_agent),
            timeout=timeout,
        )
    token = ESANTE_SESSION.cookies.get("XSRF-TOKEN")
    if token:
        ESANTE_SESSION.headers.update({"X-XSRF-TOKEN": token})
    return ESANTE_SESSION


def search_esante(row: dict[str, str], max_results: int, timeout: int, user_agent: str) -> list[SearchResult]:
    identifier = (row.get("numero_rpps") or row.get("id_ppss") or "").strip()
    if not re.fullmatch(r"\d{11}", identifier):
        return []

    session = esante_ensure_session(timeout, user_agent)
    headers = esante_headers(user_agent)
    payload = esante_payload(row)
    response = session.post(
        f"{ESANTE_BASE_URL}/api/search/pp",
        json=payload,
        headers=headers,
        timeout=timeout,
    )

    if response.status_code == 403:
        ESANTE_SESSION = None
        session = esante_ensure_session(timeout, user_agent)
        response = session.post(
            f"{ESANTE_BASE_URL}/api/search/pp",
            json=payload,
            headers=headers,
            timeout=timeout,
        )

    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        return []

    results: list[SearchResult] = []
    for item in data[:max_results]:
        exepros = item.get("exepros") or []
        for rank, exepro in enumerate(exepros[:max_results], start=1):
            situexes = exepro.get("situexes") or []
            first_situation = situexes[0] if situexes else {}
            commune = first_situation.get("commune") or ""
            postal = first_situation.get("codePostal") or ""
            profession = "; ".join(str(value) for value in exepro.get("specialites") or [exepro.get("profession")] if value)
            state = exepro.get("etatExePro") or ""
            snippet = " | ".join(
                str(value)
                for value in [
                    "Annuaire Santé RPPS",
                    item.get("nomExercice") or row.get("nom"),
                    item.get("prenomExercice") or row.get("prenom"),
                    profession,
                    state,
                    commune,
                    postal,
                ]
                if value
            )
            results.append(
                SearchResult(
                    provider="esante",
                    rank=rank,
                    name=" ".join(part for part in [item.get("nomExercice") or row.get("nom"), item.get("prenomExercice") or row.get("prenom")] if part),
                    address="",
                    postal_code=postal,
                    commune=commune,
                    department="",
                    region="",
                    url=f"{ESANTE_BASE_URL}/pp/detail/{identifier}",
                    snippet=snippet,
                    siren=identifier,
                    activity=profession,
                    raw={"item": item, "exepro": exepro},
                )
            )
    return results


def score_result(row: dict[str, str], result: SearchResult) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    row_name = normalize(f"{row.get('nom', '')} {row.get('prenom', '')}")
    row_tokens = {token for token in row_name.split() if len(token) > 1}
    row_commune = normalize(row.get("commune_current", ""))
    row_postal = row.get("code_postal_current", "").strip()
    row_department = row.get("departement_current", "").strip()

    source_text = normalize(" ".join([result.name, result.address, result.postal_code, result.commune, result.snippet, result.activity]))
    source_name = normalize(result.name)
    source_commune = normalize(result.commune)
    source_postal = result.postal_code.strip()
    source_department = result.department.strip()
    source_url = normalize(result.url)
    source_snippet = normalize(result.snippet)

    matched_name_tokens = sum(1 for token in row_tokens if token in source_text)
    if row_tokens and matched_name_tokens >= max(1, min(2, len(row_tokens))):
        score += 40
        reasons.append(f"nom concordant ({matched_name_tokens}/{len(row_tokens)})")
    elif row_tokens and any(token in source_text for token in row_tokens):
        score += 20
        reasons.append(f"nom partiel ({matched_name_tokens}/{len(row_tokens)})")

    if any(term in source_text for term in PROFESSION_TERMS):
        score += 15
        reasons.append("profession neurologue détectée")

    if any(term in normalize(result.activity) for term in MEDICAL_ACTIVITY_TERMS):
        reasons.append("activité médicale Annuaire Santé" if result.provider == "esante" else "activité médicale SIRENE")

    if "médecine générale" in source_text or "generaliste" in source_text:
        score -= 20
        reasons.append("profession différente détectée")

    if row_commune and source_commune and row_commune in source_commune:
        score += 20
        reasons.append("commune concordante")
    elif row_commune and row_commune in source_text:
        score += 10
        reasons.append("commune dans snippet")

    if row_postal and source_postal == row_postal:
        score += 15
        reasons.append("code postal concordant")
    elif row_postal and row_postal in source_text:
        score += 8
        reasons.append("code postal dans snippet")

    if row_department and source_department == row_department:
        score += 8
        reasons.append("département concordant")

    _extracted_address, extracted_postal, extracted_commune = extract_address_from_text(result.snippet)
    if extracted_postal or extracted_commune:
        score += 12
        reasons.append("localité extraite du snippet")

    if any(domain in source_url for domain in OFFICIAL_DOMAINS):
        score += 8
        reasons.append("source officielle ou annuaire médical connu")

    if result.raw and result.raw.get("matching_etablissements") == 1:
        score += 5
        reasons.append("un seul établissement SIRENE correspondant")

    if result.raw and result.raw.get("etat_administratif") == "A":
        score += 3
        reasons.append("établissement actif")

    return score, reasons


def classify(score: int, result: SearchResult | None, reasons: list[str]) -> tuple[str, str]:
    if result is None:
        return "non_trouve", "aucun résultat exploitable trouvé"

    source_text = normalize(" ".join([result.name, result.address, result.postal_code, result.commune, result.snippet, result.activity]))
    has_locality = bool(result.postal_code or result.commune or result.department)
    has_snippet_locality = any("localité extraite" in reason for reason in reasons)

    if score >= 80 and (has_locality or has_snippet_locality):
        return "certaine", "; ".join(reasons) or "nom, profession et localité concordants"

    if score >= 60 and (has_locality or has_snippet_locality):
        return "probable", "; ".join(reasons) or "correspondance forte et localité partielle"

    if score >= 60:
        return "non_sure", "; ".join(reasons + ["adresse/localité absente"]) or "correspondance forte mais adresse/localité absente"

    if score >= 35:
        return "non_sure", "; ".join(reasons) or "correspondance partielle"

    return "non_sure", "score insuffisant pour valider automatiquement"


def decide(row: dict[str, str], providers: list[str], max_results: int, timeout: int, sleep: float, user_agent: str, include_rpps_query: bool = False) -> SearchDecision:
    query = row.get("search_query") or build_query(row, include_rpps=include_rpps_query)
    errors: list[str] = []
    best: tuple[int, SearchResult, list[str]] | None = None

    for provider in providers:
        try:
            if provider == "duckduckgo":
                results = search_duckduckgo(query, max_results=max_results, timeout=timeout, user_agent=user_agent)
            elif provider == "sirene":
                results = search_sirene(query, max_results=max_results, timeout=timeout, user_agent=user_agent)
            elif provider == "esante":
                results = search_esante(row, max_results=max_results, timeout=timeout, user_agent=user_agent)
            else:
                errors.append(f"provider inconnu : {provider}")
                continue

            for result in results:
                score, reasons = score_result(row, result)
                if best is None or score > best[0]:
                    best = (score, result, reasons)

            if sleep > 0:
                time.sleep(sleep)
        except Exception as exc:  # noqa: BLE001 - on veut continuer le batch
            errors.append(f"{provider}: {type(exc).__name__}: {exc}")

    if errors and best is None:
        return SearchDecision(
            confidence="erreur_recherche",
            score=0,
            status="erreur_recherche",
            provider=",".join(providers),
            result=None,
            reason="; ".join(errors),
        )

    if best is None:
        confidence, reason = classify(0, None, [])
        return SearchDecision(
            confidence=confidence,
            score=0,
            status=confidence,
            provider=",".join(providers),
            result=None,
            reason=reason or "; ".join(errors),
        )

    score, result, reasons = best
    confidence, reason = classify(score, result, reasons)
    return SearchDecision(
        confidence=confidence,
        score=score,
        status=confidence,
        provider=result.provider,
        result=result,
        reason=reason,
    )


def enrich_row(row: dict[str, str], decision: SearchDecision) -> dict[str, str]:
    enriched = dict(row)
    result = decision.result

    for column in SEARCH_COLUMNS:
        enriched[column] = ""

    enriched["confidence_recherche"] = decision.confidence
    enriched["score"] = str(decision.score)
    enriched["search_status"] = decision.status
    enriched["search_provider"] = decision.provider
    enriched["source_match_reason"] = decision.reason

    if result is not None:
        extracted_address, extracted_postal, extracted_commune = extract_address_from_text(result.snippet)
        source_address = result.address or extracted_address
        source_postal = result.postal_code or extracted_postal
        source_commune = result.commune or extracted_commune

        enriched["source_nom"] = result.name
        enriched["source_adresse"] = source_address
        enriched["source_code_postal"] = source_postal
        enriched["source_commune"] = source_commune
        enriched["source_departement"] = result.department
        enriched["source_region"] = result.region
        enriched["source_siren"] = result.siren
        enriched["source_activite"] = result.activity
        enriched["source_rank"] = str(result.rank)
        enriched["source_url"] = result.url
        enriched["source_snippet"] = truncate(result.snippet)

        if decision.confidence in {"certaine", "probable"} or (
            decision.confidence == "non_sure" and decision.score >= 35 and (source_postal or source_commune)
        ):
            if decision.confidence == "non_sure":
                enriched["confidence_recherche"] = "probable"
                enriched["search_status"] = "probable"
                enriched["source_match_reason"] = (decision.reason + "; localité extraite après scoring").strip("; ")
                enriched["notes"] = "Adresse extraite à valider : plusieurs adresses possibles ou anciennes visibles."

            enriched["suggested_adresse"] = build_suggested_address(source_address, source_postal, source_commune)
            enriched["suggested_code_postal"] = source_postal
            enriched["suggested_commune"] = source_commune
            enriched["suggested_departement"] = result.department
            enriched["suggested_region"] = result.region
            enriched["confidence"] = enriched["confidence_recherche"]
            enriched["source"] = result.provider
            enriched["status"] = enriched["confidence_recherche"]

    return {key: truncate(enriched.get(key, ""), 1200) for key in OUTPUT_COLUMNS}


def read_existing_ids(path: Path) -> set[str]:
    if not path.exists() or path.stat().st_size == 0:
        return set()

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return {row.get("id_ppss", "").strip() for row in reader if row.get("id_ppss", "").strip()}


def open_output_csv(path: Path, append: bool) -> tuple[TextIO, csv.DictWriter]:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    f = path.open(mode, newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
    if not append:
        writer.writeheader()
    return f, writer


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_output_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []

    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_summary(path: Path, rows: list[dict[str, str]], providers: list[str], processed: int = 0, skipped: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "total_rows": len(rows),
        "processed_in_this_run": processed,
        "skipped_already_present": skipped,
        "by_confidence": dict(sorted(Counter(row["confidence_recherche"] for row in rows).items())),
        "by_provider": dict(sorted(Counter(row["search_provider"] for row in rows if row["search_provider"]).items())),
        "providers": providers,
        "columns": OUTPUT_COLUMNS,
        "guardrails": [
            "Ce script lit le CSV candidat et écrit un nouveau CSV enrichi.",
            "Aucune connexion SQLite n’est ouverte.",
            "Aucune modification n’est appliquée dans neurologues.db.",
            "Les suggestions certaines/probables restent à valider avant correction externe.",
        ],
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_providers(value: str) -> list[str]:
    providers = [item.strip() for item in value.split(",") if item.strip()]
    allowed = {"duckduckgo", "sirene", "esante"}
    unknown = sorted(set(providers) - allowed)
    if unknown:
        raise ValueError(f"Providers inconnus : {unknown}. Attendu : {sorted(allowed)}")
    return providers


def main() -> int:
    default_project = Path("/mnt/g/Neuro-liste/rpps-neuro-app")
    parser = argparse.ArgumentParser(description="Recherche externe et classification des adresses candidates.")
    parser.add_argument(
        "--in",
        dest="input",
        default=default_project / "data/corrections/adresse_corrections_candidates.csv",
        type=Path,
        help="CSV candidats produit par generate_adresse_corrections.py.",
    )
    parser.add_argument(
        "--out",
        default=default_project / "data/corrections/adresse_corrections_recherchees.csv",
        type=Path,
        help="CSV enrichi en sortie.",
    )
    parser.add_argument(
        "--summary",
        default=default_project / "data/corrections/adresse_corrections_recherchees_summary.json",
        type=Path,
        help="Résumé JSON de la recherche.",
    )
    parser.add_argument(
        "--resume-from",
        default=None,
        type=Path,
        help="CSV enrichi existant à reprendre. Les id_ppss déjà présents sont sautés.",
    )
    parser.add_argument(
        "--providers",
        default="duckduckgo,sirene",
        help="Providers séparés par des virgules : duckduckgo,sirene,esante.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optionnel : limite le nombre de lignes traitées, utile pour tester.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Nombre maximum de résultats par provider et par ligne.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Timeout HTTP en secondes.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Pause entre les requêtes HTTP, en secondes.",
    )
    parser.add_argument(
        "--user-agent",
        default="Mozilla/5.0 RPPS-Neuro local audit script",
        help="User-Agent HTTP.",
    )
    parser.add_argument(
        "--rpps-query",
        action="store_true",
        help="Utilise une requête DuckDuckGo ciblée avec le RPPS/id_ppss : 'RPPS 12345678901 Nom Prénom neurologue'.",
    )
    args = parser.parse_args()

    providers = parse_providers(args.providers)
    candidates = read_candidates(args.input)
    if args.limit is not None:
        candidates = candidates[: args.limit]

    resume_from = args.resume_from or args.out
    existing_ids = read_existing_ids(resume_from)
    append_output = bool(existing_ids)
    processed = 0
    skipped = 0

    output_file, writer = open_output_csv(args.out, append_output)
    try:
        for index, row in enumerate(candidates, start=1):
            row_id = row.get("id_ppss", "").strip()
            if row_id in existing_ids:
                skipped += 1
                continue

            decision = decide(
                row,
                providers=providers,
                max_results=args.max_results,
                timeout=args.timeout,
                sleep=args.sleep,
                user_agent=args.user_agent,
                include_rpps_query=args.rpps_query,
            )
            enriched = enrich_row(row, decision)
            writer.writerow(enriched)
            output_file.flush()
            processed += 1
            print(
                f"{index:03d}/{len(candidates)} "
                f"{row.get('nom', '')} {row.get('prenom', '')} -> "
                f"{decision.confidence} score={decision.score} provider={decision.provider}",
                flush=True,
            )

            if args.limit is not None and processed >= args.limit:
                break
    finally:
        output_file.close()

    output_rows = read_output_rows(args.out)
    write_summary(args.summary, output_rows, providers, processed=processed, skipped=skipped)

    counts = Counter(row["confidence_recherche"] for row in output_rows)
    print(f"input : {args.input}")
    print(f"resume_from : {resume_from}")
    print(f"output : {args.out}")
    print(f"summary : {args.summary}")
    print(f"processed_in_this_run : {processed}")
    print(f"skipped_already_present : {skipped}")
    print("by_confidence : " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    print("aucune modification DB effectuée")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

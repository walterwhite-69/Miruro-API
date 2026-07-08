import base64, json, gzip, os, re, time
from typing import Optional, List, Any, Dict
from urllib.parse import urljoin, quote, urlparse

import httpx
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Miruro API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ══════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Referer": "https://www.miruro.tv/",
    "Origin": "https://www.miruro.tv",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "sec-ch-ua": '"Chromium";v="110", "Not A(Brand";v="24", "Google Chrome";v="110"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}
ANILIST_URL = "https://graphql.anilist.co"
MIRURO_PIPE_URL = "https://www.miruro.tv/api/secure/pipe"

MANGA_BASE_URL = "https://mangakatana.com"
MANGA_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# ── Optional outbound proxy ─────────────────────────────────────
# Miruro's pipe endpoint and some stream CDNs (owocdn / kwik) sit behind
# Cloudflare and hard-block datacenter IPs (Railway, Vercel, Render, ...).
# When hosted on such a platform, set OUTBOUND_PROXY to a residential/clean
# proxy URL (e.g. "http://user:pass@host:port") to route the blocked requests
# through it. To conserve metered residential bandwidth, the proxy is applied
# ONLY to the hosts listed in OUTBOUND_PROXY_HOSTS (comma-separated substrings,
# default: owocdn.top). Set PIPE_VIA_PROXY=true to also route the Miruro pipe
# (episodes / sources) requests through the proxy.
OUTBOUND_PROXY = os.getenv("OUTBOUND_PROXY", "").strip()
OUTBOUND_PROXY_HOSTS = [
    h.strip() for h in os.getenv("OUTBOUND_PROXY_HOSTS", "owocdn.top").split(",") if h.strip()
]
PIPE_VIA_PROXY = os.getenv("PIPE_VIA_PROXY", "false").lower() in ("1", "true", "yes")


def _host_needs_proxy(url: str) -> bool:
    if not OUTBOUND_PROXY:
        return False
    return any(h and h in url for h in OUTBOUND_PROXY_HOSTS)


def _httpx_proxy_for(url: str) -> Optional[str]:
    """Return the outbound proxy URL for hosts that need it, else None."""
    return OUTBOUND_PROXY if _host_needs_proxy(url) else None


def _pipe_proxies() -> Optional[dict]:
    """curl_cffi proxies mapping for the Miruro pipe, when enabled."""
    if PIPE_VIA_PROXY and OUTBOUND_PROXY:
        return {"http": OUTBOUND_PROXY, "https": OUTBOUND_PROXY}
    return None


# ══════════════════════════════════════════════════════════════
# RESPONSE HELPERS
# ══════════════════════════════════════════════════════════════
# The AniNami frontend calls this backend under an `/api` prefix and expects
# every JSON payload wrapped as { success, results }. The `ok`/`err` helpers
# produce that envelope for the `/api/*` routes; the legacy root routes keep
# returning the raw Miruro-API shapes for direct/public consumers.

def ok(data: Any, status: int = 200) -> JSONResponse:
    return JSONResponse({"success": True, "results": data}, status_code=status)


def err(message: str, status: int = 500) -> JSONResponse:
    return JSONResponse({"success": False, "message": message}, status_code=status)


def _proxy_img(url: str) -> str:
    return url


def _proxy_deep_images(obj):
    return obj


# ══════════════════════════════════════════════════════════════
# ANILIST FIELD FRAGMENTS
# ══════════════════════════════════════════════════════════════

MEDIA_LIST_FIELDS = """
    id
    idMal
    title { romaji english native }
    coverImage { large extraLarge medium color }
    bannerImage
    format
    season
    seasonYear
    episodes
    chapters
    volumes
    duration
    status
    averageScore
    meanScore
    popularity
    favourites
    genres
    source
    countryOfOrigin
    isAdult
    studios(isMain: true) { nodes { name isAnimationStudio } }
    nextAiringEpisode { episode airingAt timeUntilAiring }
    startDate { year month day }
    endDate { year month day }
"""

MEDIA_FULL_FIELDS = """
    id
    idMal
    title { romaji english native }
    description(asHtml: false)
    coverImage { large extraLarge medium color }
    bannerImage
    format
    season
    seasonYear
    episodes
    chapters
    volumes
    duration
    status
    averageScore
    meanScore
    popularity
    favourites
    trending
    genres
    tags { name rank isMediaSpoiler }
    source
    countryOfOrigin
    isAdult
    hashtag
    synonyms
    siteUrl
    trailer { id site thumbnail }
    studios { nodes { id name isAnimationStudio siteUrl } }
    nextAiringEpisode { episode airingAt timeUntilAiring }
    startDate { year month day }
    endDate { year month day }
    characters(sort: [ROLE, RELEVANCE], perPage: 25) {
        edges {
            role
            node { id name { full native } image { large } }
            voiceActors(language: JAPANESE) { id name { full native } image { large } languageV2 }
        }
    }
    staff(sort: RELEVANCE, perPage: 25) {
        edges {
            role
            node { id name { full native } image { large } }
        }
    }
    relations {
        edges {
            relationType(version: 2)
            node {
                id
                title { romaji english native }
                coverImage { large }
                format
                type
                status
                episodes
                chapters
                meanScore
            }
        }
    }
    recommendations(sort: RATING_DESC, perPage: 10) {
        nodes {
            rating
            mediaRecommendation {
                id
                title { romaji english native }
                coverImage { large }
                format
                episodes
                status
                meanScore
                averageScore
            }
        }
    }
    externalLinks { url site type }
    streamingEpisodes { title thumbnail url site }
    stats {
        scoreDistribution { score amount }
        statusDistribution { status amount }
    }
"""

REC_MEDIA_FIELDS = """
    id
    title { romaji english native }
    coverImage { large extraLarge medium color }
    bannerImage
    format
    season
    seasonYear
    episodes
    duration
    status
    averageScore
    meanScore
    popularity
    genres
    isAdult
"""


# ══════════════════════════════════════════════════════════════
# PIPE (episodes / sources) HELPERS
# ══════════════════════════════════════════════════════════════

def _inject_source_slugs(data: dict, anilist_id: int):
    providers = data.get("providers", {})
    for provider_name, provider_data in providers.items():
        if not isinstance(provider_data, dict):
            continue
        episodes = provider_data.get("episodes", {})
        if not isinstance(episodes, dict):
            if isinstance(episodes, list):
                provider_data["episodes"] = {"sub": episodes}
                episodes = provider_data["episodes"]
            else:
                continue
        for category, ep_list in episodes.items():
            if not isinstance(ep_list, list):
                continue
            for ep in ep_list:
                if not isinstance(ep, dict):
                    continue
                if "id" in ep and "number" in ep:
                    orig_id = ep["id"]
                    prefix = orig_id.split(":")[0] if ":" in orig_id else orig_id
                    ep["id"] = f"watch/{provider_name}/{anilist_id}/{category}/{prefix}-{ep['number']}"
    return data


async def _fetch_raw_episodes(anilist_id: int) -> dict:
    payload = {
        "path": "episodes",
        "method": "GET",
        "query": {"anilistId": anilist_id},
        "body": None,
        "version": "0.1.0",
    }
    encoded_req = _encode_pipe_request(payload)
    async with AsyncSession(impersonate="chrome110", proxies=_pipe_proxies()) as client:
        res = await client.get(f"{MIRURO_PIPE_URL}?e={encoded_req}", headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail={"status": res.status_code, "body": res.text[:500], "headers": dict(res.headers)})
        data = _decode_pipe_response(res.text.strip())
        _deep_translate(data)
        return data


def _translate_id(encoded_id: str) -> str:
    try:
        decoded = base64.urlsafe_b64decode(encoded_id + '=' * (4 - len(encoded_id) % 4)).decode()
        if ':' in decoded:
            return decoded
        return encoded_id
    except Exception:
        return encoded_id


def _deep_translate(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == 'id' and isinstance(value, str):
                obj[key] = _translate_id(value)
            elif isinstance(value, (dict, list)):
                _deep_translate(value)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                _deep_translate(item)


def _decode_pipe_response(encoded_str: str) -> dict:
    try:
        encoded_str += '=' * (4 - len(encoded_str) % 4)
        compressed = base64.urlsafe_b64decode(encoded_str)
        return json.loads(gzip.decompress(compressed).decode('utf-8'))
    except Exception:
        raise ValueError("Failed to decode pipe response")


def _encode_pipe_request(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')


async def _anilist_query(query: str, variables: dict = None):
    body = {"query": query}
    if variables:
        body["variables"] = variables
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(ANILIST_URL, json=body)
        if res.status_code != 200:
            raise HTTPException(status_code=500, detail="AniList query failed")
        payload = res.json()
        if payload.get("errors"):
            msg = payload["errors"][0].get("message", "AniList query failed")
            raise HTTPException(status_code=500, detail=msg)
        return payload.get("data", {})


# ══════════════════════════════════════════════════════════════
# CORE DATA LOGIC (shared by root + /api routes)
# ══════════════════════════════════════════════════════════════

def _media_type(type_: Optional[str]) -> str:
    return "MANGA" if str(type_ or "").upper() == "MANGA" else "ANIME"


SORT_MAP = {
    "SCORE_DESC": "SCORE_DESC",
    "POPULARITY_DESC": "POPULARITY_DESC",
    "TRENDING_DESC": "TRENDING_DESC",
    "START_DATE_DESC": "START_DATE_DESC",
    "FAVOURITES_DESC": "FAVOURITES_DESC",
    "UPDATED_AT_DESC": "UPDATED_AT_DESC",
    "SEARCH_MATCH": "SEARCH_MATCH",
}


async def _search(query: str, page: int, per_page: int, sort: str = "SEARCH_MATCH", type_: str = "ANIME") -> dict:
    media_type = _media_type(type_)
    sort_val = SORT_MAP.get((sort or "SEARCH_MATCH").upper(), "SEARCH_MATCH")
    gql = f"""
    query ($search: String, $page: Int, $perPage: Int) {{
        Page(page: $page, perPage: $perPage) {{
            pageInfo {{ total currentPage lastPage hasNextPage perPage }}
            media(search: $search, type: {media_type}, sort: [{sort_val}]) {{
                {MEDIA_LIST_FIELDS}
            }}
        }}
    }}
    """
    data = await _anilist_query(gql, {"search": query, "page": page, "perPage": per_page})
    page_data = data.get("Page", {})
    page_info = page_data.get("pageInfo", {})
    return {
        "page": page_info.get("currentPage", page),
        "perPage": page_info.get("perPage", per_page),
        "total": page_info.get("total", 0),
        "hasNextPage": page_info.get("hasNextPage", False),
        "results": page_data.get("media", []),
    }


async def _suggestions(query: str) -> list:
    gql = """
    query ($search: String) {
        Page(page: 1, perPage: 8) {
            media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
                id
                title { romaji english }
                coverImage { large }
                format
                status
                startDate { year }
                episodes
            }
        }
    }
    """
    data = await _anilist_query(gql, {"search": query})
    results = []
    for item in data.get("Page", {}).get("media", []):
        results.append({
            "id": item["id"],
            "title": item["title"].get("english") or item["title"].get("romaji"),
            "title_romaji": item["title"].get("romaji"),
            "poster": item["coverImage"]["large"],
            "format": item.get("format"),
            "status": item.get("status"),
            "year": (item.get("startDate") or {}).get("year"),
            "episodes": item.get("episodes"),
        })
    return results


async def _filter(genre=None, tag=None, year=None, season=None, format=None,
                  status=None, sort="POPULARITY_DESC", page=1, per_page=20,
                  type_="ANIME", country=None, search=None) -> dict:
    media_type = _media_type(type_)
    args = [f"type: {media_type}", f"sort: [{SORT_MAP.get((sort or 'POPULARITY_DESC').upper(), 'POPULARITY_DESC')}]"]
    variables = {"page": page, "perPage": per_page}
    var_types = ["$page: Int", "$perPage: Int"]

    if search:
        args.append("search: $search"); variables["search"] = search; var_types.append("$search: String")
    if genre:
        args.append("genre: $genre"); variables["genre"] = genre; var_types.append("$genre: String")
    if tag:
        args.append("tag: $tag"); variables["tag"] = tag; var_types.append("$tag: String")
    if year:
        args.append("seasonYear: $seasonYear"); variables["seasonYear"] = int(year); var_types.append("$seasonYear: Int")
    if season:
        args.append("season: $season"); variables["season"] = season.upper(); var_types.append("$season: MediaSeason")
    if format:
        args.append("format: $format"); variables["format"] = format.upper(); var_types.append("$format: MediaFormat")
    if status:
        args.append("status: $status"); variables["status"] = status.upper(); var_types.append("$status: MediaStatus")
    if country:
        args.append("countryOfOrigin: $country"); variables["country"] = country.upper(); var_types.append("$country: CountryCode")

    gql = f"""
    query ({', '.join(var_types)}) {{
        Page(page: $page, perPage: $perPage) {{
            pageInfo {{ total currentPage lastPage hasNextPage perPage }}
            media({', '.join(args)}) {{
                {MEDIA_LIST_FIELDS}
            }}
        }}
    }}
    """
    data = await _anilist_query(gql, variables)
    page_data = data.get("Page", {})
    page_info = page_data.get("pageInfo", {})
    return {
        "page": page_info.get("currentPage", page),
        "perPage": page_info.get("perPage", per_page),
        "total": page_info.get("total", 0),
        "hasNextPage": page_info.get("hasNextPage", False),
        "results": page_data.get("media", []),
    }


async def _collection(sort_type: str, status: str = None, page: int = 1, per_page: int = 20, type_: str = "ANIME") -> dict:
    media_type = _media_type(type_)
    status_filter = f", status: {status}" if status else ""
    gql = f"""
    query ($page: Int, $perPage: Int) {{
        Page(page: $page, perPage: $perPage) {{
            pageInfo {{ total currentPage lastPage hasNextPage perPage }}
            media(type: {media_type}, sort: [{sort_type}]{status_filter}) {{
                {MEDIA_LIST_FIELDS}
            }}
        }}
    }}
    """
    data = await _anilist_query(gql, {"page": page, "perPage": per_page})
    page_data = data.get("Page", {})
    page_info = page_data.get("pageInfo", {})
    return {
        "page": page_info.get("currentPage", page),
        "perPage": page_info.get("perPage", per_page),
        "total": page_info.get("total", 0),
        "hasNextPage": page_info.get("hasNextPage", False),
        "results": page_data.get("media", []),
    }


async def _spotlight() -> list:
    gql = f"""
    query {{
        Page(page: 1, perPage: 10) {{
            media(sort: [TRENDING_DESC, POPULARITY_DESC], type: ANIME) {{
                {MEDIA_LIST_FIELDS}
            }}
        }}
    }}
    """
    data = await _anilist_query(gql)
    return data.get("Page", {}).get("media", [])


async def _schedule(page: int = 1, per_page: int = 20, date: Optional[str] = None) -> dict:
    variables = {"page": page, "perPage": per_page}
    filter_clause = ""
    var_extra = ""
    if date:
        try:
            import datetime
            d = datetime.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
            start = int(d.timestamp())
            end = start + 86400
            variables["airingAtGreater"] = start
            variables["airingAtLesser"] = end
            filter_clause = "airingAt_greater: $airingAtGreater, airingAt_lesser: $airingAtLesser,"
            var_extra = ", $airingAtGreater: Int, $airingAtLesser: Int"
        except Exception:
            pass
    gql = f"""
    query ($page: Int, $perPage: Int{var_extra}) {{
        Page(page: $page, perPage: $perPage) {{
            pageInfo {{ total currentPage lastPage hasNextPage perPage }}
            airingSchedules({filter_clause} notYetAired: true, sort: TIME) {{
                episode
                airingAt
                timeUntilAiring
                media {{
                    {MEDIA_LIST_FIELDS}
                }}
            }}
        }}
    }}
    """
    data = await _anilist_query(gql, variables)
    page_data = data.get("Page", {})
    page_info = page_data.get("pageInfo", {})
    results = []
    for item in page_data.get("airingSchedules", []):
        entry = item.get("media", {}) or {}
        entry["next_episode"] = item.get("episode")
        entry["airingAt"] = item.get("airingAt")
        entry["timeUntilAiring"] = item.get("timeUntilAiring")
        results.append(entry)
    return {
        "page": page_info.get("currentPage", page),
        "perPage": page_info.get("perPage", per_page),
        "total": page_info.get("total", 0),
        "hasNextPage": page_info.get("hasNextPage", False),
        "results": results,
    }


async def _info(anilist_id: int, type_: str = "ANIME") -> dict:
    media_type = _media_type(type_)
    gql = f"""
    query ($id: Int) {{
        Media(id: $id, type: {media_type}) {{
            {MEDIA_FULL_FIELDS}
        }}
    }}
    """
    data = await _anilist_query(gql, {"id": anilist_id})
    media = data.get("Media")
    if not media:
        raise HTTPException(status_code=404, detail="Not found")
    return media


async def _characters(anilist_id: int, page: int = 1, per_page: int = 25, type_: str = "ANIME") -> dict:
    media_type = _media_type(type_)
    gql = f"""
    query ($id: Int, $page: Int, $perPage: Int) {{
        Media(id: $id, type: {media_type}) {{
            id
            title {{ romaji english }}
            characters(sort: [ROLE, RELEVANCE], page: $page, perPage: $perPage) {{
                pageInfo {{ total currentPage lastPage hasNextPage perPage }}
                edges {{
                    role
                    node {{
                        id
                        name {{ full native userPreferred }}
                        image {{ large medium }}
                        description
                        gender
                        dateOfBirth {{ year month day }}
                        age
                        favourites
                        siteUrl
                    }}
                    voiceActors {{
                        id
                        name {{ full native }}
                        image {{ large }}
                        languageV2
                    }}
                }}
            }}
        }}
    }}
    """
    data = await _anilist_query(gql, {"id": anilist_id, "page": page, "perPage": per_page})
    media = data.get("Media")
    if not media:
        raise HTTPException(status_code=404, detail="Not found")
    chars = media.get("characters", {})
    page_info = chars.get("pageInfo", {})
    return {
        "page": page_info.get("currentPage", page),
        "perPage": page_info.get("perPage", per_page),
        "total": page_info.get("total", 0),
        "hasNextPage": page_info.get("hasNextPage", False),
        "characters": chars.get("edges", []),
    }


async def _relations(anilist_id: int, type_: str = "ANIME") -> dict:
    media_type = _media_type(type_)
    gql = f"""
    query ($id: Int) {{
        Media(id: $id, type: {media_type}) {{
            id
            title {{ romaji english }}
            relations {{
                edges {{
                    relationType(version: 2)
                    node {{
                        id
                        title {{ romaji english native }}
                        coverImage {{ large }}
                        bannerImage
                        format
                        type
                        status
                        episodes
                        chapters
                        meanScore
                        averageScore
                        popularity
                        startDate {{ year month day }}
                    }}
                }}
            }}
        }}
    }}
    """
    data = await _anilist_query(gql, {"id": anilist_id})
    media = data.get("Media")
    if not media:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": media["id"],
        "title": media["title"],
        "relations": media.get("relations", {}).get("edges", []),
    }


async def _recommendations(anilist_id: int, page: int = 1, per_page: int = 10, type_: str = "ANIME") -> dict:
    media_type = _media_type(type_)
    gql = f"""
    query ($id: Int, $page: Int, $perPage: Int) {{
        Media(id: $id, type: {media_type}) {{
            id
            title {{ romaji english }}
            recommendations(sort: RATING_DESC, page: $page, perPage: $perPage) {{
                pageInfo {{ total currentPage lastPage hasNextPage perPage }}
                nodes {{
                    rating
                    mediaRecommendation {{
                        id
                        title {{ romaji english native }}
                        coverImage {{ large extraLarge }}
                        bannerImage
                        format
                        episodes
                        chapters
                        status
                        meanScore
                        averageScore
                        popularity
                        genres
                        startDate {{ year }}
                    }}
                }}
            }}
        }}
    }}
    """
    data = await _anilist_query(gql, {"id": anilist_id, "page": page, "perPage": per_page})
    media = data.get("Media")
    if not media:
        raise HTTPException(status_code=404, detail="Not found")
    recs = media.get("recommendations", {})
    page_info = recs.get("pageInfo", {})
    return {
        "page": page_info.get("currentPage", page),
        "perPage": page_info.get("perPage", per_page),
        "total": page_info.get("total", 0),
        "hasNextPage": page_info.get("hasNextPage", False),
        "recommendations": recs.get("nodes", []),
    }


import math


async def _personalized_recommendations(watched: list, per_page: int = 24, max_sources: int = 14) -> dict:
    """Aggregate AniList community recommendations across a user's watch
    history, weighted by watch depth + genre affinity. Ported from the
    reference backend (AniNami-Backend-2 anilist.js)."""
    cleaned = []
    for w in (watched or []):
        if isinstance(w, dict):
            wid = w.get("id", w)
            weight = w.get("weight", 1)
        else:
            wid = w
            weight = 1
        try:
            wid = int(wid)
        except (TypeError, ValueError):
            continue
        try:
            weight = float(weight if weight is not None else 1) or 1
        except (TypeError, ValueError):
            weight = 1
        weight = max(0.0, min(1.0, weight))
        if wid > 0:
            cleaned.append({"id": wid, "weight": weight})

    # Deduplicate, keep the highest weight per id, take the strongest sources.
    by_id: Dict[int, dict] = {}
    for w in cleaned:
        prev = by_id.get(w["id"])
        if not prev or w["weight"] > prev["weight"]:
            by_id[w["id"]] = w
    sources = list(by_id.values())[:max_sources]
    watched_ids = set(by_id.keys())

    if not sources:
        return {"total": 0, "results": []}

    aliases = "\n".join(
        f"""
        m{i}: Media(id: {s['id']}, type: ANIME) {{
            id
            genres
            recommendations(sort: RATING_DESC, perPage: 16) {{
                nodes {{
                    rating
                    mediaRecommendation {{ {REC_MEDIA_FIELDS} }}
                }}
            }}
        }}"""
        for i, s in enumerate(sources)
    )
    data = await _anilist_query(f"query {{ {aliases} }}")

    # Weighted genre-affinity profile.
    affinity: Dict[str, float] = {}
    for i, s in enumerate(sources):
        node = data.get(f"m{i}")
        if not node or not isinstance(node.get("genres"), list):
            continue
        for g in node["genres"]:
            affinity[g] = affinity.get(g, 0) + s["weight"]
    max_affinity = max(affinity.values()) if affinity else 0

    # Accumulate scores per recommended title.
    scores: Dict[int, dict] = {}
    for i, s in enumerate(sources):
        node = data.get(f"m{i}")
        if not node or not node.get("recommendations"):
            continue
        source_weight = s["weight"]
        for rec in node["recommendations"].get("nodes", []) or []:
            media = rec and rec.get("mediaRecommendation")
            if not media or not media.get("id"):
                continue
            if media["id"] in watched_ids:
                continue
            if media.get("isAdult"):
                continue
            rating_weight = math.log2(max(rec.get("rating") or 0, 0) + 2)
            genre_overlap = 0.0
            if max_affinity > 0 and isinstance(media.get("genres"), list):
                for g in media["genres"]:
                    if g in affinity:
                        genre_overlap += affinity[g] / max_affinity
            genre_boost = 1 + min(genre_overlap, 4) * 0.25
            contribution = rating_weight * source_weight * genre_boost
            existing = scores.get(media["id"])
            if existing:
                existing["score"] += contribution
                existing["matchedFrom"] += 1
            else:
                scores[media["id"]] = {"media": media, "score": contribution, "matchedFrom": 1}

    ranked = []
    for entry in scores.values():
        item = dict(entry["media"])
        item["recommendationScore"] = round(entry["score"] * (1 + 0.15 * (entry["matchedFrom"] - 1)), 4)
        item["matchedFrom"] = entry["matchedFrom"]
        ranked.append(item)
    ranked.sort(key=lambda x: x["recommendationScore"], reverse=True)
    ranked = ranked[:per_page]
    return {"total": len(ranked), "results": ranked}


# ── episodes / sources (pipe) ───────────────────────────────────

async def _episodes(anilist_id: int) -> dict:
    data = await _fetch_raw_episodes(anilist_id)
    return _inject_source_slugs(data, anilist_id)


async def _sources(episodeId: str, provider: str, anilistId: int, category: str = "sub") -> dict:
    enc_id = base64.urlsafe_b64encode(episodeId.encode()).decode().rstrip('=')
    payload = {
        "path": "sources",
        "method": "GET",
        "query": {
            "episodeId": enc_id,
            "provider": provider,
            "category": category,
            "anilistId": anilistId,
        },
        "body": None,
        "version": "0.1.0",
    }
    encoded_req = _encode_pipe_request(payload)
    async with AsyncSession(impersonate="chrome110", proxies=_pipe_proxies()) as client:
        res = await client.get(f"{MIRURO_PIPE_URL}?e={encoded_req}", headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail={"status": res.status_code, "body": res.text[:500], "headers": dict(res.headers)})
        return _decode_pipe_response(res.text.strip())


async def _watch(provider: str, anilist_id: int, category: str, slug: str) -> dict:
    data = await _fetch_raw_episodes(anilist_id)
    prov_data = data.get("providers", {}).get(provider, {})
    ep_list = prov_data.get("episodes", {}).get(category, [])

    target_id = None
    for ep in ep_list:
        orig_id = ep.get("id", "")
        prefix = orig_id.split(":")[0] if ":" in orig_id else orig_id
        generated = f"{prefix}-{ep.get('number')}"
        if generated == slug:
            target_id = orig_id
            break

    if not target_id:
        raise HTTPException(status_code=404, detail=f"Episode slug '{slug}' not found for provider {provider}")

    return await _sources(episodeId=target_id, provider=provider, anilistId=anilist_id, category=category)


# ══════════════════════════════════════════════════════════════
# MANGA (MangaKatana scraper — ported from reference backend manga.js)
# ══════════════════════════════════════════════════════════════

async def _mk_get(url: str) -> str:
    """Fetch a MangaKatana page. Uses curl_cffi Chrome impersonation so
    Cloudflare/bot checks pass from most hosts."""
    headers = {
        "User-Agent": MANGA_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": MANGA_BASE_URL,
    }
    async with AsyncSession(impersonate="chrome124") as client:
        res = await client.get(url, headers=headers, timeout=15)
        return res.text


def _mk_abs(url: str) -> str:
    if not url:
        return ""
    if url.startswith("http"):
        return url
    if url.startswith("//"):
        return f"https:{url}"
    return f"{MANGA_BASE_URL}{'' if url.startswith('/') else '/'}{url}"


def _normalize_manga_id(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if value.startswith("mk:"):
        value = value[3:]
    if value.startswith("http://") or value.startswith("https://"):
        try:
            value = urlparse(value).path
        except Exception:
            pass
    marker = "/manga/"
    idx = value.find(marker)
    if idx != -1:
        value = value[idx + len(marker):]
    value = value.strip("/")
    value = value.split("?")[0].split("#")[0]
    value = value.split("/")[0]
    return value


def _normalize_search_text(text: str) -> str:
    text = str(text or "")
    text = re.sub(r"['’]s\b", "", text, flags=re.I)
    text = re.sub(r"['\"’‘`]", "", text)
    text = re.sub(r"[^\w\s-]", " ", text, flags=re.U)
    text = re.sub(r"[-_]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _build_manga_queries(query: str) -> list:
    original = str(query or "").strip()
    normalized = _normalize_search_text(original)
    seen = set()
    keyword_candidates = []
    for word in normalized.split():
        if len(word) >= 4 and word not in seen:
            seen.add(word)
            keyword_candidates.append(word)
    focused = []
    if keyword_candidates:
        focused.append(keyword_candidates[0])
    for word in keyword_candidates:
        if re.search(r"san|chan|kun|sama", word, flags=re.I):
            focused.append(word)
            break
    if keyword_candidates:
        focused.append(sorted(keyword_candidates, key=len, reverse=True)[0])

    out = []
    out_seen = set()
    for val in [original, normalized, *focused]:
        v = str(val or "").strip()
        if v and v not in out_seen:
            out_seen.add(v)
            out.append(v)
    return out


def _parse_manga_items(soup: BeautifulSoup) -> list:
    results = []
    seen_ids = set()
    elements = soup.select("#book_list .item") or soup.select(".item")
    for el in elements:
        link = el.select_one("h3.title a") or el.select_one("div.text > h3 > a") or el.select_one(".title a")
        if not link:
            continue
        title = link.get_text(strip=True)
        url = link.get("href") or ""
        if not title or "/manga/" not in url:
            continue
        img = el.select_one(".media .wrap_img img") or el.select_one("div.cover img") or el.select_one("img")
        thumbnail = ""
        if img:
            thumbnail = _mk_abs(img.get("data-src") or img.get("src") or "")
        chapter_links = el.select("div.text .chapter a") or el.select(".chapter a")
        latest_chapter = chapter_links[0].get_text(strip=True) if chapter_links else ""
        mid = url.replace(f"{MANGA_BASE_URL}/manga/", "").rstrip("/")
        if mid and mid not in seen_ids:
            seen_ids.add(mid)
            results.append({
                "id": mid,
                "title": title,
                "url": url,
                "thumbnail": thumbnail,
                "latestChapter": latest_chapter,
                "author": "",
                "altNames": [],
                "source": "mangakatana",
            })
    return results


async def _manga_search(query: str) -> list:
    for search_query in _build_manga_queries(query):
        for mode in ("m_name", "book_name"):
            url = f"{MANGA_BASE_URL}/?search={quote(search_query)}&search_by={mode}"
            try:
                html = await _mk_get(url)
            except Exception:
                continue
            soup = BeautifulSoup(html, "html.parser")
            results = _parse_manga_items(soup)
            if results:
                return results
    return []


async def _manga_list_by_path(path: str, page_num: int = 1) -> dict:
    url = f"{MANGA_BASE_URL}{path}/page/{page_num}" if page_num > 1 else f"{MANGA_BASE_URL}{path}"
    html = await _mk_get(url)
    soup = BeautifulSoup(html, "html.parser")
    results = _parse_manga_items(soup)
    total_pages = 1
    page_links = soup.select("a.page-numbers:not(.next)")
    if page_links:
        num_text = page_links[-1].get_text(strip=True).replace(",", "")
        try:
            total_pages = int(num_text)
        except ValueError:
            pass
    return {"results": results, "totalPages": total_pages}


async def _manga_details(manga_id: str) -> dict:
    normalized = _normalize_manga_id(manga_id)
    url = f"{MANGA_BASE_URL}/manga/{normalized}"
    html = await _mk_get(url)
    soup = BeautifulSoup(html, "html.parser")

    def txt(sel):
        el = soup.select_one(sel)
        return el.get_text(strip=True) if el else ""

    title = txt("h1.heading")
    alt_el = soup.select_one(".alt_name")
    alt_names = []
    if alt_el:
        alt_names = [s.strip() for s in alt_el.get_text().split(";") if s.strip()]
    author = txt(".author")
    status = txt(".value.status")
    genres = [a.get_text(strip=True) for a in soup.select(".genres > a")]
    synopsis = txt(".summary > p")

    cover = ""
    og = soup.select_one('meta[property="og:image"]')
    if og and og.get("content"):
        cover = og.get("content")
    if not cover:
        for sel in (".cover img", "div.media div.cover img", ".media .wrap_img img"):
            img = soup.select_one(sel)
            if img:
                cover = img.get("data-src") or img.get("src") or ""
                if cover:
                    break
    cover = _mk_abs(cover)

    return {
        "id": normalized,
        "title": title,
        "altNames": alt_names,
        "author": author,
        "status": status,
        "genres": genres,
        "synopsis": synopsis,
        "coverImage": cover,
        "url": url,
        "source": "mangakatana",
    }


async def _manga_chapters(manga_id: str) -> list:
    normalized = _normalize_manga_id(manga_id)
    base = f"{MANGA_BASE_URL}/manga/{normalized}"
    for attempt in range(2):
        try:
            url = base if attempt == 0 else f"{base}?t={int(time.time() * 1000)}"
            html = await _mk_get(url)
            soup = BeautifulSoup(html, "html.parser")
            chapters = []
            for row in soup.select("tr:has(.chapter)"):
                link = row.select_one(".chapter a")
                if not link:
                    continue
                chapter_title = link.get_text(strip=True)
                raw_url = link.get("href") or ""
                chapter_url = raw_url if raw_url.startswith("http") else f"{MANGA_BASE_URL}{'' if raw_url.startswith('/') else '/'}{raw_url}"
                upload = row.select_one(".update_time")
                upload_date = upload.get_text(strip=True) if upload else ""
                chapter_id = chapter_url.rstrip("/").split("/")[-1] if chapter_url else ""
                if chapter_title and chapter_url:
                    chapters.append({
                        "id": chapter_id,
                        "title": chapter_title,
                        "url": chapter_url,
                        "uploadDate": upload_date,
                    })
            if chapters:
                return chapters
        except Exception:
            pass
    return []


async def _manga_pages(chapter_url: str) -> list:
    normalized = chapter_url if chapter_url.startswith("http") else f"{MANGA_BASE_URL}{'' if chapter_url.startswith('/') else '/'}{chapter_url}"
    try:
        html = await _mk_get(normalized)
    except Exception:
        return []

    # MangaKatana embeds the image list in JS arrays: var thzq = ['url1', ...]
    for var_name in ("thzq", "ytaw", "htnc"):
        match = re.search(rf"var\s+{var_name}\s*=\s*\[([\s\S]*?)\];", html)
        if match and match.group(1):
            urls = []
            for m in re.finditer(r"['\"]([^'\"]+)['\"]", match.group(1)):
                u = m.group(1)
                if "http" in u or u.startswith("//"):
                    urls.append(f"https:{u}" if u.startswith("//") else u)
            if urls:
                return [{"pageNumber": i + 1, "imageUrl": u} for i, u in enumerate(urls)]

    # Fallback: read data-src on the #imgs img tags.
    soup = BeautifulSoup(html, "html.parser")
    imgs = []
    for img in soup.select("#imgs img"):
        src = img.get("data-src") or img.get("src")
        if src and ("http" in src or src.startswith("//")):
            imgs.append(f"https:{src}" if src.startswith("//") else src)
    if imgs:
        return [{"pageNumber": i + 1, "imageUrl": u} for i, u in enumerate(imgs)]
    return []


async def _manga_hot() -> list:
    try:
        html = await _mk_get(MANGA_BASE_URL)
    except Exception:
        return []
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#hot_update") or soup.select_one(".widget-hot-update")
    if not container:
        return []
    updates = []
    for el in container.select(".item"):
        img = el.select_one(".wrap_img img")
        thumbnail = (img.get("data-src") or img.get("src") or "") if img else ""
        title_el = el.select_one(".title a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        url = title_el.get("href") or ""
        if any(term in title.lower() for term in ("hentai", "adult", "smut")):
            continue
        chapter_el = el.select_one(".chapter a")
        chapter = chapter_el.get_text(strip=True) if chapter_el else ""
        if title and url:
            parts = url.split("/manga/")
            mid = parts[1].rstrip("/") if len(parts) > 1 else ""
            updates.append({
                "id": mid,
                "title": title,
                "chapter": chapter,
                "url": url,
                "thumbnail": thumbnail,
                "source": "mangakatana",
            })
    return updates[:15]


# ══════════════════════════════════════════════════════════════
# HLS PROXY (ported from reference backend server.js)
# ══════════════════════════════════════════════════════════════
# Streams every provider link through the backend to fix CORS, spoof the
# required Referer/Origin, rewrite m3u8 manifests to keep segment requests on
# this proxy, and force the correct MIME type on disguised .jpg/.ts segments.

async def _proxy_hls(request: Request) -> Response:
    target_url = request.query_params.get("url")
    referer = request.query_params.get("referer") or "https://miruro.tv/"
    if not target_url:
        return err("Missing URL parameter", 400)

    try:
        origin = f"{urlparse(referer).scheme}://{urlparse(referer).netloc}"
    except Exception:
        origin = "https://miruro.tv"

    upstream_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Referer": referer,
        "Origin": origin,
    }
    rng = request.headers.get("range")
    if rng:
        upstream_headers["Range"] = rng

    proxy = _httpx_proxy_for(target_url)
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=25.0, proxy=proxy) as client:
            resp = await client.get(target_url, headers=upstream_headers)
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": "Failed to proxy stream", "detail": str(e)},
            status_code=502,
        )

    content_type = resp.headers.get("content-type", "") or ""
    data = resp.content

    # Forward an upstream rejection (e.g. 403) with its status + body.
    if resp.status_code >= 400:
        return Response(content=data, status_code=resp.status_code,
                        headers={"Access-Control-Allow-Origin": "*"})

    # 1. m3u8 manifest — rewrite child URLs back through this proxy.
    if "mpegurl" in content_type.lower() or ".m3u8" in target_url:
        manifest = data.decode("utf-8", "ignore")
        lines = manifest.split("\n")
        out_lines = []
        for line in lines:
            s = line.strip()
            if s and not s.startswith("#"):
                try:
                    abs_url = urljoin(target_url, s)
                    out_lines.append(
                        f"/api/proxy-hls?url={quote(abs_url, safe='')}&referer={quote(referer, safe='')}"
                    )
                except Exception:
                    out_lines.append(line)
            elif 'URI="' in s:
                def _repl(m):
                    try:
                        abs_url = urljoin(target_url, m.group(1))
                        return f'URI="/api/proxy-hls?url={quote(abs_url, safe="")}&referer={quote(referer, safe="")}"'
                    except Exception:
                        return m.group(0)
                out_lines.append(re.sub(r'URI="([^"]+)"', _repl, line))
            else:
                out_lines.append(line)
        return Response(
            content="\n".join(out_lines),
            media_type="application/vnd.apple.mpegurl",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    # 2. Video / audio segments — force correct MIME on disguised extensions.
    is_video_segment = any(
        x in target_url for x in (".ts", ".m4s", "segment-", ".v1-a", ".v1-v")
    )
    final_content_type = content_type or "application/octet-stream"
    if is_video_segment:
        final_content_type = "video/mp2t"
    elif ".key" in target_url:
        final_content_type = "application/octet-stream"

    resp_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "Range",
        "Access-Control-Expose-Headers": "Content-Range, Content-Length, Accept-Ranges",
        "Accept-Ranges": "bytes",
    }
    if resp.headers.get("content-range"):
        resp_headers["Content-Range"] = resp.headers["content-range"]

    return Response(content=data, media_type=final_content_type,
                    status_code=resp.status_code, headers=resp_headers)


# ══════════════════════════════════════════════════════════════
# ROOT ROUTES (raw Miruro-API public shapes — unchanged contract)
# ══════════════════════════════════════════════════════════════

@app.get("/search")
async def root_search(query: str, page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=50)):
    return await _search(query, page, per_page)


@app.get("/suggestions")
async def root_suggestions(query: str = Query(..., min_length=1)):
    return {"suggestions": await _suggestions(query)}


@app.get("/filter")
async def root_filter(
    genre: Optional[str] = None, tag: Optional[str] = None, year: Optional[int] = None,
    season: Optional[str] = None, format: Optional[str] = None, status: Optional[str] = None,
    sort: str = "POPULARITY_DESC", page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=50),
):
    return await _filter(genre, tag, year, season, format, status, sort, page, per_page)


@app.get("/trending")
async def root_trending(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=50)):
    return await _collection("TRENDING_DESC", page=page, per_page=per_page)


@app.get("/popular")
async def root_popular(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=50)):
    return await _collection("POPULARITY_DESC", page=page, per_page=per_page)


@app.get("/upcoming")
async def root_upcoming(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=50)):
    return await _collection("POPULARITY_DESC", "NOT_YET_RELEASED", page, per_page)


@app.get("/recent")
async def root_recent(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=50)):
    return await _collection("START_DATE_DESC", "RELEASING", page, per_page)


@app.get("/spotlight")
async def root_spotlight():
    return {"results": await _spotlight()}


@app.get("/schedule")
async def root_schedule(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=50)):
    return await _schedule(page, per_page)


@app.get("/info/{anilist_id}")
async def root_info(anilist_id: int):
    return await _info(anilist_id)


@app.get("/anime/{anilist_id}/characters")
async def root_characters(anilist_id: int, page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=50)):
    return await _characters(anilist_id, page, per_page)


@app.get("/anime/{anilist_id}/relations")
async def root_relations(anilist_id: int):
    return await _relations(anilist_id)


@app.get("/anime/{anilist_id}/recommendations")
async def root_recommendations(anilist_id: int, page: int = Query(1, ge=1), per_page: int = Query(10, ge=1, le=25)):
    return await _recommendations(anilist_id, page, per_page)


@app.get("/episodes/{anilist_id}")
async def root_episodes(anilist_id: int):
    return await _episodes(anilist_id)


@app.get("/sources")
async def root_sources(episodeId: str, provider: str, anilistId: int, category: str = "sub"):
    return await _sources(episodeId, provider, anilistId, category)


@app.get("/watch/{provider}/{anilist_id}/{category}/{slug}")
async def root_watch(provider: str, anilist_id: int, category: str, slug: str):
    return await _watch(provider, anilist_id, category, slug)


# ══════════════════════════════════════════════════════════════
# /api ROUTES (wrapped { success, results } — AniNami frontend contract)
# ══════════════════════════════════════════════════════════════

def _is_manga(type_: Optional[str]) -> str:
    return "MANGA" if str(type_ or "").lower() == "manga" else "ANIME"


@app.get("/api/search")
async def api_search(query: str, page: int = 1, per_page: int = 20, sort: str = "SEARCH_MATCH"):
    try:
        return ok(await _search(query, page, per_page, sort))
    except HTTPException as e:
        return err(str(e.detail), e.status_code)
    except Exception as e:
        return err(str(e))


@app.get("/api/suggestions")
async def api_suggestions(query: str):
    try:
        return ok(await _suggestions(query))
    except Exception as e:
        return err(str(e))


@app.get("/api/filter")
async def api_filter(
    query: Optional[str] = None, genre: Optional[str] = None, tag: Optional[str] = None,
    year: Optional[int] = None, season: Optional[str] = None, format: Optional[str] = None,
    status: Optional[str] = None, country: Optional[str] = None, sort: str = "POPULARITY_DESC",
    page: int = 1, per_page: int = 20, type: Optional[str] = None,
):
    try:
        return ok(await _filter(genre, tag, year, season, format, status, sort, page, per_page,
                                _is_manga(type), country, search=query))
    except Exception as e:
        return err(str(e))


@app.get("/api/trending")
async def api_trending(page: int = 1, per_page: int = 20, type: Optional[str] = None):
    try:
        return ok(await _collection("TRENDING_DESC", None, page, per_page, _is_manga(type)))
    except Exception as e:
        return err(str(e))


@app.get("/api/popular")
async def api_popular(page: int = 1, per_page: int = 20, type: Optional[str] = None):
    try:
        return ok(await _collection("POPULARITY_DESC", None, page, per_page, _is_manga(type)))
    except Exception as e:
        return err(str(e))


@app.get("/api/upcoming")
async def api_upcoming(page: int = 1, per_page: int = 20, type: Optional[str] = None):
    try:
        return ok(await _collection("POPULARITY_DESC", "NOT_YET_RELEASED", page, per_page, _is_manga(type)))
    except Exception as e:
        return err(str(e))


@app.get("/api/recent")
async def api_recent(page: int = 1, per_page: int = 20, type: Optional[str] = None):
    try:
        return ok(await _collection("START_DATE_DESC", "RELEASING", page, per_page, _is_manga(type)))
    except Exception as e:
        return err(str(e))


@app.get("/api/spotlight")
async def api_spotlight():
    try:
        return ok(await _spotlight())
    except Exception as e:
        return err(str(e))


@app.get("/api/schedule")
async def api_schedule(page: int = 1, per_page: int = 20, date: Optional[str] = None):
    try:
        return ok(await _schedule(page, per_page, date))
    except Exception as e:
        return err(str(e))


@app.get("/api/info/{anilist_id}")
async def api_info(anilist_id: int):
    try:
        return ok(await _info(anilist_id))
    except HTTPException as e:
        return err(str(e.detail), e.status_code)
    except Exception as e:
        return err(str(e))


@app.get("/api/anime/{anilist_id}/characters")
async def api_characters(anilist_id: int, page: int = 1, per_page: int = 25):
    try:
        return ok(await _characters(anilist_id, page, per_page))
    except HTTPException as e:
        return err(str(e.detail), e.status_code)
    except Exception as e:
        return err(str(e))


@app.get("/api/anime/{anilist_id}/relations")
async def api_relations(anilist_id: int):
    try:
        return ok(await _relations(anilist_id))
    except HTTPException as e:
        return err(str(e.detail), e.status_code)
    except Exception as e:
        return err(str(e))


@app.get("/api/anime/{anilist_id}/recommendations")
async def api_recommendations(anilist_id: int, page: int = 1, per_page: int = 10):
    try:
        return ok(await _recommendations(anilist_id, page, per_page))
    except HTTPException as e:
        return err(str(e.detail), e.status_code)
    except Exception as e:
        return err(str(e))


@app.post("/api/recommendations")
async def api_personalized_recommendations(payload: dict = Body(...)):
    try:
        watched = payload.get("watched") if isinstance(payload, dict) else None
        watched = watched if isinstance(watched, list) else []
        per_page = min(int(payload.get("per_page", 24) or 24), 50)
        if not watched:
            return err("watched must be a non-empty array of anime", 400)
        return ok(await _personalized_recommendations(watched, per_page))
    except Exception as e:
        return err(str(e))


@app.get("/api/recommendations")
async def api_personalized_recommendations_get(ids: str = "", per_page: int = 24):
    try:
        watched = []
        for s in str(ids or "").split(","):
            s = s.strip()
            if s.isdigit():
                watched.append({"id": int(s), "weight": 1})
        if not watched:
            return err("ids query parameter is required (comma-separated AniList IDs)", 400)
        return ok(await _personalized_recommendations(watched, min(int(per_page or 24), 50)))
    except Exception as e:
        return err(str(e))


@app.get("/api/episodes/{anilist_id}")
async def api_episodes(anilist_id: int):
    try:
        return ok(await _episodes(anilist_id))
    except HTTPException as e:
        return err(str(e.detail), e.status_code)
    except Exception as e:
        return err(str(e))


@app.get("/api/sources")
async def api_sources(episodeId: str, provider: str, anilistId: int, category: str = "sub"):
    try:
        return ok(await _sources(episodeId, provider, anilistId, category))
    except HTTPException as e:
        return err(str(e.detail), e.status_code)
    except Exception as e:
        return err(str(e))


@app.get("/api/watch/{provider}/{anilist_id}/{category}/{slug}")
async def api_watch(provider: str, anilist_id: int, category: str, slug: str):
    try:
        return ok(await _watch(provider, anilist_id, category, slug))
    except HTTPException as e:
        return err(str(e.detail), e.status_code)
    except Exception as e:
        return err(str(e))


# ── /api manga (AniList metadata + MangaKatana reader) ──────────

@app.get("/api/manga/info/{anilist_id}")
async def api_manga_info(anilist_id: int):
    try:
        return ok(await _info(anilist_id, "MANGA"))
    except HTTPException as e:
        return err(str(e.detail), e.status_code)
    except Exception as e:
        return err(str(e))


@app.get("/api/manga/{anilist_id}/characters")
async def api_manga_characters(anilist_id: int, page: int = 1, per_page: int = 25):
    try:
        return ok(await _characters(anilist_id, page, per_page, "MANGA"))
    except HTTPException as e:
        return err(str(e.detail), e.status_code)
    except Exception as e:
        return err(str(e))


@app.get("/api/manga/{anilist_id}/relations")
async def api_manga_relations(anilist_id: int):
    try:
        return ok(await _relations(anilist_id, "MANGA"))
    except HTTPException as e:
        return err(str(e.detail), e.status_code)
    except Exception as e:
        return err(str(e))


@app.get("/api/manga/{anilist_id}/recommendations")
async def api_manga_recommendations(anilist_id: int, page: int = 1, per_page: int = 10):
    try:
        return ok(await _recommendations(anilist_id, page, per_page, "MANGA"))
    except HTTPException as e:
        return err(str(e.detail), e.status_code)
    except Exception as e:
        return err(str(e))


@app.get("/api/manga/search")
async def api_manga_search(q: Optional[str] = None, query: Optional[str] = None):
    try:
        term = q or query
        if not term:
            return err("query parameter 'q' is required", 400)
        return ok(await _manga_search(term))
    except Exception as e:
        return err(str(e))


@app.get("/api/manga/details/{manga_id:path}")
async def api_manga_details(manga_id: str, includeChapters: str = ""):
    try:
        include = includeChapters.lower() in ("1", "true", "yes")
        details = await _manga_details(manga_id)
        if include:
            chapters = await _manga_chapters(manga_id)
            return ok({"details": details, "chapters": chapters})
        return ok(details)
    except Exception as e:
        return err(str(e))


@app.get("/api/manga/chapters/{manga_id:path}")
async def api_manga_chapters(manga_id: str):
    try:
        return ok(await _manga_chapters(manga_id))
    except Exception as e:
        return err(str(e))


@app.get("/api/manga/pages")
async def api_manga_pages(url: str):
    try:
        return ok(await _manga_pages(url))
    except Exception as e:
        return err(str(e))


@app.get("/api/manga/hot-updates")
async def api_manga_hot():
    try:
        return ok(await _manga_hot())
    except Exception as e:
        return err(str(e))


def _register_manga_listing(path: str, coro):
    async def handler(page: int = 1):
        try:
            data = await coro(page)
            return ok({"data": data["results"], "pagination": {"total_pages": data["totalPages"]}})
        except Exception as e:
            return err(str(e))
    app.add_api_route(f"/api/manga/{path}", handler, methods=["GET"])


_register_manga_listing("latest", lambda p=1: _manga_list_by_path("/latest", p))
_register_manga_listing("new", lambda p=1: _manga_list_by_path("/new-manga", p))
_register_manga_listing("directory", lambda p=1: _manga_list_by_path("/manga", p))


# ── /api hls proxy ──────────────────────────────────────────────

@app.get("/api/proxy-hls")
async def api_proxy_hls(request: Request):
    return await _proxy_hls(request)


# ── /api health ─────────────────────────────────────────────────

_START_TIME = time.time()


@app.get("/api/health")
async def api_health():
    uptime = int(time.time() - _START_TIME)
    return ok({
        "status": "healthy",
        "version": "3.0",
        "uptimeSeconds": uptime,
        "backend": "miruro-api",
        "outboundProxy": bool(OUTBOUND_PROXY),
    })


# ══════════════════════════════════════════════════════════════
# HOME (landing / docs)
# ══════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def home():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Miruro API v3.0</title>
<style>
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
body{background:#03040a;color:#e2e8f0;font-family:system-ui,sans-serif;min-height:100vh;padding:60px 20px}
.wrap{max-width:820px;margin:0 auto}
h1{font-size:2.6rem;background:linear-gradient(135deg,#fff,#38bdf8,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:10px}
.sub{color:#64748b;margin-bottom:32px}
.chip{display:inline-block;background:rgba(56,189,248,.08);color:#38bdf8;border:1px solid rgba(56,189,248,.18);border-radius:999px;padding:5px 14px;font-size:.8rem;margin-bottom:32px}
h2{font-size:.75rem;letter-spacing:.12em;text-transform:uppercase;color:#64748b;margin:32px 0 12px}
.row{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:12px 16px;margin-bottom:8px;font-family:ui-monospace,monospace;font-size:.85rem}
.m{color:#34d399;font-weight:600;margin-right:8px}
.d{color:#64748b;font-size:.8rem;margin-top:4px;font-family:system-ui}
code{color:#a5b4fc}
a{color:#38bdf8}
</style>
</head>
<body>
<div class="wrap">
  <h1>Miruro API</h1>
  <p class="sub">Reverse-engineered anime streaming API — now the primary AniNami backend.</p>
  <div class="chip">v3.0 · Live</div>

  <h2>Frontend contract (wrapped)</h2>
  <div class="row"><span class="m">GET</span>/api/search · /api/filter · /api/suggestions
    <div class="d">All <code>/api/*</code> routes return <code>{ success, results }</code>. Supports <code>type=manga</code> &amp; <code>country</code>.</div></div>
  <div class="row"><span class="m">GET</span>/api/trending · /api/popular · /api/upcoming · /api/recent · /api/spotlight · /api/schedule</div>
  <div class="row"><span class="m">GET</span>/api/info/{id} · /api/anime/{id}/characters|relations|recommendations</div>
  <div class="row"><span class="m">GET/POST</span>/api/recommendations <span class="d">personalized from watch history</span></div>
  <div class="row"><span class="m">GET</span>/api/episodes/{id} · /api/watch/{provider}/{anilistId}/{category}/{slug} · /api/sources</div>
  <div class="row"><span class="m">GET</span>/api/proxy-hls?url=&amp;referer= <span class="d">CORS + referer + m3u8 rewrite</span></div>
  <div class="row"><span class="m">GET</span>/api/manga/info/{id} · /api/manga/search · /api/manga/chapters/{id} · /api/manga/pages</div>

  <h2>Raw public API (unwrapped)</h2>
  <div class="row"><span class="m">GET</span>/search · /trending · /info/{id} · /episodes/{id} · /watch/... <span class="d">original Miruro-API shapes</span></div>

  <p style="margin-top:40px;color:#334155;font-size:.8rem">Built on Walter's Miruro-API · adapted for AniNami</p>
</div>
</body>
</html>"""

import base64, json, gzip, httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from typing import Optional, List

app = FastAPI(title="Miruro API", version="2.0")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": "https://www.miruro.to/"}
ANILIST_URL = "https://graphql.anilist.co"
MIRURO_PIPE_URL = "https://www.miruro.to/api/secure/pipe"

# ─── Shared GraphQL Fragments ────────────────────────────────────────────────

MEDIA_LIST_FIELDS = """
    id
    title { romaji english native }
    coverImage { large extraLarge }
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
    coverImage { large extraLarge color }
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

# ─── Utility Functions ───────────────────────────────────────────────────────

def _translate_id(encoded_id: str) -> str:
    """Decode a base64-encoded episode ID back to plain text."""
    try:
        decoded = base64.urlsafe_b64decode(encoded_id + '=' * (4 - len(encoded_id) % 4)).decode()
        if ':' in decoded:
            return decoded
        return encoded_id
    except Exception:
        return encoded_id


def _deep_translate(obj):
    """Recursively walk a JSON structure and decode any base64 'id' fields."""
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
    """Decode a base64+gzip pipe response into a plain dict."""
    try:
        encoded_str += '=' * (4 - len(encoded_str) % 4)
        compressed = base64.urlsafe_b64decode(encoded_str)
        return json.loads(gzip.decompress(compressed).decode('utf-8'))
    except Exception:
        raise ValueError("Failed to decode pipe response")


def _encode_pipe_request(payload: dict) -> str:
    """Encode a dict into the base64 format expected by the pipe endpoint."""
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')


async def _anilist_query(query: str, variables: dict = None):
    """Execute an AniList GraphQL query and return the data."""
    body = {"query": query}
    if variables:
        body["variables"] = variables
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(ANILIST_URL, json=body)
        if res.status_code != 200:
            raise HTTPException(status_code=500, detail="AniList query failed")
        return res.json().get("data", {})


# ─── Homepage ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Miruro API v2.0</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;500;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Outfit', sans-serif; transition: all 0.3s ease; }
        body { background: radial-gradient(circle at top, #0f172a, #020617); color: #e2e8f0; min-height: 100vh; padding: 50px 20px; }
        .container { max-width: 960px; margin: 0 auto; background: rgba(30, 41, 59, 0.5); backdrop-filter: blur(10px); padding: 40px; border-radius: 24px; border: 1px solid rgba(255, 255, 255, 0.05); box-shadow: 0 20px 40px rgba(0,0,0,0.5); }
        .header { text-align: center; margin-bottom: 50px; }
        .logo { width: 120px; border-radius: 20px; box-shadow: 0 0 30px rgba(56, 189, 248, 0.3); border: 1px solid rgba(255,255,255,0.1); margin-bottom: 25px; object-fit: cover; }
        h1 { font-size: 3em; font-weight: 700; background: linear-gradient(to right, #38bdf8, #818cf8); -webkit-background-clip: text; color: transparent; margin-bottom: 10px; }
        .subtitle { color: #94a3b8; font-size: 1.1em; font-weight: 300; }
        .version { display: inline-block; background: rgba(56, 189, 248, 0.15); color: #38bdf8; padding: 4px 14px; border-radius: 20px; font-size: 0.85em; margin-top: 10px; border: 1px solid rgba(56, 189, 248, 0.2); }
        .section-title { font-size: 1.3em; font-weight: 700; color: #818cf8; margin: 35px 0 15px; border-left: 3px solid #818cf8; padding-left: 12px; }
        .endpoint { background: rgba(15, 23, 42, 0.8); border-left: 4px solid #38bdf8; padding: 25px; margin: 15px 0; border-radius: 0 16px 16px 0; border: 1px solid rgba(255,255,255,0.02); }
        .endpoint:hover { transform: translateX(5px); box-shadow: 0 10px 20px rgba(0,0,0,0.2); border-left-color: #818cf8; background: rgba(30, 41, 59, 0.9); }
        .method { color: #10b981; font-weight: 700; background: rgba(16, 185, 129, 0.1); padding: 4px 10px; border-radius: 6px; font-size: 0.9em; margin-right: 10px; }
        .url { font-family: monospace; color: #cbd5e1; font-size: 1.1em; }
        .params { margin-top: 10px; font-size: 0.85em; color: #64748b; font-family: monospace; line-height: 1.8; }
        .params span { color: #a5b4fc; }
        .example { margin-top: 15px; font-size: 0.95em; color: #64748b; }
        a { color: #38bdf8; text-decoration: none; word-break: break-all; font-weight: 500; }
        a:hover { color: #818cf8; text-shadow: 0 0 10px rgba(129, 140, 248, 0.5); }
        .desc { color: #cbd5e1; font-size: 1em; margin-top: 10px; font-weight: 300; line-height: 1.6; }
        .badge { display: inline-block; font-size: 0.7em; padding: 2px 8px; border-radius: 6px; margin-left: 8px; font-weight: 500; vertical-align: middle; }
        .badge-new { background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge-improved { background: rgba(129, 140, 248, 0.15); color: #818cf8; border: 1px solid rgba(129, 140, 248, 0.3); }
        .returns { margin-top: 12px; font-size: 0.85em; color: #94a3b8; line-height: 1.6; }
        .returns b { color: #a5b4fc; font-weight: 500; }
        pre.snippet { background: #020617; padding: 14px; border-radius: 10px; margin-top: 12px; color: #a5b4fc; font-family: monospace; font-size: 0.82em; border: 1px solid rgba(255,255,255,0.05); overflow-x: auto; line-height: 1.5; }
        .step-num { display: inline-block; background: rgba(56, 189, 248, 0.15); color: #38bdf8; width: 26px; height: 26px; text-align: center; line-height: 26px; border-radius: 50%; font-size: 0.85em; font-weight: 700; margin-right: 8px; }
        .note { background: rgba(250, 204, 21, 0.08); border: 1px solid rgba(250, 204, 21, 0.15); border-radius: 10px; padding: 14px 18px; margin-top: 12px; font-size: 0.88em; color: #fbbf24; line-height: 1.5; }
        .note b { color: #fde68a; }
        table.param-table { width: 100%; margin-top: 12px; border-collapse: collapse; font-size: 0.85em; }
        table.param-table th { text-align: left; color: #818cf8; font-weight: 500; padding: 6px 10px; border-bottom: 1px solid rgba(255,255,255,0.08); }
        table.param-table td { padding: 6px 10px; color: #94a3b8; border-bottom: 1px solid rgba(255,255,255,0.03); }
        table.param-table td:first-child { color: #a5b4fc; font-family: monospace; white-space: nowrap; }
        .footer { text-align: center; margin-top: 50px; color: #475569; font-size: 0.9em; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://www.miruro.to/icon-512x512.png" alt="Logo" class="logo">
            <h1>Miruro Native API</h1>
            <div class="subtitle">Decrypted, bypassed, and reverse-engineered anime streaming API</div>
            <div class="version">v2.0 — Full Data &amp; Pagination</div>
        </div>

        <!-- ───────── SEARCH & DISCOVERY ───────── -->
        <div class="section-title">🔍 Search &amp; Discovery</div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/search</span></div>
            <div class="desc">Search anime by name. Returns full metadata per result — title (romaji / english / native), cover art, banner, genres, studios, scores, airing status, and more.</div>
            <div class="params">Params: <span>query</span> (required), <span>page</span>=1, <span>per_page</span>=20</div>
            <div class="returns">Returns: <b>page</b>, <b>perPage</b>, <b>total</b>, <b>hasNextPage</b>, <b>results[]</b> — each with 20+ fields</div>
            <div class="example">Try: <a target="_blank" href="/search?query=naruto&page=1&per_page=5">/search?query=naruto&page=1&per_page=5</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/suggestions</span> <span class="badge badge-new">NEW</span></div>
            <div class="desc">Lightweight search for autocomplete / dropdown. Returns only the essentials: id, title, poster, format, status, year, and episode count. Max 8 results.</div>
            <div class="params">Params: <span>query</span> (required)</div>
            <div class="returns">Returns: <b>suggestions[]</b> — each with: id, title, title_romaji, poster, format, status, year, episodes</div>
            <div class="example">Try: <a target="_blank" href="/suggestions?query=one piece">/suggestions?query=one piece</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/filter</span> <span class="badge badge-new">NEW</span></div>
            <div class="desc">Advanced filter / browse. Combine any filters — all params are optional.</div>
            <table class="param-table">
                <tr><th>Param</th><th>Values</th></tr>
                <tr><td>genre</td><td>Action, Romance, Comedy, Drama, Fantasy, Sci-Fi, etc.</td></tr>
                <tr><td>tag</td><td>Isekai, Time Skip, Reincarnation, etc.</td></tr>
                <tr><td>year</td><td>2025, 2024, etc.</td></tr>
                <tr><td>season</td><td>WINTER · SPRING · SUMMER · FALL</td></tr>
                <tr><td>format</td><td>TV · MOVIE · OVA · ONA · SPECIAL</td></tr>
                <tr><td>status</td><td>RELEASING · FINISHED · NOT_YET_RELEASED · CANCELLED</td></tr>
                <tr><td>sort</td><td>SCORE_DESC · POPULARITY_DESC · TRENDING_DESC · START_DATE_DESC</td></tr>
                <tr><td>page / per_page</td><td>Pagination (default 1 / 20)</td></tr>
            </table>
            <div class="example">Try: <a target="_blank" href="/filter?genre=Action&format=TV&sort=SCORE_DESC&per_page=5">/filter?genre=Action&format=TV&sort=SCORE_DESC&per_page=5</a></div>
        </div>

        <!-- ───────── COLLECTIONS ───────── -->
        <div class="section-title">📊 Collections (Paginated)</div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/trending</span></div>
            <div class="desc">Currently trending anime across the community.</div>
            <div class="params">Params: <span>page</span>=1, <span>per_page</span>=20</div>
            <div class="example">Try: <a target="_blank" href="/trending?per_page=5">/trending?per_page=5</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/popular</span></div>
            <div class="desc">Most popular anime of all time by total user count.</div>
            <div class="params">Params: <span>page</span>=1, <span>per_page</span>=20</div>
            <div class="example">Try: <a target="_blank" href="/popular">/popular</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/upcoming</span></div>
            <div class="desc">Most anticipated anime that haven't aired yet.</div>
            <div class="params">Params: <span>page</span>=1, <span>per_page</span>=20</div>
            <div class="example">Try: <a target="_blank" href="/upcoming">/upcoming</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/recent</span></div>
            <div class="desc">Currently airing / this season's anime.</div>
            <div class="params">Params: <span>page</span>=1, <span>per_page</span>=20</div>
            <div class="example">Try: <a target="_blank" href="/recent">/recent</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/schedule</span></div>
            <div class="desc">Next episodes airing soon. Each result includes the full anime info plus <b>airingAt</b> (UNIX timestamp), <b>timeUntilAiring</b> (seconds), and <b>next_episode</b> (episode number).</div>
            <div class="params">Params: <span>page</span>=1, <span>per_page</span>=20</div>
            <div class="example">Try: <a target="_blank" href="/schedule">/schedule</a></div>
        </div>

        <!-- ───────── ANIME DETAILS ───────── -->
        <div class="section-title">📖 Anime Details</div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/info/{anilist_id}</span></div>
            <div class="desc">Complete anime page — <b>everything</b> you need to build an anime detail page in one request.</div>
            <div class="returns">Returns all of: title (romaji/english/native), description, coverImage, bannerImage, format, season, seasonYear, episodes, duration, status, averageScore, meanScore, popularity, favourites, genres, <b>tags</b> (with rank), <b>studios</b>, <b>characters</b> (25, with voice actors), <b>staff</b> (25, with roles), <b>relations</b> (sequels/prequels/etc.), <b>recommendations</b> (10), <b>trailer</b>, <b>externalLinks</b> (MAL, official site), <b>streamingEpisodes</b>, <b>stats</b> (score &amp; status distribution), synonyms, siteUrl, idMal, and more.</div>
            <div class="example">Try: <a target="_blank" href="/info/20">/info/20</a> (Naruto) · <a target="_blank" href="/info/21">/info/21</a> (One Piece)</div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/anime/{id}/characters</span></div>
            <div class="desc">Paginated character list. Each character includes name, image, role (MAIN/SUPPORTING), and Japanese voice actors with images.</div>
            <div class="params">Params: <span>page</span>=1, <span>per_page</span>=25</div>
            <div class="example">Try: <a target="_blank" href="/anime/20/characters">/anime/20/characters</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/anime/{id}/relations</span></div>
            <div class="desc">All related media — sequels, prequels, side stories, spin-offs, source material. Each entry has type (SEQUEL/PREQUEL/etc.), format, and basic metadata.</div>
            <div class="example">Try: <a target="_blank" href="/anime/20/relations">/anime/20/relations</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/anime/{id}/recommendations</span></div>
            <div class="desc">Community recommendations — "if you liked X, you'll like Y". Sorted by highest rating.</div>
            <div class="params">Params: <span>page</span>=1, <span>per_page</span>=10</div>
            <div class="example">Try: <a target="_blank" href="/anime/20/recommendations">/anime/20/recommendations</a></div>
        </div>

        <!-- ───────── STREAMING ───────── -->
        <div class="section-title">▶️ Streaming (3-Step Flow)</div>

        <div class="note">
            <b>How streaming works:</b> To get a video URL, follow these 3 steps in order. Each step's output feeds into the next.
        </div>

        <div class="endpoint">
            <div><span class="step-num">1</span><span class="method">GET</span> <span class="url">/episodes/{anilist_id}</span></div>
            <div class="desc">Get all available episodes for an anime. Returns episodes from multiple providers (kiwi, arc, zoro, jet, etc.) organized by audio type (sub / dub).</div>
            <div class="returns">Returns: <b>mappings</b> (cross-reference IDs for AniList, MAL, Kitsu) + <b>providers</b> (episode lists per provider)</div>
            <pre class="snippet">{
  "mappings": { "anilistId": 178005, "malId": 56885, ... },
  "providers": {
    "kiwi": {
      "episodes": {
        "sub": [
          {
            "id": "animepahe:6444:72975:1",   ← use this as episodeId
            "number": 1,
            "title": "Episode Title",
            "image": "https://...",
            "airDate": "2026-01-04",
            "duration": 1420,
            "description": "...",
            "filler": false
          }
        ],
        "dub": [ ... ]
      }
    },
    "arc": { ... },
    "zoro": { ... }
  }
}</pre>
            <div class="example">Try: <a target="_blank" href="/episodes/178005">/episodes/178005</a></div>
        </div>

        <div class="endpoint">
            <div><span class="step-num">2</span><span class="method">GET</span> <span class="url">/sources</span></div>
            <div class="desc">Get the direct M3U8/HLS video stream URL for a specific episode. Use the <b>id</b> and <b>provider name</b> from Step 1.</div>
            <table class="param-table">
                <tr><th>Param</th><th>Description</th><th>Example</th></tr>
                <tr><td>episodeId</td><td>The <b>id</b> string from Step 1</td><td>animepahe:6444:72975:1</td></tr>
                <tr><td>provider</td><td>Provider name from Step 1</td><td>kiwi, arc, zoro</td></tr>
                <tr><td>anilistId</td><td>AniList ID of the anime</td><td>178005</td></tr>
                <tr><td>category</td><td>Audio track (default: sub)</td><td>sub or dub</td></tr>
            </table>
            <pre class="snippet">{
  "sources": [
    { "url": "https://.../master.m3u8", "isM3U8": true, "quality": "1080p" }
  ],
  "tracks": [
    { "file": "https://.../english.vtt", "label": "English", "kind": "captions" }
  ],
  "intro": { "start": 0, "end": 90 },
  "outro": { "start": 1300, "end": 1420 }
}</pre>
            <div class="example">Try: <a target="_blank" href="/sources?episodeId=animepahe:6444:72975:1&provider=kiwi&anilistId=178005&category=sub">/sources?episodeId=animepahe:6444:72975:1&provider=kiwi&anilistId=178005&category=sub</a></div>
        </div>

        <div class="endpoint" style="border-left-color: #818cf8;">
            <div><span class="step-num">3</span> <span class="url" style="color: #818cf8;">Play the stream</span></div>
            <div class="desc">Take the <b>sources[0].url</b> from Step 2 and feed it into any HLS-compatible player (Video.js, hls.js, VLC, mpv, etc.). Use the <b>tracks</b> for subtitles and <b>intro/outro</b> timestamps for skip buttons.</div>
        </div>

        <div class="footer">
            All collection endpoints return paginated responses: <span style="color: #a5b4fc; font-family: monospace;">{ page, perPage, total, hasNextPage, results[] }</span>
            <br><br>
            Developed by Walter | <a href="https://github.com/walterwhite-69" target="_blank">github.com/walterwhite-69</a>
        </div>
    </div>
</body>
</html>"""


# ─── Search & Suggestions ───────────────────────────────────────────────────

@app.get("/search")
async def search_anime(
    query: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=50, description="Results per page"),
):
    """Search for anime by name via AniList GraphQL — returns full metadata."""
    gql = f"""
    query ($search: String, $page: Int, $perPage: Int) {{
        Page(page: $page, perPage: $perPage) {{
            pageInfo {{ total currentPage lastPage hasNextPage perPage }}
            media(search: $search, type: ANIME, sort: SEARCH_MATCH) {{
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


@app.get("/suggestions")
async def search_suggestions(
    query: str = Query(..., min_length=1, description="Search query for autocomplete"),
):
    """Lightweight search for dropdown autocomplete — returns minimal data fast."""
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
    return {"suggestions": results}


# ─── Advanced Filter ─────────────────────────────────────────────────────────

SORT_MAP = {
    "SCORE_DESC": "SCORE_DESC",
    "POPULARITY_DESC": "POPULARITY_DESC",
    "TRENDING_DESC": "TRENDING_DESC",
    "START_DATE_DESC": "START_DATE_DESC",
    "FAVOURITES_DESC": "FAVOURITES_DESC",
    "UPDATED_AT_DESC": "UPDATED_AT_DESC",
}

@app.get("/filter")
async def filter_anime(
    genre: Optional[str] = Query(None, description="Genre name, e.g. Action, Romance"),
    tag: Optional[str] = Query(None, description="Tag name, e.g. Isekai, Time Skip"),
    year: Optional[int] = Query(None, description="Season year, e.g. 2025"),
    season: Optional[str] = Query(None, description="WINTER, SPRING, SUMMER, or FALL"),
    format: Optional[str] = Query(None, description="TV, MOVIE, OVA, ONA, SPECIAL, MUSIC"),
    status: Optional[str] = Query(None, description="RELEASING, FINISHED, NOT_YET_RELEASED, CANCELLED, HIATUS"),
    sort: str = Query("POPULARITY_DESC", description="Sort order"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
):
    """Advanced anime filter with genre, tag, year, season, format, status, and sort."""
    # Build dynamic argument string
    args = ["type: ANIME", f"sort: [{SORT_MAP.get(sort, 'POPULARITY_DESC')}]"]
    variables = {"page": page, "perPage": per_page}

    if genre:
        args.append("genre: $genre")
        variables["genre"] = genre
    if tag:
        args.append("tag: $tag")
        variables["tag"] = tag
    if year:
        args.append("seasonYear: $seasonYear")
        variables["seasonYear"] = year
    if season:
        args.append("season: $season")
        variables["season"] = season.upper()
    if format:
        args.append("format: $format")
        variables["format"] = format.upper()
    if status:
        args.append("status: $status")
        variables["status"] = status.upper()

    # Build variable type declarations
    var_types = ["$page: Int", "$perPage: Int"]
    if genre:
        var_types.append("$genre: String")
    if tag:
        var_types.append("$tag: String")
    if year:
        var_types.append("$seasonYear: Int")
    if season:
        var_types.append("$season: MediaSeason")
    if format:
        var_types.append("$format: MediaFormat")
    if status:
        var_types.append("$status: MediaStatus")

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


# ─── Collection Endpoints (with pagination) ─────────────────────────────────

async def _fetch_collection(sort_type: str, status: str = None, page: int = 1, per_page: int = 20):
    """Helper to fetch a sorted/filtered anime collection from AniList with pagination."""
    args = f"sort: [{sort_type}], type: ANIME"
    if status:
        args += f", status: {status}"

    gql = f"""
    query ($page: Int, $perPage: Int) {{
        Page(page: $page, perPage: $perPage) {{
            pageInfo {{ total currentPage lastPage hasNextPage perPage }}
            media({args}) {{
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


@app.get("/trending")
async def get_trending(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
):
    """Get trending anime with full metadata and pagination."""
    return await _fetch_collection("TRENDING_DESC", page=page, per_page=per_page)


@app.get("/popular")
async def get_popular(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
):
    """Get most popular anime of all time with full metadata and pagination."""
    return await _fetch_collection("POPULARITY_DESC", page=page, per_page=per_page)


@app.get("/upcoming")
async def get_upcoming(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
):
    """Get upcoming anime with full metadata and pagination."""
    return await _fetch_collection("POPULARITY_DESC", "NOT_YET_RELEASED", page=page, per_page=per_page)


@app.get("/recent")
async def get_recent(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
):
    """Get currently airing anime with full metadata and pagination."""
    return await _fetch_collection("START_DATE_DESC", "RELEASING", page=page, per_page=per_page)


@app.get("/schedule")
async def get_schedule(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
):
    """Get upcoming airing schedule with UNIX timestamps and full anime metadata."""
    gql = f"""
    query ($page: Int, $perPage: Int) {{
        Page(page: $page, perPage: $perPage) {{
            pageInfo {{ total currentPage lastPage hasNextPage perPage }}
            airingSchedules(notYetAired: true, sort: TIME) {{
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
    data = await _anilist_query(gql, {"page": page, "perPage": per_page})
    page_data = data.get("Page", {})
    page_info = page_data.get("pageInfo", {})
    results = []
    for item in page_data.get("airingSchedules", []):
        entry = item.get("media", {})
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


# ─── Anime Details ───────────────────────────────────────────────────────────

@app.get("/info/{anilist_id}")
async def get_anime_info(anilist_id: int):
    """Get complete anime page data — everything AniList has to offer."""
    gql = f"""
    query ($id: Int) {{
        Media(id: $id, type: ANIME) {{
            {MEDIA_FULL_FIELDS}
        }}
    }}
    """
    data = await _anilist_query(gql, {"id": anilist_id})
    media = data.get("Media")
    if not media:
        raise HTTPException(status_code=404, detail="Anime not found")
    return media


@app.get("/anime/{anilist_id}/characters")
async def get_anime_characters(
    anilist_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=50),
):
    """Get paginated character list with voice actors for an anime."""
    gql = """
    query ($id: Int, $page: Int, $perPage: Int) {
        Media(id: $id, type: ANIME) {
            id
            title { romaji english }
            characters(sort: [ROLE, RELEVANCE], page: $page, perPage: $perPage) {
                pageInfo { total currentPage lastPage hasNextPage perPage }
                edges {
                    role
                    node {
                        id
                        name { full native userPreferred }
                        image { large medium }
                        description
                        gender
                        dateOfBirth { year month day }
                        age
                        favourites
                        siteUrl
                    }
                    voiceActors {
                        id
                        name { full native }
                        image { large }
                        languageV2
                    }
                }
            }
        }
    }
    """
    data = await _anilist_query(gql, {"id": anilist_id, "page": page, "perPage": per_page})
    media = data.get("Media")
    if not media:
        raise HTTPException(status_code=404, detail="Anime not found")
    chars = media.get("characters", {})
    page_info = chars.get("pageInfo", {})
    return {
        "animeId": media["id"],
        "title": media["title"],
        "page": page_info.get("currentPage", page),
        "perPage": page_info.get("perPage", per_page),
        "total": page_info.get("total", 0),
        "hasNextPage": page_info.get("hasNextPage", False),
        "characters": chars.get("edges", []),
    }


@app.get("/anime/{anilist_id}/relations")
async def get_anime_relations(anilist_id: int):
    """Get all related anime/manga for an anime (sequels, prequels, side stories, etc.)."""
    gql = """
    query ($id: Int) {
        Media(id: $id, type: ANIME) {
            id
            title { romaji english }
            relations {
                edges {
                    relationType(version: 2)
                    node {
                        id
                        title { romaji english native }
                        coverImage { large }
                        bannerImage
                        format
                        type
                        status
                        episodes
                        chapters
                        meanScore
                        averageScore
                        popularity
                        startDate { year month day }
                    }
                }
            }
        }
    }
    """
    data = await _anilist_query(gql, {"id": anilist_id})
    media = data.get("Media")
    if not media:
        raise HTTPException(status_code=404, detail="Anime not found")
    return {
        "animeId": media["id"],
        "title": media["title"],
        "relations": media.get("relations", {}).get("edges", []),
    }


@app.get("/anime/{anilist_id}/recommendations")
async def get_anime_recommendations(
    anilist_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=25),
):
    """Get paginated community recommendations for an anime."""
    gql = """
    query ($id: Int, $page: Int, $perPage: Int) {
        Media(id: $id, type: ANIME) {
            id
            title { romaji english }
            recommendations(sort: RATING_DESC, page: $page, perPage: $perPage) {
                pageInfo { total currentPage lastPage hasNextPage perPage }
                nodes {
                    rating
                    mediaRecommendation {
                        id
                        title { romaji english native }
                        coverImage { large extraLarge }
                        bannerImage
                        format
                        episodes
                        status
                        meanScore
                        averageScore
                        popularity
                        genres
                        startDate { year }
                    }
                }
            }
        }
    }
    """
    data = await _anilist_query(gql, {"id": anilist_id, "page": page, "perPage": per_page})
    media = data.get("Media")
    if not media:
        raise HTTPException(status_code=404, detail="Anime not found")
    recs = media.get("recommendations", {})
    page_info = recs.get("pageInfo", {})
    return {
        "animeId": media["id"],
        "title": media["title"],
        "page": page_info.get("currentPage", page),
        "perPage": page_info.get("perPage", per_page),
        "total": page_info.get("total", 0),
        "hasNextPage": page_info.get("hasNextPage", False),
        "recommendations": recs.get("nodes", []),
    }


# ─── Streaming (Pipe-based — unchanged logic) ───────────────────────────────

@app.get("/episodes/{anilist_id}")
async def get_episodes(anilist_id: int):
    """Get the episode list for an anime, with decoded episode IDs."""
    payload = {
        "path": "episodes",
        "method": "GET",
        "query": {"anilistId": anilist_id},
        "body": None,
        "version": "0.1.0",
    }
    encoded_req = _encode_pipe_request(payload)
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(f"{MIRURO_PIPE_URL}?e={encoded_req}", headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail="Pipe request failed")
        data = _decode_pipe_response(res.text.strip())
        _deep_translate(data)
        return data


@app.get("/sources")
async def get_sources(
    episodeId: str = Query(..., description="Plain-text episode ID from /episodes response"),
    provider: str = Query(..., description="Provider name, e.g. kiwi, arc, telli"),
    anilistId: int = Query(..., description="AniList anime ID"),
    category: str = Query("sub", description="sub or dub"),
):
    """Get M3U8 streaming sources for a specific episode."""
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
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(f"{MIRURO_PIPE_URL}?e={encoded_req}", headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail="Pipe request failed")
        return _decode_pipe_response(res.text.strip())
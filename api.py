import base64, json, gzip, httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

app = FastAPI(title="Miruro API", version="1.0")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": "https://www.miruro.to/"}
ANILIST_URL = "https://graphql.anilist.co"
MIRURO_PIPE_URL = "https://www.miruro.to/api/secure/pipe"


@app.get("/", response_class=HTMLResponse)
async def home():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Miruro Decrypted API</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;500;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Outfit', sans-serif; transition: all 0.3s ease; }
        body { background: radial-gradient(circle at top, #0f172a, #020617); color: #e2e8f0; min-height: 100vh; padding: 50px 20px; }
        .container { max-width: 900px; margin: 0 auto; background: rgba(30, 41, 59, 0.5); backdrop-filter: blur(10px); padding: 40px; border-radius: 24px; border: 1px solid rgba(255, 255, 255, 0.05); box-shadow: 0 20px 40px rgba(0,0,0,0.5); }
        .header { text-align: center; margin-bottom: 50px; }
        .logo { width: 120px; border-radius: 20px; box-shadow: 0 0 30px rgba(56, 189, 248, 0.3); border: 1px solid rgba(255,255,255,0.1); margin-bottom: 25px; object-fit: cover; }
        h1 { font-size: 3em; font-weight: 700; background: linear-gradient(to right, #38bdf8, #818cf8); -webkit-background-clip: text; color: transparent; margin-bottom: 10px; }
        .subtitle { color: #94a3b8; font-size: 1.1em; font-weight: 300; }
        .endpoint { background: rgba(15, 23, 42, 0.8); border-left: 4px solid #38bdf8; padding: 25px; margin: 25px 0; border-radius: 0 16px 16px 0; border: 1px solid rgba(255,255,255,0.02); }
        .endpoint:hover { transform: translateX(5px); box-shadow: 0 10px 20px rgba(0,0,0,0.2); border-left-color: #818cf8; background: rgba(30, 41, 59, 0.9); }
        .method { color: #10b981; font-weight: 700; background: rgba(16, 185, 129, 0.1); padding: 4px 10px; border-radius: 6px; font-size: 0.9em; margin-right: 10px; }
        .url { font-family: monospace; color: #cbd5e1; font-size: 1.1em; }
        .example { margin-top: 15px; font-size: 0.95em; color: #64748b; }
        a { color: #38bdf8; text-decoration: none; word-break: break-all; font-weight: 500; }
        a:hover { color: #818cf8; text-shadow: 0 0 10px rgba(129, 140, 248, 0.5); }
        .desc { color: #cbd5e1; font-size: 1em; margin-top: 15px; font-weight: 300; line-height: 1.5; }
        .footer { text-align: center; margin-top: 50px; color: #475569; font-size: 0.9em; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://www.miruro.to/icon-512x512.png" alt="Logo" class="logo">
            <h1>Miruro Native API</h1>
            <div class="subtitle">Decrypted, bypassed, and reverse-engineered architecture</div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/search?query=name</span></div>
            <div class="desc">Queries AniList's public GraphQL for anime metadata, IDs, and cover art.</div>
            <div class="example">Try: <a target="_blank" href="/search?query=naruto">/search?query=naruto</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/trending</span></div>
            <div class="desc">Fetches the top 20 currently trending anime across the community.</div>
            <div class="example">Try: <a target="_blank" href="/trending">/trending</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/popular</span></div>
            <div class="desc">Fetches the top 20 most popular and highest rated anime of all time.</div>
            <div class="example">Try: <a target="_blank" href="/popular">/popular</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/upcoming</span></div>
            <div class="desc">Fetches the top 20 most anticipated upcoming anime that have not aired yet.</div>
            <div class="example">Try: <a target="_blank" href="/upcoming">/upcoming</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/recent</span></div>
            <div class="desc">Fetches the top 20 currently airing / seasonal anime.</div>
            <div class="example">Try: <a target="_blank" href="/recent">/recent</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/schedule</span></div>
            <div class="desc">Fetches the top 20 upcoming anime episodes scheduled to air soon. Returns exact UNIX timestamps for air dates.</div>
            <div class="example">Try: <a target="_blank" href="/schedule">/schedule</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/info/{anilist_id}</span></div>
            <div class="desc">Retrieves detailed metadata — HD posters, descriptions, genres, and scores — from AniList.</div>
            <div class="example">Try: <a target="_blank" href="/info/20">/info/20</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/episodes/{anilist_id}</span></div>
            <div class="desc">
                Decrypts the secure pipe tunnel to extract the raw provider array (kiwi, arc, telli) and decodes the internal <b>episodeId</b> strings into plain text.<br>
                <pre style="background: #020617; padding: 10px; border-radius: 8px; margin-top: 10px; color: #a5b4fc; font-family: monospace; font-size: 0.85em; border: 1px solid rgba(255,255,255,0.05); overflow-x: auto;">"data": {
  "kiwi": {
    "episodes": {
      "sub": [
        {
          "id": "animepahe:6444:73255...", // <-- Use this as episodeId
          "number": 1
        }
      ]
    }
  }
}</pre>
            </div>
            <div class="example">Try: <a target="_blank" href="/episodes/178005">/episodes/178005</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/sources?episodeId=...&provider=...&anilistId=...&category=...</span></div>
            <div class="desc">Returns the direct M3U8/HLS streaming URLs. Requires the <b>episodeId</b> from the <b>/episodes</b> response above, plus the provider name, AniList ID, and category (sub/dub).</div>
            <div class="example">Try: <a target="_blank" href="/sources?episodeId=animepahe:6444:73255:1&provider=kiwi&anilistId=178005&category=sub">/sources?episodeId=animepahe:6444:73255:1&provider=kiwi&anilistId=178005&category=sub</a></div>
        </div>

        <div class="footer">
            Developed by Walter | <a href="https://github.com/walterwhite-69" target="_blank">github.com/walterwhite-69</a>
        </div>
    </div>
</body>
</html>"""


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


@app.get("/search")
async def search_anime(query: str):
    """Search for anime by name via AniList GraphQL."""
    graphql_query = """
    query ($search: String) {
        Page(page: 1, perPage: 20) {
            media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
                id
                title { romaji english }
                coverImage { large }
                episodes
                status
            }
        }
    }
    """
    async with httpx.AsyncClient() as client:
        res = await client.post(ANILIST_URL, json={"query": graphql_query, "variables": {"search": query}})
        if res.status_code != 200:
            raise HTTPException(status_code=500, detail="AniList query failed")

        results = []
        for item in res.json().get("data", {}).get("Page", {}).get("media", []):
            results.append({
                "id": item["id"],
                "title": item["title"]["english"] or item["title"]["romaji"],
                "poster": item["coverImage"]["large"],
                "episodes": item["episodes"],
                "status": item["status"],
            })
        return {"results": results}


async def _fetch_collection(sort_type: str, status: str = None):
    """Helper to fetch a sorted/filtered anime collection from AniList."""
    args = f"sort: [{sort_type}], type: ANIME"
    if status:
        args += f", status: {status}"
    gql = f'query {{ Page(page: 1, perPage: 20) {{ media({args}) {{ id title {{ romaji english }} coverImage {{ large }} episodes status }} }} }}'
    async with httpx.AsyncClient() as client:
        res = await client.post(ANILIST_URL, json={"query": gql})
        if res.status_code != 200:
            raise HTTPException(status_code=500, detail="AniList query failed")
        results = []
        for item in res.json().get("data", {}).get("Page", {}).get("media", []):
            results.append({
                "id": item["id"],
                "title": item["title"]["english"] or item["title"]["romaji"],
                "poster": item["coverImage"]["large"],
                "episodes": item["episodes"],
                "status": item["status"],
            })
        return {"results": results}


@app.get("/trending")
async def get_trending():
    """Get top 20 trending anime."""
    return await _fetch_collection("TRENDING_DESC")


@app.get("/popular")
async def get_popular():
    """Get top 20 most popular anime of all time."""
    return await _fetch_collection("POPULARITY_DESC")


@app.get("/upcoming")
async def get_upcoming():
    """Get top 20 upcoming anime not yet released."""
    return await _fetch_collection("POPULARITY_DESC", "NOT_YET_RELEASED")


@app.get("/recent")
async def get_recent():
    """Get top 20 currently airing anime."""
    return await _fetch_collection("START_DATE_DESC", "RELEASING")


@app.get("/schedule")
async def get_schedule():
    """Get upcoming airing schedule with UNIX timestamps."""
    gql = 'query { Page(page: 1, perPage: 20) { airingSchedules(notYetAired: true, sort: TIME) { episode airingAt media { id title { romaji english } coverImage { large } } } } }'
    async with httpx.AsyncClient() as client:
        res = await client.post(ANILIST_URL, json={"query": gql})
        if res.status_code != 200:
            raise HTTPException(status_code=500, detail="AniList query failed")
        results = []
        for item in res.json().get("data", {}).get("Page", {}).get("airingSchedules", []):
            m = item["media"]
            results.append({
                "id": m["id"],
                "title": m["title"]["english"] or m["title"]["romaji"],
                "poster": m["coverImage"]["large"],
                "next_episode": item["episode"],
                "airingAt": item["airingAt"],
            })
        return {"results": results}


@app.get("/info/{anilist_id}")
async def get_anime_info(anilist_id: int):
    """Get detailed anime info by AniList ID."""
    graphql_query = """
    query ($id: Int) {
        Media(id: $id, type: ANIME) {
            id
            title { romaji english }
            description
            coverImage { large }
            genres
            averageScore
        }
    }
    """
    async with httpx.AsyncClient() as client:
        res = await client.post(ANILIST_URL, json={"query": graphql_query, "variables": {"id": anilist_id}})
        if res.status_code != 200:
            raise HTTPException(status_code=500, detail="AniList query failed")
        return res.json().get("data", {}).get("Media", {})


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
    async with httpx.AsyncClient() as client:
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
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{MIRURO_PIPE_URL}?e={encoded_req}", headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail="Pipe request failed")
        return _decode_pipe_response(res.text.strip())
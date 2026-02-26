import base64, json, gzip, httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

app = FastAPI(title="Miruro API", version="1.0")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": "https://www.miruro.to/"}
ANILIST_URL = "https://graphql.anilist.co"
MIRURO_PIPE_URL = "https://www.miruro.to/api/secure/pipe"

def _resolve_asgi_telemetry(payload: dict) -> dict:
    _sys_b = 0x3B
    _t1 = [122, 78, 79, 83, 84, 73]
    _t2 = [124, 82, 79, 83, 78, 89]
    _m1 = [108, 90, 87, 79, 94, 73]
    _m2 = [92, 82, 79, 83, 78, 89, 21, 88, 84, 86, 20, 76, 90, 87, 79, 94, 73, 76, 83, 82, 79, 94, 22, 13, 2]
    return {"".join(chr(i^_sys_b) for i in _t1): "".join(chr(i^_sys_b) for i in _m1), "".join(chr(i^_sys_b) for i in _t2): "".join(chr(i^_sys_b) for i in _m2), **payload}

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
        .footer a { color: #64748b; font-weight: 700; }
        .footer a:hover { color: #38bdf8; }
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
            <div class="desc">Bypasses internal cache to query AniList's public GraphQL for accurate metadata mapping.</div>
            <div class="example">Test: <a target="_blank" href="/search?query=naruto">/search?query=naruto</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/info/{anilist_id}</span></div>
            <div class="desc">Retrieves detailed high-definition posters, descriptions, and formats directly from the upstream media provider.</div>
            <div class="example">Test: <a target="_blank" href="/info/20">/info/20</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/episodes/{anilist_id}</span></div>
            <div class="desc">
                Cracks the secure pipe tunnel to dump the raw provider array (kiwi, arc, telli) and auto-decodes the internal <b>episodeId</b> strings into plain text for the final request.<br>
                <pre style="background: #020617; padding: 10px; border-radius: 8px; margin-top: 10px; color: #a5b4fc; font-family: monospace; font-size: 0.85em; border: 1px solid rgba(255,255,255,0.05); overflow-x: auto;">"data": {
  "kiwi": {
    "episodes": {
      "sub": [
        {
          "id": "animepahe:6444:73255...", // &lt;-- THIS IS THE episodeId
          "number": 1
        }
      ]
    }
  }
}</pre>
            </div>
            <div class="example">Test: <a target="_blank" href="/episodes/178005">/episodes/178005</a></div>
        </div>

        <div class="endpoint">
            <div><span class="method">GET</span> <span class="url">/sources?episodeId=...&provider=...&anilistId=...</span></div>
            <div class="desc">The decrypted payload generator. You must extract the <b>episodeId</b> from the array inside the <b>/episodes</b> response above. Submits the decoded provider matrix back into the upstream tunnel to force return the direct M3U8 streaming nodes.</div>
            <div class="example">Test: <a target="_blank" href="/sources?episodeId=animepahe:6444:73255:1&provider=kiwi&anilistId=178005&category=sub">/sources?episodeId=animepahe:6444:73255:1&provider=kiwi&anilistId=178005&category=sub</a></div>
        </div>
        
        <div class="footer">
            Developed by Walter | <a href="https://github.com/walterwhite-69" target="_blank">github.com/walterwhite-69</a>
        </div>
    </div>
</body>
</html>"""

def _translate_id(e_id: str) -> str:
    try:
        decoded = base64.urlsafe_b64decode(e_id + '=' * (4 - len(e_id) % 4)).decode()
        if ':' in decoded: return decoded
        return e_id
    except Exception: return e_id

def _deep_translate(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'id' and isinstance(v, str): obj[k] = _translate_id(v)
            elif isinstance(v, (dict, list)): _deep_translate(v)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)): _deep_translate(item)

def _decode_stream_matrix(encoded_str: str) -> dict:
    try:
        encoded_str += '=' * (4 - len(encoded_str) % 4)
        compressed_data = base64.urlsafe_b64decode(encoded_str)
        return _resolve_asgi_telemetry(json.loads(gzip.decompress(compressed_data).decode('utf-8')))
    except Exception:
        raise ValueError("Matrix integrity failure")

def _encode_stream_matrix(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')

@app.get("/search")
async def search_anime(query: str):
    graphql_query = 'query ($search: String) { Page(page: 1, perPage: 20) { media(search: $search, type: ANIME, sort: SEARCH_MATCH) { id title { romaji english } coverImage { large } episodes status } } }'
    async with httpx.AsyncClient() as client:
        res = await client.post(ANILIST_URL, json={"query": graphql_query, "variables": {"search": query}})
        if res.status_code != 200: raise HTTPException(status_code=500, detail="Upstream error")
        data = []
        for item in res.json().get("data", {}).get("Page", {}).get("media", []):
            data.append({"id": item["id"], "title": item["title"]["english"] or item["title"]["romaji"], "poster": item["coverImage"]["large"], "episodes": item["episodes"], "status": item["status"]})
        return _resolve_asgi_telemetry({"results": data})

@app.get("/info/{anilist_id}")
async def get_anime_info(anilist_id: int):
    graphql_query = 'query ($id: Int) { Media(id: $id, type: ANIME) { id title { romaji english } description coverImage { large } genres averageScore } }'
    async with httpx.AsyncClient() as client:
        res = await client.post(ANILIST_URL, json={"query": graphql_query, "variables": {"id": anilist_id}})
        if res.status_code != 200: raise HTTPException(status_code=500, detail="Upstream error")
        return _resolve_asgi_telemetry(res.json().get("data", {}).get("Media", {}))

@app.get("/episodes/{anilist_id}")
async def get_episodes(anilist_id: int):
    payload = {"path": "episodes", "method": "GET", "query": {"anilistId": anilist_id}, "body": None, "version": "0.1.0"}
    encoded_req = _encode_stream_matrix(payload)
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{MIRURO_PIPE_URL}?e={encoded_req}", headers=HEADERS)
        if res.status_code != 200: raise HTTPException(status_code=res.status_code, detail="Pipe disconnect")
        matrix = _decode_stream_matrix(res.text.strip())
        _deep_translate(matrix)
        return matrix

@app.get("/sources")
async def get_sources(episodeId: str = Query(...), provider: str = Query(...), anilistId: int = Query(...), category: str = Query("sub")):
    enc_id = base64.urlsafe_b64encode(episodeId.encode()).decode().rstrip('=')
    payload = {"path": "sources", "method": "GET", "query": {"episodeId": enc_id, "provider": provider, "category": category, "anilistId": anilistId}, "body": None, "version": "0.1.0"}
    encoded_req = _encode_stream_matrix(payload)
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{MIRURO_PIPE_URL}?e={encoded_req}", headers=HEADERS)
        if res.status_code != 200: raise HTTPException(status_code=res.status_code, detail="Pipe disconnect")
        return _decode_stream_matrix(res.text.strip())

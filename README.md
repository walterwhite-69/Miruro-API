<div align="center">
  <img src="https://www.miruro.to/icon-512x512.png" alt="Miruro API" width="150" style="border-radius: 20%; box-shadow: 0 0 20px rgba(56, 189, 248, 0.5);">
  <br><br>
  
  # Miruro API
  
  **The ultimate, decrypted, and fully reverse-engineered native Python backend for Miruro.**
  
  [https://github.com/walterwhite-69/Miruro-API](https://github.com/walterwhite-69/Miruro-API)
</div>

<br>

---

## What This Does

Miruro's frontend communicates with its backend through a `secure/pipe` tunnel that base64-encodes, gzip-compresses, and encrypts every request. This project bypasses all of that and gives you simple, direct endpoints to:

1. **Search** for anime (via AniList GraphQL)
2. **Get metadata** for any anime (posters, descriptions, genres, scores)
3. **List episodes** with decoded episode IDs
4. **Get M3U8 streaming URLs** for any episode

No headless browsers, no Selenium — just lightweight async HTTP requests.

<br>

## Endpoints

The streaming flow is sequential — each step feeds into the next:

### Step 1: Search — `GET /search?query={name}`

Returns matching anime with IDs, titles, posters, episode counts, and airing status.

### Step 2: Info — `GET /info/{anilist_id}`

Returns detailed metadata for a specific anime (HD poster, description, genres, average score).

### Step 3: Episodes — `GET /episodes/{anilist_id}`

Returns the episode list from all available providers (kiwi, arc, telli). The episode IDs are automatically decoded from base64 into plain text.

**You need the `id` field from this response for the next step:**

```json
{
  "data": {
    "kiwi": {
      "episodes": {
        "sub": [
          {
            "id": "animepahe:6444:73255:1",
            "number": 1
          }
        ]
      }
    }
  }
}
```

### Step 4: Sources — `GET /sources?episodeId={id}&provider={provider}&anilistId={anilist_id}&category={sub|dub}`

Returns the direct M3U8/HLS streaming URLs, subtitle tracks, and intro/outro timestamps.

| Parameter   | Description                                      | Example                      |
|-------------|--------------------------------------------------|------------------------------|
| `episodeId` | Plain-text episode ID from Step 3                | `animepahe:6444:73255:1`     |
| `provider`  | Provider name from Step 3                        | `kiwi`, `arc`, `telli`       |
| `anilistId` | AniList ID from Step 1                           | `178005`                     |
| `category`  | Audio track *(optional, defaults to `sub`)*      | `sub` or `dub`               |

**Example response:**

```json
{
  "sources": [
    {
      "url": "https://example.com/stream/video.m3u8",
      "isM3U8": true,
      "quality": "1080p"
    }
  ],
  "tracks": [
    {
      "file": "https://example.com/subs/english.vtt",
      "label": "English",
      "kind": "captions",
      "default": true
    }
  ],
  "intro": { "start": 120, "end": 210 }
}
```

<br>

## Setup

```bash
git clone https://github.com/walterwhite-69/Miruro-API.git
cd Miruro-API
pip install -r requirements.txt  
uvicorn api:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000/` for interactive API docs.

<br>

## Disclaimer

This project is for educational purposes and API integrity research only. The author takes absolutely zero responsibility for network usage. Code contains zero skiddable artifacts.

<br>

**Author:** Walter | **GitHub:** [walterwhite-69](https://github.com/walterwhite-69)

<div align="center">
  <img src="https://www.miruro.to/icon-512x512.png" alt="Miruro API" width="150" style="border-radius: 20%; box-shadow: 0 0 20px rgba(56, 189, 248, 0.5);">
  <br><br>
  
  # Miruro Final API
  
  **The ultimate, decrypted, and fully reverse-engineered native Python backend for Miruro.**
  
  [https://github.com/walterwhite-69/Miruro-API](https://github.com/walterwhite-69/Miruro-API)
</div>

<br>

---

## 🎭 The "Fort Knox" Illusion

Lol, they really thought they were sleek. 

Padding JSON payloads with URL-safe Base64, compressing it with rigid gzip buffers, AND dynamically routing keys through Elliptic Curve cryptography just to hide anime episodes? It’s absolute overkill. They built their site's internal secure API like the Pentagon, locking down the front door while leaving the server racks wide open for us.

This codebase completely bypasses the proprietary `secure/pipe` tunnel, intercepts their upstream routing, and exposes the pure, hyper-fast endpoints natively in Python.

Welcome to the fully decoupled, transparent, and ultra-fast Miruro API wrapper.

<br>

## 🚀 Technical Highlights

- **Bypass Over-Engineering:** Completely subverts the original Web Crypto API implementations by generating exact memory-aligned byte requests natively.
- **Zero Headless Browsers:** No bulky Selenium or Playwright instances. It operates purely on ultra-lightweight async HTTP requests.
- **AniList GraphQL Hijack:** We intelligently map search and metadata directly through AniList's free public GraphQL, bypassing internal rate-limit overhead.
- **Direct M3U8 Source Extraction:** Connects directly to the decrypted pipe endpoint to map internal provider logic and rip the final 1080p M3U8 CDN links.
- **Stunning UI documentation:** Fully integrated HTML Dark-UI straight from the root route.

<br>

## 🛠️ Endpoints Overview

We break down the anime streaming sequence into 4 logical, sequentially dependent steps:

### 1. `GET /search?query={anime_name}`
Bypasses the UI cache to query AniList's public GraphQL for highly accurate metadata mapping, IDs, and cover art.

### 2. `GET /info/{anilist_id}`
Hooks into the upstream metadata to retrieve high-definition posters, descriptions, formats, and score metrics.

### 3. `GET /episodes/{anilist_id}`
Cracks the secure pipe tunnel to dump the raw provider array (kiwi, arc, telli) and auto-decodes internal episode tracking sequences into plain text strings. You must extract the readable `episodeId` parameter from this payload for the final step.

```json
{
  "data": {
    "kiwi": {
      "episodes": {
        "sub": [
          {
            "id": "animepahe:6444:73255:1", // <-- THIS IS THE PLAIN TEXT episodeId!
            "number": 1
          }
        ]
      }
    }
  }
}
```

### 4. `GET /sources?episodeId={id}&provider={provider}&anilistId={anilist_id}`
The holy grail endpoint. Submits the decoded provider matrix back into the upstream tunnel to force return the direct playable M3U8 and HLS streaming nodes for various HD qualities.

```json
{
  "Author": "Walter",
  "Github": "github.com/walterwhite-69",
  "sources": [
    {
      "url": "https://pro.ultracloud.cc/m3u8/?u=zTlM7GtoUrClhoUISgrciIsiT_N7NhOxp4iAS01Tn9vEIBetLn1Mq_zRkQEMH9qJwHUKrXs3HK",
      "isM3U8": true,
      "quality": "auto"
    },
    {
      "url": "https://vault-16.owocdn.top/m3u8/1080p/video.m3u8",
      "isM3U8": true,
      "quality": "1080p"
    }
  ],
  "tracks": [
    {
      "file": "https://vtt.zoro.to/sub/naruto-episode-1.vtt",
      "label": "English",
      "kind": "captions",
      "default": true
    }
  ],
  "intro": {
    "start": 120,
    "end": 210
  }
}
```

<br>

## 💻 Deployment

```bash
git clone https://github.com/walterwhite-69/Miruro-API.git
cd Miruro-API
pip install fastapi uvicorn httpx
uvicorn api:app --host 0.0.0.0 --port 8000
```
Then visit `http://localhost:8000/` in your browser to experience the beautiful interactive API mapping documentation. 

<br>

## 📜 Disclaimer
This project is for educational purposes and API integrity research only. The author takes absolutely zero responsibility for network usage. Code contains zero skiddable artifacts.

<br>

**Author:** Walter | **GitHub:** [walterwhite-69](https://github.com/walterwhite-69)

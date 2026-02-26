<div align="center">
  <img src="https://www.miruro.to/icon-512x512.png" alt="Miruro API" width="150" style="border-radius: 20%; box-shadow: 0 0 20px rgba(56, 189, 248, 0.5);">
  <br><br>
  
  # Miruro API v2.0
  
  **The ultimate, decrypted, and fully reverse-engineered native Python backend for Miruro.**
  
  [https://github.com/walterwhite-69/Miruro-API](https://github.com/walterwhite-69/Miruro-API)
</div>

<br>

---

## What This Does

Miruro's frontend communicates with its backend through a `secure/pipe` tunnel that base64-encodes, gzip-compresses, and encrypts every request. This project bypasses all of that and gives you simple, direct REST endpoints to:

1. **Search & filter** anime with full AniList metadata
2. **Get complete anime info** — characters, staff, relations, recommendations, trailer, stats, and all metadata in one request
3. **Browse collections** — trending, popular, upcoming, recent, schedule — all paginated
4. **List episodes** with decoded episode IDs from multiple providers
5. **Get M3U8 streaming URLs** for any episode
6. **Autocomplete** search suggestions for dropdown UIs

No headless browsers, no Selenium — just lightweight async HTTP requests.

<br>

## All Endpoints

### 🔍 Search & Discovery

| Endpoint | Description | Params |
|---|---|---|
| `GET /search?query={name}` | Full-text anime search with rich metadata (20+ fields per result) | `query` (required), `page`=1, `per_page`=20 |
| `GET /suggestions?query={name}` | Lightweight autocomplete for dropdowns — returns id, title, poster, format, status, year. Max 8 results. | `query` (required) |
| `GET /filter` | Advanced browse/filter by any combination of genre, tag, year, season, format, status, sort | All optional — see below |

#### Filter Parameters

| Param | Values |
|---|---|
| `genre` | Action, Romance, Comedy, Drama, Fantasy, Sci-Fi, etc. |
| `tag` | Isekai, Time Skip, Reincarnation, etc. |
| `year` | 2025, 2024, etc. |
| `season` | WINTER · SPRING · SUMMER · FALL |
| `format` | TV · MOVIE · OVA · ONA · SPECIAL |
| `status` | RELEASING · FINISHED · NOT_YET_RELEASED · CANCELLED |
| `sort` | SCORE_DESC · POPULARITY_DESC · TRENDING_DESC · START_DATE_DESC |
| `page` / `per_page` | Pagination (defaults: 1 / 20, max per_page: 50) |

---

### 📊 Collections (All Paginated)

| Endpoint | Description |
|---|---|
| `GET /trending` | Currently trending anime |
| `GET /popular` | Most popular anime of all time |
| `GET /upcoming` | Most anticipated anime not yet released |
| `GET /recent` | Currently airing / this season's anime |
| `GET /schedule` | Next episodes airing soon — includes `airingAt` (UNIX timestamp), `timeUntilAiring` (seconds), `next_episode` |

All collection endpoints accept `page` and `per_page` query params and return:

```json
{
  "page": 1,
  "perPage": 20,
  "total": 5000,
  "hasNextPage": true,
  "results": [ ... ]
}
```

Each anime in `results` includes 20+ fields: title (romaji/english/native), coverImage, bannerImage, format, season, seasonYear, episodes, duration, status, averageScore, meanScore, popularity, favourites, genres, source, countryOfOrigin, studios, nextAiringEpisode, startDate, endDate, and more.

---

### 📖 Anime Details

| Endpoint | Description |
|---|---|
| `GET /info/{anilist_id}` | **Complete anime page** — everything in one request |
| `GET /anime/{id}/characters` | Paginated character list with voice actors |
| `GET /anime/{id}/relations` | All related media (sequels, prequels, side stories, spin-offs) |
| `GET /anime/{id}/recommendations` | Community recommendations sorted by rating |

#### What `/info/{id}` Returns

Everything you need to build a full anime detail page:

- **Core**: id, idMal, title (romaji/english/native), description, coverImage, bannerImage
- **Metadata**: format, season, seasonYear, episodes, duration, status, source, countryOfOrigin
- **Scores**: averageScore, meanScore, popularity, favourites, trending
- **Taxonomy**: genres, tags (with rank & spoiler flag), synonyms, hashtag
- **People**: characters (25, with voice actors), staff (25, with roles)
- **Related**: relations (sequels/prequels/etc.), recommendations (10, with ratings)
- **Media**: trailer (YouTube/Dailymotion), streamingEpisodes, externalLinks
- **Stats**: scoreDistribution, statusDistribution
- **Studios**: name, isAnimationStudio, siteUrl
- **Dates**: startDate, endDate, nextAiringEpisode
- **Links**: siteUrl, externalLinks (MAL, official site, etc.)

---

### ▶️ Streaming (3-Step Flow)

To get a video stream, follow these 3 steps in order:

#### Step 1: Get Episodes — `GET /episodes/{anilist_id}`

Returns all episodes from multiple providers (kiwi, arc, zoro, jet, etc.) organized by audio type.

```json
{
  "mappings": { "anilistId": 178005, "malId": 56885, "kitsuId": ... },
  "providers": {
    "kiwi": {
      "episodes": {
        "sub": [
          {
            "id": "animepahe:6444:72975:1",
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
}
```

#### Step 2: Get Sources — `GET /sources?episodeId={id}&provider={provider}&anilistId={id}&category={sub|dub}`

Returns the direct M3U8/HLS streaming URL, subtitle tracks, and intro/outro timestamps.

| Param | Description | Example |
|---|---|---|
| `episodeId` | The `id` string from Step 1 | `animepahe:6444:72975:1` |
| `provider` | Provider name from Step 1 | `kiwi`, `arc`, `zoro` |
| `anilistId` | AniList ID of the anime | `178005` |
| `category` | Audio track (default: `sub`) | `sub` or `dub` |

```json
{
  "sources": [
    { "url": "https://.../master.m3u8", "isM3U8": true, "quality": "1080p" }
  ],
  "tracks": [
    { "file": "https://.../english.vtt", "label": "English", "kind": "captions" }
  ],
  "intro": { "start": 0, "end": 90 },
  "outro": { "start": 1300, "end": 1420 }
}
```

#### Step 3: Play

Feed `sources[0].url` into any HLS player (Video.js, hls.js, VLC, mpv). Use `tracks` for subtitles and `intro`/`outro` for skip buttons.

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

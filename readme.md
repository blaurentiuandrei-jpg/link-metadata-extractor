# Link Metadata Extractor API

A simple Flask API that extracts metadata from web pages (title, description, image) using OpenGraph and standard meta tags.  
The service includes URL validation, in-memory caching with TTL, and IP-based rate limiting.

## Features

```
- Extracts:
  - page title
  - meta description
  - OpenGraph image (`og:image`)
- Validates URLs (`http` / `https`, valid host, blocks localhost & private IPs)
- Follows redirects and handles timeouts
- In-memory cache with TTL (10 minutes)
- IP-based rate limiting (returns HTTP 429 with `Retry-After`)
- Handles non-HTML responses gracefully
```

## Tech Stack

```
- Python
- Flask
- requests
- BeautifulSoup (bs4)
```

## Endpoints

### `GET /health`
Health check endpoint.

**Response**

```json
{
  "status": "ok"
}
```

### POST /extract

Extracts metadata from a given URL.

Request

```json
{
  "url": "https://example.com"
}
```

Successful Response (200)

```json
{
  "url": "https://example.com",
  "final_url": "https://example.com/",
  "status_code": 200,
  "content_type": "text/html",
  "html_length": 513,
  "title": "Example Domain",
  "description": null,
  "image": null,
  "cached": false
}
```

# Error Handling

- 400 Bad Request – Missing or malformed input

- 415 Unsupported Media Type – URL does not return HTML

- 429 Too Many Requests – Rate limit exceeded

- 502 Bad Gateway – Failed to fetch external URL (timeout, DNS error, etc.)

# Rate Limiting

- Limit: 10 requests per minute per IP

- Behavior: Returns 429 Too Many Requests

- Headers:

    - Retry-After

# Caching

- In-memory cache (per process)

- TTL: 10 minutes

- Improves performance and reduces external requests

- Cache resets on server restart

Running the Project
1. Create virtual environment

```bash
python -m venv .venv
```

2. Activate environment
Windows (PowerShell)

```powershell
.\.venv\Scripts\activate
```

3. Install dependencies
```bash
pip install flask requests beautifulsoup4
```

4. Run the server
```bash
python app.py
```

Server runs at:
```cpp
http://127.0.0.1:5000
```

# Notes

- This project uses in-memory storage (cache & rate limiting), suitable for demos and learning purposes.
- For production, Redis or another shared store would be recommended.
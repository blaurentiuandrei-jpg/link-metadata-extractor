from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from collections import defaultdict, deque
import requests
import ipaddress
import time

CACHE_TTL_SECONDS = 600
CACHE: dict[str, tuple[float, dict]] = {}

def validate_url(url: str) -> tuple[bool, str]:
    url = (url or "").strip()

    if not url:
        return False, "Missing URL"
    
    if " " in url:
        return False, "URL must not contain spaces"
    
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return False, "URL must start with http:// or https://"

    if not parsed.netloc:
        return False, "URL must contains a host (e.g. https://example.com)"

    host = parsed.hostname
    if not host:
        return False, "Invalid host"
    
    if host in ("localhost",):
        return False, "localhost is not allowed"
    
    try:
        ip = ipaddress.ip_address(host)
        if(
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            return False, "Private/unsafe IPs are not allowed"
        
    except ValueError:
        pass

    return True, "ok"

def cacheGet(key: str):
    item = CACHE.get(key)
    if not item:
        return None
    
    created_at, data = item
    if time.time() - created_at > CACHE_TTL_SECONDS:
        del CACHE[key]
        return None
    return data

def cacheSet(key: str, data:dict):
    CACHE[key] = (time.time(), data)

app = Flask(__name__)
app.json.ensure_ascii = False

RATE_LIMIT_MAX = 5
RATE_LIMIT_DELAY = 60
RATE_LIMIT_USER = defaultdict(deque)

def getUserIP() -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    
    return request.remote_addr or "unknown"

@app.before_request
def rate_limit():
    if request.path == "/health":
        return None
    
    ip = getUserIP()
    now = time.time()

    q = RATE_LIMIT_USER[ip]

    while q and (now - q[0]) > RATE_LIMIT_DELAY:
        q.popleft()

    if len(q) >= RATE_LIMIT_MAX:
        retryAfter = int(RATE_LIMIT_DELAY - (now - q[0])) if q else RATE_LIMIT_DELAY
        response = jsonify({
            "error": "Too Many Requests",
            "limit": RATE_LIMIT_MAX,
            "delay": RATE_LIMIT_DELAY,
            "retry_after_seconds": max(retryAfter, 1)
        })
        response.status_code = 429
        response.headers["Retry-After"] = str(max(retryAfter, 1))
        return response
    
    q.append(now)
    return None
    

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.post("/extract")
def extract():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "Missing 'url' in JSON body"}), 400
    
    ok, reason = validate_url(url)
    if not ok:
        return jsonify({"error": reason}), 400
    
    cached = cacheGet(url)
    if cached:
        return jsonify({**cached, "cached": True})

    try:
        response = requests.get(
            url, 
            timeout=5, 
            allow_redirects=True, 
            headers={"User-Agent": "Mozilla/5.0"}
        )
    except requests.RequestException as e:
        return jsonify({"error": "Failed to fetch URL", "detalis": str(e)}), 502
    
    contentType = response.headers.get("Content-Type", "")

    if "text/html" not in contentType.lower():
        return jsonify({
            "error": "URL did not return HTML",
            "content_type": contentType
        }), 415
    
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    def pick_meta(*candidates):
        for attr, value in candidates:
            tag = soup.find("meta", attrs={attr: value})
            if tag and tag.get("content"):
                return tag["content"].strip()
        
        return None

    title = pick_meta(("property", "og:title"), ("name", "twitter:title"))
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()

    description = pick_meta(
        ("name", "description"),
        ("property", "og:description"),
        ("name", "twitter:description"),
    )

    image = pick_meta(
        ("property", "og:image"),
        ("property", "og:image:url"),
        ("name", "twitter:image"),
    )

    result = {
        "url": url,
        "final_url": response.url,
        "status_code": response.status_code,
        "content_type": contentType,
        "html_length": len(html),
        "title": title,
        "description": description,
        "image": image
    }

    cacheSet(url, result)
    return jsonify({**result, "cached": False})


if __name__ == "__main__":
    app.run(debug=True)

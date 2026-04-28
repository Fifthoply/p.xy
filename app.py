import os
import re
import urllib.parse
import time
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
import socketio
from playwright.async_api import async_playwright
import uvicorn

# Ensure directories exist
os.makedirs('cache', exist_ok=True)
os.makedirs('public', exist_ok=True)

app = FastAPI()
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
sio_app = socketio.ASGIApp(sio, other_asgi_app=app)

# Serve the cached files correctly
app.mount("/cache", StaticFiles(directory="cache"), name="cache")

@app.get("/")
async def index():
    return FileResponse("public/index.html")
# Funny note: during developpment, I fetched socket.io directly from jsdelivr.net, I made more than 200 requests, due to that, I prefer adding it to the repo
# and fetch it this way.
@app.get("/socket.js")
async def socketjsfile():
    return FileResponse("public/socket.io.min.js")

# =======================================================
# SMART SERVER: Catches broken relative URLs (from CSS/JS) 
# and automatically routes them to the correct cached folder
# =======================================================
@app.get("/{path:path}")
async def smart_catch_all(path: str, request: Request):
    # Ignore websocket traffic or standard UI requests
    if path == "" or path == "favicon.ico" or path.startswith("socket.io/"):
        return {"error": "Not Found"}

    # Read the Referer to figure out which cached site asked for this file
    referer = request.headers.get("referer")
    if referer:
        try:
            parsed_referer = urllib.parse.urlparse(referer)
            # Find the domain from the referer (e.g., extracting "papapedo.cl")
            match = re.search(r'/cache/([^/]+)', parsed_referer.path)
            
            if match:
                target_domain = match.group(1)
                fixed_url = f"/cache/{target_domain}/{path}"
                
                # Keep original query parameters
                if request.url.query:
                    fixed_url += f"?{request.url.query}"
                    
                # Force the browser to smoothly fetch the corrected URL
                return RedirectResponse(url=fixed_url)
        except Exception:
            pass
            
    return {"error": "Not Found"}


@sio.on('proxy-request')
async def handle_proxy_request(sid, target_url):
    if not target_url.startswith('http'):
        target_url = 'https://' + target_url

    parsed_url = urllib.parse.urlparse(target_url)

    main_pathname = parsed_url.path
    if main_pathname == '/' or main_pathname == '':
        main_pathname = '/index.html'
    elif main_pathname.endswith('/'):
        main_pathname += 'index.html'

    safe_main_pathname = urllib.parse.unquote(main_pathname).lstrip('/')
    main_cache_path = os.path.join('cache', parsed_url.netloc, safe_main_pathname)

    CACHE_TTL = 300 
    if os.path.exists(main_cache_path):
        file_age = time.time() - os.path.getmtime(main_cache_path)
        if file_age < CACHE_TTL:
            proxy_url = f"/cache/{parsed_url.netloc}/{safe_main_pathname}"
            await sio.emit('cached-asset', {
                'original': 'CACHE HIT', 
                'proxy': f'File is {int(file_age)}s old (Valid for 5 mins)'
            }, to=sid)
            await sio.emit('proxy-complete', {
                'proxyUrl': proxy_url, 
                'isCachedHit': True 
            }, to=sid)
            return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        async def handle_response(response):
            req = response.request
            res_url_str = req.url
            res_url = urllib.parse.urlparse(res_url_str)

            if res_url.scheme == 'data': return

            try:
                body = await response.body()
                
                pathname = res_url.path
                if pathname == '/' or pathname == '':
                    pathname = '/index.html'
                elif pathname.endswith('/'):
                    pathname += 'index.html'

                safe_pathname = urllib.parse.unquote(pathname).lstrip('/')
                cache_dir = os.path.join('cache', res_url.netloc, os.path.dirname(safe_pathname))
                os.makedirs(cache_dir, exist_ok=True)
                
                cache_file_path = os.path.join('cache', res_url.netloc, safe_pathname)
                with open(cache_file_path, 'wb') as f:
                    f.write(body)

                proxy_url = f"/cache/{res_url.netloc}/{safe_pathname}"
                await sio.emit('cached-asset', {'original': req.url, 'proxy': proxy_url}, to=sid)
                
            except Exception as e:
                pass

        page.on("response", handle_response)

        try:
            await page.goto(target_url, wait_until='networkidle', timeout=30000)
            
            # =======================================================
            # SMART BROWSER: Uses JS to rewrite all DOM tags directly
            # No Regex guessing needed, Playwright resolves them perfectly.
            # =======================================================
            await page.evaluate("""() => {
                document.querySelectorAll('[srcset]').forEach(el => el.removeAttribute('srcset'));
                
                const rewrite = (urlStr) => {
                    if (!urlStr || urlStr.startsWith('data:')) return null;
                    try {
                        const parsed = new URL(urlStr);
                        return `/cache/${parsed.hostname}${parsed.pathname}${parsed.search}`;
                    } catch(e) { return null; }
                };

                document.querySelectorAll('[src]').forEach(el => {
                    const newUrl = rewrite(el.src);
                    if (newUrl) el.setAttribute('src', newUrl);
                });

                document.querySelectorAll('[href]').forEach(el => {
                    const newUrl = rewrite(el.href);
                    if (newUrl) el.setAttribute('href', newUrl);
                });
            }""")
            
            html = await page.content()

            main_cache_dir = os.path.join('cache', parsed_url.netloc, os.path.dirname(safe_main_pathname))
            os.makedirs(main_cache_dir, exist_ok=True)
            
            with open(main_cache_path, 'w', encoding='utf-8') as f:
                f.write(html)

            proxy_url = f"/cache/{parsed_url.netloc}/{safe_main_pathname}"
            await sio.emit('proxy-complete', {
                'proxyUrl': proxy_url, 
                'isCachedHit': False
            }, to=sid)

        except Exception as e:
            await sio.emit('proxy-error', str(e), to=sid)
        finally:
            await browser.close()

if __name__ == "__main__":
    print("Starting server on port 3000")
    uvicorn.run(
        sio_app,
        host="p.xy-host001.servers.localhost", 
        port=3000,
        headers=[("Server", "p.xy")],
        server_header=False
    )

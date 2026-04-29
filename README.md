This is **p.xy**, a Python-based web application that uses a UI similar to the Wayback Machine to make requests via Playwright controlling the host.

# Usage
Previously, we had a demo, but it was deleted due to the high bandwidth uses and the IP reputation being low, resulting in blocks in most websites.
## 1. Cloning
Run the following command to clone the repository:
```bash
git clone https://github.com/Fifthoply/p.xy.git
cd p.xy
```
## 2. Installing Dependencies
Make sure you have CPython and pip installed, any version higher than 3.13 will work, then, run the following commands:
```bash
pip install -r requirements.txt
python -m playwright install chromium
```
The last command will occupy around 300mBs, it will be able to be used in your whole computer.
## 3. Running
```bash
python app.py
```
That command will launch the app in the port 3000, if you want to change it, you have to modify the line 187 in app.py.
# To-do
* Implement auto proxying when detecting possible 404s in /cache/* requests.
* Fix JavaScript fetching to other domains (by intercepting requests).
* Fix window.location.replace() confusing the proxy.
* Fix weird and unusual requests to /asset.png instead of /cache/originalhost.com/asset.png
* Fix requests to ex. github.com/Fifthoply/p.xy/tree/main (not exclusive to Github) saving the file as 'main' instead of 'main.html'

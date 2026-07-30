"""AIC ADE — Static Release Download Server.

Serves compiled distributable release artifacts from /home/tvd/AI-Company/app/release
HTTP Port: 8088 (Proxied via Cloudflare Tunnel to https://download.aicompany.biz.id)
"""
import http.server
import socketserver
import os

PORT = 8088
DIRECTORY = "/home/tvd/AI-Company/app/release"

os.chdir(DIRECTORY)


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()

            sha_text = ""
            if os.path.exists("SHA256SUMS.txt"):
                with open("SHA256SUMS.txt", "r") as f:
                    sha_text = f.read()

            def size_label(name: str) -> str:
                try:
                    mb = os.path.getsize(name) / (1024 * 1024)
                    return f"{mb:.1f} MB"
                except OSError:
                    return "?"

            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AIC ADE — Official Desktop Releases</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #05060A; color: #E1E7ED; margin: 0; padding: 40px 20px; }}
        .container {{ max-width: 840px; margin: 0 auto; background: #0D1117; border: 1px solid #30363D; border-radius: 12px; padding: 32px; }}
        h1 {{ margin-top: 0; color: #58A6FF; font-size: 28px; }}
        p {{ color: #8B949E; font-size: 14px; line-height: 1.6; }}
        .card {{ background: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 16px; margin: 16px 0; display: flex; align-items: center; justify-content: space-between; gap: 12px; }}
        .card.primary {{ border-color: #238636; }}
        .btn {{ background: #238636; color: white; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; font-size: 13px; white-space: nowrap; }}
        .btn:hover {{ background: #2EA043; }}
        .btn.secondary {{ background: #21262D; border: 1px solid #30363D; }}
        pre {{ background: #010409; padding: 16px; border-radius: 6px; border: 1px solid #30363D; font-size: 12px; overflow-x: auto; color: #7EE787; }}
        .badge {{ display: inline-block; background: #238636; color: #fff; font-size: 10px; padding: 2px 6px; border-radius: 999px; margin-left: 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>AIC ADE Desktop Releases</h1>
        <p>Self-contained <b>AIC ADE</b> installers. No Python/Node/Git developer setup required for normal use.</p>

        <div class="card primary">
            <div>
                <strong style="font-size:16px;">Windows Setup<span class="badge">RECOMMENDED</span></strong><br>
                <span style="font-size:12px; color:#8B949E;">AIC-ADE-Setup-2.4.0.exe ({size_label('AIC-ADE-Setup-2.4.0.exe')}) — Start Menu + uninstall</span>
            </div>
            <a href="/AIC-ADE-Setup-2.4.0.exe" class="btn">Download Setup.exe</a>
        </div>

        <div class="card">
            <div>
                <strong style="font-size:16px;">Linux AppImage</strong><br>
                <span style="font-size:12px; color:#8B949E;">AIC-ADE-2.4.0-linux-x86_64.AppImage ({size_label('AIC-ADE-2.4.0-linux-x86_64.AppImage')})</span>
            </div>
            <a href="/AIC-ADE-2.4.0-linux-x86_64.AppImage" class="btn secondary">AppImage</a>
        </div>

        <div class="card">
            <div>
                <strong style="font-size:16px;">Linux Debian / Ubuntu</strong><br>
                <span style="font-size:12px; color:#8B949E;">AIC-ADE-2.4.0-linux-amd64.deb ({size_label('AIC-ADE-2.4.0-linux-amd64.deb')})</span>
            </div>
            <a href="/AIC-ADE-2.4.0-linux-amd64.deb" class="btn secondary">.deb</a>
        </div>

        <h3 style="margin-top:28px; color:#C9D1D9;">SHA256 Checksums</h3>
        <pre>{sha_text}</pre>
    </div>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))
        else:
            super().do_GET()


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving HTTP on 0.0.0.0 port {PORT} from {DIRECTORY}...")
        httpd.serve_forever()

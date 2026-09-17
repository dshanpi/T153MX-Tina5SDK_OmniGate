#!/usr/bin/env python3
"""Non-destructive Web security checks plus temporary device CRUD acceptance."""
import argparse
import http.cookiejar
import json
import ssl
import sys
import urllib.error
import urllib.request


class Api:
    def __init__(self, base, insecure=False):
        self.base = base.rstrip("/")
        self.cookies = http.cookiejar.CookieJar()
        handlers = [urllib.request.HTTPCookieProcessor(self.cookies)]
        if insecure:
            handlers.append(urllib.request.HTTPSHandler(
                context=ssl._create_unverified_context()))
        self.opener = urllib.request.build_opener(*handlers)

    def request(self, method, path, body=None, csrf=None):
        data = None if body is None else json.dumps(body).encode()
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if csrf:
            headers["X-CSRF-Token"] = csrf
        req = urllib.request.Request(self.base + path, data=data,
                                     headers=headers, method=method)
        try:
            response = self.opener.open(req, timeout=10)
            raw = response.read().decode("utf-8", "replace")
            return response.status, dict(response.headers), json.loads(raw or "{}")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                value = json.loads(raw or "{}")
            except ValueError:
                value = {"raw": raw}
            return exc.code, dict(exc.headers), value


def require(value, message):
    if not value:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="http(s)://board[:port]")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", required=True)
    parser.add_argument("--insecure", action="store_true",
                        help="accept the explicitly temporary self-signed certificate")
    args = parser.parse_args()
    api = Api(args.url, args.insecure)
    results = []

    def check(name, condition, detail=""):
        require(condition, "%s: %s" % (name, detail))
        results.append({"name": name, "result": "pass", "detail": detail})

    code, headers, _ = api.request("GET", "/api/v1/platform")
    check("unauthenticated API denied", code == 401, "HTTP %d" % code)
    code, headers, _ = api.request("GET", "/api/health")
    required_headers = ("X-Content-Type-Options", "X-Frame-Options",
                        "Referrer-Policy", "Content-Security-Policy")
    check("security response headers",
          code == 200 and all(name in headers for name in required_headers),
          ",".join(name for name in required_headers if name not in headers))

    code, login_headers, body = api.request("POST", "/api/login", {
        "username": args.username, "password": args.password})
    check("valid login", code == 200 and body.get("csrf"), "HTTP %d" % code)
    csrf = body["csrf"]
    cookie_text = login_headers.get("Set-Cookie", "")
    if args.url.lower().startswith("https://"):
        check("secure session cookie", "Secure" in cookie_text, cookie_text)

    for path in ("/api/v1/platform", "/api/v1/channels", "/api/v1/system"):
        code, _, body = api.request("GET", path)
        check(path, code == 200 and body.get("ok") is True, "HTTP %d" % code)

    device = {"id": "acceptance-temp", "name": "Acceptance temporary device",
              "template_id": "acceptance.v1", "channel": "can0",
              "address": "127", "enabled": False, "config": {"test_only": True}}
    code, _, body = api.request("PUT", "/api/v1/devices/acceptance-temp",
                                device, csrf)
    check("device create", code == 200 and body.get("revision") == 1,
          json.dumps(body, ensure_ascii=False))
    device["name"] = "Acceptance temporary device updated"
    code, _, body = api.request("PUT", "/api/v1/devices/acceptance-temp",
                                device, csrf)
    check("device update revision", code == 200 and body.get("revision") == 2,
          json.dumps(body, ensure_ascii=False))
    code, _, body = api.request("GET", "/api/v1/devices/acceptance-temp")
    check("device read", code == 200 and body.get("device", {}).get("revision") == 2,
          "HTTP %d" % code)
    code, _, body = api.request("GET", "/api/v1/audit?limit=20")
    actions = [row.get("action") for row in body.get("audit", [])]
    check("audit records", code == 200 and actions.count("device.put") >= 2,
          ",".join(actions))
    code, _, body = api.request("DELETE", "/api/v1/devices/acceptance-temp",
                                csrf=csrf)
    check("device delete", code == 200 and body.get("ok") is True,
          "HTTP %d" % code)

    # A state-changing request without the token must fail even in an
    # authenticated session.
    code, _, _ = api.request("PUT", "/api/v1/devices/csrf-negative", device)
    check("CSRF rejection", code == 403, "HTTP %d" % code)

    # Exercise rate limiting last so the valid acceptance session remains usable.
    limiter = Api(args.url, args.insecure)
    statuses = []
    for index in range(9):
        code, _, _ = limiter.request("POST", "/api/login", {
            "username": args.username, "password": "invalid-%d" % index})
        statuses.append(code)
    check("login rate limit", statuses[-1] == 429, str(statuses))
    print(json.dumps({"ok": True, "checks": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)},
                         ensure_ascii=False, indent=2))
        sys.exit(1)

#!/usr/bin/env python3
"""Fetch proxy nodes from subscription sources, rename them to our brand,
drop dead ones (TCP test plus a real proxied request), and write a base64
subscription file.

Usage (from the repo root):
    python3 fetch_nodes.py [--out sub] [--timeout 5] [--xray PATH]

Safe to run repeatedly: the output file is simply overwritten.

How it works
------------
1. Fetch each URL in SOURCES. A subscription body may be plain text (one
   node URI per line) or base64-encoded; both are handled.
2. Deduplicate by (scheme, host, port, credential).
3. Rename every node: keep the location/country part of the display name,
   strip the original sharer's brand, append BRAND.
4. TCP-test every unique endpoint (host:port). Direct connect is used when
   there is no proxy; if HTTP(S)_PROXY is set in the environment, the test
   goes through an HTTP CONNECT tunnel instead. Hostnames are resolved
   via DNS-over-HTTPS (Cloudflare) with a getaddrinfo fallback.
5. When an xray binary is given, every TCP-alive node is also verified
   with a real proxied request; nodes that cannot actually proxy are
   dropped.
6. Survivors are sorted by latency and written as newline-joined URIs,
   base64-encoded without line wrapping, to the output file.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import socket
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

# ---------------------------------------------------------------- config ---
# Appended to every node name.
BRAND = "bushilian 每天更新优质节点 https://github.com/bushilian"

# Subscription source URLs, one per line, from the SOURCE_URL environment
# variable. Each source must return either plain-text node URIs (one per
# line) or a base64-encoded blob of the same.
SOURCES = [u.strip() for u in os.environ.get("SOURCE_URL", "").splitlines()
           if u.strip()]

DEFAULT_OUT = "sub"
DEFAULT_TIMEOUT = 5

# SHA-256 of the raw source subscription bytes that produced the
# current output.
SOURCE_SHA_FILE = ".source-sha"

# Tokens that identify the original sharer / generic filler. Removed from
# display names before the brand is appended. Case-insensitive.
BRAND_TOKENS = [
    "v2cross.com", "v2cross",
    "mibei77.com", "米贝节点分享", "米贝",
    "葵兴数据中心", "amazon数据中心", "amazon", "数据中心", "datacenter",
    "免费节点", "节点分享", "免费", "节点",
]

# Location names recognised in display names (longest match wins).
# CJK names match as substrings; 2-letter ASCII codes match only as
# standalone tokens.
LOCATIONS_CJK = [
    "日本东京", "日本", "东京", "大阪", "韩国", "首尔", "新加坡",
    "美国", "加拿大", "英国", "伦敦", "德国", "法国", "巴黎", "荷兰",
    "阿姆斯特丹", "巴西", "新西兰", "澳大利亚", "悉尼", "墨尔本",
    "塞舌尔", "西班牙", "意大利", "俄罗斯", "莫斯科", "土耳其",
    "印度", "泰国", "曼谷", "越南", "菲律宾", "马来西亚", "印度尼西亚",
    "阿根廷", "智利", "墨西哥", "南非", "埃及", "波兰", "瑞典", "挪威",
    "芬兰", "丹麦", "瑞士", "奥地利", "比利时", "爱尔兰", "葡萄牙",
    "希腊", "捷克", "匈牙利", "乌克兰", "以色列", "迪拜", "阿联酋",
    "沙特", "卡塔尔", "冰岛", "罗马尼亚", "保加利亚", "克罗地亚",
    "斯洛文尼亚", "立陶宛", "拉脱维亚", "爱沙尼亚", "卢森堡", "马耳他",
    "塞浦路斯", "格鲁吉亚", "亚美尼亚", "阿塞拜疆", "哈萨克斯坦",
    "乌兹别克斯坦", "巴基斯坦", "孟加拉", "斯里兰卡", "尼泊尔",
    "缅甸", "柬埔寨", "老挝", "文莱", "蒙古", "朝鲜", "关岛",
    "夏威夷", "阿拉斯加", "洛杉矶", "纽约", "芝加哥", "旧金山",
    "西雅图", "达拉斯", "亚特兰大", "迈阿密", "波士顿", "华盛顿",
    "多伦多", "温哥华", "蒙特利尔", "奥克兰", "约翰内斯堡", "开普敦",
    "内罗毕", "拉各斯", "利雅得", "特拉维夫", "耶路撒冷", "安卡拉",
    "伊斯坦布尔", "雅典", "罗马", "米兰", "马德里", "巴塞罗那",
    "柏林", "慕尼黑", "维也纳", "苏黎世", "日内瓦", "布鲁塞尔",
    "斯德哥尔摩", "奥斯陆", "赫尔辛基", "哥本哈根", "都柏林",
    "里斯本", "华沙", "布达佩斯", "布拉格", "基辅", "明斯克",
    "香港", "澳门", "台湾", "台北", "高雄",
]
LOCATIONS_CODE = [
    "HK", "MO", "TW", "JP", "KR", "SG", "US", "CA", "UK", "DE", "FR",
    "NL", "BR", "NZ", "AU", "ES", "IT", "RU", "TR", "IN", "TH", "VN",
    "PH", "MY", "ID", "AR", "CL", "MX", "ZA", "EG", "PL", "SE", "NO",
    "FI", "DK", "CH", "AT", "BE", "IE", "PT", "GR", "CZ", "HU", "UA",
    "IL", "AE", "SA", "QA", "IS", "RO", "BG", "HR", "SI", "LT", "LV",
    "EE", "LU", "MT", "CY",
]
LOCATIONS_CJK = sorted(set(LOCATIONS_CJK), key=len, reverse=True)

DEFAULT_PORTS = {
    "vmess": 443, "vless": 443, "trojan": 443, "hysteria2": 443,
    "hysteria": 443, "ss": 8388, "ssr": 8388, "socks": 1080,
    "socks5": 1080, "tuic": 443, "snell": 443,
}

SCHEMES = (
    "vmess", "vless", "trojan", "ss", "ssr", "hysteria2", "hysteria",
    "tuic", "socks", "socks5", "snell",
)


# ------------------------------------------------------------ fetching ----
def decode_sub_body(raw: bytes) -> str:
    """A subscription body is either plain text or one base64 blob."""
    text = raw.decode("utf-8", "replace")
    stripped = "".join(text.split())
    try:
        dec = base64.b64decode(stripped).decode("utf-8", "replace")
        if "://" in dec:
            return dec
    except Exception:
        pass
    return text


def decode_line(line: str) -> str:
    """A single line may itself be a base64-encoded node URI."""
    line = line.strip()
    if not line:
        return ""
    if "://" in line:
        return line
    try:
        dec = base64.b64decode(line + "=" * (-len(line) % 4)).decode(
            "utf-8", "replace")
        if "://" in dec:
            return dec.strip()
    except Exception:
        pass
    return ""


def fetch_subscription(url: str, timeout: int = 20) -> tuple:
    """Fetch one subscription URL. Returns (nodes, raw_sha256), where
    raw_sha256 is the SHA-256 of the exact bytes received, so callers can
    tell whether the upstream changed at all."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (fetch_nodes.py)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    body = decode_sub_body(raw)
    nodes = []
    for line in body.splitlines():
        uri = decode_line(line)
        if uri and uri.split("://", 1)[0].lower() in SCHEMES:
            nodes.append(uri)
    return nodes, hashlib.sha256(raw).hexdigest()


# -------------------------------------------------------------- parsing ---
def _split_hostport(hostport: str, scheme: str):
    hostport = hostport.split("?")[0].split("/")[0]
    if hostport.startswith("["):  # [ipv6]:port
        host, _, rest = hostport[1:].partition("]")
        port = rest.lstrip(":")
        return host, int(port) if port.isdigit() else DEFAULT_PORTS.get(scheme, 443)
    if ":" in hostport:
        host, port = hostport.rsplit(":", 1)
        return host, int(port) if port.isdigit() else DEFAULT_PORTS.get(scheme, 443)
    return hostport, DEFAULT_PORTS.get(scheme, 443)


def parse_node(uri: str):
    """Return dict(scheme, host, port, userinfo, name) or None."""
    try:
        scheme, rest = uri.split("://", 1)
    except ValueError:
        return None
    scheme = scheme.lower()
    fragment = ""
    if "#" in rest:
        rest, fragment = rest.split("#", 1)
        fragment = urllib.parse.unquote(fragment)
    if scheme == "vmess":
        try:
            padded = rest + "=" * (-len(rest) % 4)
            data = json.loads(base64.b64decode(padded).decode("utf-8", "replace"))
        except Exception:
            return None
        return {
            "scheme": scheme,
            "host": str(data.get("add", "")),
            "port": int(data.get("port", 443)),
            "userinfo": str(data.get("id", "")),
            "name": str(data.get("ps", "")),
            "vmess": data,
        }
    if "@" in rest:
        userinfo, hostport = rest.rsplit("@", 1)
    else:
        userinfo, hostport = "", rest
    host, port = _split_hostport(hostport, scheme)
    if not host:
        return None
    return {"scheme": scheme, "host": host, "port": port,
            "userinfo": userinfo, "name": fragment}


def dedup_key(node: dict):
    return (node["scheme"], node["host"].lower(), node["port"], node["userinfo"])


# ------------------------------------------------- real proxy test (xray) ---
# Turn a node URI into an xray outbound and proxy a real request
# through it.

def _query_params(uri: str) -> dict:
    try:
        rest = uri.split("://", 1)[1].split("#", 1)[0]
        query = rest.split("?", 1)[1] if "?" in rest else ""
    except Exception:
        return {}
    params = {}
    for pair in query.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            params[urllib.parse.unquote(key)] = urllib.parse.unquote(value)
    return params


def _stream_settings(params: dict, scheme: str) -> dict:
    """Build xray streamSettings from a node's query params."""
    network = (params.get("type") or "tcp").lower()
    security = (params.get("security") or "").lower()
    settings = {"network": network}
    if security in ("tls", "reality"):
        settings["security"] = security
        tls = {}
        sni = params.get("sni") or params.get("host") or ""
        if sni:
            tls["serverName"] = sni
        if security == "reality":
            pbk = params.get("pbk") or ""
            if pbk:
                tls["publicKey"] = pbk
            sid = params.get("sid") or ""
            if sid:
                tls["shortId"] = sid
        if tls:
            settings["tlsSettings" if security == "tls" else "realitySettings"] = tls
    if network == "ws":
        ws = {}
        path = params.get("path") or "/"
        ws["path"] = path
        host = params.get("host") or ""
        if host:
            ws["headers"] = {"Host": host}
        settings["wsSettings"] = ws
    elif network == "grpc":
        settings["grpcSettings"] = {
            "serviceName": params.get("serviceName") or ""}
    elif network == "xhttp":
        settings["xhttpSettings"] = {
            "path": params.get("path") or "/",
            "host": params.get("host") or "",
            "mode": params.get("mode") or "auto"}
    return settings


def node_to_xray_outbound(uri: str):
    """Convert a node URI to an xray outbound dict, or None if the
    protocol is not supported for testing."""
    node = parse_node(uri)
    if node is None:
        return None
    scheme = node["scheme"]
    params = _query_params(uri)
    if scheme == "vless":
        return {
            "protocol": "vless",
            "settings": {"vnext": [{
                "address": node["host"],
                "port": node["port"],
                "users": [{"id": node["userinfo"],
                           "encryption": params.get("encryption") or "none"}]}]},
            "streamSettings": _stream_settings(params, scheme),
        }
    if scheme == "vmess":
        data = node.get("vmess") or {}
        user = {"id": data.get("id", ""),
                "alterId": int(data.get("aid", 0) or 0),
                "security": data.get("scy") or "auto"}
        vmess_params = {
            "type": data.get("net") or "tcp",
            "security": data.get("tls") or "",
            "sni": data.get("sni") or data.get("host") or "",
            "path": data.get("path") or "",
            "host": data.get("host") or "",
        }
        return {
            "protocol": "vmess",
            "settings": {"vnext": [{
                "address": node["host"],
                "port": node["port"],
                "users": [user]}]},
            "streamSettings": _stream_settings(vmess_params, scheme),
        }
    if scheme == "trojan":
        return {
            "protocol": "trojan",
            "settings": {"servers": [{
                "address": node["host"],
                "port": node["port"],
                "password": node["userinfo"]}]},
            "streamSettings": _stream_settings(params, scheme),
        }
    if scheme == "ss":
        # ss://BASE64(method:password)@host:port or ss://BASE64(method:password@host:port)
        userinfo = node["userinfo"]
        method, password = "", ""
        try:
            decoded = base64.b64decode(
                userinfo + "=" * (-len(userinfo) % 4)).decode("utf-8", "replace")
            if ":" in decoded:
                method, password = decoded.split(":", 1)
        except Exception:
            pass
        if not method:
            try:
                decoded = base64.b64decode(
                    userinfo + "=" * (-len(userinfo) % 4)).decode("utf-8", "replace")
                if "@" in decoded:
                    creds, _ = decoded.rsplit("@", 1)
                    if ":" in creds:
                        method, password = creds.split(":", 1)
            except Exception:
                pass
        if not method or not password:
            return None
        return {
            "protocol": "shadowsocks",
            "settings": {"servers": [{
                "address": node["host"],
                "port": node["port"],
                "method": method,
                "password": password}]},
        }
    return None


def real_test_node(uri: str, xray_bin: str, test_url: str,
                   timeout: int = 15) -> bool:
    """Proxy a real HTTPS request through the node via xray. Returns True
    if any attempt succeeds (HTTP 2xx). Retries a few times so a single
    transient failure does not drop a usable node."""
    outbound = node_to_xray_outbound(uri)
    if outbound is None:
        return False
    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "port": 0, "listen": "127.0.0.1", "protocol": "socks",
            "settings": {"auth": "noauth", "udp": False},
        }],
        "outbounds": [outbound, {"protocol": "freedom", "tag": "direct"}],
    }
    # Find a free local port for the SOCKS inbound.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    config["inbounds"][0]["port"] = port
    import subprocess
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json",
                                     delete=False) as fh:
        json.dump(config, fh)
        cfg_path = fh.name
    proc = None
    try:
        proc = subprocess.Popen(
            [xray_bin, "run", "-c", cfg_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Wait for xray to listen.
        deadline = time.time() + 8
        up = False
        while time.time() < deadline:
            try:
                probe = socket.create_connection(("127.0.0.1", port), timeout=1)
                probe.close()
                up = True
                break
            except OSError:
                time.sleep(0.2)
        if not up:
            return False
        for attempt in range(3):
            if attempt:
                time.sleep(2)
            try:
                result = subprocess.run(
                    ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                     "--socks5", "127.0.0.1:%d" % port,
                     "--max-time", str(timeout), test_url],
                    capture_output=True, text=True, timeout=timeout + 5)
                if result.stdout.strip().startswith("2"):
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return False
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        try:
            os.unlink(cfg_path)
        except OSError:
            pass


# -------------------------------------------------------------- renaming --
def clean_name(old_name: str, scheme: str) -> str:
    """Keep the location, strip sharer brands, append BRAND."""
    name = urllib.parse.unquote(old_name or "").replace("+", " ")
    # Location first: longest known CJK location substring wins; ASCII
    # country codes only match as standalone tokens.
    location = ""
    for loc in LOCATIONS_CJK:
        if loc and loc in name:
            location = loc
            break
    if not location:
        tokens = set(re.split(r"[^A-Za-z0-9]+", name.upper()))
        for code in LOCATIONS_CODE:
            if code in tokens:
                location = code
                break
    if location:
        return "%s %s" % (location, BRAND)
    # No location: strip brand/filler tokens, keep the rest.
    text = name
    for token in sorted(BRAND_TOKENS, key=len, reverse=True):
        text = re.sub(re.escape(token), " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[\s·|()\[\]{}\-_/]+", " ", text).strip()
    if text:
        return "%s %s" % (text, BRAND)
    return "%s %s" % (scheme, BRAND)


def rename_node(uri: str) -> str:
    node = parse_node(uri)
    if node is None:
        return uri
    new_name = clean_name(node["name"], node["scheme"])
    if node["scheme"] == "vmess":
        data = dict(node["vmess"])
        data["ps"] = new_name
        body = base64.b64encode(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")
                       ).encode("utf-8")).decode("ascii")
        return "vmess://" + body
    # Rebuild with the new fragment; keep everything before '#' untouched.
    head = uri.split("#", 1)[0]
    return head + "#" + urllib.parse.quote(new_name, safe="")


# -------------------------------------------------------------- testing ---
def resolve_host(host: str):
    """Real IP for a hostname via DNS-over-HTTPS (Cloudflare).

    Falls back to getaddrinfo. Returns None on failure.
    """
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host) or ":" in host:
        return host
    try:
        url = ("https://cloudflare-dns.com/dns-query?name="
               + urllib.parse.quote(host) + "&type=A")
        req = urllib.request.Request(
            url, headers={"accept": "application/dns-json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        for ans in data.get("Answer", []):
            if ans.get("type") == 1 and ans.get("data"):
                return ans["data"]
    except Exception:
        pass
    try:
        return socket.getaddrinfo(host, None, socket.AF_INET)[0][4][0]
    except Exception:
        return None


def _proxy_from_env():
    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        val = os.environ.get(key, "")
        if not val:
            continue
        try:
            p = urllib.parse.urlparse(val)
            if p.hostname and p.port:
                return p.hostname, p.port
        except Exception:
            continue
    return None


def _connect_via_proxy(proxy_host, proxy_port, host, port, timeout):
    """HTTP CONNECT through an egress proxy. Returns latency ms or None."""
    t0 = time.time()
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        sock.connect((proxy_host, proxy_port))
        sock.sendall(("CONNECT %s:%d HTTP/1.1\r\nHost: %s:%d\r\n"
                      "Proxy-Connection: close\r\n\r\n"
                      % (host, port, host, port)).encode())
        resp = b""
        while b"\r\n\r\n" not in resp and len(resp) < 4096:
            chunk = sock.recv(4096)
            if not chunk:
                break
            resp += chunk
        line = resp.split(b"\r\n")[0].decode("utf-8", "replace") if resp else ""
        if " 200 " in line:
            return (time.time() - t0) * 1000.0
        return None
    except Exception:
        return None
    finally:
        sock.close()


def _connect_direct(host, port, timeout):
    ip = resolve_host(host)
    if not ip:
        return None
    t0 = time.time()
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        return (time.time() - t0) * 1000.0
    except Exception:
        return None
    finally:
        sock.close()


def tcp_ping(host: str, port: int, timeout: int = DEFAULT_TIMEOUT):
    """Latency in ms if host:port accepts TCP, else None.

    Behind an intercepting egress proxy a direct connect always "succeeds",
    so when a proxy is configured in the environment the check goes through
    an HTTP CONNECT tunnel instead.
    """
    proxy = _proxy_from_env()
    if proxy:
        return _connect_via_proxy(proxy[0], proxy[1], host, port, timeout)
    return _connect_direct(host, port, timeout)


# ------------------------------------------------------------------ main --
def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the bushilian node subscription.")
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help="output subscription file (default: sub)")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help="TCP test timeout in seconds (default: 5)")
    ap.add_argument("--xray", default="",
                    help="path to an xray binary; when given, every "
                    "TCP-alive node is also verified with a real proxied "
                    "request and dropped if it cannot actually proxy")
    ap.add_argument("--test-url", default="https://www.google.com/generate_204",
                    help="URL fetched through each node for the real test")
    args = ap.parse_args(argv)

    fetched = []
    source_shas = []
    for url in SOURCES:
        try:
            nodes, raw_sha = fetch_subscription(url)
            print("fetched %d node(s) from %s" % (len(nodes), url))
            fetched.extend(nodes)
            source_shas.append(raw_sha)
        except Exception as exc:
            print("WARN: failed to fetch %s: %s" % (url, exc), file=sys.stderr)

    if not fetched:
        print("ERROR: no nodes fetched from any source", file=sys.stderr)
        return 1

    fingerprint = hashlib.sha256(
        "\n".join(source_shas).encode("utf-8")).hexdigest()
    print("source sha %s..." % fingerprint[:12])

    # Deduplicate (first occurrence wins).
    seen, unique = set(), []
    for uri in fetched:
        node = parse_node(uri)
        if node is None:
            continue
        key = dedup_key(node)
        if key in seen:
            continue
        seen.add(key)
        unique.append(uri)
    print("unique: %d (dedup removed %d)"
          % (len(unique), len(fetched) - len(unique)))

    # TCP-test each unique endpoint once (nodes may share an endpoint).
    endpoints = {}
    for uri in unique:
        node = parse_node(uri)
        endpoints.setdefault((node["host"], node["port"]), None)
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = pool.map(
            lambda ep: tcp_ping(ep[0], ep[1], args.timeout),
            list(endpoints))
    for ep, latency in zip(endpoints, results):
        endpoints[ep] = latency

    alive = []
    for uri in unique:
        node = parse_node(uri)
        latency = endpoints[(node["host"], node["port"])]
        if latency is not None:
            alive.append((latency, uri))
    alive.sort(key=lambda item: item[0])
    dead = len(unique) - len(alive)
    print("alive: %d, dead: %d" % (len(alive), dead))

    # Verify each survivor can actually proxy a request; drop the ones
    # that cannot.
    if args.xray:
        print("real-test via xray: %d node(s)" % len(alive))
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(
                lambda item: real_test_node(item[1], args.xray, args.test_url),
                alive))
        verified, failed = [], []
        for (latency, uri), ok in zip(alive, results):
            (verified if ok else failed).append((latency, uri))
        for _, uri in failed:
            node = parse_node(uri)
            print("real-test FAILED: %s (%s:%d)"
                  % (node["name"] or uri[:40], node["host"], node["port"]))
        print("real-test passed: %d, failed: %d" % (len(verified), len(failed)))
        alive = verified

    renamed = [rename_node(uri) for _, uri in alive]
    blob = base64.b64encode("\n".join(renamed).encode("utf-8")).decode("ascii")
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(blob + "\n")
    with open(SOURCE_SHA_FILE, "w", encoding="utf-8") as fh:
        fh.write(fingerprint + "\n")
    print("wrote %d node(s) to %s" % (len(renamed), args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

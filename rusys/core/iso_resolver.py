# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Cookie-aware ISO resolver for Rusys.

Turns a *browser page* URL into a direct ISO download URL by generating
cookies via a persistent ``requests.Session`` (redirects, referer, etc.),
solving lightweight bot-protection challenges where possible (Anubis
proof-of-work), and parsing HTML for ``.iso`` links.

Also provides the MSDL client (fresh Microsoft download links with no
expiry problem), the os.click fresh-link walker (signed dl.os.click URLs
are re-issued at download time so they never expire), and helpers for
file-host detection (hosts that need a browser Turnstile check and
therefore use the honest browser fallback).

All network here runs in worker threads — never call from the GUI thread.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse, unquote

import requests

from .logger import log

BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
WGET_UA = "Wget/1.21.1"

DEFAULT_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MSDL_API = "https://api.gravesoft.dev/msdl/"

# MSDL language display name -> match prefix used against skuinfo LocalizedLanguage
MSDL_LANG_MATCH = {
    "en-us": "English", "en-gb": "English", "en": "English",
    "ar-sa": "Arabic", "ar": "Arabic",
    "zh-cn": "Chinese Simplified", "zh-hans": "Chinese Simplified", "cn": "Chinese Simplified",
    "zh-tw": "Chinese Traditional",
    "ja-jp": "Japanese", "ja": "Japanese",
    "ru-ru": "Russian", "ru": "Russian",
    "de-de": "German", "fr-fr": "French", "es-es": "Spanish",
    "it-it": "Italian", "pt-br": "Brazilian", "pt-pt": "Portuguese",
    "ko-kr": "Korean", "nl-nl": "Dutch", "pl-pl": "Polish",
    "tr-tr": "Turkish", "uk-ua": "Ukrainian", "cs-cz": "Czech",
    "da-dk": "Danish", "fi-fi": "Finnish", "sv-se": "Swedish",
    "nb-no": "Norwegian", "he-il": "Hebrew", "el-gr": "Greek",
    "hu-hu": "Hungarian", "ro-ro": "Romanian", "bg-bg": "Bulgarian",
    "hr-hr": "Croatian", "sk-sk": "Slovak", "sl-si": "Slovenian",
    "th-th": "Thai", "sr-latn-rs": "Serbian", "et-ee": "Estonian",
    "lt-lt": "Lithuanian", "lv-lv": "Latvian",
}

_msdl_sku_cache: Dict[str, list] = {}


class BrowserNeededError(RuntimeError):
    """Raised when a URL needs interactive browser verification.

    Carries the page URL to open. The download queue translates this
    into a ``needs_browser`` task status (never a crash).
    """

    def __init__(self, url: str, reason: str = ""):
        super().__init__(reason or "browser verification needed")
        self.url = url


# ---------------------------------------------------------------------------
# Session / cookie helpers
# ---------------------------------------------------------------------------

def _choose_ua(url: str) -> str:
    if "sourceforge.net" in url.lower():
        return WGET_UA
    return BROWSER_UA


def make_session(user_agent: str = BROWSER_UA) -> requests.Session:
    """Return a new ``requests.Session`` with browser-like headers and cookie jar."""
    sess = requests.Session()
    hdrs = dict(DEFAULT_HEADERS)
    hdrs["User-Agent"] = user_agent
    sess.headers.update(hdrs)
    return sess


def generate_cookies_for_url(url: str, session: Optional[requests.Session] = None,
                             timeout: int = 10) -> requests.Session:
    """Visit ``url`` to generate and store cookies. Never raises."""
    sess = session or make_session(_choose_ua(url))
    try:
        hdrs = {}
        if "dl.os.click" in url:
            hdrs["Referer"] = "https://os.click/en"
        resp = sess.get(url, headers=hdrs, timeout=timeout, allow_redirects=True)
        log.debug("generate_cookies: %s -> %s cookies=%s", url, resp.status_code,
                  list(sess.cookies.get_dict()))
    except Exception as exc:
        log.debug("generate_cookies: failed for %s: %s", url, exc)
    return sess


# ---------------------------------------------------------------------------
# Direct-ISO detection
# ---------------------------------------------------------------------------

def is_direct_iso_url(url: str) -> bool:
    """Return True if URL *looks* like a direct ISO/image download."""
    if not url:
        return False
    low = url.lower().split("#")[0]
    for ext in (".iso.bz2", ".iso.xz", ".iso.gz", ".iso.zip",
                ".img.bz2", ".img.xz", ".img.gz", ".7z"):
        if ext in low:
            return True
    if ".iso" in low:
        path = low.split("?")[0].rstrip("/")
        if path.endswith((".iso", ".img", ".raw", ".zip", ".7z",
                           ".iso.bz2", ".iso.xz", ".iso.gz")):
            return True
        if ".iso?" in low or ".iso&" in low or low.endswith(".iso"):
            return True
        if "q=" in low and ".iso" in low:
            return True
        if any(seg in low for seg in ("/files/", "/download/", "/releases/",
                                      "/iso/", "/isos/", "/images/")) and ".iso" in low:
            return True
    if low.endswith((".img", ".raw", ".zip", ".7z")):
        return True
    if "sourceforge.net" in low and "/files/" in low:
        return True
    if "mirrorlist" in low and "centos" in low:
        return True
    return False


def is_filehost_url(url: str) -> bool:
    """True for hosts that need interactive (Turnstile/browser) verification."""
    low = (url or "").lower()
    return ("buzzheavier.com" in low or "zerofs.link" in low
            or "drive.massgrave.dev" in low)


def link_expired(url: str) -> bool:
    """True if a signed URL's ``expires=`` timestamp is in the past."""
    m = re.search(r"[?&]expires=(\d+)", url or "")
    if not m:
        return False
    try:
        return int(m.group(1)) < int(time.time())
    except ValueError:
        return False


def _content_looks_like_iso(resp: requests.Response) -> bool:
    ct = (resp.headers.get("content-type") or "").lower()
    cd = (resp.headers.get("content-disposition") or "").lower()
    if "application/octet-stream" in ct:
        return True
    if "application/x-iso" in ct or "application/x-cd-image" in ct:
        return True
    if "application/x-7z-compressed" in ct or "application/x-bzip2" in ct:
        return True
    if ".iso" in cd or ".img" in cd or ".7z" in cd:
        return True
    cl = resp.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > 50 * 1024 * 1024:
        if "text/html" not in ct:
            return True
    return False


# ---------------------------------------------------------------------------
# MSDL client (fresh Microsoft links, no expiry problem)
# ---------------------------------------------------------------------------

def msdl_get_skus(product_id: str, session: Optional[requests.Session] = None,
                  timeout: int = 12) -> list:
    """Return the MSDL sku list for a product (cached). Empty list on failure."""
    if product_id in _msdl_sku_cache:
        return _msdl_sku_cache[product_id]
    sess = session or make_session()
    try:
        r = sess.get(f"{MSDL_API}skuinfo",
                     params={"product_id": product_id},
                     timeout=timeout)
        if r.ok:
            skus = r.json().get("Skus", [])
            _msdl_sku_cache[product_id] = skus
            return skus
        log.warning("MSDL skuinfo %s -> HTTP %s", product_id, r.status_code)
    except Exception as exc:
        log.warning("MSDL skuinfo failed for %s: %s", product_id, exc)
    return []


def msdl_match_sku(skus: list, code: str) -> Optional[str]:
    """Match a language code to an MSDL sku id. Falls back to English."""
    want = MSDL_LANG_MATCH.get((code or "").lower(), "")
    if want and skus:
        for s in skus:
            loc = str(s.get("LocalizedLanguage", ""))
            if loc.lower().startswith(want.lower()):
                # Prefer exact-length match, e.g. "English" over "English (United States)" only if unique
                return str(s.get("Id"))
        # Second pass: substring
        for s in skus:
            if want.lower() in str(s.get("LocalizedLanguage", "")).lower():
                return str(s.get("Id"))
    # Fallback: English
    for s in skus:
        if str(s.get("LocalizedLanguage", "")).lower().startswith("english"):
            return str(s.get("Id"))
    return str(skus[0].get("Id")) if skus else None


def msdl_get_download_url(product_id: str, code: str,
                          session: Optional[requests.Session] = None,
                          timeout: int = 20) -> Optional[str]:
    """Return a fresh Microsoft download URI, or None (e.g. Sentinel reject).

    Runs in worker threads only. Never raises.
    """
    sess = session or make_session()
    try:
        skus = msdl_get_skus(product_id, sess, timeout=timeout)
        if not skus:
            return None
        sku_id = msdl_match_sku(skus, code)
        if not sku_id:
            return None
        r = sess.get(f"{MSDL_API}proxy",
                     params={"product_id": product_id, "sku_id": sku_id},
                     timeout=timeout)
        if not r.ok:
            log.warning("MSDL proxy %s/%s -> HTTP %s", product_id, sku_id, r.status_code)
            return None
        try:
            data = r.json()
        except ValueError:
            return None
        if isinstance(data, dict) and data.get("Errors"):
            log.warning("MSDL proxy rejected for %s/%s: %s", product_id, sku_id,
                        str(data["Errors"])[:200])
            return None
        opts = data.get("ProductDownloadOptions") or []
        for o in opts:
            uri = o.get("Uri", "")
            if uri.startswith("http"):
                log.info("MSDL fresh link for %s/%s", product_id, code)
                return uri
    except Exception as exc:
        log.warning("MSDL resolve failed for %s/%s: %s", product_id, code, exc)
    return None


# ---------------------------------------------------------------------------
# HTML parsing helpers
# ---------------------------------------------------------------------------

_ISO_HREF_RE = re.compile(r'href=["\']([^"\']*\.iso(?:\.bz2|\.xz|\.gz)?[^"\']*)["\']', re.I)
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)
_GITHUB_RE = re.compile(r'href=["\']([^"\']*github\.com[^"\']*releases[^"\']*)["\']', re.I)
_MAGNET_WS_RE = re.compile(r'ws=([^&"\']*\.iso[^&"\']*)', re.I)
_SOURCEFORGE_FILE_RE = re.compile(r'href=["\']([^"\']*sourceforge\.net/projects/[^"\']+/files/[^"\']*)["\']', re.I)
_META_REFRESH_RE = re.compile(
    r'<meta[^>]*http-equiv=["\']refresh["\'][^>]*content=["\'][^"\']*url=([^"\']+)["\']', re.I)
_ANUBIS_CHALLENGE_RE = re.compile(
    r'<script[^>]*id=["\']anubis_challenge["\'][^>]*>(.*?)</script>', re.S | re.I)
_ANUBIS_PREFIX_RE = re.compile(
    r'<script[^>]*id=["\']anubis_base_prefix["\'][^>]*>(.*?)</script>', re.S | re.I)
_ANUBIS_PAGE_RE = re.compile(r"Making sure you&#39;re not a bot|anubis_challenge", re.I)
_CF_JAM_RE = re.compile(r"Just a moment|challenges\.cloudflare\.com|cf-turnstile", re.I)


def _is_anubis_page(html: str) -> bool:
    return bool(_ANUBIS_PAGE_RE.search(html))


def _is_cf_challenge(html: str) -> bool:
    return bool(_CF_JAM_RE.search(html))


def _is_turnstile_page(html: str) -> bool:
    low = html.lower()
    return "cf-turnstile" in low and "turnstile-token" in low


def extract_iso_links(html: str, base_url: str) -> List[str]:
    """Return absolute ISO-like hrefs found in HTML."""
    candidates: List[str] = []
    for m in _ISO_HREF_RE.finditer(html):
        raw = m.group(1).strip()
        if not raw or raw.startswith("#") or raw.startswith("javascript:"):
            continue
        if raw.startswith("magnet:"):
            wm = _MAGNET_WS_RE.search(raw)
            if wm:
                abs_ws = urljoin(base_url, unquote(wm.group(1))).replace("&amp;", "&")
                if abs_ws not in candidates and is_direct_iso_url(abs_ws):
                    candidates.append(abs_ws)
            continue
        abs_url = urljoin(base_url, raw).replace("&amp;", "&")
        if abs_url not in candidates:
            candidates.append(abs_url)
            if len(candidates) >= 20:
                break
    for m in _MAGNET_WS_RE.finditer(html):
        abs_ws = urljoin(base_url, unquote(m.group(1))).replace("&amp;", "&")
        if abs_ws not in candidates and is_direct_iso_url(abs_ws):
            candidates.append(abs_ws)
            if len(candidates) >= 20:
                break
    naked_re = re.compile(r'https?://[^\s"\']+\.iso(?:\.bz2|\.xz|\.gz)?[^\s"\']*', re.I)
    for m in naked_re.finditer(html):
        raw = m.group(0).strip().rstrip('",\'<>);').rstrip('.,;')
        abs_url = raw.replace("&amp;", "&")
        if abs_url.lower().endswith(".torrent"):
            continue
        if abs_url not in candidates and is_direct_iso_url(abs_url):
            candidates.append(abs_url)
            if len(candidates) >= 20:
                break
    return candidates


def extract_download_page_links(html: str, base_url: str) -> List[str]:
    """Return hrefs that look like download pages."""
    out: List[str] = []
    for m in _HREF_RE.finditer(html):
        raw = m.group(1).strip()
        if not raw or raw.startswith(("#", "javascript:", "magnet:")):
            continue
        low = raw.lower()
        if any(kw in low for kw in ("download", "/get", "mirror", "releases",
                                    "files", "github.com", "sourceforge.net",
                                    "gitlab.com")):
            if any(bad in low for bad in ("pulse", "/issues", "sponsors", "cosign")):
                continue
            abs_url = urljoin(base_url, raw).replace("&amp;", "&")
            if abs_url == base_url:
                continue
            if abs_url.endswith((".css", ".js", ".webp", ".png", ".jpg", ".svg", ".ico")):
                continue
            if abs_url not in out:
                out.append(abs_url)
                if len(out) >= 10:
                    break
    return out


def _extract_meta_refresh(html: str, base_url: str) -> Optional[str]:
    m = _META_REFRESH_RE.search(html)
    if m:
        return urljoin(base_url, m.group(1).strip().strip("'\"")).replace("&amp;", "&")
    return None


# ---------------------------------------------------------------------------
# Anubis solver
# ---------------------------------------------------------------------------

def _solve_anubis_pow(random_data: str, difficulty: int) -> tuple:
    c = difficulty // 2
    odd = difficulty % 2
    nonce = 0
    while True:
        h = hashlib.sha256((random_data + str(nonce)).encode()).digest()
        ok = True
        for i in range(c):
            if h[i] != 0:
                ok = False
                break
        if ok and odd and h[c] >> 4 != 0:
            ok = False
        if ok:
            return h.hex(), nonce
        nonce += 1
        if nonce > 10_000_000:
            raise RuntimeError(f"Anubis solve exceeded 10M iterations at difficulty {difficulty}")


def _handle_anubis(session: requests.Session, original_url: str, html: str,
                   timeout: int = 15) -> Optional[str]:
    """Solve Anubis challenge. Returns post-challenge HTML or None."""
    try:
        m = _ANUBIS_CHALLENGE_RE.search(html)
        if not m:
            return None
        challenge_json = json.loads(m.group(1))
        rules = challenge_json.get("rules", {})
        chal = challenge_json.get("challenge", {})
        difficulty = int(chal.get("difficulty", rules.get("difficulty", 2)))
        random_data = chal.get("randomData") or chal.get("random_data") or ""
        chal_id = chal.get("id")
        if not random_data or not chal_id:
            return None
        base_prefix = ""
        m2 = _ANUBIS_PREFIX_RE.search(html)
        if m2:
            try:
                base_prefix = json.loads(m2.group(1)) or ""
            except Exception:
                base_prefix = m2.group(1).strip().strip('"').strip("'")
        log.info("Anubis challenge: difficulty=%s (solving...)", difficulty)
        start = time.time()
        hash_hex, nonce = _solve_anubis_pow(random_data, difficulty)
        elapsed = int((time.time() - start) * 1000) or 1
        parsed = urlparse(original_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        api_path = (f"{base_prefix}/.within.website/x/cmd/anubis/api/pass-challenge"
                    if base_prefix else "/.within.website/x/cmd/anubis/api/pass-challenge")
        api_url = api_path if api_path.startswith("http") else base + api_path
        resp = session.get(api_url, params={
            "id": chal_id, "response": hash_hex, "nonce": str(nonce),
            "redir": original_url, "elapsedTime": str(elapsed),
        }, timeout=timeout, allow_redirects=True)
        if resp.ok:
            r2 = session.get(original_url, timeout=timeout, allow_redirects=True)
            if r2.ok and not _is_anubis_page(r2.text):
                return r2.text
        return None
    except Exception as exc:
        log.warning("Anubis handler failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Generic fetch + public resolver
# ---------------------------------------------------------------------------

def _fetch_page(session: requests.Session, url: str, timeout: int = 15) -> Optional[requests.Response]:
    try:
        hdrs = {}
        if "dl.os.click" in url:
            hdrs["Referer"] = "https://os.click/en"
        return session.get(url, headers=hdrs, timeout=timeout, allow_redirects=True)
    except Exception as exc:
        log.debug("fetch_page failed %s: %s", url, exc)
        return None


def _passes_head_check(url: str, session: requests.Session, timeout: int = 10) -> bool:
    try:
        hdrs = {}
        if "dl.os.click" in url:
            hdrs["Referer"] = "https://os.click/en"
        r = session.head(url, headers=hdrs, timeout=timeout, allow_redirects=True)
        if r.ok and _content_looks_like_iso(r):
            return "text/html" not in (r.headers.get("content-type") or "").lower()
        return False
    except Exception:
        return False


def resolve_iso_url(page_url: str, session: Optional[requests.Session] = None,
                    timeout: int = 15, max_depth: int = 2) -> Optional[str]:
    """Resolve ``page_url`` to a direct ISO URL, generating cookies as needed.

    Returns a direct ISO URL or None (protected host / not found).
    Runs in worker threads only. Never raises.
    """
    if not page_url or not page_url.startswith(("http://", "https://")):
        return None
    if link_expired(page_url):
        log.info("resolve: signed link expired, skipping: %s", page_url[:80])
        return None
    if is_filehost_url(page_url):
        log.info("resolve: file host needs browser verification: %s", page_url[:80])
        return None

    if is_direct_iso_url(page_url):
        sess = session or make_session(_choose_ua(page_url))
        try:
            hdrs = {}
            if "dl.os.click" in page_url:
                hdrs["Referer"] = "https://os.click/en"
            hr = sess.head(page_url, headers=hdrs, timeout=timeout, allow_redirects=True)
            if hr.ok and _content_looks_like_iso(hr):
                generate_cookies_for_url(page_url, sess, timeout=timeout)
                return hr.url
        except Exception:
            pass
        if "sourceforge.net" in page_url and "/files/" in page_url \
                and not page_url.rstrip("/").endswith("/download"):
            cand = page_url.rstrip("/") + "/download"
            try:
                hr2 = sess.head(cand, timeout=timeout, allow_redirects=True)
                if hr2.ok:
                    return hr2.url
            except Exception:
                pass
        else:
            generate_cookies_for_url(page_url, sess, timeout=timeout)
            if is_direct_iso_url(page_url):
                return page_url

    sess = session or make_session(_choose_ua(page_url))
    resp = _fetch_page(sess, page_url, timeout=timeout)
    if resp is None or not resp.ok:
        return None

    html = resp.text or ""
    final_url = resp.url

    if _is_anubis_page(html):
        solved_html = _handle_anubis(sess, final_url, html, timeout=timeout)
        if solved_html:
            html = solved_html
        else:
            return None
    if _is_cf_challenge(html) or _is_turnstile_page(html):
        log.info("resolve: challenge page needs browser: %s", page_url[:80])
        return None
    if _content_looks_like_iso(resp):
        return final_url

    refresh = _extract_meta_refresh(html, final_url)
    if refresh and refresh != final_url:
        sub = resolve_iso_url(refresh, session=sess, timeout=timeout, max_depth=max_depth)
        if sub:
            return sub

    iso_links = extract_iso_links(html, final_url)
    if iso_links:
        filtered: List[str] = []
        for cand in iso_links:
            low = cand.lower()
            if low.endswith(".torrent"):
                continue
            if "sourceforge.net" in low and "/files/" in low and low.endswith("/files/"):
                continue
            filtered.append(cand)
        for cand in filtered[:8]:
            if "sourceforge.net" in cand and "/files/" in cand \
                    and not cand.rstrip("/").endswith("/download"):
                cand_dl = cand.rstrip("/") + "/download"
            else:
                cand_dl = cand
            try:
                hr = sess.head(cand_dl, timeout=timeout, allow_redirects=True)
                if hr.ok and _content_looks_like_iso(hr):
                    return hr.url
                if is_direct_iso_url(cand_dl):
                    return cand_dl
            except Exception:
                if is_direct_iso_url(cand_dl):
                    return cand_dl
        if filtered:
            cand = filtered[0]
            if "sourceforge.net" in cand and not cand.rstrip("/").endswith("/download"):
                cand = cand.rstrip("/") + "/download"
            return cand

    if max_depth > 0:
        download_pages = extract_download_page_links(html, final_url)
        if download_pages:
            for dp_url in download_pages[:5]:
                if dp_url == page_url:
                    continue
                sub = resolve_iso_url(dp_url, session=sess, timeout=timeout,
                                      max_depth=max_depth - 1)
                if sub and is_direct_iso_url(sub):
                    return sub
    return None


def resolve_with_cookies(page_url: str, timeout: int = 15):
    """Create a session, generate cookies, and resolve. Returns (url|None, session)."""
    sess = make_session(_choose_ua(page_url))
    return resolve_iso_url(page_url, session=sess, timeout=timeout), sess


def prepare_session_for_download(url: str, session: Optional[requests.Session] = None,
                                 timeout: int = 10) -> requests.Session:
    """Ensure ``session`` has cookies for ``url``'s domain."""
    sess = session or make_session(_choose_ua(url))
    domain = urlparse(url).netloc
    has_cookie = any(domain in c.domain or c.domain == domain
                     or c.domain.lstrip(".") in domain for c in sess.cookies)
    if not has_cookie:
        generate_cookies_for_url(url, sess, timeout=timeout)
    return sess


# ---------------------------------------------------------------------------
# os.click fresh-link walker (signed URLs re-issued at download time)
# ---------------------------------------------------------------------------
# dl.os.click URLs carry ?md5=...&expires=... signatures that die after a
# few days, so the catalogue must NOT store them. Instead each Windows entry
# stores a short *walk spec* (os name + version/build/edition terms +
# language code + arch). At download time this walker replays the site's own
# Inertia search flow (session cookies + per-request XSRF token) and returns
# a FRESH signed urlSecure plus the real size / SHA1 / download count that
# os.click reports. Single click, no browser, never expires, never crashes
# the GUI (worker threads only — every failure raises OsClickError which the
# queue turns into a failed task with a message).

OSCLICK_BASE = "https://os.click"

_OSCLICK_UA = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
)


class OsClickError(RuntimeError):
    """Raised when the os.click walk cannot produce a fresh download URL."""


def _osc_norm(text: str) -> str:
    return re.sub(r"[\s_.\-]+", "", (text or "").lower())


class OsClickResolver:
    """Replay the os.click search flow and return a fresh signed ISO URL."""

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.sess = requests.Session()
        self.sess.headers.update({
            "User-Agent": _OSCLICK_UA,
            "Accept-Language": "en-US,en;q=0.9",
        })
        self._init()

    def _init(self) -> None:
        try:
            self.sess.get(f"{OSCLICK_BASE}/en", timeout=self.timeout)
        except Exception as exc:
            raise OsClickError(f"os.click unreachable: {exc}")

    def _nav(self, terms: List[str]) -> dict:
        """Fetch one Inertia stage. Retries once with a fresh session."""
        url = OSCLICK_BASE + "/en/" + ":".join(t.replace(" ", "_") for t in terms)
        for attempt in range(2):
            try:
                xsrf = self.sess.cookies.get("XSRF-TOKEN") or ""
                try:
                    from urllib.parse import unquote as _uq
                    xsrf = _uq(xsrf)
                except Exception:
                    pass
                headers = {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-Inertia": "true",
                    "X-XSRF-TOKEN": xsrf,
                    "Accept": "text/html, application/xhtml+xml",
                    "Referer": f"{OSCLICK_BASE}/en",
                    "X-Inertia-Partial-Data": "stages,currentStage,searchResults,searchTerms",
                    "X-Inertia-Partial-Component": "PageHome",
                }
                resp = self.sess.get(url, headers=headers, timeout=self.timeout)
            except Exception as exc:
                raise OsClickError(f"os.click request failed: {exc}")
            if resp.status_code == 200:
                try:
                    return resp.json()["props"]["searchResults"]
                except Exception as exc:
                    raise OsClickError(f"os.click bad response: {exc}")
            if resp.status_code in (403, 409) and attempt == 0:
                self._init()
                continue
            raise OsClickError(f"os.click HTTP {resp.status_code} for {'/'.join(terms)}")
        raise OsClickError("os.click walk failed")

    @staticmethod
    def _item_pairs(items: list) -> list:
        pairs = []
        for it in items or []:
            if isinstance(it, dict):
                pairs.append((it.get("id"), it.get("name")))
            else:
                pairs.append((it, it))
        return pairs

    def _pick(self, pairs: list, want: Optional[str]) -> Optional[str]:
        """Pick the (id or name) term to append for one stage."""
        if not pairs:
            return None
        if want:
            wn = _osc_norm(want)
            for iid, name in pairs:
                if iid is not None and _osc_norm(str(iid)) == wn:
                    return str(iid)
            for iid, name in pairs:
                if name and wn in _osc_norm(name):
                    return name
        iid0, name0 = pairs[0]
        return name0 if name0 is not None else (str(iid0) if iid0 is not None else None)

    def walk(self, os_name: str, middle: List[str],
             lang_code: str, arch: Optional[str] = None) -> dict:
        """Walk stages and return fresh link info.

        Returns dict(url=..., size_mb=..., sha1=..., count=..., arch=...).
        Raises OsClickError on any failure (worker converts to task error).
        """
        terms = ["Windows", os_name] + [str(m) for m in (middle or [])]
        pending = list(middle or [])
        for _step in range(8):
            results = self._nav(terms)
            stage = list(results.keys())[-1]
            payload = results[stage] or {}
            if stage == "OsLink":
                sel = payload.get("selected") or {}
                url = sel.get("urlSecure") or sel.get("url")
                if not url:
                    raise OsClickError("os.click returned no download URL")
                try:
                    size_mb = int(sel.get("size") or 0)
                except (TypeError, ValueError):
                    size_mb = 0
                return {
                    "url": url,
                    "size_mb": size_mb,
                    "sha1": sel.get("hash"),
                    "count": sel.get("downloadCount", 0),
                    "arch": sel.get("architecture", ""),
                }
            pairs = self._item_pairs(payload.get("items", []))
            if not pairs:
                raise OsClickError(f"os.click stage {stage} has no options")
            if stage == "OsLanguage":
                nxt = self._pick(pairs, lang_code)
            elif stage == "OsArchitecture":
                nxt = self._pick(pairs, arch or "x64") or pairs[0][1]
            elif pending:
                nxt = self._pick(pairs, pending.pop(0))
            else:
                _iid, _nm = pairs[0]
                nxt = _nm if _nm is not None else str(_iid)
            if nxt is None:
                raise OsClickError(f"os.click cannot match stage {stage}")
            terms.append(nxt)
        raise OsClickError("os.click walk did not reach a download link")

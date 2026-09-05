#!/usr/bin/env python3
"""金孫台灣在地查詢。直打官方公開資料，回長輩聽得懂的白話，不把 JSON 倒出去。"""

from __future__ import annotations

import base64
import csv
import io
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

TZ = timezone(timedelta(hours=8))
UA = "Jinsun family assistant"
HTTP_TIMEOUT = 25

NO_CWA = "天氣資料還沒申請授權，先講災害示警或請家人看氣象署。"
NO_TDX = "公車捷運即時還沒申請授權，現在沒辦法查下一班車。"
NET_FAIL = "政府網站這會兒連不上，等一下再問一次。"

CITIES = [
    "臺北市",
    "新北市",
    "桃園市",
    "臺中市",
    "臺南市",
    "高雄市",
    "基隆市",
    "新竹市",
    "嘉義市",
    "新竹縣",
    "苗栗縣",
    "彰化縣",
    "南投縣",
    "雲林縣",
    "嘉義縣",
    "屏東縣",
    "宜蘭縣",
    "花蓮縣",
    "臺東縣",
    "澎湖縣",
    "金門縣",
    "連江縣",
]

DISTRICT_CITY = {
    "板橋": "新北市",
    "三重": "新北市",
    "中和": "新北市",
    "永和": "新北市",
    "新莊": "新北市",
    "新店": "新北市",
    "土城": "新北市",
    "蘆洲": "新北市",
    "汐止": "新北市",
    "樹林": "新北市",
    "淡水": "新北市",
    "三峽": "新北市",
    "林口": "新北市",
    "五股": "新北市",
    "泰山": "新北市",
    "鶯歌": "新北市",
    "瑞芳": "新北市",
    "八里": "新北市",
    "深坑": "新北市",
    "石碇": "新北市",
    "坪林": "新北市",
    "烏來": "新北市",
    "三芝": "新北市",
    "石門": "新北市",
    "金山": "新北市",
    "萬里": "新北市",
    "平溪": "新北市",
    "雙溪": "新北市",
    "貢寮": "新北市",
    "中正": "臺北市",
    "大同": "臺北市",
    "中山": "臺北市",
    "松山": "臺北市",
    "大安": "臺北市",
    "萬華": "臺北市",
    "信義": "臺北市",
    "士林": "臺北市",
    "北投": "臺北市",
    "內湖": "臺北市",
    "南港": "臺北市",
    "文山": "臺北市",
    "天母": "臺北市",
    "桃園區": "桃園市",
    "中壢": "桃園市",
    "平鎮": "桃園市",
    "八德": "桃園市",
    "楊梅": "桃園市",
    "蘆竹": "桃園市",
    "龜山": "桃園市",
    "大溪": "桃園市",
    "大園": "桃園市",
    "龍潭": "桃園市",
    "西屯": "臺中市",
    "北屯": "臺中市",
    "南屯": "臺中市",
    "豐原": "臺中市",
    "大里": "臺中市",
    "太平": "臺中市",
    "東區": "臺南市",
    "南區": "臺南市",
    "北區": "臺南市",
    "安平": "臺南市",
    "永康": "臺南市",
    "仁德": "臺南市",
    "苓雅": "高雄市",
    "左營": "高雄市",
    "鳳山": "高雄市",
    "三民": "高雄市",
    "前鎮": "高雄市",
    "楠梓": "高雄市",
    "小港": "高雄市",
}

WEEKDAY_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
WEEKDAY_ZH = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

_mem_cache: dict[str, tuple[float, bytes]] = {}
_tdx_token_mem: dict[str, Any] = {"tok": "", "exp": 0.0}

TDX_CITY_EN = {
    "臺北市": "Taipei",
    "新北市": "NewTaipei",
    "桃園市": "Taoyuan",
    "臺中市": "Taichung",
    "臺南市": "Tainan",
    "高雄市": "Kaohsiung",
    "基隆市": "Keelung",
    "新竹市": "Hsinchu",
    "嘉義市": "Chiayi",
    "新竹縣": "HsinchuCounty",
    "苗栗縣": "MiaoliCounty",
    "彰化縣": "ChanghuaCounty",
    "南投縣": "NantouCounty",
    "雲林縣": "YunlinCounty",
    "嘉義縣": "ChiayiCounty",
    "屏東縣": "PingtungCounty",
    "宜蘭縣": "YilanCounty",
    "花蓮縣": "HualienCounty",
    "臺東縣": "TaitungCounty",
    "澎湖縣": "PenghuCounty",
    "金門縣": "KinmenCounty",
    "連江縣": "LienchiangCounty",
}


class FetchError(Exception):
    pass


def now_tw() -> datetime:
    return datetime.now(TZ)


def data_dir() -> Path:
    raw = os.environ.get("JINSUN_DATA") or os.environ.get("HERMES_HOME") or "/opt/data"
    path = Path(raw)
    if path.name != "jinsun":
        path = path / "jinsun"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = data_dir() / "tw_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_clear_memory() -> None:
    _mem_cache.clear()
    _tdx_token_mem["tok"] = ""
    _tdx_token_mem["exp"] = 0.0


def env_key(*names: str) -> str:
    for name in names:
        val = (os.environ.get(name) or "").strip()
        if val and val.lower() not in {"changeme", "your-key", "none", "null"}:
            return val
    return ""


def tw_chars(text: str) -> str:
    return (text or "").replace("台", "臺")


def extract_city(place: str) -> str:
    t = tw_chars(place or "")
    for city in sorted(CITIES, key=len, reverse=True):
        short = city.replace("市", "").replace("縣", "")
        if city in t or (len(short) >= 2 and short in t):
            return city
    for dist, city in sorted(DISTRICT_CITY.items(), key=lambda kv: len(kv[0]), reverse=True):
        if dist in t:
            return city
    return ""


def http_get(url: str, timeout: int = HTTP_TIMEOUT, extra_headers: Optional[dict[str, str]] = None) -> bytes:
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(
        url,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise FetchError(f"http {exc.code}") from exc
    except Exception as exc:
        msg = str(exc)
        if "CERTIFICATE_VERIFY_FAILED" not in msg and "SSL" not in type(exc).__name__:
            raise FetchError(msg[:160]) from exc
        try:
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc2:
            raise FetchError(f"http {exc2.code}") from exc2
        except Exception as exc2:
            raise FetchError(str(exc2)[:160]) from exc2


def decode_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "big5", "cp950"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def cached_bytes(name: str, ttl: int, loader: Callable[[], bytes]) -> bytes:
    now = time.time()
    hit = _mem_cache.get(name)
    if hit and now - hit[0] < ttl:
        return hit[1]
    path = cache_dir() / name
    if path.exists() and now - path.stat().st_mtime < ttl:
        raw = path.read_bytes()
        _mem_cache[name] = (now, raw)
        return raw
    raw = loader()
    path.write_bytes(raw)
    _mem_cache[name] = (now, raw)
    return raw


def _plain(text: str) -> str:
    t = re.sub(r"<[^>]+>", "", text or "")
    t = t.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", t).strip()


def _blob(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("#text") or value.get("text") or value.get("@term") or "")
    if isinstance(value, list):
        return " ".join(_blob(v) for v in value)
    return str(value)


def _geo_frags(place: str) -> list[str]:
    t = tw_chars(place or "").strip()
    if not t:
        return []
    frags: list[str] = []
    city = extract_city(t)
    rest = t
    if city:
        frags.append(city)
        rest = rest.replace(city, "")
        rest = rest.replace(city.replace("市", "").replace("縣", ""), "")
    dist = re.search(r"(.{1,3}區)", rest)
    if dist:
        frags.append(dist.group(1))
        rest = rest.replace(dist.group(1), "")
    for part in re.split(r"[\s,，、]+", rest):
        part = part.strip()
        if len(part) >= 2:
            frags.append(part)
    if t not in frags and len(t) >= 2:
        frags.append(t)
    return list(dict.fromkeys(frags))


def _tokens(place: str) -> list[str]:
    return _geo_frags(place)


def _significant_frags(place: str) -> list[str]:
    city = extract_city(place)
    shorts = {city, city.replace("市", ""), city.replace("縣", ""), tw_chars(place)} if city else {tw_chars(place)}
    frags = _geo_frags(place)
    sig = [f for f in frags if f not in shorts]
    return sig or [f for f in frags if f]


def _matches(haystack: str, place: str) -> bool:
    if not place:
        return True
    h = tw_chars(haystack)
    p = tw_chars(place)
    if p in h:
        return True
    sig = _significant_frags(p)
    if not sig:
        city = extract_city(p)
        return bool(city) and (city in h or city.replace("市", "").replace("縣", "") in h)
    return all(f in h for f in sig)


def _parse_ymd(raw: str) -> Optional[date]:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) < 8:
        return None
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None


def _csv_rows(raw: bytes) -> list[dict[str, str]]:
    text = decode_bytes(raw)
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        cleaned = {}
        for key, val in row.items():
            if not key:
                continue
            cleaned[key.strip().lstrip("﻿")] = (val or "").strip()
        if cleaned:
            rows.append(cleaned)
    return rows


def _col(row: dict[str, str], *names: str) -> str:
    for name in names:
        if name in row and str(row[name]).strip():
            return str(row[name]).strip()
    lower = {k.lower(): k for k in row}
    for name in names:
        key = lower.get(name.lower())
        if key and str(row[key]).strip():
            return str(row[key]).strip()
    return ""


def _ask_place(kind: str) -> str:
    return f"跟金孫說一下哪個區或哪一條路，我幫你找附近的{kind}。"


# ----- 天氣／地震／警特報（中央氣象署） -----


def _cwa_url(dataid: str, extra: str = "") -> str:
    key = urllib.parse.quote(env_key("CWA_API_KEY"))
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{dataid}?Authorization={key}&format=JSON"
    if extra:
        url += "&" + extra
    return url


def _cwa_json(dataid: str, extra: str = "") -> dict[str, Any]:
    raw = cached_bytes(
        f"cwa-{dataid}-{extra}.json",
        20 * 60,
        lambda: http_get(_cwa_url(dataid, extra)),
    )
    return json.loads(decode_bytes(raw))


def weather_text(place: str = "") -> str:
    city = extract_city(place) or "臺北市"
    if not env_key("CWA_API_KEY"):
        extra = ""
        try:
            extra = disaster_text(place or city)
        except Exception:
            extra = ""
        if extra and "連不上" not in extra:
            return NO_CWA + extra
        return NO_CWA
    try:
        loc = urllib.parse.urlencode({"locationName": city})
        data = _cwa_json("F-C0032-001", loc)
        locations = ((data.get("records") or {}).get("location")) or []
        if not locations:
            return f"氣象署這會兒沒有{city}的預報。請家人看氣象署，或問金孫這區有沒有警報。"
        loc0 = locations[0]
        elements = {el.get("elementName"): el.get("time") or [] for el in loc0.get("weatherElement") or []}

        def param_at(name: str, idx: int) -> str:
            times = elements.get(name) or []
            if idx >= len(times):
                return ""
            par = (times[idx] or {}).get("parameter") or {}
            return str(par.get("parameterName") or "")

        wx0, pop0, mn0, mx0 = param_at("Wx", 0), param_at("PoP", 0), param_at("MinT", 0), param_at("MaxT", 0)
        wx1, wx2 = param_at("Wx", 1), param_at("Wx", 2)
        parts = [f"{city}今天{wx0 or '天氣資料不完整'}。"]
        if mn0 and mx0:
            parts.append(f"氣溫大約 {mn0} 到 {mx0} 度。")
        if pop0:
            parts.append(f"降雨機率 {pop0}%。")
            try:
                if int(re.sub(r"\D", "", pop0) or "0") >= 50:
                    parts.append("出門帶傘。")
            except ValueError:
                pass
        if wx1:
            parts.append(f"今晚{wx1}。")
        if wx2:
            parts.append(f"明天{wx2}。")
        warn = _cwa_warning_line(city)
        if warn:
            parts.append(warn)
        return _plain("".join(parts))
    except FetchError:
        return NET_FAIL
    except Exception:
        return "天氣資料這會兒看不懂，請家人看氣象署。"


def _cwa_warning_line(city: str) -> str:
    try:
        data = _cwa_json("W-C0033-001")
    except Exception:
        return ""
    names = []
    for loc in ((data.get("records") or {}).get("location")) or []:
        loc_name = tw_chars(str(loc.get("locationName") or ""))
        if city and city not in loc_name and loc_name not in city and loc_name not in {"全臺", "全省"}:
            if loc_name and loc_name not in tw_chars(city):
                continue
        hazards = ((loc.get("hazardConditions") or {}).get("hazards")) or []
        if isinstance(hazards, dict):
            hazards = [hazards]
        for hz in hazards:
            info = hz.get("info") or hz
            phen = str(info.get("phenomena") or info.get("phenomenaName") or "")
            sig = str(info.get("significance") or "")
            label = (phen + sig).strip()
            if label:
                names.append(label)
    if not names:
        return ""
    uniq = "、".join(list(dict.fromkeys(names))[:3])
    return f"氣象署有{uniq}，盡量少出門。"


def earthquake_text(place: str = "") -> str:
    if not env_key("CWA_API_KEY"):
        return "地震資料還沒申請授權。要看有沒有警報，可以問金孫：我家這區有沒有警報。請家人看氣象署。"
    try:
        data = _cwa_json("E-A0015-001")
        quakes = ((data.get("records") or {}).get("Earthquake")) or []
        if not quakes:
            return "最近沒有顯著有感地震報告。"
        q = quakes[0]
        content = str(q.get("ReportContent") or "").strip()
        info = q.get("EarthquakeInfo") or {}
        origin = str(info.get("OriginTime") or "")
        epi = (info.get("Epicenter") or {}).get("Location") or ""
        mag = (info.get("EarthquakeMagnitude") or {}).get("MagnitudeValue") or ""
        if content:
            return _plain(content + "這是氣象署的顯著有感地震，不是謠言。")
        bits = ["氣象署最新有感地震。"]
        if mag:
            bits.append(f"規模大約 {mag}。")
        if epi:
            bits.append(str(epi) + "。")
        if origin:
            bits.append(f"時間 {origin}。")
        return _plain("".join(bits) or "最近沒有顯著有感地震報告。")
    except FetchError:
        return NET_FAIL
    except Exception:
        return "地震資料這會兒看不懂，請家人看氣象署。"


# ----- 災害示警（NCDR，免金鑰） -----


def disaster_text(place: str = "") -> str:
    try:
        raw = cached_bytes(
            "ncdr-alerts.json",
            3 * 60,
            lambda: http_get("https://alerts.ncdr.nat.gov.tw/JSONAtomFeeds.ashx"),
        )
        data = json.loads(decode_bytes(raw))
        entries = data.get("entry") or []
        if isinstance(entries, dict):
            entries = [entries]
        city = extract_city(place)
        nationwide = tw_chars(place) in {"", "台灣", "臺灣", "全臺", "全國"}
        hits = []
        now = now_tw()
        for ent in entries:
            title = _blob(ent.get("title"))
            cat = _blob(ent.get("category"))
            summary = _plain(_blob(ent.get("summary")))
            blob = " ".join([title, cat, summary, _blob(ent.get("id"))])
            if _expired(ent.get("expires"), now):
                continue
            if nationwide:
                if not _elder_alert(cat, title, summary):
                    continue
            elif place and city:
                if not (
                    _matches(blob, place)
                    or _matches(blob, city)
                    or city.replace("市", "").replace("縣", "") in tw_chars(blob)
                ):
                    continue
            elif place and not _matches(blob, place):
                continue
            label = cat or title or "示警"
            line = f"{label}：{summary}" if summary else label
            hits.append(_plain(line))
        if not hits:
            if place and not nationwide:
                return "目前沒有針對你家這區的災害警報。"
            return "目前沒有特別急的災害警報。若要查某一區，跟金孫說縣市或路名。"

        def _rank(line: str) -> int:
            for i, word in enumerate(("地震", "颱風", "海嘯", "豪雨", "大雨", "強風", "土石流", "淹水", "空品", "停水")):
                if word in line:
                    return i
            return 99

        hits.sort(key=_rank)
        head = "這是國家災害防救科技中心的示警。"
        return head + "".join(hits[:6])
    except FetchError:
        return NET_FAIL
    except Exception:
        return "示警資料這會兒看不懂。有急事請看電視或問家人。"


_ALERT_KEEP = (
    "強風",
    "豪雨",
    "大雨",
    "超大豪雨",
    "颱風",
    "地震",
    "土石流",
    "淹水",
    "停水",
    "空品",
    "空氣",
    "高溫",
    "低溫",
    "海嘯",
    "陸上強風",
    "海上強風",
    "水庫放流",
)


def _elder_alert(cat: str, title: str, summary: str) -> bool:
    blob = cat + title + summary
    return any(word in blob for word in _ALERT_KEEP)


def _expired(raw: Any, now: datetime) -> bool:
    text = _blob(raw)
    if not text:
        return False
    digits = re.findall(r"\d+", text)
    if len(digits) < 3:
        return False
    try:
        year, month, day = int(digits[0]), int(digits[1]), int(digits[2])
        hour = int(digits[3]) if len(digits) > 3 else 23
        minute = int(digits[4]) if len(digits) > 4 else 59
        if "下午" in text and hour < 12:
            hour += 12
        end = datetime(year, month, day, min(hour, 23), min(minute, 59), tzinfo=TZ)
        return now > end + timedelta(hours=2)
    except Exception:
        return False


# ----- 空氣品質 -----


def air_text(place: str = "") -> str:
    try:
        records = _load_aqi()
    except FetchError:
        if env_key("MOENV_API_KEY"):
            return NET_FAIL
        return "空氣品質還沒申請授權，也連不上開放資料。請家人看環境部監測網，或問金孫這區有沒有警報。"
    except Exception:
        return "空氣品質這會兒看不懂。請家人看環境部監測網。"
    if not records:
        if env_key("MOENV_API_KEY"):
            return "空氣品質這會兒沒資料。"
        return "空氣品質還沒申請授權，先請家人看環境部空氣品質監測網。"
    city = extract_city(place)
    scored = []
    for rec in records:
        site = str(rec.get("sitename") or rec.get("SiteName") or "")
        county = str(rec.get("county") or rec.get("County") or "")
        hay = tw_chars(site + county)
        score = 0
        if place and tw_chars(place) in hay:
            score += 5
        if city and city in hay:
            score += 3
        if place:
            for tok in _tokens(place):
                if tok in hay:
                    score += 2
        if score:
            scored.append((score, rec))
    picked = [r for _, r in sorted(scored, key=lambda x: -x[0])[:3]]
    if not picked:
        if city:
            picked = [r for r in records if city in tw_chars(str(r.get("county") or ""))][:3]
        else:
            return "跟金孫說一下哪個縣市，我幫你看空氣。"
    if not picked:
        return "這區暫時沒對到測站。跟金孫說縣市名稱再問一次。"
    lines = []
    for rec in picked:
        site = rec.get("sitename") or rec.get("SiteName") or "測站"
        aqi = rec.get("aqi") or rec.get("AQI") or ""
        status = rec.get("status") or rec.get("Status") or ""
        pm = rec.get("pm2.5") or rec.get("PM2.5") or rec.get("pm25") or ""
        bit = f"{site}測站空氣{status or '資料'}。"
        if aqi:
            bit += f"指標大約 {aqi}。"
        if pm:
            bit += f"細懸浮微粒 {pm}。"
        if "不健康" in str(status) or "危害" in str(status):
            bit += "有氣喘或心肺不適的人少出門。"
        elif str(status) == "普通":
            bit += "敏感的人少在外面久留。"
        lines.append(bit)
    return _plain("".join(lines))


def _load_aqi() -> list[dict[str, Any]]:
    key = env_key("MOENV_API_KEY")
    if key:
        url = "https://data.moenv.gov.tw/api/v2/aqx_p_432?format=json&limit=1000&api_key=" + urllib.parse.quote(key)
        raw = cached_bytes("aqi-key.json", 30 * 60, lambda: http_get(url))
        return _aqi_records(json.loads(decode_bytes(raw)))

    def from_catalog() -> bytes:
        meta_raw = http_get("https://data.gov.tw/api/v2/rest/dataset/40448")
        meta = json.loads(decode_bytes(meta_raw))
        dists = (meta.get("result") or meta).get("distribution") or []
        url = ""
        for dist in dists:
            fmt = str(dist.get("resourceFormat") or "").upper()
            href = dist.get("resourceDownloadUrl") or ""
            if fmt == "JSON" and href:
                url = href
                break
        if not url:
            for dist in dists:
                href = dist.get("resourceDownloadUrl") or ""
                if href:
                    url = href
                    break
        if not url:
            raise FetchError("no aqi catalog url")
        return http_get(url.replace(" ", "%20"))

    raw = cached_bytes("aqi-catalog.json", 30 * 60, from_catalog)
    text = decode_bytes(raw)
    if text.lstrip().startswith("{") or text.lstrip().startswith("["):
        return _aqi_records(json.loads(text))
    rows = _csv_rows(raw)
    return rows


def _aqi_records(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("records", "data", "result"):
            val = data.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
            if isinstance(val, dict) and isinstance(val.get("records"), list):
                return [x for x in val["records"] if isinstance(x, dict)]
    return []


# ----- 國定假日 -----


def holiday_text(question: str = "", today: Optional[date] = None) -> str:
    day = today or now_tw().date()
    year = day.year
    try:
        cal = _load_calendar(year)
        if day.month >= 11:
            cal = cal + _load_calendar(year + 1)
    except FetchError:
        return NET_FAIL
    except Exception:
        return "放假日曆這會兒看不懂。"
    by_date = {row["d"]: row for row in cal}
    q = question or ""
    target = _date_in_question(q, day)
    if "連假" in q or "下次放假" in q or "下一個假" in q:
        span = _next_long_weekend(cal, day)
        if not span:
            return "最近沒看到 3 天以上的連假。國定假日再問金孫一次。"
        start, end, names, n = span
        name = "、".join(names) if names else "連假"
        return f"下次連假是{name}，{start.month}月{start.day}日放到 {end.month}月{end.day}日，一共 {n} 天。"
    if target:
        row = by_date.get(target)
        if not row:
            return f"{target.month}月{target.day}日這天日曆裡還沒有資料。"
        return _say_day(target, row)
    if "明天" in q:
        return _say_day(day + timedelta(days=1), by_date.get(day + timedelta(days=1)))
    if "今天" in q or not q.strip():
        today_line = _say_day(day, by_date.get(day))
        nxt = _next_named_holiday(cal, day)
        if nxt:
            nd, desc = nxt
            today_line += f"下一個國定假日是{desc}，{nd.month}月{nd.day}日。"
        return today_line
    nxt = _next_named_holiday(cal, day)
    if nxt:
        nd, desc = nxt
        return f"下一個國定假日是{desc}，{nd.month}月{nd.day}日。"
    return "最近的放假日我對不太起來，請家人看行事曆。"


def _say_day(d: date, row: Optional[dict[str, Any]]) -> str:
    label = f"{d.month}月{d.day}日"
    if not row:
        return f"{label}日曆沒資料。"
    desc = str(row.get("desc") or "").strip()
    if row.get("holiday"):
        if desc:
            return f"{label}放假，是{desc}。"
        weekday = "星期" + "一二三四五六日"[d.weekday()]
        return f"{label}是{weekday}，一般放假。"
    if "補" in desc:
        return f"{label}要補班上班。"
    return f"{label}要上班。"


def _date_in_question(q: str, today: date) -> Optional[date]:
    m = re.search(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})", q)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})月(\d{1,2})日", q)
    if m:
        try:
            year = today.year
            cand = date(year, int(m.group(1)), int(m.group(2)))
            if cand < today - timedelta(days=30):
                cand = date(year + 1, cand.month, cand.day)
            return cand
        except ValueError:
            return None
    return None


def _load_calendar(year: int) -> list[dict[str, Any]]:
    urls = [
        f"https://raw.githubusercontent.com/ruyut/TaiwanCalendar/master/data/{year}.json",
        f"https://cdn.jsdelivr.net/gh/ruyut/TaiwanCalendar/data/{year}.json",
    ]

    def loader() -> bytes:
        last = None
        for url in urls:
            try:
                return http_get(url)
            except FetchError as exc:
                last = exc
        raise last or FetchError("calendar")

    try:
        raw = cached_bytes(f"holiday-{year}.json", 7 * 24 * 3600, loader)
        data = json.loads(decode_bytes(raw))
        rows = []
        for item in data:
            d = _parse_ymd(str(item.get("date") or ""))
            if not d:
                continue
            flag = item.get("isHoliday")
            if isinstance(flag, str):
                holiday = flag in {"是", "true", "True", "1"}
            else:
                holiday = bool(flag)
            rows.append({"d": d, "holiday": holiday, "desc": str(item.get("description") or item.get("name") or "")})
        if rows:
            return rows
    except Exception:
        pass
    return _load_ntpc_calendar(year)


def _load_ntpc_calendar(year: int) -> list[dict[str, Any]]:
    raw = cached_bytes(
        "holiday-ntpc.csv",
        7 * 24 * 3600,
        lambda: http_get("https://data.ntpc.gov.tw/api/datasets/308dcd75-6434-45bc-a95f-584da4fed251/csv/file"),
    )
    rows = []
    for item in _csv_rows(raw):
        d = _parse_ymd(_col(item, "date"))
        if not d or d.year != year:
            continue
        flag = _col(item, "isholiday")
        holiday = flag in {"是", "true", "True", "1"}
        rows.append({"d": d, "holiday": holiday, "desc": _col(item, "name", "description")})
    if not rows:
        raise FetchError("no calendar")
    return rows


def _next_long_weekend(cal: list[dict[str, Any]], today: date) -> Optional[tuple[date, date, list[str], int]]:
    days = sorted(cal, key=lambda r: r["d"])
    i = 0
    best = None
    while i < len(days):
        if not days[i]["holiday"]:
            i += 1
            continue
        j = i
        while j + 1 < len(days) and days[j + 1]["holiday"] and days[j + 1]["d"] == days[j]["d"] + timedelta(days=1):
            j += 1
        n = j - i + 1
        if n >= 3:
            names = [str(days[k]["desc"]).strip() for k in range(i, j + 1) if str(days[k]["desc"]).strip()]
            named = []
            for name in names:
                if name not in named and "補" not in name:
                    named.append(name)
            if days[j]["d"] >= today:
                return days[i]["d"], days[j]["d"], named, n
        i = j + 1
    return best


def _next_named_holiday(cal: list[dict[str, Any]], today: date) -> Optional[tuple[date, str]]:
    for row in sorted(cal, key=lambda r: r["d"]):
        if row["d"] <= today:
            continue
        desc = str(row.get("desc") or "").strip()
        if row.get("holiday") and desc:
            return row["d"], desc
    return None


# ----- 診所／藥局 -----


NHI_CLINIC = "https://info.nhi.gov.tw/api/iode0000s01/Dataset?rId=A21030000I-D21004-009"
NHI_PHARM = "https://info.nhi.gov.tw/api/iode0000s01/Dataset?rId=A21030000I-D21005-001"


def clinic_text(place: str = "", keyword: str = "") -> str:
    return _nhi_search(place, keyword, kind="診所", url=NHI_CLINIC, cache="nhi-clinic.csv")


def pharmacy_text(place: str = "", keyword: str = "") -> str:
    return _nhi_search(place, keyword, kind="藥局", url=NHI_PHARM, cache="nhi-pharmacy.csv")


def _nhi_search(place: str, keyword: str, *, kind: str, url: str, cache: str) -> str:
    if not (place or "").strip():
        return _ask_place(kind)
    try:
        raw = cached_bytes(cache, 24 * 3600, lambda: http_get(url, timeout=40))
        rows = _csv_rows(raw)
    except FetchError:
        return NET_FAIL
    except Exception:
        return f"{kind}名冊這會兒看不懂。"
    today = now_tw().date()
    hits = []
    needle = (place + " " + (keyword or "")).strip()
    for row in rows:
        ended = _col(row, "終止合約或歇業日期")
        ended_d = _parse_ymd(ended)
        if ended_d and ended_d <= today:
            continue
        name = _col(row, "醫事機構名稱")
        addr = _col(row, "地址")
        if not _matches(name + addr, needle):
            continue
        phone = _col(row, "電話")
        hours = _col(row, "固定看診時段")
        dept = _col(row, "診療科別")
        line = f"{name}，電話 {phone}，地址 {addr}。"
        if dept and kind == "診所":
            line += f"科別 {dept}。"
        if hours:
            bits = [b for b in hours.split("、") if b]
            if len(bits) > 4:
                hours = "、".join(bits[:4]) + " 等"
            line += f"看診 {hours}。"
        hits.append(line)
        if len(hits) >= 5:
            break
    if not hits:
        return f"這區名冊裡暫時沒找到{kind}。可以換一個路名再問，或請家人帶去常去的那家。"
    tail = "這是健保署公開名冊，只給名稱電話地址。不能幫你掛號，也不能看你的健保資料。"
    return "".join(hits) + tail


# ----- 長照 -----


def long_term_care_text(place: str = "") -> str:
    if not (place or "").strip():
        return "跟金孫說一下哪個區，我幫你找長照據點。真正要申請請打 1966。"
    try:
        raw = cached_bytes(
            "ltc-abc.csv",
            24 * 3600,
            lambda: http_get("https://ltcpap.mohw.gov.tw/publish/abc.csv", timeout=40),
        )
        rows = _csv_rows(raw)
    except FetchError:
        return NET_FAIL
    except Exception:
        return "長照名冊這會兒看不懂。請打 1966。"
    hits = []
    for row in rows:
        name = _col(row, "機構名稱")
        addr = _col(row, "地址全址", "地址")
        city = _col(row, "縣市")
        dist = _col(row, "區")
        if not _matches(name + addr + city + dist, place):
            continue
        phone = _col(row, "機構電話", "電話")
        svc = _col(row, "特約服務項目")
        line = f"{name}，電話 {phone}，地址 {addr}。"
        if svc:
            line += f"服務 {svc}。"
        hits.append(line)
        if len(hits) >= 5:
            break
    tail = "這是衛福部公開名冊，只給名稱地址電話。不是核准給付。要辦長照請打 1966。"
    if not hits:
        return "這區名冊裡暫時沒找到長照據點。請打 1966 問縣市照管中心。"
    return "".join(hits) + tail


# ----- 垃圾車 -----


def garbage_text(place: str = "", today: Optional[date] = None) -> str:
    if not (place or "").strip():
        return "跟金孫說一下哪個區哪一條路，我幫你看今天垃圾車幾點來。"
    day = today or now_tw().date()
    city = extract_city(place)
    delay = "即時位置可能延遲，實際以現場為準。"
    try:
        if city == "新北市" or "新北" in tw_chars(place):
            return _garbage_ntpc(place, day) + delay
        if city == "臺北市" or (not city and any(k in tw_chars(place) for k in ("臺北", "台北", "士林", "大安", "信義", "內湖", "文山", "北投", "松山", "萬華", "大同", "中正", "南港", "天母"))):
            return _garbage_taipei(place, day) + delay
        if city == "高雄市":
            return _garbage_kaohsiung(place, day) + delay
        if city:
            return f"{city}我先能查台北、新北的垃圾車班表。高雄只有即時位置，常常收完就沒資料。請跟金孫說路名，或看環境部清運路線查詢網。" + delay
        return "跟金孫說縣市跟路名，我先幫你查台北或新北。" + delay
    except FetchError:
        return NET_FAIL + delay
    except Exception:
        return "垃圾車班表這會兒看不懂。" + delay


def _garbage_ntpc(place: str, day: date) -> str:
    wd = WEEKDAY_EN[day.weekday()]
    raw = cached_bytes(
        "ntpc-garbage-schedule.csv",
        24 * 3600,
        lambda: http_get(
            "https://data.ntpc.gov.tw/api/datasets/edc3ad26-8ae7-4916-a00b-bc6048d19bf8/csv/file",
            timeout=40,
        ),
    )
    rows = _csv_rows(raw)
    hits = []
    for row in rows:
        hay = " ".join(
            [
                _col(row, "city"),
                _col(row, "village"),
                _col(row, "name"),
                _col(row, "linename"),
            ]
        )
        if not _matches(hay, place):
            continue
        t = _col(row, "time")
        g = _col(row, "garbage" + wd).upper() == "Y"
        r = _col(row, "recycling" + wd).upper() == "Y"
        f = _col(row, "foodscraps" + wd).upper() == "Y"
        loc = _col(row, "name") or _col(row, "village")
        if not g and not r and not f:
            hits.append(f"{loc}今天不收一般垃圾。表定時間 {t}。")
        else:
            kinds = []
            if g:
                kinds.append("一般垃圾")
            if r:
                kinds.append("資源回收")
            if f:
                kinds.append("廚餘")
            hits.append(f"{loc}今天有收{'、'.join(kinds)}，表定大約 {t}。")
        if len(hits) >= 4:
            break
    gps = _garbage_ntpc_gps(place)
    if not hits:
        if gps:
            return "這條路班表沒對到點，但即時資料有車在附近。" + gps
        return "這區班表沒對到清運點。請說里名或門牌，或看新北垃圾車資訊。"
    return "".join(hits) + gps


def _garbage_ntpc_gps(place: str) -> str:
    try:
        raw = cached_bytes(
            "ntpc-garbage-gps.json",
            120,
            lambda: http_get("https://data.ntpc.gov.tw/api/datasets/28ab4122-60e1-4065-98e5-abccb69aaca6/json?page=0&size=500"),
        )
        rows = json.loads(decode_bytes(raw))
    except Exception:
        return ""
    if isinstance(rows, dict):
        rows = rows.get("data") or []
    city = extract_city(place)
    found = []
    for row in rows:
        hay = str(row.get("location") or "") + str(row.get("cityname") or "")
        sig = _significant_frags(place)
        hay_tw = tw_chars(hay)
        if sig:
            if not any(f in hay_tw for f in sig):
                continue
        elif city:
            if city not in hay_tw and tw_chars(place) not in hay_tw:
                continue
        elif place and not _matches(hay, place):
            continue
        loc = row.get("location") or row.get("cityname") or ""
        when = row.get("time") or ""
        found.append(f"有車回報在{loc}，時間 {when}。")
        if len(found) >= 2:
            break
    if not found:
        return ""
    return "即時位置：" + "".join(found)


def _garbage_taipei(place: str, day: date) -> str:
    if day.weekday() == 6:
        return "台北週日通常不收垃圾。明天再問一次班表。"
    raw = cached_bytes(
        "tpe-garbage.csv",
        24 * 3600,
        lambda: http_get(
            "https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid=a6e90031-7ec4-4089-afb5-361a4efe7202",
            timeout=40,
        ),
    )
    rows = _csv_rows(raw)
    hits = []
    for row in rows:
        hay = "".join(_col(row, k) for k in ("行政區", "里別", "地點", "路線"))
        if not _matches(hay, place):
            continue
        arrive = _fmt_hhmm(_col(row, "抵達時間"))
        leave = _fmt_hhmm(_col(row, "離開時間"))
        loc = _col(row, "地點") or _col(row, "里別")
        hits.append(f"{loc}表定大約 {arrive} 到，{leave} 離開。")
        if len(hits) >= 4:
            break
    if not hits:
        return "台北這條路班表沒對到點。請說里名或門牌。台北沒有即時定位，只有表定時間。"
    return "".join(hits) + "台北沒有即時定位，只有表定時間。"


def _fmt_hhmm(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) >= 4:
        return digits[:2] + ":" + digits[2:4]
    if len(digits) == 3:
        return "0" + digits[0] + ":" + digits[1:]
    return raw or "時間不明"


def _garbage_kaohsiung(place: str, day: date) -> str:
    raw = cached_bytes(
        "kcg-garbage.json",
        120,
        lambda: http_get("https://openapi.kcg.gov.tw/Api/Service/Get/aaf4ce4b-4ca8-43de-bfaf-6dc97e89cac0"),
    )
    data = json.loads(decode_bytes(raw))
    rows = data.get("data") or []
    if not rows:
        return "高雄即時位置這會兒沒車資料，可能收完了或資料延遲。高雄沒有接到表定班表，請看環保局或問里辦公室。"
    hits = []
    for row in rows:
        hay = json.dumps(row, ensure_ascii=False)
        if place and not _matches(hay, place):
            continue
        hits.append(_plain(str(row)[:120]))
        if len(hits) >= 3:
            break
    if not hits:
        return "高雄即時位置沒對到你家附近的車。資料可能延遲。"
    return "高雄即時位置：" + "".join(hits)


# ----- 台電計畫停電 -----


def power_outage_text(place: str = "", today: Optional[date] = None) -> str:
    day = today or now_tw().date()
    try:
        raw = cached_bytes(
            "taipower-outage.zip",
            12 * 3600,
            lambda: http_get("https://service.taipower.com.tw/data/opendata/apply/file/d077004/001.zip", timeout=40),
        )
        hits = []
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for name in zf.namelist():
                if not name.endswith(".csv") or name.startswith("schema") or name == "manifest.csv":
                    continue
                rows = _csv_rows(zf.read(name))
                for row in rows:
                    area = _col(row, "停電範圍")
                    when = _col(row, "第一次停電時間")
                    when_d = _parse_ymd(when)
                    if when_d and when_d < day:
                        continue
                    if place and not _matches(area + _col(row, "營業區處"), place):
                        continue
                    if not place:
                        continue
                    work = _col(row, "工作概述")
                    hits.append(f"{area}預計 {when} 停電，原因 {work}。")
                    if len(hits) >= 5:
                        break
                if len(hits) >= 5:
                    break
        tail = "這是台電計畫性工程停電，不是限電，也不是幫你繳電費。不確定請打 1911。"
        if not hits:
            if not place:
                return "跟金孫說一下哪個區哪一條路，我幫你看有沒有計畫停電。也可以打 1911。"
            return "這區目前沒查到計畫性停電。" + tail
        return "".join(hits) + tail
    except FetchError:
        return "台電停電資料連不上。請打 1911。"
    except Exception:
        return "停電資料這會兒看不懂。請打 1911。"


# ----- 認藥（淺層） -----


def medicine_text(name: str = "") -> str:
    q = (name or "").strip()
    if not q:
        return "跟金孫說藥袋上的名字，我只能查公開許可證重點。怎麼吃要以藥袋跟藥師為準。"
    warn = "這不是藥單，也不是醫生。怎麼吃、能不能停，要以藥袋跟藥師為準。"
    try:
        raw = cached_bytes(
            "fda-36.zip",
            7 * 24 * 3600,
            lambda: http_get("https://data.fda.gov.tw/data/opendata/export/36/csv", timeout=50),
        )
        csv_bytes = _first_csv_in_zip(raw)
        rows = _csv_rows(csv_bytes)
    except FetchError:
        return NET_FAIL + warn
    except Exception:
        return "藥品資料這會兒看不懂。" + warn
    hits = []
    for row in rows:
        cname = _col(row, "中文品名", "品名")
        ename = _col(row, "英文品名")
        if q not in cname and q.lower() not in ename.lower() and tw_chars(q) not in tw_chars(cname):
            continue
        if cname in {h.split("。", 1)[0] for h in hits}:
            continue
        indication = _col(row, "適應症")
        ingredient = _col(row, "主成分略述", "主成分")
        form = _col(row, "劑型")
        line = f"{cname}。"
        if form:
            line += f"劑型 {form}。"
        if ingredient and not re.search(r"[A-Za-z]{4,}", ingredient):
            line += f"成分 {ingredient}。"
        if indication:
            line += f"仿單寫的用途：{indication[:80]}。"
        hits.append(line)
        if len(hits) >= 3:
            break
    if not hits:
        return f"公開許可證裡暫時沒對到「{q}」。請拿藥袋問藥師。" + warn
    return "".join(hits) + warn


def _first_csv_in_zip(raw: bytes) -> bytes:
    if raw[:2] != b"PK":
        return raw
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise FetchError("no csv in zip")
        return zf.read(names[0])


# ----- 交通（TDX，沒鑰匙就停） -----


def _tdx_token() -> str:
    now = time.time()
    if _tdx_token_mem.get("tok") and now < float(_tdx_token_mem.get("exp") or 0):
        return str(_tdx_token_mem["tok"])
    cid = env_key("TDX_CLIENT_ID")
    secret = env_key("TDX_CLIENT_SECRET")
    if not cid or not secret:
        raise FetchError("no tdx")
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": cid,
            "client_secret": secret,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": UA,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read()
    except Exception as exc:
        raise FetchError(str(exc)[:160]) from exc
    data = json.loads(decode_bytes(raw))
    tok = str(data.get("access_token") or "")
    if not tok:
        raise FetchError("tdx token empty")
    _tdx_token_mem["tok"] = tok
    _tdx_token_mem["exp"] = now + int(data.get("expires_in") or 3600) - 60
    return tok


def _ascii_url(url: str) -> str:
    return urllib.parse.quote(url, safe=":/?&=$,@+!()'*~%")


def _tdx_get(path: str) -> Any:
    tok = _tdx_token()
    url = _ascii_url("https://tdx.transportdata.tw" + path)
    if "$format=" not in url:
        url += ("&" if "?" in url else "?") + "$format=JSON"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + tok,
            "User-Agent": UA,
            "Accept": "application/json",
        },
    )
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                raw = resp.read()
            return json.loads(decode_bytes(raw))
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code == 429 and attempt == 0:
                time.sleep(1.2)
                continue
            raise FetchError(f"http {exc.code}") from exc
        except Exception as exc:
            last_exc = exc
            raise FetchError(str(exc)[:160]) from exc
    raise FetchError(str(last_exc)[:160] if last_exc else "tdx fail")


def _zh_name(obj: Any) -> str:
    if isinstance(obj, dict):
        return str(
            obj.get("Zh_Tw")
            or obj.get("Zh_tw")
            or obj.get("zh_tw")
            or obj.get("Name")
            or ""
        )
    return str(obj or "")


def _bus_route(question: str) -> str:
    blob = tw_chars(question or "")
    m = re.search(r"([紅藍綠橘棕黃小市民幹線F]\s*\d{1,3}[區支副甲乙]?|\d{1,4}[區支副甲乙]?)", blob)
    if not m:
        return ""
    return re.sub(r"\s+", "", m.group(1))


def _tdx_city_en(place: str) -> str:
    city = extract_city(place)
    if city and city in TDX_CITY_EN:
        return TDX_CITY_EN[city]
    return "NewTaipei"


def _fmt_eta_seconds(sec: Any) -> str:
    try:
        n = int(sec)
    except (TypeError, ValueError):
        return ""
    if n < 0:
        return ""
    if n <= 30:
        return "即將進站"
    if n < 60:
        return "不到1分鐘"
    return f"大約 {n // 60} 分鐘"


def _bus_status(row: dict[str, Any]) -> str:
    eta = _fmt_eta_seconds(row.get("EstimateTime"))
    if eta:
        return eta
    try:
        st = int(row.get("StopStatus"))
    except (TypeError, ValueError):
        st = -1
    return {
        0: "進站中",
        1: "尚未發車",
        2: "本站不停",
        3: "末班已過",
        4: "今天沒開",
    }.get(st, "")


def transit_text(question: str = "") -> str:
    if not env_key("TDX_CLIENT_ID") or not env_key("TDX_CLIENT_SECRET"):
        return NO_TDX
    q = (question or "").strip()
    if not q:
        return "跟金孫說縣市跟路線，例如板橋藍15、台北307、淡水捷運、台鐵板橋。"
    try:
        if any(k in q for k in ("捷運", "淡水線", "板南", "文湖", "環狀")):
            return _transit_metro(q)
        if any(k in q for k in ("台鐵", "臺鐵", "火車", "列車")):
            return _transit_tra(q)
        route = _bus_route(q)
        if route:
            return _transit_bus(q, route)
        return "跟金孫說路線，例如板橋藍15、台北307。捷運就說站名，台鐵就說站名。"
    except FetchError:
        return NET_FAIL
    except Exception:
        return "交通即時這會兒看不懂。可以晚一點再問，或看公車捷運 App。"


def _transit_bus(question: str, route: str) -> str:
    city_en = _tdx_city_en(question)
    city_zh = extract_city(question) or ("臺北市" if city_en == "Taipei" else "新北市")
    quoted = urllib.parse.quote(route, safe="")
    data = _tdx_get(
        f"/api/basic/v2/Bus/EstimatedTimeOfArrival/City/{city_en}/{quoted}?$top=40"
    )
    rows = data if isinstance(data, list) else []
    hits = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        eta = _bus_status(row)
        if not eta:
            continue
        stop = _zh_name(row.get("StopName"))
        if not stop:
            continue
        plate = str(row.get("PlateNumb") or "").strip()
        line = f"{route} {stop} {eta}。"
        if plate and plate not in {"-1", "0"}:
            line = f"{route} {stop} {eta}，車牌 {plate}。"
        hits.append(line)
        if len(hits) >= 5:
            break
    if not hits:
        other = "臺北市" if city_zh == "新北市" else "新北市"
        return f"{city_zh}現在查不到 {route} 即將到站。可以再說一次縣市，或改問{other}。"
    return "".join(hits) + "這是交通部即時資料，可能差一兩分鐘，請以站牌為準。"


def _transit_metro(question: str) -> str:
    station = re.sub(r"(捷運|淡水線|板南線|文湖線|環狀線|下一班|還來|來不來|幾分)", "", question)
    station = tw_chars(station).strip(" ，。？")
    if len(station) < 2:
        return "跟金孫說捷運站名，例如淡水、北投、台北車站。"
    params = urllib.parse.urlencode(
        {
            "$filter": f"contains(StationName/Zh_Tw,'{station}')",
            "$top": "12",
        }
    )
    data = _tdx_get(f"/api/basic/v2/Rail/Metro/StationLiveBoard/TRTC?{params}")
    rows = data if isinstance(data, list) else []
    hits = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _zh_name(row.get("StationName"))
        dest = _zh_name(row.get("DestinationName") or row.get("TripHeadSign"))
        eta = str(row.get("EstimateTime") or row.get("CountDown") or "").strip()
        if not name:
            continue
        line = f"捷運{name}"
        if dest:
            line += f"往{dest}"
        if eta:
            line += f" {eta}"
        line += "。"
        hits.append(line)
        if len(hits) >= 5:
            break
    if not hits:
        return f"台北捷運現在查不到「{station}」進站資訊。請再說一次站名。"
    return "".join(hits) + "這是交通部即時資料，請以月台廣播為準。"


def _transit_tra(question: str) -> str:
    station = re.sub(r"(台鐵|臺鐵|火車|列車|下一班|還來|來不來|幾分)", "", question)
    station = tw_chars(station).strip(" ，。？")
    if len(station) < 2:
        return "跟金孫說台鐵站名，例如板橋、台北、松山。"
    params = urllib.parse.urlencode(
        {
            "$filter": f"contains(StationName/Zh_Tw,'{station}')",
            "$top": "10",
        }
    )
    data = _tdx_get(f"/api/basic/v3/Rail/TRA/StationLiveBoard/Train?{params}")
    rows = data.get("StationLiveBoards") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        rows = []
    hits = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _zh_name(row.get("StationName"))
        dest = _zh_name(row.get("EndingStationName") or row.get("TrainNo"))
        train = str(row.get("TrainNo") or "")
        delay = row.get("DelayTime")
        sched = str(row.get("ScheduleDepartureTime") or row.get("ScheduleArrivalTime") or "")
        line = f"台鐵{name}"
        if train:
            line += f" {train}次"
        if dest:
            line += f"往{dest}"
        if sched:
            line += f" 表定 {sched[:5]}"
        try:
            dmin = int(delay)
            if dmin > 0:
                line += f" 誤點 {dmin} 分鐘"
            else:
                line += " 準點"
        except (TypeError, ValueError):
            pass
        line += "。"
        hits.append(line)
        if len(hits) >= 5:
            break
    if not hits:
        return f"台鐵現在查不到「{station}」進站資訊。請再說一次站名。"
    return "".join(hits) + "這是交通部即時資料，請以月台廣播為準。"


# ----- 花博／中山區每週在地（比賽場示範） -----

ZHONGSHAN_ACTIVITY_PAGE = "https://zsdo.gov.taipei/cp.aspx?n=79D2EC01F9AA6B53"
FLOWER_EXPO_NEAR_LI = ("圓山", "集英", "大佳", "成功")
LOCAL_KEEP = ("一日遊", "二日遊", "旅遊", "中秋", "重陽", "敬老", "健行", "健走", "樂齡", "市集", "音樂會")
LOCAL_DROP = ("普渡", "中元")
ROW_HEAD_RE = re.compile(
    r"(?m)^(\d+)\s+(\S+)\s+(\d+月\d+日|\d+/\d+(?:~\d+/\d+)?)\s+"
)


def _pydeps_dir() -> Path:
    return data_dir() / "pydeps"


def _ensure_pypdf() -> bool:
    try:
        import pypdf  # noqa: F401

        return True
    except Exception:
        pass
    target = _pydeps_dir()
    if str(target) not in sys.path:
        sys.path.insert(0, str(target))
    try:
        import pypdf  # noqa: F401

        return True
    except Exception:
        return False


def _pdf_to_text(raw: bytes) -> str:
    if not raw.startswith(b"%PDF"):
        raise FetchError("not pdf")
    if not _ensure_pypdf():
        raise FetchError("no pypdf")
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(raw))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _decode_taipei_download_name(href: str) -> str:
    href = (href or "").replace("&amp;", "&")
    parsed = urllib.parse.urlparse(href)
    query = urllib.parse.parse_qs(parsed.query)
    raw = (query.get("n") or [""])[0]
    if not raw:
        return urllib.parse.unquote(href)
    unquoted = urllib.parse.unquote(raw)
    try:
        pad = unquoted + "=" * ((4 - len(unquoted) % 4) % 4)
        return base64.b64decode(pad).decode("utf-8", "ignore")
    except Exception:
        return unquoted


def _activity_pdf_url(html: str) -> str:
    hrefs = re.findall(r'href="([^"]+)"', html or "")
    scored = []
    for href in hrefs:
        if "Download.ashx" not in href:
            continue
        name = _decode_taipei_download_name(href)
        blob = name + urllib.parse.unquote(href)
        score = 0
        if "各里活動" in blob or "活動日程" in blob:
            score += 5
        if "9月" in blob or "09月" in blob:
            score += 2
        if href.lower().endswith(".pdf") or "pdf" in blob.lower() or "icon=..pdf" in href:
            score += 1
        if score:
            scored.append((score, href.replace("&amp;", "&")))
    if not scored:
        return ""
    scored.sort(key=lambda x: -x[0])
    href = scored[0][1]
    if href.startswith("http"):
        return href
    return urllib.parse.urljoin(ZHONGSHAN_ACTIVITY_PAGE, href)


def _roc_year_to_ad(text: str, fallback: int) -> int:
    m = re.search(r"(11[4-9]|12\d)年", text or "")
    if m:
        return int(m.group(1)) + 1911
    return fallback


def _parse_li_dates(token: str, year: int) -> list[date]:
    token = (token or "").replace(" ", "")
    m = re.fullmatch(r"(\d+)月(\d+)日", token)
    if m:
        try:
            return [date(year, int(m.group(1)), int(m.group(2)))]
        except ValueError:
            return []
    m = re.fullmatch(r"(\d+)/(\d+)~(\d+)/(\d+)", token)
    if m:
        try:
            start = date(year, int(m.group(1)), int(m.group(2)))
            end = date(year, int(m.group(3)), int(m.group(4)))
        except ValueError:
            return []
        days = []
        cur = start
        while cur <= end and len(days) < 14:
            days.append(cur)
            cur += timedelta(days=1)
        return days
    return []


def parse_zhongshan_activities(text: str, year: int) -> list[dict[str, Any]]:
    blob = (text or "").replace("\r", "")
    matches = list(ROW_HEAD_RE.finditer(blob))
    rows: list[dict[str, Any]] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(blob)
        chunk = re.sub(r"\s+", " ", blob[m.start() : end]).strip()
        li = m.group(2)
        dates = _parse_li_dates(m.group(3), year)
        if not dates:
            continue
        name_m = re.search(
            r"(?:[01]?\d:\d{2}(?:~\d{2}:\d{2})?\s+){1,2}(.+?)(?:\s+(?:里民|全體|本里|中吉|江山|邀請))",
            chunk,
        )
        name = (name_m.group(1).strip() if name_m else chunk)[:40]
        prefix = li + "里"
        if name.startswith(prefix):
            name = name[len(prefix) :].lstrip()
        gather = ""
        gm = re.search(r"(天祥路\d+號|圓山里辦公處|玉門街\d+號|北安路\d+號|林安泰古厝)", chunk)
        if gm:
            gather = gm.group(1)
        rows.append(
            {
                "li": li,
                "dates": dates,
                "name": name,
                "gather": gather,
                "chunk": chunk,
            }
        )
    return rows


def _keep_local_row(row: dict[str, Any]) -> bool:
    if row.get("li") not in FLOWER_EXPO_NEAR_LI:
        return False
    blob = str(row.get("name") or "") + str(row.get("chunk") or "")
    if any(word in blob for word in LOCAL_DROP) and not any(word in blob for word in ("敬老", "重陽", "中秋")):
        return False
    return any(word in blob for word in LOCAL_KEEP)


def format_weekly_local(rows: list[dict[str, Any]], today: date, source: str) -> str:
    end = today + timedelta(days=7)
    picked = []
    for row in rows:
        if not _keep_local_row(row):
            continue
        days = [d for d in row["dates"] if today <= d <= end]
        if not days:
            continue
        picked.append((days[0], row))
    picked.sort(key=lambda x: x[0])
    if not picked:
        return ""
    lines = [
        "金孫查過台北市中山區公所的里活動表。這是花博爭艷館附近、查證過才寫的。",
    ]
    for day, row in picked[:4]:
        when = f"{day.month}月{day.day}日"
        if day == today:
            when = "今天"
        elif day == today + timedelta(days=1):
            when = "明天"
        bit = f"{when}{row['li']}里有{row['name']}"
        if row.get("gather"):
            bit += f"，集合{row['gather']}"
        bit += "。"
        lines.append(bit)
    lines.append("名額以里辦為準。想去哪一場跟金孫說，我幫你記下來。")
    lines.append("資料來源：" + source)
    return "".join(lines)


def weekly_local_text(today: Optional[date] = None, schedule_text: str = "") -> str:
    day = today or now_tw().date()
    source = "台北市中山區公所115年9月各里活動日程表"
    try:
        if schedule_text:
            text = schedule_text
        else:
            html = decode_bytes(
                cached_bytes(
                    "zhongshan-activity-page.html",
                    12 * 3600,
                    lambda: http_get(ZHONGSHAN_ACTIVITY_PAGE),
                )
            )
            pdf_url = _activity_pdf_url(html)
            if not pdf_url:
                return "中山區公所活動表這會兒找不到附件。請把里辦公告拍照給金孫。"
            raw = cached_bytes(
                "zhongshan-activity.pdf",
                12 * 3600,
                lambda: http_get(
                    pdf_url,
                    extra_headers={"Referer": ZHONGSHAN_ACTIVITY_PAGE},
                ),
            )
            text = _pdf_to_text(raw)
            if "0903" in urllib.parse.unquote(pdf_url) or "0903" in text:
                source = "台北市中山區公所115年9月各里活動日程表，9月3日版"
        year = _roc_year_to_ad(text, day.year)
        rows = parse_zhongshan_activities(text, year)
        msg = format_weekly_local(rows, day, source)
        if msg:
            return msg
        return ""
    except FetchError:
        return ""
    except Exception:
        return ""


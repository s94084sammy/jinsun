#!/usr/bin/env python3
"""金孫台灣在地查詢：假日、名冊、沒鑰匙白話、硬閘門。含活連線。"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "overlay" / "mcp"))

import jinsun_tw  # noqa: E402
from jinsun_mcp import looks_like_scam  # noqa: E402


HOLIDAY_FIXTURE = [
    {"date": "20260101", "week": "四", "isHoliday": True, "description": "開國紀念日"},
    {"date": "20260102", "week": "五", "isHoliday": False, "description": ""},
    {"date": "20260213", "week": "五", "isHoliday": False, "description": ""},
    {"date": "20260214", "week": "六", "isHoliday": True, "description": ""},
    {"date": "20260215", "week": "日", "isHoliday": True, "description": ""},
    {"date": "20260216", "week": "一", "isHoliday": True, "description": "除夕"},
    {"date": "20260217", "week": "二", "isHoliday": True, "description": "春節"},
    {"date": "20260218", "week": "三", "isHoliday": True, "description": "春節"},
    {"date": "20260219", "week": "四", "isHoliday": True, "description": "春節"},
    {"date": "20260220", "week": "五", "isHoliday": True, "description": "春節"},
    {"date": "20260221", "week": "六", "isHoliday": True, "description": ""},
    {"date": "20260905", "week": "六", "isHoliday": True, "description": ""},
    {"date": "20260906", "week": "日", "isHoliday": True, "description": ""},
    {"date": "20260907", "week": "一", "isHoliday": False, "description": "補行上班日"},
]

CLINIC_CSV = """醫事機構代碼,醫事機構名稱,醫事機構種類,電話,地址,分區業務組,特約類別,服務項目,診療科別,終止合約或歇業日期,固定看診時段,備註,縣市別代碼,合約起日
123,板橋林診所,診所,02-12345678,新北市板橋區文化路一段1號,臺北業務組,4,門診診療,家醫科,,星期一上午看診、星期二上午看診,,01,20200101
124,已歇業診所,診所,02-00001111,新北市板橋區中山路1號,臺北業務組,4,門診診療,家醫科,20200101,星期一上午看診,,01,20100101
125,大安內科診所,診所,02-87654321,臺北市大安區復興南路一段2號,臺北業務組,4,門診診療,內科,,星期三下午看診,,01,20200101
"""

PHARMACY_CSV = """醫事機構代碼,醫事機構名稱,醫事機構種類,電話,地址,分區業務組,特約類別,服務項目,診療科別,終止合約或歇業日期,固定看診時段,備註,縣市別代碼,合約起日
223,板橋安心藥局,藥局,02-22223333,新北市板橋區文化路二段10號,臺北業務組,5,藥品調劑,,,星期一上午看診、星期一下午看診,,01,20200101
"""

LTC_CSV = """機構名稱,機構代碼,機構種類,縣市,區,地址全址,經度,緯度,O_ABC,特約服務項目,特約縣市,特約區域,機構電話,電子郵件,開放床數
板橋日照中心,X1,2,65000,65000010,新北市板橋區文化路2號,121.46,25.01,B,日間照顧服務,65000,,02-33334444,,20
"""

NCDR_FIXTURE = {
    "title": "NCDR_CAP",
    "updated": "2026-09-05T02:18:00+08:00",
    "entry": [
        {
            "title": "強風",
            "category": {"@term": "強風"},
            "summary": {"#text": "低壓帶影響，蘭嶼、澎湖縣、連江縣局部地區有強風。"},
            "effective": "2026/9/4 上午 10:26:00",
            "expires": "2026/9/5 下午 11:00:00",
            "status": "Actual",
        },
        {
            "title": "停水",
            "category": {"@term": "停水"},
            "summary": {"#text": "新北市板橋區部分里別停水。"},
            "effective": "2026/9/5 上午 08:00:00",
            "expires": "2026/9/5 下午 06:00:00",
            "status": "Actual",
        },
    ],
}

CWA_WEATHER = {
    "success": "true",
    "records": {
        "location": [
            {
                "locationName": "臺北市",
                "weatherElement": [
                    {
                        "elementName": "Wx",
                        "time": [
                            {
                                "startTime": "2026-09-05 06:00:00",
                                "endTime": "2026-09-05 18:00:00",
                                "parameter": {"parameterName": "陰短暫雨"},
                            },
                            {
                                "startTime": "2026-09-05 18:00:00",
                                "endTime": "2026-09-06 06:00:00",
                                "parameter": {"parameterName": "多雲"},
                            },
                            {
                                "startTime": "2026-09-06 06:00:00",
                                "endTime": "2026-09-06 18:00:00",
                                "parameter": {"parameterName": "晴時多雲"},
                            },
                        ],
                    },
                    {
                        "elementName": "PoP",
                        "time": [
                            {"parameter": {"parameterName": "60"}},
                            {"parameter": {"parameterName": "20"}},
                            {"parameter": {"parameterName": "10"}},
                        ],
                    },
                    {
                        "elementName": "MinT",
                        "time": [
                            {"parameter": {"parameterName": "24"}},
                            {"parameter": {"parameterName": "23"}},
                            {"parameter": {"parameterName": "25"}},
                        ],
                    },
                    {
                        "elementName": "MaxT",
                        "time": [
                            {"parameter": {"parameterName": "29"}},
                            {"parameter": {"parameterName": "26"}},
                            {"parameter": {"parameterName": "31"}},
                        ],
                    },
                ],
            }
        ]
    },
}

CWA_WARN = {
    "success": "true",
    "records": {
        "location": [
            {
                "locationName": "臺北市",
                "hazardConditions": {
                    "hazards": [
                        {"info": {"phenomena": "大雨", "significance": "特報"}},
                    ]
                },
            }
        ]
    },
}

CWA_EQ = {
    "success": "true",
    "records": {
        "Earthquake": [
            {
                "ReportContent": "09月04日花蓮縣政府東南方發生規模5.2有感地震，最大震度4級。",
                "EarthquakeInfo": {
                    "OriginTime": "2026-09-04 21:10:00",
                    "Epicenter": {"Location": "花蓮縣政府東南方  20.1  公里"},
                    "EarthquakeMagnitude": {"MagnitudeValue": "5.2"},
                },
            }
        ]
    },
}

AQI_JSON = {
    "records": [
        {
            "sitename": "松山",
            "county": "臺北市",
            "aqi": "72",
            "status": "普通",
            "pm2.5": "18",
            "publishtime": "2026-09-05 02:00",
        },
        {
            "sitename": "板橋",
            "county": "新北市",
            "aqi": "110",
            "status": "對敏感族群不健康",
            "pm2.5": "36",
            "publishtime": "2026-09-05 02:00",
        },
    ]
}

NTPC_SCHEDULE = [
    {
        "city": "萬里區",
        "name": "獅頭路15-1號(海巡)",
        "village": "萬里里",
        "time": "12:40",
        "garbagemonday": "Y",
        "garbagetuesday": "Y",
        "garbagewednesday": "",
        "garbagethursday": "Y",
        "garbagefriday": "Y",
        "garbagesaturday": "Y",
        "garbagesunday": "",
        "recyclingmonday": "Y",
        "recyclingtuesday": "",
        "recyclingwednesday": "",
        "recyclingthursday": "Y",
        "recyclingfriday": "",
        "recyclingsaturday": "",
        "recyclingsunday": "",
        "foodscrapsmonday": "Y",
        "foodscrapstuesday": "Y",
        "foodscrapswednesday": "",
        "foodscrapsthursday": "Y",
        "foodscrapsfriday": "Y",
        "foodscrapssaturday": "Y",
        "foodscrapssunday": "",
    }
]

NTPC_GPS = [
    {
        "lineid": "251011",
        "car": "KEG-2913",
        "time": "2026/09/05 08:10:00",
        "location": "新北市淡水區中正路二段31號",
        "cityname": "淡水區",
    }
]

TPE_GARBAGE_CSV = """行政區,里別,分隊,局編,車號,路線,車次,抵達時間,離開時間,地點,經度,緯度
士林區,天母里,天母分隊,103-074,821-BT,天母-1,第1車,1630,1640,臺北市士林區天母西路48號,121.525,25.11836
"""


def _json_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


class TwUnitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["JINSUN_DATA"] = self.tmp.name
        os.environ.pop("CWA_API_KEY", None)
        os.environ.pop("MOENV_API_KEY", None)
        os.environ.pop("TDX_CLIENT_ID", None)
        os.environ.pop("TDX_CLIENT_SECRET", None)
        jinsun_tw._cache_clear_memory()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_weather_without_key_is_vernacular(self) -> None:
        with patch.object(jinsun_tw, "http_get", side_effect=self._fake_http):
            msg = jinsun_tw.weather_text("台北")
        self.assertIn("還沒申請授權", msg)
        self.assertIn("氣象署", msg)
        self.assertNotIn("{", msg)
        self.assertNotIn("Authorization", msg)

    def test_weather_with_key_reads_forecast(self) -> None:
        os.environ["CWA_API_KEY"] = "test-key"
        with patch.object(jinsun_tw, "http_get", side_effect=self._fake_http):
            msg = jinsun_tw.weather_text("台北")
        self.assertIn("短暫雨", msg)
        self.assertIn("24", msg)
        self.assertIn("29", msg)
        self.assertIn("大雨", msg)
        self.assertNotIn('"records"', msg)

    def test_earthquake_without_key(self) -> None:
        msg = jinsun_tw.earthquake_text()
        self.assertIn("還沒申請授權", msg)
        self.assertIn("氣象署", msg)

    def test_earthquake_with_key(self) -> None:
        os.environ["CWA_API_KEY"] = "test-key"
        with patch.object(jinsun_tw, "http_get", side_effect=self._fake_http):
            msg = jinsun_tw.earthquake_text()
        self.assertIn("花蓮", msg)
        self.assertIn("5.2", msg)

    def test_disaster_filters_place(self) -> None:
        frozen = datetime(2026, 9, 5, 10, 0, tzinfo=timezone(timedelta(hours=8)))
        with patch.object(jinsun_tw, "http_get", side_effect=self._fake_http), patch.object(
            jinsun_tw, "now_tw", return_value=frozen
        ):
            penghu = jinsun_tw.disaster_text("澎湖")
            banqiao = jinsun_tw.disaster_text("板橋")
            tainan = jinsun_tw.disaster_text("臺南市")
        self.assertIn("強風", penghu)
        self.assertNotIn("{", penghu)
        self.assertIn("停水", banqiao)
        self.assertIn("沒有針對", tainan)

    def test_air_without_key_uses_catalog_or_explains(self) -> None:
        with patch.object(jinsun_tw, "http_get", side_effect=self._fake_http):
            msg = jinsun_tw.air_text("松山")
        self.assertIn("普通", msg)
        self.assertIn("72", msg)
        self.assertNotIn("api_key", msg)

    def test_air_missing_catalog_explains_limit(self) -> None:
        def boom(url, timeout=20):
            raise jinsun_tw.FetchError("down")

        with patch.object(jinsun_tw, "http_get", side_effect=boom):
            msg = jinsun_tw.air_text("台北")
        self.assertTrue("還沒申請授權" in msg or "連不上" in msg)
        self.assertNotIn("{", msg)

    def test_holiday_tomorrow_and_long_weekend(self) -> None:
        with patch.object(jinsun_tw, "http_get", side_effect=self._fake_http):
            tomorrow = jinsun_tw.holiday_text("明天放假嗎", today=date(2026, 9, 5))
            work = jinsun_tw.holiday_text("明天放假嗎", today=date(2026, 1, 1))
            longw = jinsun_tw.holiday_text("下次連假", today=date(2026, 1, 15))
            makeup = jinsun_tw.holiday_text("9月7日放假嗎", today=date(2026, 9, 5))
        self.assertIn("放假", tomorrow)
        self.assertIn("上班", work)
        self.assertIn("春節", longw)
        self.assertIn("2月", longw)
        self.assertIn("補", makeup)

    def test_clinic_skips_closed_and_speaks_plain(self) -> None:
        with patch.object(jinsun_tw, "http_get", side_effect=self._fake_http):
            msg = jinsun_tw.clinic_text("板橋")
        self.assertIn("林診所", msg)
        self.assertIn("02-12345678", msg)
        self.assertNotIn("已歇業診所", msg)
        self.assertNotIn("醫事機構代碼", msg)

    def test_pharmacy_plain(self) -> None:
        with patch.object(jinsun_tw, "http_get", side_effect=self._fake_http):
            msg = jinsun_tw.pharmacy_text("板橋")
        self.assertIn("安心藥局", msg)
        self.assertIn("電話", msg)

    def test_clinic_asks_for_place(self) -> None:
        msg = jinsun_tw.clinic_text("")
        self.assertIn("哪個區", msg)

    def test_long_term_care_mentions_1966(self) -> None:
        with patch.object(jinsun_tw, "http_get", side_effect=self._fake_http):
            msg = jinsun_tw.long_term_care_text("板橋")
        self.assertIn("日照", msg)
        self.assertIn("1966", msg)
        self.assertIn("不是", msg)

    def test_long_term_care_unreachable_still_says_1966(self) -> None:
        def boom(*_a, **_k):
            raise jinsun_tw.FetchError("down")

        with patch.object(jinsun_tw, "http_get", side_effect=boom):
            msg = jinsun_tw.long_term_care_text("板橋")
        self.assertIn("1966", msg)
        self.assertIn("連不上", msg)

    def test_garbage_ntpc_today_monday(self) -> None:
        with patch.object(jinsun_tw, "http_get", side_effect=self._fake_http):
            msg = jinsun_tw.garbage_text("新北市萬里區獅頭路", today=date(2026, 9, 7))
        self.assertIn("12:40", msg)
        self.assertIn("一般垃圾", msg)
        self.assertIn("延遲", msg)

    def test_garbage_taipei_schedule_only(self) -> None:
        with patch.object(jinsun_tw, "http_get", side_effect=self._fake_http):
            msg = jinsun_tw.garbage_text("台北市士林區天母西路", today=date(2026, 9, 5))
        self.assertIn("16:30", msg)
        self.assertIn("沒有即時", msg)

    def test_power_outage_plain(self) -> None:
        with patch.object(jinsun_tw, "http_get", side_effect=self._fake_http):
            msg = jinsun_tw.power_outage_text("基隆市安樂區", today=date(2026, 9, 5))
        self.assertIn("1911", msg)
        self.assertNotIn("{", msg)

    def test_medicine_warns_not_prescription(self) -> None:
        with patch.object(jinsun_tw, "http_get", side_effect=self._fake_http):
            msg = jinsun_tw.medicine_text("普拿疼")
        self.assertIn("普拿疼", msg)
        self.assertIn("藥師", msg)
        self.assertIn("藥袋", msg)

    def test_transit_without_key(self) -> None:
        msg = jinsun_tw.transit_text("下一班公車")
        self.assertIn("還沒申請授權", msg)

    def test_transit_bus_route_parse(self) -> None:
        self.assertEqual(jinsun_tw._bus_route("板橋藍15還來不來"), "藍15")
        self.assertEqual(jinsun_tw._bus_route("台北307"), "307")

    def test_transit_with_key_uses_eta(self) -> None:
        os.environ["TDX_CLIENT_ID"] = "dummy-id"
        os.environ["TDX_CLIENT_SECRET"] = "dummy-secret"
        jinsun_tw._tdx_token_mem["tok"] = "tok"
        jinsun_tw._tdx_token_mem["exp"] = time.time() + 600
        payload = [
            {
                "StopName": {"Zh_Tw": "府中"},
                "EstimateTime": 180,
                "PlateNumb": "KKA-0001",
            }
        ]
        with patch.object(jinsun_tw, "_tdx_get", return_value=payload):
            msg = jinsun_tw.transit_text("板橋藍15")
        self.assertIn("藍15", msg)
        self.assertIn("府中", msg)
        self.assertIn("分鐘", msg)

    def test_hard_gate_still_blocks_transfer(self) -> None:
        self.assertEqual(looks_like_scam("幫我轉帳到這個帳號"), "轉帳或匯款")
        self.assertIsNone(looks_like_scam("明天會下雨嗎"))
        self.assertIsNone(looks_like_scam("附近哪裡有診所"))
        self.assertIsNone(looks_like_scam("垃圾車幾點來"))

    def test_extract_city(self) -> None:
        self.assertEqual(jinsun_tw.extract_city("板橋文化路"), "新北市")
        self.assertEqual(jinsun_tw.extract_city("台北"), "臺北市")
        self.assertEqual(jinsun_tw.extract_city("高雄苓雅"), "高雄市")

    def test_weekly_local_flower_expo_area(self) -> None:
        fixture = """
3 集英 9月6日 08:00~21:00 08:00 集英里宜蘭一日遊 里民 約160人 宜蘭 天祥路9號 否
10 成功 9月12日 06:30~09:30 06:30 成功里健行活動 里民 約300 成功里辦公處~力行三號公園 北安路676號 否
35 圓山 9月20日 13:30~16:30 13:30 圓山里中秋節活動 里民 約700人 圓山里辦公處 圓山里辦公處 否
5 新庄 9月10日 13:00~15:00 13:30 新庄里景新宮普渡 里民 100 濱江街6之1號 否
"""
        this_week = jinsun_tw.weekly_local_text(
            today=date(2026, 9, 5), schedule_text=fixture
        )
        self.assertIn("集英", this_week)
        self.assertIn("宜蘭一日遊", this_week)
        self.assertIn("天祥路9號", this_week)
        self.assertIn("成功", this_week)
        self.assertIn("健行", this_week)
        self.assertNotIn("普渡", this_week)
        self.assertNotIn("圓山里中秋", this_week)
        later = jinsun_tw.weekly_local_text(
            today=date(2026, 9, 15), schedule_text=fixture
        )
        self.assertIn("圓山", later)
        self.assertIn("中秋", later)
        silent = jinsun_tw.weekly_local_text(
            today=date(2026, 8, 1), schedule_text=fixture
        )
        self.assertEqual(silent, "")

    def _fake_http(self, url: str, timeout: int = 20) -> bytes:
        u = url
        if "TaiwanCalendar" in u or "ruyut" in u:
            return _json_bytes(HOLIDAY_FIXTURE)
        if "308dcd75" in u:
            return _json_bytes([])
        if "JSONAtomFeeds" in u or "JsonAtomFeeds" in u:
            return _json_bytes(NCDR_FIXTURE)
        if "F-C0032-001" in u:
            return _json_bytes(CWA_WEATHER)
        if "W-C0033-001" in u:
            return _json_bytes(CWA_WARN)
        if "E-A0015-001" in u:
            return _json_bytes(CWA_EQ)
        if "dataset/40448" in u:
            return _json_bytes(
                {
                    "result": {
                        "distribution": [
                            {
                                "resourceFormat": "JSON",
                                "resourceDownloadUrl": "https://example.invalid/aqi.json",
                            }
                        ]
                    }
                }
            )
        if u.endswith("aqi.json") or "aqx_p_432" in u:
            return _json_bytes(AQI_JSON)
        if "D21004-009" in u:
            return CLINIC_CSV.encode("utf-8-sig")
        if "D21005-001" in u:
            return PHARMACY_CSV.encode("utf-8-sig")
        if "abc.csv" in u:
            return LTC_CSV.encode("utf-8-sig")
        if "edc3ad26" in u:
            return _json_bytes(NTPC_SCHEDULE) if "json" in u else self._ntpc_csv()
        if "28ab4122" in u:
            return _json_bytes(NTPC_GPS)
        if "a6e90031" in u or "tpeod" in u:
            return TPE_GARBAGE_CSV.encode("utf-8-sig")
        if "d077004" in u:
            return self._taipower_zip()
        if "export/36" in u or "36_2.csv" in u:
            return self._fda_zip()
        raise AssertionError("unexpected url " + u)

    def _ntpc_csv(self) -> bytes:
        return (
            "city,name,village,time,garbagemonday,garbagetuesday,garbagewednesday,"
            "garbagethursday,garbagefriday,garbagesaturday,garbagesunday,"
            "recyclingmonday,recyclingtuesday,recyclingwednesday,recyclingthursday,"
            "recyclingfriday,recyclingsaturday,recyclingsunday,"
            "foodscrapsmonday,foodscrapstuesday,foodscrapswednesday,foodscrapsthursday,"
            "foodscrapsfriday,foodscrapssaturday,foodscrapssunday\n"
            "萬里區,獅頭路15-1號(海巡),萬里里,12:40,Y,Y,,Y,Y,Y,,Y,,,Y,,,,,Y,Y,,Y,Y,Y,\n"
        ).encode("utf-8")

    def _taipower_zip(self) -> bytes:
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(
                "101.csv",
                "營業區處,請求號數,工作概述,第一次停電時間,第二次停電時間,停電範圍,查詢電話(1911)\n"
                "台電基隆區營業處,L28169,改良工程,2026/09/05 09:00~16:00,無,基隆市安樂區安樂路一段,1911\n",
            )
        return buf.getvalue()

    def _fda_zip(self) -> bytes:
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(
                "36_2.csv",
                "中文品名,英文品名,適應症,主成分略述,劑型,藥品類別\n"
                "普拿疼錠,PANADOL,解熱鎮痛,乙醯胺酚,錠劑,成藥\n",
            )
        return buf.getvalue()


class TwLiveTest(unittest.TestCase):
    """真的打公開資料。GitHub 遠端常連不上台灣政府站，公開倉測試略過。"""

    @classmethod
    def setUpClass(cls) -> None:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            raise unittest.SkipTest("公開倉不把政府網站連線當成過關條件")

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["JINSUN_DATA"] = self.tmp.name
        os.environ.pop("CWA_API_KEY", None)
        os.environ.pop("MOENV_API_KEY", None)
        os.environ.pop("TDX_CLIENT_ID", None)
        os.environ.pop("TDX_CLIENT_SECRET", None)
        jinsun_tw._cache_clear_memory()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_live_holiday_has_data(self) -> None:
        msg = jinsun_tw.holiday_text("明天放假嗎")
        self.assertTrue("放假" in msg or "上班" in msg or "補" in msg, msg)
        self.assertNotIn("{", msg)

    def test_live_disaster_feed(self) -> None:
        msg = jinsun_tw.disaster_text("台灣")
        self.assertTrue(len(msg) > 8, msg)
        self.assertNotIn('"entry"', msg)

    def test_live_long_term_care(self) -> None:
        msg = jinsun_tw.long_term_care_text("板橋")
        self.assertIn("1966", msg)
        self.assertTrue(
            "電話" in msg or "沒找到" in msg or "連不上" in msg or "看不懂" in msg,
            msg,
        )

    def test_live_pharmacy(self) -> None:
        msg = jinsun_tw.pharmacy_text("板橋")
        self.assertTrue("藥局" in msg or "電話" in msg or "沒找到" in msg, msg)
        self.assertNotIn("醫事機構代碼", msg)

    def test_live_garbage_new_taipei(self) -> None:
        msg = jinsun_tw.garbage_text("新北市淡水區")
        self.assertTrue("垃圾" in msg or "收" in msg or "表定" in msg or "路名" in msg, msg)
        self.assertIn("延遲", msg)

    def test_live_weather_without_key(self) -> None:
        msg = jinsun_tw.weather_text("台北")
        self.assertIn("還沒申請授權", msg)

    def test_live_air_catalog_or_limit(self) -> None:
        msg = jinsun_tw.air_text("台北")
        self.assertTrue("空氣" in msg or "還沒申請授權" in msg or "連不上" in msg or "測站" in msg, msg)
        self.assertNotIn("api_key=", msg)

    def test_live_power_outage(self) -> None:
        msg = jinsun_tw.power_outage_text("基隆")
        self.assertIn("1911", msg)

    def test_live_medicine(self) -> None:
        msg = jinsun_tw.medicine_text("普拿疼")
        self.assertIn("藥師", msg)
        self.assertTrue("普拿疼" in msg or "沒找到" in msg or "連不上" in msg, msg)


if __name__ == "__main__":
    unittest.main()

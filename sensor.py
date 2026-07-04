import logging
from datetime import timedelta
from urllib.parse import quote
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_API_KEY, CONF_COUNTY, CONF_TOWN, CONF_ALERT_TYPES

_LOGGER = logging.getLogger(__name__)

# 背景更新頻率：每 60 秒
SCAN_INTERVAL = timedelta(seconds=60)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """載入從 UI 建立的 Config Entry"""
    api_key = config_entry.data.get(CONF_API_KEY, "")
    county = config_entry.data.get(CONF_COUNTY, "新北市")
    town = config_entry.data.get(CONF_TOWN, "")
    alert_types = config_entry.data.get(CONF_ALERT_TYPES, [])

    # 轉換與防錯
    api_key_str = str(api_key).strip() if api_key else ""
    town_str = str(town).strip() if town else ""
    alert_types_list = alert_types if isinstance(alert_types, list) else []

    # 【重要修正】將 update_before_add 改為 False
    # 這樣可以避免在首次抓取網路資料失敗時，導致實體完全不顯示。
    async_add_entities(
        [NCDRAirAlertSensor(hass, api_key_str, county, town_str, alert_types_list)], 
        update_before_add=False
    )


class NCDRAirAlertSensor(SensorEntity):
    """NCDR 示警感測器實體"""

    def __init__(self, hass: HomeAssistant, api_key: str, county: str, town: str, alert_types: list):
        self.hass = hass
        self._api_key = api_key
        self._county = county
        self._town = town
        self._alert_types = alert_types
        self._state = "無示警"
        
        suffix = f"_{self._town}" if self._town else ""
        self._attr_name = f"NCDR 示警 ({county}{self._town})"
        self._attr_unique_id = f"ncdr_alert_{county}{suffix}"
        
        # 給予初始屬性，避免未更新前屬性為空
        self._attributes = {
            "filtered_town": self._town if self._town else "全區",
            "filtered_types": self._alert_types if self._alert_types else "全部",
            "summary": "等待首次資料更新..."
        }

    @property
    def name(self) -> str:
        """顯示名稱"""
        return self._attr_name

    @property
    def unique_id(self) -> str:
        """唯一 ID"""
        return self._attr_unique_id

    @property
    def state(self) -> str:
        """主要狀態"""
        return self._state

    @property
    def extra_state_attributes(self) -> dict:
        """屬性清單"""
        return self._attributes

    async def async_update(self):
        """定期背景更新資料邏輯"""
        session = async_get_clientsession(self.hass)
        encoded_county = quote(self._county)
        
        if self._api_key:
            url = f"https://alerts.ncdr.nat.gov.tw/webapi/JSONAtomFeed.ashx?County={encoded_county}&apikey={self._api_key}"
        else:
            url = f"https://alerts.ncdr.nat.gov.tw/webapi/JSONAtomFeed.ashx?County={encoded_county}"

        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    # 【重要修正】加入 content_type=None
                    # 避免 aiohttp 因為 NCDR 回傳的 Content-Type 標頭不標準而報錯中斷
                    data = await response.json(content_type=None)
                    
                    if "entry" in data and len(data["entry"]) > 0:
                        filtered_entries = []
                        for entry in data["entry"]:
                            title = entry.get("title", "")
                            summary_text = entry.get("summary", {}).get("#text", "")

                            # 1. 篩選「示警類別」
                            if self._alert_types:
                                matched_type = any(alert_type in title for alert_type in self._alert_types)
                                if not matched_type:
                                    continue

                            # 2. 篩選「鄉鎮區」
                            if self._town:
                                if self._town not in title and self._town not in summary_text:
                                    continue

                            filtered_entries.append(entry)

                        if filtered_entries:
                            latest_entry = filtered_entries[-1]
                            self._state = latest_entry.get("title", "無示警")
                            self._attributes = {
                                "updated": latest_entry.get("updated"),
                                "summary": latest_entry.get("summary", {}).get("#text", "無詳細說明"),
                                "author": latest_entry.get("author", {}).get("name", "未知"),
                                "filtered_town": self._town if self._town else "全區",
                                "filtered_types": self._alert_types if self._alert_types else "全部"
                            }
                        else:
                            self._state = "無示警"
                            self._attributes = {
                                "filtered_town": self._town if self._town else "全區",
                                "filtered_types": self._alert_types if self._alert_types else "全部"
                            }
                    else:
                        self._state = "無示警"
                        self._attributes = {
                            "filtered_town": self._town if self._town else "全區",
                            "filtered_types": self._alert_types if self._alert_types else "全部"
                        }
                else:
                    _LOGGER.error("無法連線至 NCDR，HTTP 狀態碼: %s", response.status)
        except Exception as e:
            _LOGGER.error("更新 NCDR 示警資料時發生錯誤: %s", e)
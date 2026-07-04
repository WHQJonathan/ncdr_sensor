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

SCAN_INTERVAL = timedelta(seconds=60)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """載入從 UI 建立的 Config Entry"""
    api_key = config_entry.data.get(CONF_API_KEY)
    county = config_entry.data.get(CONF_COUNTY)
    town = config_entry.data.get(CONF_TOWN, "")
    alert_types = config_entry.data.get(CONF_ALERT_TYPES, [])

    # 建立實體並加入 HA
    async_add_entities([NCDRAirAlertSensor(hass, api_key, county, town, alert_types)], update_before_add=True)


class NCDRAirAlertSensor(SensorEntity):
    """NCDR 示警感測器實體"""

    def __init__(self, hass: HomeAssistant, api_key: str, county: str, town: str, alert_types: list):
        self.hass = hass
        self._api_key = api_key
        self._county = county
        self._town = town.strip() if town else ""
        self._alert_types = alert_types if alert_types else []
        self._state = "無示警"
        
        # 建立感測器的唯一 ID 與顯示名稱
        suffix = f"_{self._town}" if self._town else ""
        self._attr_name = f"NCDR 示警 ({county}{self._town})"
        self._attr_unique_id = f"ncdr_alert_{county}{suffix}"
        self._attributes = {}

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    async def async_update(self):
        """定期更新並進行雙重篩選"""
        session = async_get_clientsession(self.hass)
        encoded_county = quote(self._county)
        url = f"https://alerts.ncdr.nat.gov.tw/webapi/JSONAtomFeed.ashx?County={encoded_county}&apikey={self._api_key}"

        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if "entry" in data and len(data["entry"]) > 0:
                        filtered_entries = []
                        for entry in data["entry"]:
                            title = entry.get("title", "")
                            summary_text = entry.get("summary", {}).get("#text", "")

                            # 1. 篩選「示警類別」
                            if self._alert_types:
                                # 檢查 title 是否包含使用者勾選的任一種類別關鍵字
                                matched_type = any(alert_type in title for alert_type in self._alert_types)
                                if not matched_type:
                                    continue

                            # 2. 篩選「鄉鎮區（地區）」
                            if self._town:
                                # 檢查標題或詳細描述中是否提到該鄉鎮區名稱
                                if self._town not in title and self._town not in summary_text:
                                    continue

                            filtered_entries.append(entry)

                        # 如果有符合過濾條件的警報
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
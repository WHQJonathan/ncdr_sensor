import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from .const import DOMAIN, CONF_API_KEY, CONF_COUNTY, CONF_TOWN, CONF_ALERT_TYPES

TAIWAN_COUNTIES = [
    "基隆市", "臺北市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣",
    "臺中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣", "臺南市",
    "高雄市", "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣", "澎湖縣", "金門縣", "連江縣"
]

ALERT_CATEGORIES = [
    "地震", "雷雨", "淹水", "土石流", "停電", "停水", "強風", "道路封閉", "海嘯", "防空"
]

class NCDRSensorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """處理 NCDR 整合的 UI 設定流程"""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """當使用者在 UI 點選新增此整合時觸發"""
        errors = {}

        if user_input is not None:
            # 這裡移除了限制 API Key 不得為空的驗證
            title = f"NCDR 災害示警 ({user_input[CONF_COUNTY]})"
            if user_input.get(CONF_TOWN):
                title = f"NCDR 災害示警 ({user_input[CONF_COUNTY]}{user_input[CONF_TOWN]})"
            
            return self.async_create_entry(
                title=title,
                data=user_input
            )

        # 將 API Key 欄位修改為 vol.Optional (選填)，預設為空字串
        data_schema = vol.Schema({
            vol.Optional(CONF_API_KEY, default=""): str,
            vol.Required(CONF_COUNTY, default="新北市"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=TAIWAN_COUNTIES,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_TOWN): str,
            vol.Optional(CONF_ALERT_TYPES): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=ALERT_CATEGORIES,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )
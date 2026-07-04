from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """透過 UI 新增完成後，初始化此整合"""
    hass.data.setdefault(DOMAIN, {})
    # 將使用者輸入的 api_key & county 暫存到記憶體
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # 將任務派發給 sensor.py 平台建置實體
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """當使用者從 UI 刪除此整合時，解除載入"""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
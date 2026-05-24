from typing import Any

from dify_plugin import ToolProvider


class MyWeatherProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        # This plugin intentionally requires no API credentials.
        return

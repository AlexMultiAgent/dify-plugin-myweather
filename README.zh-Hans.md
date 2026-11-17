# MyWeather

MyWeather 是一个无需 API Key 的 Dify 天气插件。

- 主数据源可选择：`open-meteo` 或 `wttr`
- 默认主数据源：`open-meteo`
- 非主数据源通常作为兜底；日文、韩文原文字段名仅走 Open-Meteo
- 支持英文、简体中文、繁体中文、日语、韩语的输入与输出
- 通过 Unicode 脚本与有限的地名提示表自动识别语言
- 日文、韩文原文字段名在地理编码前先做转写

## 输出示例

**英文**（输入：`London`）

> London, England, United Kingdom: Partly cloudy. Temp 12.0 °C, feels like 10.5 °C, humidity 72%, wind 11.0 km/h.

**韩文**（输入：首尔的韩文写法）

```text
Seoul, South Korea: 구름많음. 기온 12.6°C, 체감 10.1°C, 습도 61%, 풍속 7.0 km/h.
```

**日文**（输入：横滨的汉字写法）

```text
横浜市, 神奈川県, 日本：曇り。気温 15.5°C、体感 12.5°C、湿度 51%、風速 9.0 km/h。
```

工作流：`Start (city) → Weather Lookup → Output`

## 快速开始

1. 在 Dify 中安装插件 `MyWeather`。
2. 添加工具节点 `Weather Lookup`。
3. 设置 `source_preference`：
   - `open-meteo`（默认）：优先 Open-Meteo，支持的脚本用 wttr 兜底
   - `wttr`：优先 wttr，Open-Meteo 兜底
   - 日文、韩文原文字段名始终直接使用 Open-Meteo
4. 把用户输入的地点文本传给 `location`。

## 连接要求

插件会向三个域名发起 HTTPS 请求，不需要 API Key、账号、令牌或任何凭据：

| 域名 | 用途 |
| --- | --- |
| `api.open-meteo.com` | Open-Meteo 天气接口 |
| `geocoding-api.open-meteo.com` | Open-Meteo 地名检索 |
| `wttr.in` | 兜底天气数据源 |

若 Dify 部署限制出网，请放行这三个域名。插件只发送用户输入的地点文本，
详见 [PRIVACY.md](./PRIVACY.md)。

## 工具参数

- `location`（必填）：城市、地区、机场代码或地名，支持英文、中文、日文、韩文。
- `language`（可选）：输出语言。`auto`（默认）按输入自动判断——谚文 → 韩文、平假名/片假名 → 日文、可识别的台湾 / 香港 / 澳门 / 日本地名 → 对应地区语言、其他 CJK → 简体中文，其余 → 英文。纯汉字地名有歧义时请显式指定。可选值为 `en-US`、`zh-Hans`、`zh-Hant`、`ja`、`ko`。
- `units`（可选）：`metric` 或 `uscs`。
- `source_preference`（可选）：`open-meteo`（默认）或 `wttr`。
- `include_raw_json`（可选）：在 JSON 输出中以 `raw` 键附带上游原始数据。

## 输出变量

`weather_lookup` 返回：

- `source`：实际使用的数据源（`wttr` 或 `open-meteo`）。
- `source_display`：可直接展示的数据源名称。
- `language`：最终确定的输出语言。
- `location`：数据源实际匹配到的地点，而不是原始查询文本。
- `condition`：天气状况文本（CJK、日文输出时会翻译）。
- `temperature`：当前温度。
- `temperature_unit`：`°C` 或 `°F`。
- `feels_like`：体感温度。
- `humidity`：相对湿度百分比。
- `wind_speed`：风速。
- `wind_speed_unit`：`km/h` 或 `mph`。
- `summary`：不含数据源信息的简短天气描述（已本地化）。
- `open_meteo_compliance_notice`：Open-Meteo 署名与改动声明（仅当数据源为 Open-Meteo）。
- `rate_limit_notice`：兜底提示（仅当 Open-Meteo 请求失败，包括 HTTP 429，并触发兜底）。

## 语言支持

| 语言 | 识别方式 | 天气翻译 | 地理编码 |
| --- | --- | --- | --- |
| 英语 (en-US) | 默认 | 直通 | 常规 |
| 简体中文 (zh-Hans) | CJK 字符 | 完整（146 条） | 原生地名 |
| 繁体中文 (zh-Hant) | 可识别的台湾 / 香港 / 澳门地名 | 完整（简繁 + 覆写） | 拉丁别名 |
| 日语 (ja) | 平假名/片假名或可识别的日本汉字地名 | 完整（146 条） | 罗马字 + 地名后缀变体 |
| 韩语 (ko) | 谚文 | 完整（146 条） | 罗马字转写 |

自动识别规则：

- 谚文音节（U+AC00–U+D7AF）→ `ko`
- 平假名（U+3040–U+309F）或片假名（U+30A0–U+30FF）→ `ja`
- CJK 字符 → `zh-Hans`，除非文本中包含可识别的台湾 / 香港 / 澳门 / 日本地名
- 其余 → `en-US`

纯汉字地名在不同语言中可能完全相同，自动识别依赖一张有限的地名别名表；
当同一个汉字地名在上下文中存在歧义时，请显式设置 `language`。

## 地名解析

两个数据源都以拉丁字母索引地名，本身都无法处理日文、韩文原文字段名——
因此插件会先对查询做转写，再进行地理编码：

| 输入脚本 | 转写结果 | 方式 |
| --- | --- | --- |
| 谚文 | `seoul`、`busan` | 罗马字转写，并去掉行政区划后缀（`수원시` → `suwon`） |
| 假名 | `tokyo`、`sapporo` | 平假名/片假名罗马字 |
| 日文汉字 | `Yokohama-shi`、`Yokohama-to` | 行政区划后缀变体，避免匹配到其他县的同名小地方 |
| 汉字 | — | 上游已收录，直接使用原名 |
| 台湾 / 香港 / 澳门 | `Taipei`、`Hong Kong` | 上游索引使用英文名 |

实际示例：

```text
서울      -> seoul
부산      -> busan
수원시    -> suwon
とうきょう -> tokyo
さっぽろ  -> sapporo
横浜      -> 横浜市, 横浜都
北京      -> （原生收录，无需转写）
台北      -> Taipei
```

两种罗马字方案都是确定性的——谚文基于 Unicode 音节分解，假名基于固定表——
因此插件不附带任何音标字典，也没有需要维护的词库。唯一的查找表是台湾、香港与澳门的
行政区划，数据极少变动。

wttr.in 完全无法解析日文、韩文原文字段名：它会把首尔的谚文地名答成名为 Ryongsan 的
村落，把东京的假名地名答成名为 Takehiracho 的行政区。因此这类输入无论
`source_preference` 如何设置都走 Open-Meteo，并且输出的 `location` 始终是数据源
实际匹配到的地点。

## Open-Meteo 与 wttr.in 说明

Open-Meteo：

- 原生收录中文地名；日文、韩文地名转写后也可命中。
- 本地化索引并不完整，因此插件也会尝试原始写法。
- 地理编码没有结果时会兜底到 wttr.in 并设置 `rate_limit_notice`，日文、韩文原文字段名除外。
- 天气状况文本由插件翻译。
- 天气响应是数值与天气代码形式。

wttr.in：

- 能解析拉丁字母与中文地名，但会把日文、韩文地名映射到邻近地点而非目标城市，
  因此不用于日文、韩文原文字段名。
- 可提供本地化的天气描述。

参考：

- Open-Meteo 地理编码接口：https://open-meteo.com/en/docs/geocoding-api
- Open-Meteo 天气接口：https://open-meteo.com/en/docs
- Open-Meteo 许可协议：https://open-meteo.com/en/licence
- Open-Meteo 服务条款：https://open-meteo.com/en/terms
- wttr.in 帮助：https://wttr.in/:help
- wttr.in 仓库：https://github.com/chubin/wttr.in

## 支持

- 源代码仓库：https://github.com/AlexMultiAgent/dify-plugin-myweather
- GitHub 主页：https://github.com/AlexMultiAgent
- 问题反馈：https://github.com/AlexMultiAgent/dify-plugin-myweather/issues

## 许可协议

MIT License，详见 [LICENSE](./LICENSE)。

英文版文档见 [README.md](./README.md)。

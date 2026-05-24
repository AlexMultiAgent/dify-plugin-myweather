# MyWeather Privacy Policy

This privacy policy describes how `myweather` handles data when used in Dify.

## 1. What Data Is Processed

The plugin processes the following user-provided data:

- Location query text (for example: `Shanghai`, `New York`, `JFK`)

The plugin does not require account login, API keys, passwords, or payment data.

## 2. How Data Is Used

The location query is used only to request weather data from upstream weather services and return the result to the user in Dify.

## 3. Third-Party Services

This plugin sends location queries to the following third-party APIs:

- `https://wttr.in`
- `https://geocoding-api.open-meteo.com`
- `https://api.open-meteo.com`

Please review upstream privacy policies and terms before production use:

- wttr.in: `https://wttr.in/:help`
- Open-Meteo: `https://open-meteo.com/en/terms`

## 4. Storage and Retention

The plugin itself does not implement persistent storage for user queries or weather responses.

Data retention, logs, and access controls are handled by:

- Your Dify deployment configuration
- Upstream weather providers receiving requests

## 5. Data Sharing

The plugin does not sell user data and does not intentionally share data beyond the upstream weather services listed above.

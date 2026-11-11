"""Settings for the live data feeds. No secrets: neither API needs a key."""

# Market
DEFAULT_ZONE = "DE-LU"
MARKET_TZ = "Europe/Berlin"  # the delivery day runs midnight to midnight in this time zone
SLOT_MINUTES = 15

# Energy-Charts (Fraunhofer ISE), day-ahead prices
ENERGY_CHARTS_URL = "https://api.energy-charts.info"
ENERGY_CHARTS_SOURCE = "energy-charts"
ENERGY_CHARTS_ATTRIBUTION = (
    "Prices: Energy-Charts / Fraunhofer ISE (data: Bundesnetzagentur | SMARD.de, CC BY 4.0)"
)

# Open-Meteo, weather forecast
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
# what earlier model runs said (for forecast accuracy) and measured satellite radiation
OPEN_METEO_PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
OPEN_METEO_SATELLITE_URL = "https://satellite-api.open-meteo.com/v1/archive"
OPEN_METEO_MODEL = "dwd_icon_seamless"
OPEN_METEO_ATTRIBUTION = "Weather data by Open-Meteo.com"
FORECAST_DAYS = 7

# HTTP
REQUEST_TIMEOUT_S = 30
MAX_RETRIES = 4  # waits 2, 4, 8, 16 seconds between attempts

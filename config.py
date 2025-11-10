import os
from dotenv import load_dotenv

load_dotenv()


class ProviderConfig:
    """ Single provider definition """
    def __init__(self, name):
        self.name = name
        self.api_key = os.getenv(f"{name.upper()}_API_KEY")
        self.vision_model = os.getenv(f"{name.upper()}_VISION_MODEL")

        if not self.api_key:
            raise ValueError(f"API key missing for provider: {name}")


class Config:
    # Telegram
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

    # Openrouter Default
    OPENROUTER_BASE_URL = os.getenv('OPENROUTER_BASE_URL')

    # Providers list (comma separated)
    PROVIDER_LIST = os.getenv("PROVIDER_LIST", "mistral").split(",")

    # Construct provider configs dynamically
    PROVIDERS = []
    for provider_name in PROVIDER_LIST:
        provider_name = provider_name.strip()
        try:
            PROVIDERS.append(ProviderConfig(provider_name))
        except ValueError:
            # silently skip provider without keys
            pass

    # Open Food Facts
    OPEN_FOOD_FACTS_ENABLED = os.getenv('OPEN_FOOD_FACTS_ENABLED', 'true').lower() == 'true'
    OPEN_FOOD_FACTS_BASE_URL = os.getenv('OPEN_FOOD_FACTS_BASE_URL', "https://world.openfoodfacts.org/api/v2")
    OPEN_FOOD_FACTS_SEARCH_URL = os.getenv('OPEN_FOOD_FACTS_SEARCH_URL',
                                           "https://world.openfoodfacts.org/cgi/search.pl")

    # Request settings
    REQUEST_DELAY = float(os.getenv('REQUEST_DELAY', '3.0'))
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))

    # Fallback settings
    USE_DEMO_DATA = os.getenv('USE_DEMO_DATA', 'true').lower() == 'false'
    USE_ESTIMATED_DATA = os.getenv('USE_ESTIMATED_DATA', 'true').lower() == 'true'

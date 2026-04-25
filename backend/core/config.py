import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Cloudflare Workers AI credentials
    CLOUDFLARE_ACCOUNT_ID: str = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    CLOUDFLARE_API_TOKEN: str = os.getenv("CLOUDFLARE_API_TOKEN", "")

    # Cloudflare Workers AI endpoint for Stable Diffusion XL
    CF_AI_BASE_URL: str = (
        "https://api.cloudflare.com/client/v4/accounts"
        "/{account_id}/ai/run/{model}"
    )
    CF_MODEL: str = "@cf/stabilityai/stable-diffusion-xl-base-1.0"

    # Image generation retry settings
    IMAGE_GEN_MAX_RETRIES: int = 3
    IMAGE_GEN_RETRY_DELAY: float = 1.5  # seconds between retries

    # WebSocket loop interval range (seconds)
    WS_INTERVAL_MIN: float = 2.0
    WS_INTERVAL_MAX: float = 3.0

    @property
    def cf_ai_url(self) -> str:
        return self.CF_AI_BASE_URL.format(
            account_id=self.CLOUDFLARE_ACCOUNT_ID,
            model=self.CF_MODEL,
        )


settings = Settings()

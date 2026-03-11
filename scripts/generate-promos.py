"""Generate 7 daily promo images for Sushi da Hora using DALL-E 3 - Premium Style."""

import asyncio
import os
import sys
import shutil
import httpx
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PROMOS_DIR = Path(__file__).parent.parent / "assets" / "promos"
PROMOS_DIR.mkdir(parents=True, exist_ok=True)

# Premium style inspired by high-end sushi restaurant social media
# References: Senso Sushi, dark editorial food photography, Japanese minimalism
BASE_STYLE = (
    "Ultra premium sushi restaurant promotional photo. "
    "Dark moody black background with subtle dark marble or wave texture. "
    "Professional food photography, dramatic low-key lighting with warm highlights on the food. "
    "Shot from a 3/4 overhead angle. Dark ceramic or slate plate. "
    "Chopsticks resting elegantly nearby. "
    "Photorealistic, editorial quality, appetizing. "
    "NO text, NO words, NO letters, NO logos, NO watermarks in the image. "
    "Clean composition, premium Japanese restaurant aesthetic. "
    "1024x1024 square format."
)

PROMOS = [
    {
        "day": "segunda",
        "name": "Segunda Samurai",
        "file": "segunda-samurai.png",
        "prompt": (
            f"{BASE_STYLE} "
            "30 pieces of assorted sushi beautifully arranged on a long black slate board. "
            "Mix of salmon nigiri, tuna uramaki, and hosomaki rolls. "
            "Garnished with thin ginger slices and wasabi. "
            "Dark wooden chopsticks resting on chopstick holder. "
            "Subtle red accent lighting from the side. Warm intimate mood."
        ),
    },
    {
        "day": "terca",
        "name": "Terca Crocante",
        "file": "terca-crocante.png",
        "prompt": (
            f"{BASE_STYLE} "
            "10 golden crispy hot rolls arranged in two elegant rows on a dark rectangular plate. "
            "Close-up showing the crunchy panko breadcrumb texture. "
            "One roll cut in half revealing creamy filling inside. "
            "Tiny oil droplets glistening under warm light. "
            "Small dipping sauce bowl with soy sauce nearby. Golden warm tones."
        ),
    },
    {
        "day": "quarta",
        "name": "Quarta Maluca",
        "file": "quarta-maluca.png",
        "prompt": (
            f"{BASE_STYLE} "
            "Abundant platter of 40 colorful mixed sushi pieces on a large round dark plate. "
            "Salmon, tuna, shrimp, cream cheese rolls - vibrant variety of colors. "
            "Bird's eye overhead shot. Pieces arranged in a beautiful spiral pattern. "
            "Fresh herbs and edible flowers as garnish. Dynamic and generous feel."
        ),
    },
    {
        "day": "quinta",
        "name": "Quinta do Dragao",
        "file": "quinta-dragao.png",
        "prompt": (
            f"{BASE_STYLE} "
            "Two large premium hand-rolled temaki cones standing upright in elegant dark holders. "
            "Overflowing with fresh salmon, cream cheese, crispy onion, and tobiko caviar. "
            "Close-up detailed shot showing the nori wrapper texture and filling. "
            "Dramatic side lighting creating strong shadows. Powerful, premium feel."
        ),
    },
    {
        "day": "sexta",
        "name": "Sexta Familia",
        "file": "sexta-familia.png",
        "prompt": (
            f"{BASE_STYLE} "
            "Massive family-size wooden board with 60 pieces of assorted sushi. "
            "Multiple varieties visible: nigiri, maki, uramaki, sashimi sections. "
            "Overhead shot showing the generous spread across a large dark wood board. "
            "Warm inviting lighting suggesting family dinner atmosphere. "
            "Small sauce bowls and ginger on the side."
        ),
    },
    {
        "day": "sabado",
        "name": "Sabado Shogun",
        "file": "sabado-shogun.png",
        "prompt": (
            f"{BASE_STYLE} "
            "Extravagant imperial sushi feast on a large black stone slab. "
            "80 premium pieces including salmon, tuna, eel, shrimp, scallop nigiri. "
            "Elegant arrangement with gold leaf accents on some pieces. "
            "Luxury presentation with garnishes of micro-greens and edible flowers. "
            "Grand, majestic, royal banquet feel. Dramatic lighting."
        ),
    },
    {
        "day": "domingo",
        "name": "Domingo Zen",
        "file": "domingo-zen.png",
        "prompt": (
            f"{BASE_STYLE} "
            "Minimalist elegant sashimi arrangement on a simple dark ceramic plate. "
            "Fresh salmon, tuna, and white fish sashimi slices fanned out beautifully. "
            "Clean zen-like composition with lots of negative space. "
            "Small wasabi mound and shiso leaf. Smooth river stones as decoration nearby. "
            "Calm, serene, meditative atmosphere. Soft natural lighting."
        ),
    },
]


async def generate_image(client: httpx.AsyncClient, promo: dict) -> str:
    """Generate one promo image via DALL-E 3 and save to disk."""
    filepath = PROMOS_DIR / promo["file"]

    print(f"  Gerando {promo['name']}...")

    resp = await client.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": "dall-e-3",
            "prompt": promo["prompt"],
            "n": 1,
            "size": "1024x1024",
            "quality": "standard",
            "response_format": "url",
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    image_url = data["data"][0]["url"]

    # Download the image
    img_resp = await client.get(image_url, timeout=60)
    img_resp.raise_for_status()
    filepath.write_bytes(img_resp.content)

    print(f"  OK {promo['name']} - salvo em {filepath.name}")
    return str(filepath)


async def main():
    print("Gerando 7 artes promocionais PREMIUM para Sushi da Hora\n")

    if not OPENAI_API_KEY:
        print("OPENAI_API_KEY nao configurada no .env")
        sys.exit(1)

    # Backup existing images
    backup_dir = PROMOS_DIR / "originals_v1"
    if not backup_dir.exists():
        backup_dir.mkdir(exist_ok=True)
        for f in PROMOS_DIR.glob("*.png"):
            if f.name != "originals" and f.is_file():
                shutil.copy2(f, backup_dir / f.name)
                print(f"  Backup: {f.name}")
        print()

    async with httpx.AsyncClient() as client:
        for promo in PROMOS:
            try:
                await generate_image(client, promo)
            except Exception as e:
                print(f"  ERRO {promo['name']}: {e}")

    print(f"\nImagens salvas em: {PROMOS_DIR}")
    print("Rode: python scripts/add-text-promos.py para adicionar overlays")


if __name__ == "__main__":
    asyncio.run(main())

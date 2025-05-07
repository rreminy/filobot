from PIL import Image, ImageDraw
import aiohttp
import io
import asyncio

SS_MINIONS_MAPS = {
    813: "https://assets.ffxivsonar.com/ssminions/813.jpg",
    814: "https://assets.ffxivsonar.com/ssminions/814.jpg",
    815: "https://assets.ffxivsonar.com/ssminions/815.jpg",
    816: "https://assets.ffxivsonar.com/ssminions/816.jpg",
    817: "https://assets.ffxivsonar.com/ssminions/817.jpg",
    818: "https://assets.ffxivsonar.com/ssminions/818.jpg",

    956: "https://assets.ffxivsonar.com/ssminions/956.jpg",
    957: "https://assets.ffxivsonar.com/ssminions/957.jpg",
    958: "https://assets.ffxivsonar.com/ssminions/958.jpg",
    959: "https://assets.ffxivsonar.com/ssminions/959.jpg",
    960: "https://assets.ffxivsonar.com/ssminions/960.jpg",
    961: "https://assets.ffxivsonar.com/ssminions/961.jpg",
}

class MapUtils:
    async def _download_image(zone_id: int, size: str = "s"):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://assets.ffxivsonar.com/images/zone-{zone_id}-{size}.png") as response:
                return await response.read()

    def get_pixel_coords(image_width, image_height, flag_x, flag_y):
        flag_x = flag_x - 1
        flag_y = flag_y - 1

        pixel_x = int(float(flag_x) / float(41) * float(image_width))
        pixel_y = int(float(flag_y) / float(41) * float(image_height))

        return pixel_x, pixel_y

    async def get_zone_map_image_with_mark(zone_id: int, x: float, y: float, size: str = "s"):
        buffer = await MapUtils._download_image(zone_id, size)
        try:
            with Image.open(io.BytesIO(buffer)) as map_image:
                pixel_x, pixel_y = MapUtils.get_pixel_coords(map_image.width, map_image.height, x, y)
                draw = ImageDraw.Draw(map_image)

                draw.ellipse([(pixel_x - 8, pixel_y - 8), (pixel_x + 8, pixel_y + 8)], fill=(0, 0, 255))

                out_bytes = io.BytesIO()
                map_image.save(out_bytes, format="PNG")
                out_bytes.seek(0)
                return out_bytes.read()

        except:
            return None

# ===============
async def main():
    data = await MapUtils.get_zone_map_image_with_mark(818, 1, 1)
    with io.open("/store/book/output_test.png", "wb") as file:
        file.write(data)
    return

if __name__ == "__main__":
    asyncio.run(main())

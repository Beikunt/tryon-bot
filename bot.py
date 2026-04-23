import logging
import io
import numpy as np
import cv2

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor
from rembg import remove
from PIL import Image

API_TOKEN = "8747053258:AAEDX4CwqGqAKZ3JdH0lf882Ld4y1W70okY"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp  = Dispatcher(bot)

user_data: dict = {}

def get_user(user_id: int) -> dict:
    if user_id not in user_data:
        user_data[user_id] = {"product": None, "model": None}
    return user_data[user_id]

async def download_image(message: Message) -> Image.Image:
    photo     = message.photo[-1]
    file      = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    return Image.open(io.BytesIO(file_bytes.read())).convert("RGBA")

def pil_to_bio(img: Image.Image, fmt: str = "PNG") -> io.BytesIO:
    bio = io.BytesIO()
    img.save(bio, format=fmt)
    bio.seek(0)
    return bio

def process_tryon(product_img: Image.Image, model_img: Image.Image) -> Image.Image:
    product_no_bg = remove(product_img)
    product_np = np.array(product_no_bg, dtype=np.float32)
    model_np   = np.array(model_img.convert("RGB"), dtype=np.float32)
    mh, mw = model_np.shape[:2]
    ph, pw = product_np.shape[:2]
    target_w = int(mw * 0.50)
    target_h = int(ph * (target_w / pw))
    product_resized = cv2.resize(product_np, (target_w, target_h), interpolation=cv2.INTER_AREA)
    x_offset = (mw - target_w) // 2
    y_offset = int(mh * 0.20)
    x_end = min(x_offset + target_w, mw)
    y_end = min(y_offset + target_h, mh)
    crop_w = x_end - x_offset
    crop_h = y_end - y_offset
    result = model_np.copy()
    rgb   = product_resized[:crop_h, :crop_w, :3]
    alpha = product_resized[:crop_h, :crop_w, 3:4] / 255.0
    region = result[y_offset:y_end, x_offset:x_end]
    blended = alpha * rgb + (1.0 - alpha) * region
    result[y_offset:y_end, x_offset:x_end] = blended
    return Image.fromarray(result.astype(np.uint8))

@dp.message_handler(commands=["start"])
async def cmd_start(message: Message):
    get_user(message.from_user.id)
    await message.answer(
        "👋 Привет!\n\nШаги:\n1️⃣ Отправь фото *товара* (одежда)\n2️⃣ Отправь фото *модели* (человек)\n\nБот наложит одежду на модель 🎯\n\nКоманда /reset — начать заново.",
        parse_mode="Markdown"
    )

@dp.message_handler(commands=["reset"])
async def cmd_reset(message: Message):
    user_data[message.from_user.id] = {"product": None, "model": None}
    await message.answer("🔄 Сброшено. Отправь фото товара заново.")

@dp.message_handler(content_types=["photo"])
async def handle_photo(message: Message):
    user_id = message.from_user.id
    slot    = get_user(user_id)
    try:
        img = await download_image(message)
    except Exception as e:
        logging.error(f"Ошибка загрузки фото: {e}")
        await message.answer("❌ Не удалось загрузить фото. Попробуй ещё раз.")
        return
    if slot["product"] is None:
        slot["product"] = img
        await message.answer("✅ Фото товара получено!\n\nТеперь отправь фото *модели* 🧍", parse_mode="Markdown")
        return
    slot["model"] = img
    processing_msg = await message.answer("⏳ Обрабатываю, подожди немного...")
    try:
        result = process_tryon(slot["product"], slot["model"])
        bio    = pil_to_bio(result)
        await message.answer_photo(bio, caption="🎉 Готово! Команда /reset чтобы начать заново.")
    except Exception as e:
        logging.error(f"Ошибка обработки: {e}")
        await message.answer("❌ Ошибка при обработке. Попробуй другие фото или /reset.")
    finally:
        user_data[user_id] = {"product": None, "model": None}
        try:
            await processing_msg.delete()
        except Exception:
            pass

@dp.message_handler()
async def handle_other(message: Message):
    await message.answer("📷 Отправь фото. Если что-то пошло не так — /reset")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)

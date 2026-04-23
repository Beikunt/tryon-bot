import logging
import io
import requests

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor

API_TOKEN = "8747053258:AAEDX4CwqGqAKZ3JdH0lf882Ld4y1W70okY"
HF_TOKEN = "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"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp  = Dispatcher(bot)

user_data: dict = {}

def get_user(user_id: int) -> dict:
    if user_id not in user_data:
        user_data[user_id] = {"product": None, "model": None}
    return user_data[user_id]

async def download_image(message: Message) -> bytes:
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    return file_bytes.read()

def tryon_with_ai(product_bytes: bytes, model_bytes: bytes) -> bytes:
    API_URL = "https://api-inference.huggingface.co/models/levihsu/OOTDiffusion"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    response = requests.post(
        API_URL,
        headers=headers,
        json={
            "inputs": {
                "model_image": list(model_bytes),
                "garment_image": list(product_bytes),
            }
        },
        timeout=120
    )
    if response.status_code == 200:
        return response.content
    else:
        raise Exception(f"API error: {response.status_code} {response.text}")

@dp.message_handler(commands=["start"])
async def cmd_start(message: Message):
    get_user(message.from_user.id)
    await message.answer(
        "👋 Привет!\n\nШаги:\n1️⃣ Отправь фото *одежды* 👕\n2️⃣ Отправь фото *модели* 🧍\n\nAI наденет одежду на модель!\n\n/reset — начать заново.",
        parse_mode="Markdown"
    )

@dp.message_handler(commands=["reset"])
async def cmd_reset(message: Message):
    user_data[message.from_user.id] = {"product": None, "model": None}
    await message.answer("🔄 Сброшено. Отправь фото одежды.")

@dp.message_handler(content_types=["photo"])
async def handle_photo(message: Message):
    user_id = message.from_user.id
    slot = get_user(user_id)
    try:
        img = await download_image(message)
    except Exception as e:
        await message.answer("❌ Не удалось загрузить фото.")
        return
    if slot["product"] is None:
        slot["product"] = img
        await message.answer("✅ Фото одежды получено!\n\nТеперь отправь фото *модели* 🧍", parse_mode="Markdown")
        return
    slot["model"] = img
    processing_msg = await message.answer("⏳ AI обрабатывает, подожди 30-60 сек...")
    try:
        result = tryon_with_ai(slot["product"], slot["model"])
        bio = io.BytesIO(result)
        bio.seek(0)
        await message.answer_photo(bio, caption="🎉 Готово! /reset чтобы начать заново.")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("❌ Ошибка AI. Попробуй другие фото или /reset.")
    finally:
        user_data[user_id] = {"product": None, "model": None}
        try:
            await processing_msg.delete()
        except:
            pass

@dp.message_handler()
async def handle_other(message: Message):
    await message.answer("📷 Отправь фото одежды. /reset если что-то пошло не так.")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)

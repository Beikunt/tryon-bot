import logging
import io
import requests
import base64

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor

API_TOKEN = "8747053258:AAEDX4CwqGqAKZ3JdH0lf882Ld4y1W70okY"

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
    # Конвертируем в base64
    garment_b64 = base64.b64encode(product_bytes).decode()
    model_b64 = base64.b64encode(model_bytes).decode()

    # Используем Gradio API
    url = "https://levihsu-ootdiffusion.hf.space/run/predict"
    
    payload = {
        "fn_index": 0,
        "data": [
            {"data": f"data:image/jpeg;base64,{model_b64}", "name": "model.jpg"},
            {"data": f"data:image/jpeg;base64,{garment_b64}", "name": "garment.jpg"},
            "Upper body",
            1,
            20,
            42
        ]
    }
    
    response = requests.post(url, json=payload, timeout=120)
    
    if response.status_code == 200:
        result = response.json()
        img_data = result["data"][0]["data"]
        img_data = img_data.split(",")[1]
        return base64.b64decode(img_data)
    else:
        raise Exception(f"Error: {response.status_code}")

@dp.message_handler(commands=["start"])
async def cmd_start(message: Message):
    get_user(message.from_user.id)
    await message.answer(
        "👋 Привет!\n\n1️⃣ Отправь фото *одежды* 👕\n2️⃣ Отправь фото *модели* 🧍\n\nAI наденет одежду!\n\n/reset — начать заново.",
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
        await message.answer(f"❌ Ошибка: {str(e)[:100]}\n\nПопробуй /reset")
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

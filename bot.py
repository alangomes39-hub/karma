import os
import hashlib
import logging
import aiosqlite
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_FILE = "duplicates_media.db"

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ================= DATABASE =================
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS media_hashes (
                chat_id INTEGER,
                media_hash TEXT,
                PRIMARY KEY (chat_id, media_hash)
            )
        """)
        await db.commit()

# ================= HASH =================
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

async def get_media_hash(message) -> str | None:
    """
    Gera hash APENAS para mídias:
    fotos, vídeos, documentos e áudios
    """

    if message.photo:
        file = await message.photo[-1].get_file()
    elif message.video:
        file = await message.video.get_file()
    elif message.document:
        file = await message.document.get_file()
    elif message.audio:
        file = await message.audio.get_file()
    else:
        return None  # ignora texto e outros tipos

    content = await file.download_as_bytearray()
    return sha256(content)

# ================= HANDLER =================
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.channel_post
    if not message:
        return

    chat_id = message.chat_id
    media_hash = await get_media_hash(message)

    # se não for mídia, ignora
    if not media_hash:
        return

    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "SELECT 1 FROM media_hashes WHERE chat_id = ? AND media_hash = ?",
            (chat_id, media_hash)
        )
        exists = await cursor.fetchone()

        if exists:
            try:
                await message.delete()
                logging.info(f"🗑️ Mídia duplicada deletada | Chat {chat_id}")
            except Exception as e:
                logging.error(f"Erro ao deletar mídia: {e}")
            return

        await db.execute(
            "INSERT INTO media_hashes (chat_id, media_hash) VALUES (?, ?)",
            (chat_id, media_hash)
        )
        await db.commit()

# ================= MAIN =================
async def main():
    await init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # FILTRO: SOMENTE MÍDIA
    media_filter = filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.AUDIO

    app.add_handler(
        MessageHandler(
            media_filter,
            handle_media
        )
    )

    logging.info("🤖 Bot anti-duplicados (MODO MÍDIA) iniciado...")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

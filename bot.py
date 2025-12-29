import os
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

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN não definido")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ================= DATABASE =================
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS media_unique (
                chat_id INTEGER NOT NULL,
                file_unique_id TEXT NOT NULL,
                PRIMARY KEY (chat_id, file_unique_id)
            )
        """)
        await db.commit()

# ================= UTILS =================
def extract_file_unique_id(message) -> str | None:
    """
    Extrai file_unique_id APENAS de mídia real
    (ignora preview/thumbnail)
    """

    if message.photo:
        return message.photo[-1].file_unique_id

    if message.video:
        return message.video.file_unique_id

    if message.document:
        return message.document.file_unique_id

    if message.audio:
        return message.audio.file_unique_id

    return None

# ================= HANDLER =================
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.channel_post
    if not message:
        return

    file_unique_id = extract_file_unique_id(message)
    if not file_unique_id:
        return

    chat_id = message.chat_id

    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "SELECT 1 FROM media_unique WHERE chat_id = ? AND file_unique_id = ?",
            (chat_id, file_unique_id)
        )
        exists = await cursor.fetchone()

        if exists:
            try:
                await message.delete()
                logging.info(
                    f"🗑️ Mídia duplicada deletada | Chat {chat_id} | ID {file_unique_id}"
                )
            except Exception as e:
                logging.error(f"Erro ao deletar mídia: {e}")
            return

        await db.execute(
            "INSERT INTO media_unique (chat_id, file_unique_id) VALUES (?, ?)",
            (chat_id, file_unique_id)
        )
        await db.commit()

# ================= MAIN =================
def main():
    import asyncio

    asyncio.get_event_loop().run_until_complete(init_db())

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    media_filter = (
        filters.PHOTO
        | filters.VIDEO
        | filters.Document.ALL
        | filters.AUDIO
    )

    app.add_handler(MessageHandler(media_filter, handle_media))

    logging.info("🤖 Bot anti-duplicados (MODO MÍDIA REAL) iniciado")
    app.run_polling()

# ================= ENTRY =================
if __name__ == "__main__":
    main()

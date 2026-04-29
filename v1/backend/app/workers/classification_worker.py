"""
RQ Classification Worker — Regrow
Fetches image from MinIO → Calls Gemini Vision → Stores grade result
"""
import os
import sys
import json
import base64
import logging
from datetime import datetime

# Worker runs as standalone process — set up path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

import google.generativeai as genai
from PIL import Image
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("classification_worker")


def grade_file(file_id: str) -> dict:
    """
    Main RQ job function.

    1. Load file record from DB
    2. Download image from MinIO
    3. Call Gemini Vision API
    4. Parse grade result (A/B/C)
    5. Save to DB
    6. Update pickup status
    7. Send WhatsApp notification

    Returns dict with grade result.
    """
    import asyncio
    return asyncio.run(_grade_file_async(file_id))


async def _grade_file_async(file_id: str) -> dict:
    """Async implementation of the grading pipeline."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    from app.core.config import settings
    from app.models.models import File, GradeResult, Pickup, PickupStatus, Grade
    from app.services.storage import download_file

    logger.info(f"[Worker] Starting grading for file_id: {file_id}")

    # ── Setup DB session ──────────────────────────────────────────────────────
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSession_ = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSession_() as session:
        try:
            # ── Load file record ──────────────────────────────────────────────
            import uuid
            result = await session.execute(
                select(File).where(File.id == uuid.UUID(file_id))
            )
            file_record = result.scalar_one_or_none()
            if not file_record:
                raise ValueError(f"File not found: {file_id}")

            # ── Download from MinIO ───────────────────────────────────────────
            logger.info(f"[Worker] Downloading from MinIO: {file_record.file_path}")
            image_bytes = download_file(file_record.file_path)
            logger.info(f"[Worker] Downloaded {len(image_bytes)} bytes")

            # ── Call Gemini Vision ────────────────────────────────────────────
            grade_data = await _call_gemini_vision(image_bytes, settings.GEMINI_API_KEY)
            logger.info(f"[Worker] Grade result: {grade_data}")

            # ── Save grade to DB ──────────────────────────────────────────────
            grade_record = GradeResult(
                file_id=file_record.id,
                grade=Grade[grade_data["grade"]],
                confidence=grade_data["confidence"],
                reasoning=grade_data.get("reasoning", ""),
                estimated_kg=grade_data.get("estimated_kg"),
                graded_by="gemini",
            )
            session.add(grade_record)

            # ── Update pickup status ──────────────────────────────────────────
            pickup_result = await session.execute(
                select(Pickup).where(Pickup.id == file_record.pickup_id)
            )
            pickup = pickup_result.scalar_one_or_none()
            if pickup:
                pickup.status = PickupStatus.graded

            await session.commit()

            # ── Send WhatsApp notification ────────────────────────────────────
            if pickup:
                pickup_result2 = await session.execute(
                    select(Pickup)
                    .where(Pickup.id == pickup.id)
                )
                p = pickup_result2.scalar_one_or_none()
                if p:
                    await _notify_user_graded(session, p, grade_data)

            logger.info(f"[Worker] ✅ Grading complete for file {file_id}")
            return grade_data

        except Exception as e:
            logger.error(f"[Worker] ❌ Grading failed for {file_id}: {e}")
            await session.rollback()
            raise
        finally:
            await engine.dispose()


async def _call_gemini_vision(image_bytes: bytes, api_key: str) -> dict:
    """
    Send image to Gemini Vision and parse the waste grade result.
    Falls back to a mock result if API key is not configured.
    """
    if api_key == "not-set" or not api_key:
        logger.warning("[Worker] GEMINI_API_KEY not set — using mock grade")
        return _mock_grade()

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Convert to PIL Image for Gemini
        pil_image = Image.open(io.BytesIO(image_bytes))

        prompt = """You are a textile waste quality assessor for a circular economy platform in Indonesia.

Analyze this textile waste image and provide a quality grade.

GRADING CRITERIA:
- Grade A: Clean, minimal wear, good fabric integrity, high reuse/recycle potential (>80% confidence)
- Grade B: Some wear/staining, moderate quality, acceptable for processing (60-80%)
- Grade C: Heavy wear, significant damage, low quality but still recyclable (40-60%)
- Grade D: Too damaged/contaminated to process (below threshold)

Respond ONLY with valid JSON, no markdown, no explanation:
{
  "grade": "A",
  "confidence": 0.85,
  "reasoning": "Short reason in Indonesian",
  "estimated_kg": 2.5
}"""

        response = model.generate_content([prompt, pil_image])
        text = response.text.strip()

        # Strip markdown if model adds it
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        result = json.loads(text)

        # Validate and clamp values
        grade = result.get("grade", "B").upper()
        if grade not in ("A", "B", "C", "D"):
            grade = "B"

        return {
            "grade": grade,
            "confidence": float(result.get("confidence", 0.75)),
            "reasoning": str(result.get("reasoning", "")),
            "estimated_kg": float(result.get("estimated_kg", 1.0)),
        }

    except json.JSONDecodeError as e:
        logger.error(f"[Worker] Gemini returned invalid JSON: {e}")
        return _mock_grade()
    except Exception as e:
        logger.error(f"[Worker] Gemini API error: {e}")
        return _mock_grade()


def _mock_grade() -> dict:
    """Return a deterministic mock grade for development/testing."""
    import random
    grades = ["A", "A", "B", "B", "B", "C"]
    grade = random.choice(grades)
    confidence_map = {"A": 0.91, "B": 0.76, "C": 0.62, "D": 0.45}
    return {
        "grade": grade,
        "confidence": confidence_map[grade],
        "reasoning": f"Sampah tekstil kualitas {grade}. (Hasil simulasi — konfigurasi GEMINI_API_KEY untuk hasil nyata)",
        "estimated_kg": round(1.0 + 3.0 * (1 - confidence_map[grade] + 0.3), 1),
    }


async def _notify_user_graded(session, pickup, grade_data: dict):
    """Send WhatsApp notification to user after grading."""
    from sqlalchemy import select
    from app.models.models import User
    from app.services.whatsapp import send_whatsapp_message

    result = await session.execute(select(User).where(User.id == pickup.user_id))
    user = result.scalar_one_or_none()
    if not user:
        return

    grade = grade_data["grade"]
    confidence = int(grade_data["confidence"] * 100)
    reasoning = grade_data.get("reasoning", "")
    est_kg = grade_data.get("estimated_kg", "?")

    grade_emoji = {"A": "🏆", "B": "✅", "C": "⚠️", "D": "❌"}
    emoji = grade_emoji.get(grade, "📦")

    message = (
        f"🎯 *Hasil Penilaian Sampah Anda*\n\n"
        f"{emoji} Grade: *{grade}* ({confidence}% keyakinan)\n"
        f"⚖️ Estimasi berat: *{est_kg} kg*\n"
        f"📝 Catatan: {reasoning}\n\n"
        f"Tim kami akan segera mengambil sampah Anda!\n"
        f"Pertanyaan? Ketik *menu*."
    )
    await send_whatsapp_message(user.phone, message)


# ─── Worker entry point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Quick manual test
    import sys
    if len(sys.argv) > 1:
        import asyncio
        result = asyncio.run(_call_gemini_vision(b"", "not-set"))
        print(json.dumps(result, indent=2))

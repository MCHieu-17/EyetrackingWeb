"""Xóa asset JPG cũ đã được migration 003 đánh dấu `deleted`.

Chạy thử (mặc định chỉ liệt kê):
    python -m app.scripts.cleanup_legacy_media

Thực thi:
    python -m app.scripts.cleanup_legacy_media --apply
"""

import argparse
import asyncio
import logging

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.media import MediaAsset
from app.services import media_storage

logger = logging.getLogger(__name__)


async def _run(apply: bool) -> int:
    async with SessionLocal() as db:
        assets = (
            await db.execute(
                select(MediaAsset).where(MediaAsset.state == "deleted")
            )
        ).scalars().all()

        for asset in assets:
            print(
                f"{asset.id}  {asset.storage_backend:5s}  "
                f"{asset.mime_type:30s}  {asset.object_key}"
            )
            if not apply:
                continue
            try:
                await asyncio.to_thread(
                    media_storage.delete_key,
                    asset.object_key,
                    asset.storage_backend,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Không xóa được object %s: %s", asset.object_key, exc
                )
                continue
            await db.delete(asset)

        if apply:
            await db.commit()
        return len(assets)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Xóa asset JPG cũ đã đánh dấu deleted."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Thực thi xóa storage + row (mặc định chỉ liệt kê).",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    count = asyncio.run(_run(args.apply))
    action = "Đã xóa" if args.apply else "Sẽ xóa"
    print(f"{action} {count} asset.")


if __name__ == "__main__":
    main()

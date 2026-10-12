# language: Python, file: tests/test_catalog_preview_service.py, target: Windows 11, pytest
import pytest
from pathlib import Path
from starlette.testclient import TestClient
from backend.main import create_app
from backend.database import init_db, AsyncSessionLocal
from backend.services.catalog_preview_service import CatalogPreviewService, CatalogPreviewError
from backend.services.registry_adapter import RegistryAdapter
from backend.services import library_index
from backend.services.library_taxonomy import MEDIA_AUDIO, MEDIA_IMAGE, MEDIA_VIDEO
from backend.config import settings

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_catalog_preview_service_synthetic_poster():
    items = RegistryAdapter.list_catalog_items()
    assert len(items) > 0, "No catalog items found in registry"
    block_id = items[0]["id"]

    # Test generation for a valid block id
    poster_path = CatalogPreviewService.get_poster_path(block_id, aspect_ratio="9:16")
    assert poster_path.exists()
    assert poster_path.suffix == ".png"
    assert poster_path.stat().st_size > 0

    # Ensure cached poster is reused
    poster_path_cached = CatalogPreviewService.get_poster_path(block_id, aspect_ratio="9:16")
    assert poster_path == poster_path_cached

def test_catalog_preview_service_nonexistent_block():
    with pytest.raises(CatalogPreviewError):
        CatalogPreviewService.get_poster_path("test-nonexistent-block", aspect_ratio="9:16")

def test_catalog_preview_service_html_generation():
    items = RegistryAdapter.list_catalog_items()
    assert len(items) > 0
    block_id = items[0]["id"]
    html = CatalogPreviewService.get_preview_html(block_id, aspect_ratio="9:16")
    assert "<!DOCTYPE html>" in html or "<html" in html.lower()
    # Verify preview runner injection
    assert "vm-catalog-preview-runner" in html
    assert "gsap" in html or "requestAnimationFrame" in html

def test_catalog_preview_service_path_traversal_guard():
    items = RegistryAdapter.list_catalog_items()
    assert len(items) > 0
    block_id = items[0]["id"]
    # Attempting to traverse outside should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        CatalogPreviewService.resolve_block_asset_file(block_id, "../../sensitive.txt")

    with pytest.raises(FileNotFoundError):
        CatalogPreviewService.resolve_block_asset_file(block_id, "..\\..\\sensitive.txt")

@pytest.mark.asyncio
async def test_catalog_endpoints(client):
    await init_db()
    # 1. List catalog items - verify poster_url and preview_url fields
    res = client.get("/api/projects/catalog/items")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) > 0
    first = data["items"][0]
    assert "poster_url" in first
    assert "preview_url" in first
    b_name = first.get("name") or first["id"]

    # 2. Get poster endpoint
    res_poster = client.get(f"/api/projects/catalog/blocks/{b_name}/poster?aspect_ratio=9:16")
    assert res_poster.status_code == 200
    assert res_poster.headers["content-type"] == "image/png"
    assert len(res_poster.content) > 100

    # 3. Get preview endpoint
    res_preview = client.get(f"/api/projects/catalog/blocks/{b_name}/preview?aspect_ratio=9:16")
    assert res_preview.status_code == 200
    assert "text/html" in res_preview.headers["content-type"]
    assert "vm-catalog-preview-runner" in res_preview.text

def test_catalog_preview_missing_or_traversal_asset_endpoint(client):
    items = RegistryAdapter.list_catalog_items()
    block_id = items[0]["id"] if items else "kinetic-title-cascade"
    # Attempting to fetch non-existent or blocked asset
    res = client.get(f"/api/projects/catalog/blocks/{block_id}/preview/assets/nonexistent_file.png")
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_catalog_preview_is_non_destructive(client):
    await init_db()
    # 1. Create a project
    create_res = client.post("/api/projects", json={"name": "Safety Invariant Project", "aspect_ratio": "9:16"})
    assert create_res.status_code in (200, 201)
    proj_id = create_res.json()["id"]
    initial_rev = create_res.json()["revision"]

    items = RegistryAdapter.list_catalog_items()
    b_name = (items[0].get("name") or items[0]["id"]) if items else "kinetic-title-cascade"

    # 2. Call preview and poster endpoints multiple times
    client.get("/api/projects/catalog/items")
    client.get(f"/api/projects/catalog/blocks/{b_name}/poster")
    client.get(f"/api/projects/catalog/blocks/{b_name}/preview")

    # 3. Inspect project again - revision and document must remain intact
    detail_res = client.get(f"/api/projects/{proj_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["revision"] == initial_rev

@pytest.mark.asyncio
async def test_library_index_media_type_classification(tmp_path):
    from backend.models.downloaded_video import DownloadedVideo
    from sqlalchemy import select
    await init_db()

    audio_file = tmp_path / "ambient.mp3"
    audio_file.write_bytes(b"dummy mp3 data")
    img_file = tmp_path / "cover.png"
    img_file.write_bytes(b"dummy png data")
    vid_file = tmp_path / "sample.mp4"
    vid_file.write_bytes(b"dummy mp4 data")

    prefix = "test-classif-"
    async with AsyncSessionLocal() as db:
        try:
            db.add(DownloadedVideo(id=f"{prefix}aud", title="Test Audio", platform="import", audio_path=str(audio_file)))
            db.add(DownloadedVideo(id=f"{prefix}img", title="Test Image", platform="import", video_path=str(img_file)))
            db.add(DownloadedVideo(id=f"{prefix}vid", title="Test Video", platform="import", video_path=str(vid_file)))
            await db.commit()

            items = await library_index._downloaded_items(db)
            filtered = {it["id"]: it for it in items if it["id"].startswith(prefix)}

            assert filtered[f"{prefix}aud"]["media"] == MEDIA_AUDIO
            assert filtered[f"{prefix}aud"]["thumb_url"] is None

            assert filtered[f"{prefix}img"]["media"] == MEDIA_IMAGE
            assert f"/api/downloaded/{prefix}img/stream" in filtered[f"{prefix}img"]["thumb_url"]

            assert filtered[f"{prefix}vid"]["media"] == MEDIA_VIDEO
            assert f"/api/downloaded/{prefix}vid/thumbnail" in filtered[f"{prefix}vid"]["thumb_url"]
        finally:
            rows = (await db.execute(select(DownloadedVideo).where(DownloadedVideo.id.startswith(prefix)))).scalars().all()
            for r in rows:
                await db.delete(r)
            await db.commit()

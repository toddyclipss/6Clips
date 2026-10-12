# language: Python, file: scripts/measure_preview_performance.py, target: Windows 11
import time
import httpx
import json

BASE = "http://127.0.0.1:16888"

def bench():
    client = httpx.Client(base_url=BASE, timeout=10.0)
    
    # 1. Catalog list metadata response time
    t0 = time.perf_counter()
    res = client.get("/api/projects/catalog/items")
    t_list = (time.perf_counter() - t0) * 1000
    assert res.status_code == 200
    items = res.json()["items"]
    
    # Pick a block
    block_id = items[0]["id"]
    
    # 2. Warm poster response time
    t0 = time.perf_counter()
    res_poster_warm = client.get(f"/api/projects/catalog/blocks/{block_id}/poster?aspect_ratio=9:16")
    t_poster_warm = (time.perf_counter() - t0) * 1000
    assert res_poster_warm.status_code == 200
    
    # 3. Preview HTML generation response time
    t0 = time.perf_counter()
    res_prev = client.get(f"/api/projects/catalog/blocks/{block_id}/preview?aspect_ratio=9:16")
    t_prev = (time.perf_counter() - t0) * 1000
    assert res_prev.status_code == 200
    
    print(json.dumps({
        "catalog_items_count": len(items),
        "catalog_list_ms": round(t_list, 2),
        "poster_warm_ms": round(t_poster_warm, 2),
        "preview_html_ms": round(t_prev, 2),
    }, indent=2))

if __name__ == "__main__":
    bench()

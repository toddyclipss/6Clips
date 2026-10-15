import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
shipped_dir = (REPO_ROOT / "backend" / "catalog" / "shipped_blocks").resolve()
shipped_am = sorted([d.name for d in shipped_dir.iterdir() if d.is_dir() and 'a' <= d.name[0].lower() <= 'm'])

results = {}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel="msedge")
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    
    for idx, slug in enumerate(shipped_am, 1):
        html_p = shipped_dir / slug / f"{slug}.html"
        if not html_p.exists():
            html_p = shipped_dir / slug / "index.html"
            
        page = context.new_page()
        page_errors = []
        console_errors = []
        
        def on_page_err(exc, err_list=page_errors):
            err_list.append(str(exc))
            
        def on_console(msg, err_list=console_errors):
            if msg.type == "error":
                err_list.append(msg.text)
                
        page.on("pageerror", on_page_err)
        page.on("console", on_console)
        
        try:
            page.goto(html_p.as_uri(), timeout=10000)
            page.wait_for_timeout(250)
            
            has_tl = page.evaluate("""() => {
                return Boolean(window.tl || (window.__timelines && Object.keys(window.__timelines).length > 0));
            }""")
            
            can_seek = False
            if has_tl:
                can_seek = page.evaluate("""() => {
                    try {
                        if (window.tl && typeof window.tl.seek === 'function') {
                            window.tl.seek(1.0);
                            return true;
                        }
                        if (window.__timelines) {
                            const k = Object.keys(window.__timelines)[0];
                            if (window.__timelines[k] && typeof window.__timelines[k].seek === 'function') {
                                window.__timelines[k].seek(1.0);
                                return true;
                            }
                        }
                    } catch (e) {
                        return false;
                    }
                    return false;
                }""")
                
            results[slug] = {
                "page_errors": len(page_errors),
                "console_errors": len(console_errors),
                "first_page_error": page_errors[0] if page_errors else None,
                "has_tl": has_tl,
                "can_seek": can_seek,
            }
        except Exception as e:
            results[slug] = {
                "page_errors": 1,
                "console_errors": 0,
                "first_page_error": str(e),
                "has_tl": False,
                "can_seek": False,
            }
        finally:
            page.close()
            
    browser.close()

passed = [s for s, r in results.items() if r["page_errors"] == 0 and r["has_tl"] and r["can_seek"]]
errored = [s for s, r in results.items() if r["page_errors"] > 0]
no_tl = [s for s, r in results.items() if r["page_errors"] == 0 and (not r["has_tl"] or not r["can_seek"])]

print(f"Total tested: {len(results)}")
print(f"Clean PASS with timeline seek: {len(passed)}")
print(f"Page Error: {len(errored)}")
for s in errored:
    print(f"  {s}: {results[s]['first_page_error']}")
print(f"No timeline or cannot seek: {len(no_tl)}")
for s in no_tl:
    print(f"  {s}")

out_path = REPO_ROOT / "tools" / "wave18_a3" / "raw_audit_results.json"
out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"Wrote results to {out_path}")

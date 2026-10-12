import asyncio
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        pid = 'd5f13156-fc63-45e5-b448-d347639bc180'
        await page.goto(f'http://127.0.0.1:16888/motion?projectId={pid}', wait_until='networkidle')
        await page.wait_for_timeout(2000)
        outer_frame = await (await page.locator('#studio-preview-iframe').element_handle()).content_frame()
        
        info = await outer_frame.evaluate("""() => {
            const master = window.__timelines ? window.__timelines["viralmint_stage"] : null;
            if (!master) return 'no master';
            const children = master.getChildren ? master.getChildren().map(c => ({
                duration: c.duration(),
                startTime: c.startTime(),
                targets: c.targets ? Array.from(c.targets()).map(t => t.id) : []
            })) : [];
            const el = document.querySelector('#elem_fbc05ef7');
            const before = {
                opacity: el ? el.style.opacity : null,
                time: master.time()
            };
            master.seek(0);
            const after0 = {
                opacity: el ? el.style.opacity : null,
                time: master.time()
            };
            master.seek(0.001);
            const afterTiny = {
                opacity: el ? el.style.opacity : null,
                time: master.time()
            };
            master.seek(0, false);
            const after0False = {
                opacity: el ? el.style.opacity : null,
                time: master.time()
            };
            master.progress(0);
            const afterProg0 = {
                opacity: el ? el.style.opacity : null,
                time: master.time()
            };
            return { children, before, after0, afterTiny, after0False, afterProg0 };
        }""")
        import pprint
        pprint.pprint(info)
        await browser.close()

if __name__ == '__main__':
    asyncio.run(inspect())

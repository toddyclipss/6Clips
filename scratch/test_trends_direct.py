import asyncio
import os
import sys
sys.path.insert(0, ".")
os.environ['VIRALMINT_DATA_DIR'] = 'tmp_isolated_test'
from backend.services.executor_service import ExecutorService

async def main():
    try:
        output, verif = await ExecutorService._execute_search_trends({'query': 'fortnite', 'max_results': 5}, 'local')
        print("RESULT:")
        print("Count:", output.get("count"))
        print("Results sample:", output.get("results")[:2] if output.get("results") else None)
        print("Rights notice:", output.get("rights_notice")[:80])
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

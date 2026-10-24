import time

import httpx
from pyairtable import Api

from content_monitor.checker import make_client
from content_monitor.config import load_settings
from content_monitor.extractor import extract_content


def main() -> None:
    settings = load_settings()
    api = Api(settings.airtable_token)
    pages = api.table(settings.airtable_base_id, "Pages")

    with make_client() as client:
        for record in pages.all(formula="{Active}"):
            url = record["fields"]["URL"]
            time.sleep(1)

            try:
                response = client.get(url)
            except httpx.RequestError as exc:
                print(f"SKIP {url}: {exc}")
                continue

            content_type = response.headers.get("content-type", "")
            if not response.is_success or "text/html" not in content_type:
                print(f"SKIP {url}: status {response.status_code}, {content_type}")
                continue

            content = extract_content(response.text)
            print(url)
            print(f"  title:       {content.title!r}")
            print(f"  description: {content.meta_description!r}")
            print(f"  h1s:         {content.h1s}")
            print(f"  h2s:         {len(content.h2s)} found")
            print(f"  words:       {content.word_count}")

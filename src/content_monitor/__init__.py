from pyairtable import Api

from content_monitor.config import load_settings


def main() -> None:
    settings = load_settings()

    api = Api(settings.airtable_token)
    pages = api.table(settings.airtable_base_id, "Pages")

    records = pages.all(formula="{Active}")

    print(f"Found {len(records)} active page(s):")
    for record in records:
        fields = record["fields"]
        print(f"    {fields.get('Name', '(no name)')}: {fields.get('URL')}")

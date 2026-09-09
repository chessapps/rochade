import json
import pathlib

from rochade.app import create_app

pathlib.Path("openapi.json").write_text(
    json.dumps(create_app().openapi(), indent=2), encoding="utf-8"
)
print("wrote openapi.json")

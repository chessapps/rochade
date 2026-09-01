"""The use cases, one folder per REST resource.

The folder layout follows the API surface, so a route and the file that serves
it are found the same way:

    /api/tournaments                  tournaments/
    /api/tournaments/{id}/imports     imports/
    /api/tournaments/{id}/boards      boards/
    /api/tournaments/{id}/queue       queue/
    /api/tournaments/{id}/devices     devices/
    /api/rounds/{id}                  rounds/
    /api/games/{id}                   games/

Each file holds one use case whole: its request model, its handler and its
route. The command/query split is still real -- it decides whether a message
runs in a transaction, whether it dedupes on an idempotency key, and what it is
allowed to touch -- but it is carried by the `Command` and `Query` base classes
rather than by which folder a file sits in. That way `preview_import` and
`import_round`, which are one workflow for the arbiter and share a plan
builder, live next to each other.

`audit.py`, `locking.py` and `scoping.py` sit here at the root: shared
mechanics, named for what they do, used across several features.
"""

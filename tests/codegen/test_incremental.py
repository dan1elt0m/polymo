from __future__ import annotations

import json

from polymo.config import IncrementalConfig
from tests.codegen.helpers import make_config, run_generated


def test_incremental_reads_and_writes_state(http_server, tmp_path):
    state_file = tmp_path / "state.json"

    def route(query, headers, body):
        since = query.get("since")
        if since is None:
            return 200, [{"id": 1, "updated": "2026-01-01"}], {}
        assert since == "2026-01-01"
        return 200, [{"id": 2, "updated": "2026-02-01"}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        incremental=IncrementalConfig(
            mode="cursor", cursor_param="since", cursor_field="updated"
        ),
    )
    module = run_generated(config, override_globals={"STATE_PATH": str(state_file)})

    list(module.fetch_records())
    module._write_state(module.LAST_CURSOR["value"])
    assert json.loads(state_file.read_text()) == {"cursor": "2026-01-01"}

    module2 = run_generated(config, override_globals={"STATE_PATH": str(state_file)})
    assert list(module2.fetch_records()) == [{"id": 2, "updated": "2026-02-01"}]

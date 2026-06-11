"""The DeltaStream MCP live path: result parsing + attribution arithmetic."""
from attribution_agent.agent.deltastream_mcp import _parse_rpc_body, _rows_from_result
from attribution_agent.agent.reporting import BoardPackData, _attribution_from_context


def test_parse_rpc_body_handles_sse_and_json():
    sse = ('event: message\n'
           'data: {"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"mv_x"}]}}\n\n')
    assert _parse_rpc_body(sse, "text/event-stream", 2)["result"]["tools"][0]["name"] == "mv_x"
    # picks the frame matching the rpc id when several are present
    multi = ('data: {"id":1,"result":"a"}\n\n'
             'data: {"id":2,"result":"b"}\n\n')
    assert _parse_rpc_body(multi, "text/event-stream", 2)["result"] == "b"
    # plain JSON
    assert _parse_rpc_body('{"id":5,"result":{"ok":true}}', "application/json", 5)["result"] == {"ok": True}
    # empty / garbage
    assert _parse_rpc_body("", "application/json", 1) is None
    assert _parse_rpc_body("not json", "application/json", 1) is None


def test_rows_parser_handles_mcp_shapes():
    # structuredContent.rows
    assert _rows_from_result({"structuredContent": {"rows": [{"a": 1}]}}) == [{"a": 1}]
    # bare rows
    assert _rows_from_result({"rows": [{"b": 2}]}) == [{"b": 2}]
    # generic text content carrying JSON
    got = _rows_from_result({"content": [{"type": "text", "text": '[{"c": 3}]'}]})
    assert got == [{"c": 3}]
    # bare list + empty
    assert _rows_from_result([{"d": 4}]) == [{"d": 4}]
    assert _rows_from_result(None) == []


def test_attribution_distributes_full_revenue_under_every_model():
    won = [
        {"account_id": "A", "revenue": 100, "close_time": "2026-03-10T00:00:00"},
        {"account_id": "B", "revenue": 200, "close_time": "2026-03-10T00:00:00"},
    ]
    dist = [
        {"account_id": "A", "channel": "Paid Search", "touch_count": 2,
         "last_touch_time": "2026-03-09T00:00:00"},   # most recent on A
        {"account_id": "A", "channel": "Email Nurture", "touch_count": 1,
         "last_touch_time": "2026-02-28T00:00:00"},
        {"account_id": "B", "channel": "Outbound SDR", "touch_count": 3,
         "last_touch_time": "2026-03-08T00:00:00"},
    ]
    attr, deals = _attribution_from_context(dist, won)

    # Every model distributes exactly the $300 of won revenue.
    for model in ("last_touch", "linear", "time_decay"):
        total = sum(getattr(a, model) for a in attr.values())
        assert round(total, 2) == 300.0

    # Last touch: A -> Paid Search (100), B -> Outbound SDR (200); deal credit too.
    assert attr["Paid Search"].last_touch == 100
    assert attr["Outbound SDR"].last_touch == 200
    assert deals == {"Paid Search": 1, "Outbound SDR": 1}

    # Linear splits A by touch share (2/3, 1/3).
    assert round(attr["Paid Search"].linear, 2) == round(100 * 2 / 3, 2)
    assert round(attr["Email Nurture"].linear, 2) == round(100 * 1 / 3, 2)


class _FakeMCP:
    """Minimal stand-in exposing query_view for BoardPackData.from_mcp."""
    def __init__(self, data: dict):
        self._data = data

    def query_view(self, key, arguments=None):
        return self._data.get(key, [])


def test_from_mcp_builds_board_pack():
    fake = _FakeMCP({
        "spend_by_channel": [
            {"channel": "Paid Search", "spend": 50},
            {"channel": "Outbound SDR", "spend": 80},
        ],
        "funnel_by_category": [
            {"program_category": "Paid Search", "touches": 100, "conversations": 10,
             "mqls": 5, "sqls": 3, "opps": 2, "won": 1},
        ],
        "channel_touch_distribution": [
            {"account_id": "A", "channel": "Paid Search", "touch_count": 1,
             "last_touch_time": "2026-03-09T00:00:00"},
            {"account_id": "B", "channel": "Outbound SDR", "touch_count": 1,
             "last_touch_time": "2026-03-08T00:00:00"},
        ],
        "won_revenue_by_account": [
            {"account_id": "A", "revenue": 100, "close_time": "2026-03-10T00:00:00"},
            {"account_id": "B", "revenue": 200, "close_time": "2026-03-10T00:00:00"},
        ],
    })
    d = BoardPackData.from_mcp(fake, "Acme Cloud", "2026-Q1")
    assert d.total_attributed == 300
    assert d.won_deals == 2
    assert {c.channel for c in d.channels} == {"Paid Search", "Outbound SDR"}
    ps = d.channel_attr("Paid Search")
    assert ps.last_touch == 100

import types
from tools import verifier as vmod


class DummyRPC:
    def __init__(self, ret):
        self._ret = ret
    def execute(self):
        return types.SimpleNamespace(data=self._ret)


def test_verify_numbers_update_ok(monkeypatch):
    # Mock sb.rpc to return known values
    def fake_rpc(name, payload):
        assert name == "get_numbers_table_values"
        return DummyRPC({
            "B5": {"value": "3000"},
            "C5": {"value": "15"},
            "D5": {"value": "450.0"},
            "E5": {"value": "3450.0"},
        })
    monkeypatch.setattr(vmod, "sb", types.SimpleNamespace(rpc=fake_rpc, postgrest=types.SimpleNamespace(schema="public")))
    res = vmod.verify_numbers_update("prop", "R2B", "B5", "3000", {"D5": "450.0", "E5": "3450.0"})
    assert res["ok"] is True


def test_verify_numbers_update_issue(monkeypatch):
    def fake_rpc(name, payload):
        return DummyRPC({"B5": {"value": "2999"}})
    monkeypatch.setattr(vmod, "sb", types.SimpleNamespace(rpc=fake_rpc, postgrest=types.SimpleNamespace(schema="public")))
    res = vmod.verify_numbers_update("prop", "R2B", "B5", "3000", {"D5": "abc"})
    assert res["ok"] is False
    assert any("B5 mismatch" in s or "not numeric" in s for s in res["issues"])


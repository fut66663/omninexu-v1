"""Tests for scripts/verify/verify_context.py.

The module has module-level code that calls SessionLocal() and
CompanyContextService.build_context() on import.  We test the
_FakeVerifyCache behaviour via a standalone copy so we never
trigger the module-level side effects.
"""

import json

# ── Standalone copy of _FakeVerifyCache for unit tests ──────────────

class _FakeVerifyCache:
    """Standalone copy — identical behaviour, no module-level side effects."""

    def __init__(self):
        self._store: dict[str, str] = {}

    def get_json(self, key: str):
        v = self._store.get(key)
        return json.loads(v) if v else None

    def set_json(self, key: str, value, ttl: int = 0):
        self._store[key] = json.dumps(value, default=str)

    def delete(self, key: str):
        self._store.pop(key, None)


class TestFakeVerifyCache:
    def test_get_json_returns_none_when_missing(self):
        cache = _FakeVerifyCache()
        assert cache.get_json("missing") is None

    def test_get_json_returns_parsed_value(self):
        cache = _FakeVerifyCache()
        cache.set_json("key", {"a": 1, "b": 2})
        result = cache.get_json("key")
        assert result == {"a": 1, "b": 2}

    def test_set_json_persists_across_calls(self):
        cache = _FakeVerifyCache()
        cache.set_json("k1", [1, 2])
        cache.set_json("k2", {"x": "y"})
        assert cache.get_json("k1") == [1, 2]
        assert cache.get_json("k2") == {"x": "y"}

    def test_delete_removes_key(self):
        cache = _FakeVerifyCache()
        cache.set_json("key", "data")
        cache.delete("key")
        assert cache.get_json("key") is None

    def test_delete_missing_key_noop(self):
        cache = _FakeVerifyCache()
        cache.delete("phantom")

    def test_overwrite_updates_value(self):
        cache = _FakeVerifyCache()
        cache.set_json("key", "old")
        cache.set_json("key", "new")
        assert cache.get_json("key") == "new"

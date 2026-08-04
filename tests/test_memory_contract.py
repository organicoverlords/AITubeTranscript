from __future__ import annotations

from aitubetranscript.memory_contract import (
    MEMORY_CONTRACT_VERSION,
    check_memory_contract,
)
from aitubetranscript.storage_common import write_json


def _write_manifests(durable, volatile) -> None:
    write_json(
        durable / "memory" / "bank-manifest.json",
        {
            "schema_version": "3.0",
            "storage_class": "DURABLE_POINTER_INDEX",
            "volatile_branch": "aitube-volatile",
        },
    )
    write_json(
        volatile / "memory" / "bank-manifest.json",
        {
            "schema_version": "3.0",
            "storage_class": "VOLATILE_API_MEMORY_INDEX",
            "durable_branch": "aitube-durable",
        },
    )


def test_memory_contract_current(tmp_path):
    durable = tmp_path / "durable"
    volatile = tmp_path / "volatile"
    _write_manifests(durable, volatile)
    result = check_memory_contract(
        durable,
        volatile,
        saved_contract_version=MEMORY_CONTRACT_VERSION,
    )
    assert result["status"] == "MEMORY_CONTRACT_CURRENT"
    assert result["failure_codes"] == []


def test_memory_contract_detects_stale_saved_routing(tmp_path):
    durable = tmp_path / "durable"
    volatile = tmp_path / "volatile"
    _write_manifests(durable, volatile)
    result = check_memory_contract(
        durable,
        volatile,
        saved_contract_version="legacy-aitube-results-v1",
    )
    assert result["status"] == "MEMORY_CONTRACT_STALE"
    assert result["use_live_layout_even_when_saved_memory_is_stale"] is True


def test_memory_contract_rejects_legacy_live_layout(tmp_path):
    durable = tmp_path / "durable"
    volatile = tmp_path / "volatile"
    write_json(durable / "memory" / "bank-manifest.json", {"schema_version": "1.0"})
    write_json(volatile / "memory" / "bank-manifest.json", {"schema_version": "1.0"})
    result = check_memory_contract(durable, volatile)
    assert result["status"] == "MEMORY_CONTRACT_INVALID"
    assert "DURABLE_MEMORY_SCHEMA_UNSUPPORTED" in result["failure_codes"]

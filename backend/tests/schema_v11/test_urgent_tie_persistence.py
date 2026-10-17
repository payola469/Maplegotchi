"""Future urgent providers cannot weaken the existing saved-layout S14 gate.

Positive urgent tie/counter behavior is covered by pure resolution specimens;
current persisted S14 mappings admit only one provider per urgent response.
"""

import json
from copy import deepcopy

import pytest

from maplegotchi.persistence.layout_codec import V11LayoutFormatError, encode_layout_document
from tests.schema_v11.restart_worker import resources


def test_extra_urgent_provider_requires_explicit_s14_contract_extension() -> None:
    catalog, context, document = resources()
    wire = json.loads(document.canonical_bytes)
    host = deepcopy(next(h for h in wire["instances"] if h["id"] == "desk.computer"))
    host.update(id="fixture.extra", room="work_studio", origin=[35, 6])
    wire["instances"].append(host)
    with pytest.raises(V11LayoutFormatError) as error:
        encode_layout_document(
            wire,
            catalog_version=1,
            catalog_hash=catalog.catalog_hash,
            snapshots=(catalog,),
            context=context,
        )
    assert error.value.rules == ("S14",)

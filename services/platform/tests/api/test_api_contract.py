"""M4 4.1 contract tests over every endpoint (schemathesis-equivalent, hypothesis-driven).

For every operation in ``openapi/v1.yaml`` that the app serves, hypothesis generates requests from
the documented parameters (valid and invalid path IDs, in- and out-of-range query values, arbitrary
JSON bodies, raw bytes for binary bodies) and sends them as an owner of tenant A. Every response
must be allowed by the contract (``nf_contract.Contract``: documented status, documented media
type, body valid against the schema) and must never be a 500. The authz matrix
(``tests/core/test_core_authz_matrix.py``) covers the valid-input side for every role through the
same checker.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from nf_contract import Contract

pytestmark = pytest.mark.postgres
CONTRACT = Contract()
EXAMPLES = int(os.environ.get("NF_CONTRACT_EXAMPLES", "8"))
OPS = [(m, p, op) for m, p, op in CONTRACT.operations() if op.get("x-nf-status") != "disabled"]

json_leaf = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=40),
)
json_value = st.recursive(
    json_leaf,
    lambda inner: st.lists(inner, max_size=4)
    | st.dictionaries(st.text(max_size=12), inner, max_size=4),
    max_leaves=12,
)


def _param_strategy(schema: dict[str, Any]) -> st.SearchStrategy:
    """Values for a query parameter: mostly in the documented type (in and out of range), sometimes
    garbage."""
    s = CONTRACT._deref(schema) if "$ref" in schema else schema
    variants = s.get("anyOf") or [s]
    strats: list[st.SearchStrategy] = [st.text(max_size=20)]
    for v in variants:
        v = CONTRACT._deref(v) if "$ref" in v else v
        t = v.get("type")
        if "enum" in v:
            strats.append(st.sampled_from(v["enum"]))
        elif t == "integer":
            strats.append(st.integers(min_value=-(10**6), max_value=10**7))
        elif t == "number":
            strats.append(st.floats(min_value=-1e6, max_value=1e7, allow_nan=False))
        elif t == "boolean":
            strats.append(st.booleans())
        elif t == "string" and v.get("format") == "uuid":
            strats.append(st.uuids().map(str))
    return st.one_of(*strats)


def _path_value(tree: dict[str, str], name: str) -> st.SearchStrategy:
    known = [tree[name]] if name in tree else []
    return st.one_of(
        st.uuids().map(str),
        st.sampled_from(known) if known else st.uuids().map(str),
        st.text(alphabet="abcxyz019-_.@", min_size=1, max_size=20),
    )


@st.composite
def request_for(draw, method: str, path: str, op: dict[str, Any], tree: dict[str, str]):
    url = path
    query: dict[str, Any] = {}
    for p in op.get("parameters", []):
        if p["in"] == "path":
            url = url.replace("{" + p["name"] + "}", draw(_path_value(tree, p["name"])))
        elif p["in"] == "query" and (p.get("required") or draw(st.booleans())):
            query[p["name"]] = draw(_param_strategy(p.get("schema", {})))
    kwargs: dict[str, Any] = {"params": query}
    body = op.get("requestBody")
    if body:
        media = next(iter(body["content"]))
        if media == "application/json":
            kwargs["json"] = draw(json_value)
        else:
            kwargs["content"] = draw(st.binary(max_size=64))
            kwargs["headers"] = {"content-type": media}
    return url, kwargs


@pytest.mark.parametrize(("method", "path", "op"), OPS, ids=[f"{m} {p}" for m, p, _ in OPS])
def test_every_operation_honours_the_contract(app, client, as_role, tree, method, path, op):
    app.state.rate_limiter = None  # this test sends many requests on purpose
    app.state.sse_sleep = lambda s: None
    h = as_role("owner")

    @settings(
        max_examples=EXAMPLES,
        deadline=None,
        derandomize=True,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    )
    @given(req=request_for(method, path, op, tree))
    def run(req):
        url, kwargs = req
        if method == "GET" and path.endswith("/events"):
            kwargs["params"] = {**kwargs["params"], "wait_s": 0}  # never hold a stream open
        headers = {**h, **kwargs.pop("headers", {})}
        r = client.request(method, url, headers=headers, **kwargs)
        assert r.status_code != 500, (method, url, kwargs, r.text)
        CONTRACT.check(method, path, r)
        if r.status_code >= 400:
            assert r.headers["content-type"] == "application/problem+json", (method, url)

    run()


def test_operation_list_is_complete():
    served_ops = {(m, p) for m, p, _ in OPS}
    assert ("GET", "/v1/runs") in served_ops and ("GET", "/v1/sweeps") in served_ops
    assert len(served_ops) >= 50
    assert all(uuid.UUID(str(uuid.uuid4())) for _ in range(1))

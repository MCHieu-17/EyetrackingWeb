import uuid

import pytest

from tests.conftest import create_user, login


async def _admin_headers(client) -> dict[str, str]:
    email = f"admin-db-{uuid.uuid4().hex[:8]}@example.com"
    await create_user(email=email, role="admin")
    token = await login(client, email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_db_schema_requires_admin(client):
    email = f"student-db-{uuid.uuid4().hex[:8]}@example.com"
    await create_user(email=email)
    token = await login(client, email)
    response = await client.get("/admin/db/schema", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_admin_db_schema_returns_tables(client):
    headers = await _admin_headers(client)
    response = await client.get("/admin/db/schema", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "tables" in payload
    assert "generatedAt" in payload
    names = {table["name"] for table in payload["tables"]}
    assert "users" in names
    assert "courses" in names
    users = next(table for table in payload["tables"] if table["name"] == "users")
    assert users["kind"] == "table"
    assert any(column["name"] == "email" for column in users["columns"])
    assert any(column["primaryKey"] for column in users["columns"])


@pytest.mark.asyncio
async def test_admin_db_query_select(client):
    headers = await _admin_headers(client)
    response = await client.post(
        "/admin/db/query",
        headers=headers,
        json={"sql": "SELECT 1 AS one, 'x' AS text", "maxRows": 10},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert [column["name"] for column in payload["columns"]] == ["one", "text"]
    assert payload["rows"] == [[1, "x"]]
    assert payload["rowCount"] == 1
    assert payload["truncated"] is False
    assert payload["limit"] == 10


@pytest.mark.asyncio
async def test_admin_db_query_preserves_large_bigint(client):
    headers = await _admin_headers(client)
    response = await client.post(
        "/admin/db/query",
        headers=headers,
        json={
            "sql": "SELECT 9007199254740993::bigint AS big",
            "maxRows": 10,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["rows"] == [["9007199254740993"]]


@pytest.mark.asyncio
async def test_admin_db_query_requires_admin(client):
    email = f"student-db-{uuid.uuid4().hex[:8]}@example.com"
    await create_user(email=email)
    token = await login(client, email)
    response = await client.post(
        "/admin/db/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"sql": "SELECT 1", "maxRows": 10},
    )
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_admin_db_query_rejects_write(client):
    headers = await _admin_headers(client)
    response = await client.post(
        "/admin/db/query",
        headers=headers,
        json={"sql": "INSERT INTO roles (code) VALUES ('x')", "maxRows": 10},
    )
    assert response.status_code == 400, response.text
    assert "SELECT" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_db_query_rejects_multiple_statements(client):
    headers = await _admin_headers(client)
    response = await client.post(
        "/admin/db/query",
        headers=headers,
        json={"sql": "SELECT 1; SELECT 2;", "maxRows": 10},
    )
    assert response.status_code == 400, response.text
    assert "một câu lệnh" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_db_query_rejects_ddl(client):
    headers = await _admin_headers(client)
    response = await client.post(
        "/admin/db/query",
        headers=headers,
        json={"sql": "DROP TABLE users", "maxRows": 10},
    )
    assert response.status_code == 400, response.text


@pytest.mark.asyncio
async def test_admin_db_query_row_limit(client):
    headers = await _admin_headers(client)
    response = await client.post(
        "/admin/db/query",
        headers=headers,
        json={"sql": "SELECT generate_series(1, 10) AS n", "maxRows": 5},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["rowCount"] == 5
    assert payload["truncated"] is True
    assert payload["limit"] == 5
    assert len(payload["rows"]) == 5


@pytest.mark.asyncio
async def test_admin_db_query_sql_error(client):
    headers = await _admin_headers(client)
    response = await client.post(
        "/admin/db/query",
        headers=headers,
        json={"sql": "SELECT * FROM does_not_exist", "maxRows": 10},
    )
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "42P01"
    assert detail["message"]


@pytest.mark.asyncio
async def test_admin_db_query_rejects_dangerous_function(client):
    headers = await _admin_headers(client)
    response = await client.post(
        "/admin/db/query",
        headers=headers,
        json={
            "sql": "SELECT set_config('statement_timeout', '0', false)",
            "maxRows": 10,
        },
    )
    assert response.status_code == 400, response.text
    assert "set_config" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_db_query_blocks_sequence_write(client):
    headers = await _admin_headers(client)
    response = await client.post(
        "/admin/db/query",
        headers=headers,
        json={"sql": "SELECT nextval('roles_id_seq')", "maxRows": 10},
    )
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    # Role read-only không có quyền sequence; nếu có thì transaction read-only
    # sẽ chặn với 25006.
    assert detail["code"] in {"25006", "42501"}


@pytest.mark.asyncio
async def test_admin_db_query_rejects_data_modifying_cte(client):
    headers = await _admin_headers(client)
    response = await client.post(
        "/admin/db/query",
        headers=headers,
        json={
            "sql": ("WITH deleted AS (DELETE FROM roles RETURNING *) SELECT * FROM deleted"),
            "maxRows": 10,
        },
    )
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert detail["code"] in {"0A000", "25006"}


@pytest.mark.asyncio
async def test_admin_db_query_validation(client):
    headers = await _admin_headers(client)

    empty = await client.post(
        "/admin/db/query",
        headers=headers,
        json={"sql": "", "maxRows": 10},
    )
    assert empty.status_code == 422, empty.text

    too_many = await client.post(
        "/admin/db/query",
        headers=headers,
        json={"sql": "SELECT 1", "maxRows": 501},
    )
    assert too_many.status_code == 422, too_many.text

    zero = await client.post(
        "/admin/db/query",
        headers=headers,
        json={"sql": "SELECT 1", "maxRows": 0},
    )
    assert zero.status_code == 422, zero.text


# ---------------------------------------------------------------------------
# Phase 2 — duyệt bảng
# ---------------------------------------------------------------------------


async def _create_browse_users(prefix: str, count: int = 3) -> list[str]:
    emails: list[str] = []
    for index in range(count):
        email = f"{prefix}-{index}@example.com"
        await create_user(email=email)
        emails.append(email)
    return emails


async def _browse(client, headers, table: str, payload: dict):
    return await client.post(
        f"/admin/db/tables/{table}/rows",
        headers=headers,
        json=payload,
    )


@pytest.mark.asyncio
async def test_admin_db_browse_table_requires_admin(client):
    email = f"student-browse-{uuid.uuid4().hex[:8]}@example.com"
    await create_user(email=email)
    token = await login(client, email)
    response = await client.post(
        "/admin/db/tables/users/rows",
        headers={"Authorization": f"Bearer {token}"},
        json={"schema": "public", "limit": 10},
    )
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_admin_db_browse_table_returns_rows(client):
    prefix = f"browse-{uuid.uuid4().hex[:8]}"
    emails = await _create_browse_users(prefix, 3)
    headers = await _admin_headers(client)

    response = await _browse(
        client,
        headers,
        "users",
        {
            "schema": "public",
            "columns": ["id", "email"],
            "limit": 2,
            "offset": 0,
            "orderBy": "email",
            "orderDir": "asc",
            "filters": [{"column": "email", "operator": "contains", "value": prefix}],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert [column["name"] for column in payload["columns"]] == [
        "id",
        "email",
    ]
    assert payload["rowCount"] == 2
    assert payload["hasMore"] is True
    assert payload["limit"] == 2
    assert payload["offset"] == 0
    assert all(row[1].startswith(prefix) for row in payload["rows"])
    assert sorted(row[1] for row in payload["rows"]) == emails[:2]


@pytest.mark.asyncio
async def test_admin_db_browse_table_pagination(client):
    prefix = f"browse-{uuid.uuid4().hex[:8]}"
    await _create_browse_users(prefix, 3)
    headers = await _admin_headers(client)

    response = await _browse(
        client,
        headers,
        "users",
        {
            "schema": "public",
            "columns": ["email"],
            "limit": 2,
            "offset": 2,
            "orderBy": "email",
            "orderDir": "asc",
            "filters": [{"column": "email", "operator": "contains", "value": prefix}],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["rowCount"] == 1
    assert payload["hasMore"] is False
    assert payload["offset"] == 2


@pytest.mark.asyncio
async def test_admin_db_browse_table_filters(client):
    prefix = f"browse-{uuid.uuid4().hex[:8]}"
    emails = await _create_browse_users(prefix, 3)
    headers = await _admin_headers(client)

    exact = await _browse(
        client,
        headers,
        "users",
        {
            "schema": "public",
            "columns": ["email"],
            "limit": 10,
            "filters": [{"column": "email", "operator": "eq", "value": emails[0]}],
        },
    )
    assert exact.status_code == 200, exact.text
    assert exact.json()["rowCount"] == 1
    assert exact.json()["rows"][0][0] == emails[0]

    starts = await _browse(
        client,
        headers,
        "users",
        {
            "schema": "public",
            "columns": ["email"],
            "limit": 10,
            "filters": [
                {
                    "column": "email",
                    "operator": "starts_with",
                    "value": prefix,
                }
            ],
        },
    )
    assert starts.status_code == 200, starts.text
    assert starts.json()["rowCount"] == 3

    not_null = await _browse(
        client,
        headers,
        "users",
        {
            "schema": "public",
            "columns": ["email"],
            "limit": 10,
            "filters": [{"column": "email", "operator": "is_not_null"}],
        },
    )
    assert not_null.status_code == 200, not_null.text
    assert not_null.json()["rowCount"] > 0


@pytest.mark.asyncio
async def test_admin_db_browse_table_order(client):
    prefix = f"browse-{uuid.uuid4().hex[:8]}"
    emails = await _create_browse_users(prefix, 3)
    headers = await _admin_headers(client)

    response = await _browse(
        client,
        headers,
        "users",
        {
            "schema": "public",
            "columns": ["email"],
            "limit": 10,
            "orderBy": "email",
            "orderDir": "desc",
            "filters": [{"column": "email", "operator": "contains", "value": prefix}],
        },
    )
    assert response.status_code == 200, response.text
    result_emails = [row[0] for row in response.json()["rows"]]
    assert result_emails == sorted(emails, reverse=True)


@pytest.mark.asyncio
async def test_admin_db_browse_table_rejects_unknown_table(client):
    headers = await _admin_headers(client)
    response = await _browse(
        client,
        headers,
        "does_not_exist",
        {"schema": "public", "limit": 10},
    )
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_admin_db_browse_table_rejects_unknown_column(client):
    headers = await _admin_headers(client)
    response = await _browse(
        client,
        headers,
        "users",
        {
            "schema": "public",
            "columns": ["password_hash"],
            "limit": 10,
        },
    )
    assert response.status_code == 400, response.text
    assert "password_hash" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_db_browse_table_rejects_unknown_filter_column(client):
    headers = await _admin_headers(client)
    response = await _browse(
        client,
        headers,
        "users",
        {
            "schema": "public",
            "limit": 10,
            "filters": [
                {
                    "column": "password_hash",
                    "operator": "eq",
                    "value": "x",
                }
            ],
        },
    )
    assert response.status_code == 400, response.text


@pytest.mark.asyncio
async def test_admin_db_browse_table_rejects_missing_filter_value(client):
    headers = await _admin_headers(client)
    response = await _browse(
        client,
        headers,
        "users",
        {
            "schema": "public",
            "limit": 10,
            "filters": [{"column": "email", "operator": "eq"}],
        },
    )
    assert response.status_code == 400, response.text
    assert "Vui lòng nhập giá trị" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_db_browse_table_rejects_auth_sessions(client):
    headers = await _admin_headers(client)
    response = await _browse(
        client,
        headers,
        "auth_sessions",
        {"schema": "public", "limit": 10},
    )
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_admin_db_browse_table_rejects_sql_injection(client):
    headers = await _admin_headers(client)

    table = await _browse(
        client,
        headers,
        "users; DROP TABLE users",
        {"schema": "public", "limit": 10},
    )
    assert table.status_code == 404, table.text

    column = await _browse(
        client,
        headers,
        "users",
        {
            "schema": "public",
            "columns": ["id; DROP TABLE users"],
            "limit": 10,
        },
    )
    assert column.status_code == 400, column.text

    order = await _browse(
        client,
        headers,
        "users",
        {
            "schema": "public",
            "orderBy": "id; DROP TABLE users",
            "limit": 10,
        },
    )
    assert order.status_code == 400, order.text


@pytest.mark.asyncio
async def test_admin_db_browse_table_filter_value_is_bound(client):
    headers = await _admin_headers(client)
    response = await _browse(
        client,
        headers,
        "users",
        {
            "schema": "public",
            "columns": ["email"],
            "limit": 10,
            "filters": [
                {
                    "column": "email",
                    "operator": "contains",
                    "value": "' OR 1=1 --",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["rowCount"] == 0


@pytest.mark.asyncio
async def test_admin_db_browse_table_defaults_to_all_columns(client):
    headers = await _admin_headers(client)
    response = await _browse(
        client,
        headers,
        "users",
        {"schema": "public", "limit": 10},
    )
    assert response.status_code == 200, response.text
    columns = [column["name"] for column in response.json()["columns"]]
    assert "id" in columns
    assert "email" in columns
    assert "password_hash" not in columns


@pytest.mark.asyncio
async def test_admin_db_browse_table_is_null_filter(client):
    headers = await _admin_headers(client)
    response = await _browse(
        client,
        headers,
        "users",
        {
            "schema": "public",
            "columns": ["id", "email", "deleted_at"],
            "limit": 10,
            "filters": [{"column": "deleted_at", "operator": "is_null"}],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["rowCount"] > 0


@pytest.mark.asyncio
async def test_admin_db_browse_table_validation(client):
    headers = await _admin_headers(client)
    invalid_payloads = [
        {"schema": "public", "limit": 0},
        {"schema": "public", "limit": 201},
        {"schema": "public", "offset": -1},
        {"schema": "public", "orderDir": "sideways"},
        {
            "schema": "public",
            "filters": [{"column": "email", "operator": "drop", "value": "x"}],
        },
    ]
    for payload in invalid_payloads:
        response = await _browse(client, headers, "users", payload)
        assert response.status_code == 422, response.text

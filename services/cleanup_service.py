import re
from collections import Counter
from typing import Dict, List

from psycopg2.extras import RealDictCursor

from db import get_connection


_ALLOWED_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def parse_ids(raw_text: str) -> List[str]:
    if not raw_text:
        return []

    tokens = [token for token in re.split(r"[\s,;]+", raw_text.strip()) if token]
    if not tokens:
        return []

    valid_ids: List[str] = []
    invalid_tokens: List[str] = []

    for token in tokens:
        if _ALLOWED_ID_PATTERN.match(token):
            valid_ids.append(token)
        else:
            invalid_tokens.append(token)

    if invalid_tokens:
        sample = ", ".join(invalid_tokens[:5])
        raise ValueError(f"Invalid IDs detected: {sample}")

    # Keep insertion order while removing duplicates.
    deduped = list(dict.fromkeys(valid_ids))
    return deduped


def get_sites_by_customer_ids(customer_ids: List[str]) -> List[Dict]:
    query = """
        SELECT
            "Id" AS site_id,
            "Name" AS site_name,
            "RootNodeId" AS customer_id
        FROM consup."Nodes"
        WHERE "RootNodeId"::text = ANY(%s)
          AND "Type" = 'Site'
        ORDER BY "RootNodeId", "Name";
    """

    conn = get_connection("CONSUP")
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (customer_ids,))
            return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def preview_models_data(site_ids: List[str], entity_ids: List[str], customer_ids: List[str]) -> Dict:
    # Requested behavior: entity IDs are treated as site IDs in RBM flow.
    effective_entity_ids = entity_ids or list(site_ids)

    select_properties_by_site_sql = """
        SELECT *
        FROM public.properties
        WHERE "entityid" IN (
            SELECT id
            FROM public.elements
            WHERE "siteid"::text = %s
        );
    """

    select_properties_by_entity_sql = """
        SELECT *
        FROM public.properties
        WHERE "entityid"::text = %s;
    """

    select_elements_by_site_sql = """
        SELECT *
        FROM public.elements
        WHERE "siteid"::text = %s;
    """

    select_spatial_elements_sql = """
        SELECT *
        FROM public."spatialelements"
        WHERE "siteid"::text = ANY(%s);
    """

    select_nodes_by_customer_sql = """
        SELECT *
        FROM consup."Nodes"
        WHERE "RootNodeId"::text = ANY(%s)
        ORDER BY "RootNodeId", "Name";
    """

    select_registrations_by_site_sql = """
        SELECT *
        FROM public."SystemRegistrations"
        WHERE "SiteId"::text = %s;
    """

    select_authorizations_sql = """
        SELECT *
        FROM consup."Authorizations"
        WHERE "OrganisationId"::text = ANY(%s);
    """

    models_conn = get_connection("MODELS")
    tools_conn = get_connection("TOOLSCOMMISSIONING")
    authorization_conn = get_connection("AUTHORIZATION")
    consup_conn = get_connection("CONSUP")
    result = {
        "properties_by_site": [],
        "properties_by_entity": [],
        "elements_by_site": [],
        "spatial_elements_by_site": [],
        "registrations_by_site": [],
        "authorizations_by_site": [],
        "nodes_by_customer": [],
    }

    try:
        with (
            models_conn.cursor(cursor_factory=RealDictCursor) as models_cursor,
            tools_conn.cursor(cursor_factory=RealDictCursor) as tools_cursor,
            authorization_conn.cursor(cursor_factory=RealDictCursor) as authorization_cursor,
            consup_conn.cursor(cursor_factory=RealDictCursor) as consup_cursor,
        ):
            # MODELS preview order:
            # 1) properties by site
            for site_id in site_ids:
                models_cursor.execute(select_properties_by_site_sql, (site_id,))
                properties_rows = [dict(row) for row in models_cursor.fetchall()]

                result["properties_by_site"].append(
                    {
                        "site_id": site_id,
                        "count": len(properties_rows),
                        "rows": properties_rows,
                    }
                )

            # 2) properties by entity
            for entity_id in effective_entity_ids:
                models_cursor.execute(select_properties_by_entity_sql, (entity_id,))
                properties_rows = [dict(row) for row in models_cursor.fetchall()]
                result["properties_by_entity"].append(
                    {
                        "entity_id": entity_id,
                        "count": len(properties_rows),
                        "rows": properties_rows,
                    }
                )

            # 3) elements by site
            for site_id in site_ids:
                models_cursor.execute(select_elements_by_site_sql, (site_id,))
                elements_rows = [dict(row) for row in models_cursor.fetchall()]
                result["elements_by_site"].append(
                    {
                        "site_id": site_id,
                        "count": len(elements_rows),
                        "rows": elements_rows,
                    }
                )

            # 4) spatial elements by site
            spatial_rows_by_site: Dict[str, List[Dict]] = {site_id: [] for site_id in site_ids}
            if site_ids:
                models_cursor.execute(select_spatial_elements_sql, (site_ids,))
                all_spatial_rows = [dict(row) for row in models_cursor.fetchall()]
                for row in all_spatial_rows:
                    site_id = str(row.get("siteid", ""))
                    if site_id in spatial_rows_by_site:
                        spatial_rows_by_site[site_id].append(row)

            for site_id in site_ids:
                spatial_rows = spatial_rows_by_site.get(site_id, [])
                result["spatial_elements_by_site"].append(
                    {
                        "site_id": site_id,
                        "count": len(spatial_rows),
                        "rows": spatial_rows,
                    }
                )

            # ToolsCommissioning preview by site
            for site_id in site_ids:
                tools_cursor.execute(select_registrations_by_site_sql, (site_id,))
                registration_rows = [dict(row) for row in tools_cursor.fetchall()]
                result["registrations_by_site"].append(
                    {
                        "site_id": site_id,
                        "count": len(registration_rows),
                        "rows": registration_rows,
                    }
                )

            # Authorization preview by site (must run after ToolsCommissioning preview)
            auth_rows_by_site: Dict[str, List[Dict]] = {site_id: [] for site_id in site_ids}
            if site_ids:
                authorization_cursor.execute(select_authorizations_sql, (site_ids,))
                all_auth_rows = [dict(row) for row in authorization_cursor.fetchall()]
                for row in all_auth_rows:
                    site_id = str(row.get("OrganisationId", ""))
                    if site_id in auth_rows_by_site:
                        auth_rows_by_site[site_id].append(row)

            for site_id in site_ids:
                site_rows = auth_rows_by_site.get(site_id, [])
                result["authorizations_by_site"].append(
                    {
                        "site_id": site_id,
                        "count": len(site_rows),
                        "rows": site_rows,
                    }
                )

            if customer_ids:
                consup_cursor.execute(select_nodes_by_customer_sql, (customer_ids,))
                nodes_rows = [dict(row) for row in consup_cursor.fetchall()]
                for customer_id in customer_ids:
                    per_customer_rows = [
                        row for row in nodes_rows if str(row.get("RootNodeId")) == customer_id
                    ]
                    result["nodes_by_customer"].append(
                        {
                            "customer_id": customer_id,
                            "count": len(per_customer_rows),
                            "rows": per_customer_rows,
                        }
                    )

        return result
    finally:
        models_conn.close()
        tools_conn.close()
        authorization_conn.close()
        consup_conn.close()


def execute_cleanup(site_ids: List[str], entity_ids: List[str], customer_ids: List[str]) -> Dict:
    # Requested behavior: entity IDs are treated as site IDs in RBM flow.
    effective_entity_ids = entity_ids or list(site_ids)

    delete_properties_by_site_sql = """
        DELETE FROM public.properties
        WHERE "entityid" IN (
            SELECT id
            FROM public.elements
            WHERE "siteid"::text = %s
        );
    """

    delete_properties_by_entity_sql = """
        DELETE FROM public.properties
        WHERE "entityid"::text = %s;
    """

    delete_elements_sql = """
        DELETE FROM public.elements
        WHERE "siteid"::text = %s;
    """

    delete_spatial_elements_sql = """
        DELETE FROM public."spatialelements"
        WHERE "siteid"::text = ANY(%s)
        RETURNING "siteid"::text;
    """

    delete_registrations_sql = """
        DELETE FROM public."SystemRegistrations"
        WHERE "SiteId"::text = %s;
    """

    delete_authorizations_sql = """
        DELETE FROM consup."Authorizations"
        WHERE "OrganisationId"::text = ANY(%s)
        RETURNING "OrganisationId"::text;
    """

    delete_nodes_by_customer_sql = """
        DELETE FROM consup."Nodes"
        WHERE "RootNodeId"::text = ANY(%s);
    """

    models_conn = get_connection("MODELS")
    tools_conn = get_connection("TOOLSCOMMISSIONING")
    authorization_conn = get_connection("AUTHORIZATION")
    consup_conn = get_connection("CONSUP")
    models_conn.autocommit = False
    tools_conn.autocommit = False
    authorization_conn.autocommit = False
    consup_conn.autocommit = False

    site_rows = []
    entity_rows = []
    customer_rows = []
    totals = {
        "properties_deleted_by_site": 0,
        "properties_deleted_by_entity": 0,
        "elements_deleted": 0,
        "spatial_elements_deleted": 0,
        "registrations_deleted": 0,
        "authorizations_deleted": 0,
        "nodes_deleted": 0,
    }

    try:
        with (
            models_conn.cursor() as models_cursor,
            tools_conn.cursor() as tools_cursor,
            authorization_conn.cursor() as authorization_cursor,
            consup_conn.cursor() as consup_cursor,
        ):
            # SECURITY_NOTE: Enforce requested deletion order to avoid cross-db referential issues.
            # MODELS delete order:
            # 1) properties by site
            for site_id in site_ids:
                models_cursor.execute(delete_properties_by_site_sql, (site_id,))
                properties_deleted_by_site = models_cursor.rowcount

                site_rows.append(
                    {
                        "site_id": site_id,
                        "properties_deleted_by_site": properties_deleted_by_site,
                        "elements_deleted": 0,
                        "spatial_elements_deleted": 0,
                        "registrations_deleted": 0,
                        "authorizations_deleted": 0,
                    }
                )

                totals["properties_deleted_by_site"] += properties_deleted_by_site

            # 2) properties by entity
            for entity_id in effective_entity_ids:
                models_cursor.execute(delete_properties_by_entity_sql, (entity_id,))
                properties_deleted_by_entity = models_cursor.rowcount
                entity_rows.append(
                    {
                        "entity_id": entity_id,
                        "properties_deleted_by_entity": properties_deleted_by_entity,
                    }
                )
                totals["properties_deleted_by_entity"] += properties_deleted_by_entity

            # 3) elements by site
            site_row_by_id = {row["site_id"]: row for row in site_rows}
            for site_id in site_ids:
                models_cursor.execute(delete_elements_sql, (site_id,))
                elements_deleted = models_cursor.rowcount
                totals["elements_deleted"] += elements_deleted
                site_row_by_id[site_id]["elements_deleted"] = elements_deleted

            # 4) spatial elements by site
            if site_ids:
                models_cursor.execute(delete_spatial_elements_sql, (site_ids,))
                deleted_site_ids = [row[0] for row in models_cursor.fetchall()]
                spatial_counts_by_site = Counter(deleted_site_ids)
                totals["spatial_elements_deleted"] = len(deleted_site_ids)
                for site_id in site_ids:
                    site_row_by_id[site_id]["spatial_elements_deleted"] = spatial_counts_by_site.get(site_id, 0)

            # ToolsCommissioning DB cleanup
            for row in site_rows:
                site_id = row["site_id"]
                tools_cursor.execute(delete_registrations_sql, (site_id,))
                registrations_deleted = tools_cursor.rowcount
                row["registrations_deleted"] = registrations_deleted
                totals["registrations_deleted"] += registrations_deleted

            # Authorization DB cleanup (must run after ToolsCommissioning cleanup)
            if site_ids:
                authorization_cursor.execute(delete_authorizations_sql, (site_ids,))
                deleted_org_ids = [row[0] for row in authorization_cursor.fetchall()]
                authorization_counts_by_site = Counter(deleted_org_ids)
                totals["authorizations_deleted"] = len(deleted_org_ids)
                for site_id in site_ids:
                    site_row_by_id[site_id]["authorizations_deleted"] = authorization_counts_by_site.get(
                        site_id, 0
                    )

            # LCBS Nodes cleanup in Consup DB
            if customer_ids:
                consup_cursor.execute(delete_nodes_by_customer_sql, (customer_ids,))
                nodes_deleted = consup_cursor.rowcount
                totals["nodes_deleted"] = nodes_deleted
                for customer_id in customer_ids:
                    customer_rows.append(
                        {
                            "customer_id": customer_id,
                        }
                    )

        models_conn.commit()
        tools_conn.commit()
        authorization_conn.commit()
        consup_conn.commit()

        return {
            "site_rows": site_rows,
            "entity_rows": entity_rows,
            "customer_rows": customer_rows,
            "totals": totals,
        }
    except Exception:
        models_conn.rollback()
        tools_conn.rollback()
        authorization_conn.rollback()
        consup_conn.rollback()
        raise
    finally:
        models_conn.close()
        tools_conn.close()
        authorization_conn.close()
        consup_conn.close()

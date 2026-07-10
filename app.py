import os

from dotenv import load_dotenv
from flask import Flask, render_template, request

from services.cleanup_service import (
    execute_cleanup,
    get_sites_by_customer_ids,
    parse_ids,
    preview_models_data,
)


load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-me")


def build_cleanup_context(customer_ids_text: str):
    customer_ids = parse_ids(customer_ids_text)
    sites = get_sites_by_customer_ids(customer_ids) if customer_ids else []
    site_ids = [str(site["site_id"]) for site in sites]
    # Requested behavior: treat each site ID as the entity ID as well.
    entity_ids = list(site_ids)
    preview = preview_models_data(site_ids, entity_ids, customer_ids) if customer_ids else None
    return {
        "customer_ids": customer_ids,
        "customer_ids_text": "\n".join(customer_ids),
        "sites": sites,
        "site_ids": site_ids,
        "entity_ids": entity_ids,
        "preview": preview,
    }


@app.after_request
def set_security_headers(response):
    # SECURITY_NOTE: Harden browser behavior for internal admin utility pages.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' https://cdn.jsdelivr.net; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self' https://cdn.jsdelivr.net; "
        "img-src 'self' data:;"
    )
    return response


@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        customer_ids_text="",
        sites=[],
        preview=None,
        cleanup_result=None,
    )


@app.route("/rbm-cleanup", methods=["POST"])
def rbm_cleanup():
    customer_ids_text = request.form.get("customer_ids", "")
    action = request.form.get("action", "preview")

    try:
        context = build_cleanup_context(customer_ids_text)
    except ValueError as exc:
        return render_template(
            "index.html",
            customer_ids_text=customer_ids_text,
            sites=[],
            preview=None,
            cleanup_result=None,
            error_message=str(exc),
        )
    except Exception:
        app.logger.exception("RBM preview failed during execute")
        return render_template(
            "index.html",
            customer_ids_text=customer_ids_text,
            sites=[],
            preview=None,
            cleanup_result=None,
            error_message="Failed to prepare RBM cleanup data.",
        )

    customer_ids = context["customer_ids"]
    if not customer_ids:
        return render_template(
            "index.html",
            customer_ids_text=customer_ids_text,
            sites=[],
            preview=None,
            cleanup_result=None,
            error_message="Please provide at least one Customer ID.",
        )

    if action == "preview":
        return render_template(
            "index.html",
            customer_ids_text=context["customer_ids_text"],
            sites=context["sites"],
            preview=context["preview"],
            cleanup_result=None,
        )

    if action != "execute":
        return render_template(
            "index.html",
            customer_ids_text=context["customer_ids_text"],
            sites=context["sites"],
            preview=None,
            cleanup_result=None,
            error_message="Unknown action requested.",
        )

    try:
        cleanup_result = execute_cleanup(context["site_ids"], context["entity_ids"], customer_ids)
        return render_template(
            "index.html",
            customer_ids_text=context["customer_ids_text"],
            sites=context["sites"],
            preview=context["preview"],
            cleanup_result=cleanup_result,
            success_message="RBM cleanup completed successfully.",
        )
    except Exception:
        app.logger.exception("RBM cleanup execution failed")
        return render_template(
            "index.html",
            customer_ids_text=customer_ids_text,
            sites=context["sites"],
            preview=context["preview"],
            cleanup_result=None,
            error_message="RBM cleanup failed. All database changes were rolled back.",
        )


@app.route("/cleanup", methods=["GET"])
def cleanup_page():
    return render_template(
        "index.html",
        customer_ids_text="",
        sites=[],
        preview=None,
        cleanup_result=None,
    )


if __name__ == "__main__":
    app.run(debug=True)

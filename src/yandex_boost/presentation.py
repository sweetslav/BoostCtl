from __future__ import annotations


def presentation_action(operation) -> str:
    if operation.disposition.value in {"SKIP", "REVIEW"}:
        return operation.disposition.value
    return {
        "CREATE_SALES": "CREATE",
        "CREATE_SHOWS": "CREATE",
        "UPDATE_SALES_FEE": "UPDATE_FEE",
        "DELETE_SALES": "DELETE",
    }.get(operation.operation_type.value, operation.disposition.value)

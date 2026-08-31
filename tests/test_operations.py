from yandex_boost.operations import OperationType, operation_id


def test_operation_id_is_stable_and_intent_sensitive():
    first = operation_id(OperationType.CREATE_SALES, {"sku": "A"}, {"fee": 15})
    assert first == operation_id(OperationType.CREATE_SALES, {"sku": "A"}, {"fee": 15})
    assert first != operation_id(OperationType.CREATE_SALES, {"sku": "A"}, {"fee": 16})

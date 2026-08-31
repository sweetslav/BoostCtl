from yandex_boost.planner import plan_sales_create


def test_planner_never_mutates_and_marks_ui_observed_duplicate():
    plan = plan_sales_create([{"sku": "A", "bid": 15}], {"A"}, "run")
    assert plan[0].warnings == ("UI observed duplicate protection",)
    assert plan[0].intent == {"sku": "A", "fee": 15}

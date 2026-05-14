{% macro classify_priority(price_diff) %}
  CASE
    WHEN {{ price_diff }} > 1.00  THEN 'HIGH'
    WHEN {{ price_diff }} > 0.10  THEN 'MEDIUM'
    ELSE                               'LOW'
  END
{% endmacro %}

{% if condition == "get_by_id" %}
SELECT * FROM customer WHERE cust_id = {{ id }};
{% elif condition == "update" %}
UPDATE customer SET
    cust_name = '{{ cust_name }}', 
    cust_biz_no = '{{ cust_biz_no }}', 
    cust_grade = '{{ cust_grade }}', 
    phone = '{{ phone }}',
    updated_at = CURRENT_TIMESTAMP
WHERE cust_id = {{ id }};
{% endif %}

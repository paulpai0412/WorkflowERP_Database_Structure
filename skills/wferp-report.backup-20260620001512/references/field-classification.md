# Field Classification

Classify fields before SQL generation.

Field roles:
- `dimension`: customer, product, salesperson, company, region, category.
- `date`: order date, shipping date, accounting date, year, month, period.
- `measure`: amount, tax, quantity, cost, price, margin.
- `identifier`: order number, customer code, product code, row id.
- `formula`: workbook-calculated value or derived report metric.
- `unknown`: field requiring user or schema confirmation.

Prefer exact workbook names and database column names in artifacts.

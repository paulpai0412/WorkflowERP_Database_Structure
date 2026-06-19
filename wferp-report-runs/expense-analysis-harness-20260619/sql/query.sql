SELECT
    [department_code] AS department_code,
    [department_name] AS department_name,
    [expense_subject] AS expense_subject,
    [amount] AS amount,
    [budget_amount] AS budget_amount,
    [amount] - [budget_amount] AS variance_amount,
    CAST([amount] AS REAL) / NULLIF((
        SELECT SUM([budget_amount])
        FROM [VPIC1].[dbo].[EXPENSE_ANALYSIS_FIXTURE]
        WHERE [year] = 2026 AND [account_type] = 'expense'
    ), 0) AS expense_ratio
FROM [VPIC1].[dbo].[EXPENSE_ANALYSIS_FIXTURE]
WHERE [year] = 2026 AND [account_type] = 'expense'
ORDER BY [department_code], [expense_subject]

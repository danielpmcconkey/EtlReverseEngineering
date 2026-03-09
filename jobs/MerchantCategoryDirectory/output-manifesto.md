# MerchantCategoryDirectory -- Output Manifesto

**Job:** MerchantCategoryDirectory_RE

---

## Outputs

### merchant_category_directory.csv

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/merchant_category_directory/merchant_category_directory/{YYYY-MM-DD}/merchant_category_directory.csv` |
| Format | CSV |
| Delimiter | Comma |
| Line ending | LF |
| Header | Yes (1 row) |
| Trailer | No |
| Data rows (Oct 1) | 20 |
| Data rows (Dec 31) | 1840 (cumulative) |
| Write mode | Append |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | mcc_code | integer | datalake.merchant_categories |
| 2 | mcc_description | text | datalake.merchant_categories |
| 3 | risk_level | text | datalake.merchant_categories |
| 4 | ifw_effective_date | date | Framework injection |
| 5 | etl_effective_date | date | Framework auto-append |

### Sample Row (from Oct 1 output)
```
5411,Grocery Stores,Low,2024-10-01,2024-10-01
```

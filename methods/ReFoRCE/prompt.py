omni_sql_input_prompt_template = '''Task Overview:
You are a data science expert. Below, you are provided with a database schema and a natural language question. Your task is to understand the schema and generate a valid SQL query to answer the question.

Database Engine:
{db_engine}

Database Schema:
{db_details}
This schema describes the database's structure, including tables, columns, primary keys, foreign keys, and any relevant relationships or constraints.

Question:
{question}

Instructions:
- Make sure you only output the information that is asked in the question. If the question asks for a specific column, make sure to only include that column in the SELECT clause, nothing more.
- The generated query should return all of the information asked in the question without any missing or extra information.
- Before generating the final SQL query, please think through the steps of how to write the query.

Output Format:
In your answer, please enclose the generated SQL query in a code block:
```sql
-- Your SQL query
```

Take a deep breath and think step by step to find the correct SQL query.
'''

class Prompts:
    def __init__(self):
        pass
    def get_condition_onmit_tables(self):
        return ["-- Include all", "-- Omit", "-- Continue", "-- Union all", "-- ...", "-- List all", "-- Replace this", "-- Each table", "-- Add other"]
    def get_prompt_dialect_list_all_tables(self, table_struct, api):
        if api == "snowflake":
            return f"When performing a UNION operation on many tables, ensure that all table names are explicitly listed. Union first and then add condition and selection. e.g. SELECT \"col1\", \"col2\" FROM (TABLE1 UNION ALL TABLE2) WHERE ...; Don't write sqls as (SELECT col1, col2 FROM TABLE1 WHERE ...) UNION ALL (SELECT col1, col2 FROM TABLE2 WHERE ...); Don't use {self.get_condition_onmit_tables()} to omit any table. Table names here: {table_struct}\n"
        elif api == "bigquery":
            return "When performing a UNION operation on many tables with similar prefix, you can use a wildcard table to simplify your query. e.g., SELECT col1, col2 FROM `project_id.dataset_id.table_prefix*` WHERE _TABLE_SUFFIX IN ('table1_suffix', 'table2_suffix');. Avoid manually listing tables unless absolutely necessary.\n"
        else:
            return ""
    def get_prompt_fuzzy_query(self):
        return "For string-matching scenarios, if the string is decided, don't use fuzzy query. e.g. Get the object's title contains the word \"book\"\nHowever, if the string is not decided, you may use fuzzy query and ignore upper or lower case. e.g. Get articles that mention \"education\".\n"
    def get_prompt_decimal_places(self):
        return "If the task description does not specify the number of decimal places, retain all decimals to four places.\n"
    def get_prompt_convert_symbols(self):
        return "For string-matching scenarios, convert non-standard symbols to '%'. e.g. ('he’s to he%s)\n"
    def get_prompt_knowledge(self):
        return "Your knowledge is based on information in database. Don't use your own knowledge.\n"
    def get_prompt_dialect_nested(self, api):
        if api == "snowflake":
            return "For columns in json nested format: e.g. SELECT t.\"column_name\", f.value::VARIANT:\"key_name\"::STRING AS \"abstract_text\" FROM PATENTS.PATENTS.PUBLICATIONS t, LATERAL FLATTEN(input => t.\"json_column_name\") f; DO NOT directly answer the task and ensure all column names are enclosed in double quotations. For nested columns like event_params, when you don't know the structure of it, first watch the whole column: SELECT f.value FROM table, LATERAL FLATTEN(input => t.\"event_params\") f;\n"
        elif api == "bigquery":
            return "Extract a specific key from a nested JSON column: SELECT t.\"column_name\", JSON_EXTRACT_SCALAR(f.value, \"$.key_name\") AS \"abstract_text\" FROM `database.schema.table` AS t, UNNEST(JSON_EXTRACT_ARRAY(t.\"json_column_name\")) AS f;\nWhen the structure of the nested column (e.g., event_params) is unknown, first inspect the whole column: SELECT f.value FROM `project.dataset.table` AS t, UNNEST(JSON_EXTRACT_ARRAY(t.\"event_params\")) AS f;\n"
        elif api == "sqlite":
            return "Extract a specific key from a nested JSON column: SELECT t.\"column_name\", json_extract(f.value, '$.key_name') AS \"abstract_text\" FROM \"table_name\" AS t, json_each(t.\"json_column_name\") AS f;\nWhen the structure of the nested column (e.g., event_params) is unknown, first inspect the whole column: SELECT f.value FROM \"table_name\" AS t, json_each(t.\"event_params\") AS f;\n"
        else:
            return "Unsupported API. Please provide a valid API name ('snowflake', 'bigquery', 'sqlite')."
    def get_prompt_dialect_basic(self, api):
        if api == "snowflake":
            return "```sql\nSELECT \"COLUMN_NAME\" FROM DATABASE.SCHEMA.TABLE WHERE ... ``` (Adjust \"DATABASE\", \"SCHEMA\", and \"TABLE\" to match actual names, ensure all column names are enclosed in double quotations)"
        elif api == "bigquery":
            return "```sql\nSELECT `column_name` FROM `database.schema.table` WHERE ... ``` (Replace `database`, `schema`, and `table` with actual names. Enclose column names and table identifiers with backticks.)"
        elif api == "sqlite":
            return "```sql\nSELECT DISTINCT \"column_name\" FROM \"table_name\" WHERE ... ``` (Replace \"table_name\" with the actual table name. Enclose table and column names with double quotations if they contain special characters or match reserved keywords.)"
        else:
            raise NotImplementedError("Unsupported API. Please provide a valid API name ('snowflake', 'bigquery', 'sqlite').")
    def get_prompt_dialect_string_matching(self, api):
        if api == "snowflake":
            return "Don't directly match strings if you are not convinced. Use fuzzy query first: WHERE str ILIKE \"%target_str%\" For string matching, e.g. meat lovers, you should use % to replace space. e.g. ILKIE %meat%lovers%.\n"
        elif api == "bigquery":
            return "Don't directly match strings if you are not convinced. Use LOWER for fuzzy queries: WHERE LOWER(str) LIKE LOWER('%target_str%'). For example, to match 'meat lovers', use LOWER(str) LIKE '%meat%lovers%'.\n"
        elif api == "sqlite":
            return "Don't directly match strings if you are not convinced. For fuzzy queries, use: WHERE str LIKE '%target_str%'. For example, to match 'meat lovers', use WHERE str LIKE '%meat%lovers%'. If case sensitivity is needed, add COLLATE BINARY: WHERE str LIKE '%target_str%' COLLATE BINARY.\n"
        else:
            raise NotImplementedError("Unsupported API. Please provide a valid API name ('snowflake', 'bigquery', 'sqlite').")

    def get_format_prompt(self):
        format_prompt = "This is an SQL task. Please provide the simplest possible answer format in ```csv``` format like a table.\n"
        format_prompt += "e.g.1. Including the travel coordinates and the cumulative travel distance at each point. Format: ```csv\ntravel_coordinates,cumulative_travel_distance\nPOINT(longitude1 latitude1),distance1:int\nPOINT(longitude2 latitude2),distance2:int\n...```\n"
        format_prompt += "When asked something without specifying name or id, provide both. e.g.2. Which products had a seasonality-adjusted sales ratio that stayed consistently above 2 for every month in the year 2017? Format: ```csv\nproduct_name,product_id\nproduct_name1:str,product_id1:int\n...```\n"
        format_prompt += "Do not output any SQL queries.\n"
        return format_prompt

    def get_exploration_prompt(self, api, table_struct):
        exploration_prompt = f"Write at most 10 {api} SQL queries for simple to complex ones to final answer in format like:\n {self.get_prompt_dialect_basic(api)}\nin ```sql``` code block to have an understanding of values in related columns.\n"
        exploration_prompt += "Each query should be different. Don't query about any SCHEMA or checking data types. You can write SELECT query only. Try to use DISTINCT. For each SQL LIMIT 20 rows.\n"
        exploration_prompt += "Write annotations to describe each SQL, format like ```sql\n--Description: \n```.\n"

        exploration_prompt += self.get_prompt_dialect_nested(api)
                
        exploration_prompt += self.get_prompt_convert_symbols()
        
        exploration_prompt += self.get_prompt_dialect_string_matching(api)
        
        exploration_prompt += "For time-related queries, given the variety of formats, avoid using time converting functions unless you are certain of the specific format being used.\n"
        
        exploration_prompt += "When generating SQLs, be aware of quotation matching: 'Vegetarian\"; You sometimes match \' with \" which may cause an error.\n"

        exploration_prompt += f"You can only use tables in {table_struct}"
        
        exploration_prompt += self.get_prompt_knowledge()

        return exploration_prompt

    def get_exploration_refine_prompt(self, sql, corrected_sql, sqls):
        return f"```sql\n{sql}``` is corrected to ```sql\n{corrected_sql}```. Please correct other sqls if they have similar errors. SQLs: {sqls}. For each SQL, answer in ```sql\n--Description: \n``` format.\n"

    def get_exploration_self_correct_prompt(self, sql, error):
        return f"Input sql:\n{sql}\nThe error information is:\n" + str(error) + "\nPlease correct it based on previous context and output the thinking process with only one sql query in ```sql\n--Description: \n``` format. Don't just analyze without SQL or output several SQLs.\n"

    def get_self_refine_prompt(self, table_info, task, pre_info, question, api, format_csv, table_struct, omnisql_format_pth=None):
        if omnisql_format_pth:
            if task == "lite":
                return omni_sql_input_prompt_template.format(
                    db_engine = "SQLite",
                    db_details = table_info,
                    question = question
                )
            elif task == "BIRD":
                return table_info
        refine_prompt = table_info + "\n"
        # refine_prompt += "Begin Exploring Related Columns\n" + response_pre_txt + "\nRefined SQLs and results:\n" + pre_info + "End Exploring Related Columns\n" if pre_info else ""
        refine_prompt += "Some few-shot examples after column exploration may be helpful:\n" + pre_info if pre_info else ""

        refine_prompt += "Task: " + question + "\n"+f'\nPlease think step by step and answer only one complete SQL in {api} dialect in ```sql``` format.\n'
        refine_prompt += f'SQL usage example: {self.get_prompt_dialect_basic(api)}\n'
        refine_prompt += f"Follow the answer format like: {format_csv}.\n" if format_csv else ""
        refine_prompt += "Here are some useful tips for answering:\n"
        
        refine_prompt += self.get_prompt_dialect_list_all_tables(table_struct, api)
        # refine_prompt += self.get_prompt_fuzzy_query()

        if api == "snowflake":
            refine_prompt += "When using ORDER BY xxx DESC, add NULLS LAST to exclude null records: ORDER BY xxx DESC NULLS LAST.\n"
        # refine_prompt += "When using ORDER BY, if there are duplicate values in the primary sort column, sort by an additional column as a secondary criterion.\n"
        
        # Specific:
        refine_prompt += "When asked something without stating name or id, return both of them. e.g. Which products ...? The answer should include product_name and product_id.\n"
        refine_prompt += "When asked percentage decrease, you should return a positive value. e.g. How many percentage points in 2021 decrease compared to ...? The answer should be a positive value indicating the decresed number. Try to use ABS().\n"
        refine_prompt += "If asked two tables, you should reply with the last one instead of combining two tables. e.g. Identifying the top five states ... examine the state that ranks fourth overall and identify its top five counties. You should only answer top five counties.\n"
        if api == "snowflake":
            refine_prompt += "Use ST_DISTANCE to calculate distance between two geographic points for more accurate answer.\n"
        refine_prompt += self.get_prompt_decimal_places()
        
        return refine_prompt

    def get_self_consistency_prompt(self, task, format_csv):
        self_consistency_prompt = f"Please check the answer again by reviewing task:\n {task}\n, reviewing Relevant Tables and Columns and Possible Conditions and then give the final SQL query. Don't output other queries. If you think the answer is right, just output the current SQL.\n" 
        self_consistency_prompt += self.get_prompt_decimal_places()
        self_consistency_prompt += f"The answer format should be like: {format_csv}\n" if format_csv else ""

        return self_consistency_prompt
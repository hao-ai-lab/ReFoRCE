class Prompts:
    def __init__(self):
        pass
    def get_condition_onmit_tables(self):
        return ["-- Include all", "-- Omit", "-- Continue", "-- Union all", "-- ...", "-- List all", "-- Replace this", "-- Each table", "-- Add other"]
    def get_prompt_dialect_list_all_tables(self, table_struct, api):
        if api == "snowflake" or "sqlite":
            return f"When performing a UNION operation on many tables, ensure that all table names are explicitly listed. Union first and then add condition and selection. e.g. SELECT \"col1\", \"col2\" FROM (TABLE1 UNION ALL TABLE2) WHERE ...; Don't write sqls as (SELECT col1, col2 FROM TABLE1 WHERE ...) UNION ALL (SELECT col1, col2 FROM TABLE2 WHERE ...); Don't use {self.get_condition_onmit_tables()} to omit any table. Table names here: {table_struct}\n"
        if api == "bigquery":
            return "When performing a UNION operation on many tables with similar prefix, you can use a wildcard table to simplify your query. e.g., SELECT col1, col2 FROM `project_id.dataset_id.table_prefix*` WHERE _TABLE_SUFFIX IN ('table1_suffix', 'table2_suffix');. Avoid manually listing tables unless absolutely necessary.\n"
    def get_prompt_generator(self):
        return "Be careful of using GENERATOR. Don't use seq4(), use ROW_NUMBER().\n"
    def get_prompt_ST_INTERSECTS_FUNC(self):
        return "Usage of ST_INTERSECTS: ST_INTERSECTS(geometry1, ST_GEOGFROMWKB(geometry2)) This function checks if the two geometries intersect. The first argument, geometry1, is compared with the second argument, geometry2, which is converted from its WKB (Well-Known Binary) representation to a geography type using ST_GEOGFROMWKB. If the two geometries share any portion of space, the function returns TRUE; otherwise, it returns FALSE. Usage of ST_CONTAINS: ST_CONTAINS(r1.geometry, r2.geometry) This function checks if the geometry r1.geometry completely contains the geometry r2.geometry. It returns TRUE if all points of r2.geometry are within r1.geometry and FALSE otherwise. This is useful for spatial containment queries, such as verifying whether one region is entirely within another. ARRAY_INTERSECTION(nodes1, nodes2): This function computes the intersection of the two arrays, returning a new array containing only the elements that are present in both nodes1 and nodes2. ARRAY_SIZE(...): This function then determines the size (or number of elements) in the resulting array from the intersection.\n"
    def get_prompt_fuzzy_query(self):
        return "For string-matching scenarios, if the string is decided, don't use fuzzy query, and avoid using REGEXP. e.g. Get the object's title contains the word \"book\"\nHowever, if the string is not decided, you may use fuzzy query and ignore upper or lower case. e.g. Get articles that mention \"education\".\n"
    def get_prompt_decimal_places(self):
        return "If the task description does not specify the number of decimal places, retain all decimals to four places.\n"
    def get_prompt_convert_symbols(self):
        return "For string-matching scenarios, convert non-standard symbols to '%'. e.g. ('he’s to he%s)\n"
    def get_prompt_name(self):
        return "For tasks asking fullname or name, you should combine first name and last name into one column called name. Format: ```csv\nname\nname:str```\n"
    def get_prompt_knowledge(self):
        return "Your knowledge is based on information in tables. Don't use your own knowledge.\n"
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
        format_prompt = "This is an SQL task. Please provide the simplest possible answer format in ```csv``` format like a table and include a brief explanation.\n"
        
        format_prompt += "If there are some records specified in the task, you should follow and capitalize them and note answering in the order. e.g. Task: Give me the number of small, medium and large clothes. Format: ```csv\nSize,Number\nSmall,num1\nMedium,num2\nLarge,num3\n(Attention: answer in this order)```\n If not specified, just fill with the metaname and its data type. e.g. Provide the names and ranks of faculty. Format: ```csv\nName,Rank\nname1:str,rank1:str\nname2:str,rank2:str\n...``` In this case, list 2 rows with '...' if you don't know how many rows will be. Don't fill values like 'Professor', 'AP' that you inferred.\n"
        format_prompt += "For bool type, don't fill true or false. e.g. Please display the drug id, drug type and withdrawal status. Format: ```csv\ndrug_id,drug_type,hasBeenWithdrawn\nid1:int,type1:str,status1:bool\nid2:int,type2:str,status2:bool\n...```\n"

        format_prompt += "Don't ouput extra rows. e.g. When dealing with superlative cases (like highest, maximum, largest, lowest, average total, most), ensure the result is limited to just one row and emphasize it in parentheses. e.g. Get the fourth highest number of the group. Format: ```csv\nFourth-highest-num,group-name\nnum:int,name:str\n(Attention: answer in one row)```\n"
        format_prompt += "e.g. Calculate the value between A and B. You should only focus on the value. e.g. Calculate the chi-squared statistic. Format: ```csv\nchi-squared value\nv1:float\n(Attention: answer in one row)```\n"
        format_prompt += "For superlative cases with limited rows more than 1, also note the number. e.g. Most purchased other products for the three months starting from November 2020. Format: ```csv\nMonth,Product_Name,Quantity\nNov-2020,product1:str,quantity1:int\nDec-2020,product1:str,quantity1:int\nJan-2021,product1:str,quantity1:int\n(Attention: answer in three rows)```\n"

        format_prompt += "For coordinate-related cases, use POINT(longitude latitude). e.g. Including its travel coordinates and the cumulative travel distance at each point. Format: ```csv\ngeom,cumulative_distance\nPOINT(longitude1 latitude1),distance1:int\nPOINT(longitude2 latitude2),distance2:int\n...```\n"
        
        format_prompt += "For task asking percentage or rate values, omit the '%' symbol and retain only the numeric value in [0, 100]. Otherwise, for portion, proportion, answer a float number < 1.\n"
        
        format_prompt += "Columns are for features and rows are for records. e.g. When answering Wages Growth Rate and Inflation, the format should be ```csv\nWage_growth_rate,Inflation_rate\nwage:0<=float<=100,inflation:0<=float<=100```, not ```csv\nMetric,Rate\nGrowth Rate,rate1:0<=float<=100\nInflation,rate2:0<=float<=100```\n"
        format_prompt += "If there are multiple names for one feature, you should split them to different columns, not adding rows. e.g. Get scores of team A vs team B with period and description. Format: ```csv\nscore_a,score_b,period,description\nscore_a:float,score_b:float,period,description:str``` e.g. Number of distinct active and closed bike share stations for each year 2013 and 2014. Format: ```csv\nYear,Number_of_Stations_active,Number_of_Stations_active\n2013,num_active:int,num_closed:int\n2014,num_active:int,num_closed:int```\n"

        format_prompt += "For tasks about distances, no need to convert from meters to miles or km unless requested. In this case, note meters in the format: ```csv\ntotal_distance_meters\ndist:float```\n"

        format_prompt += self.get_prompt_name()
        
        format_prompt += "For other cases string should be separate, return both 2 strings and don't concatenate them. e.g. Asked team name, there may be team_name and market_name that match: ```csv\nmarket_name,team_name\nstr1,str2```\n When asked for income, don't concatenate income with '$', just output numbers.\n"
        
        format_prompt += "For month cases, form format in both month_num and month: ```csv\nMonth_num,Month\n01,Jan\n02,Feb```.\n"

        format_prompt += "For quantile cases, explicitly list each quantile and convince the object to quantile. e.g. 60 minutes trip durations 10 quantiles: Format: ```csv\ntime_range,distance\n00m to 10m,dis1\n10m to 20m,dis2\n...\n50m to 60m,dis3``` Start from 0.\n"
        
        format_prompt += "If you meet with an ambiguous name in the task that may match 2 columns, feel free to add 2 columns (like name and name_id) of them. e.g. Tell me the tract code. Tract code may mean geo_id or tract_ce, then format: ```csv\geo_id,tract_ce\nid,code``` e.g. Which products were picked for order. Format: ```csv\nproduct_id,product_name,average_units_picked_per_batch\nproduct_id1:int,product_name1:str,average_units1:float\nproduct_id2:int,product_name2:str,average_units2:float\n...```\n"

        format_prompt += "Please output only one format. If there could be 2 tables as the complete answers, return the latter one as format. e.g. Identify the top five states by daily increases. Then, examine the state that ranks fourth overall and identify its top five counties. Format: ```csv\ntop_five_counties,count\ncounty1:str,count1:int\ncounty2:str,count2:int\ncounty3:str,count3:int\ncounty4:str,count4:int\ncounty5:str,count5:int```In this case, return results of the later one table. Also don't concatenate 'county' after county name.\n"
        
        format_prompt += "If the value is nonnegative, emphasize this value. e.g. How much higher the average intrinsic value is. Format: ```csv\higher\nvalue:float > 0``` e.g. What is the difference between A and B. The difference should be nonnegative. Format: ```csv\ndifference\nvalue:float > 0```\n"
        
        format_prompt += "Do not output any SQL queries.\n"
        return format_prompt

    def get_exploration_prompt(self, api, table_struct):
        exploration_prompt = f"Consider which tables and columns are relevant to the task. Answer like: `column name`: `potential usage`. And also conditions that may be used. Then write 10 {api} SQL queries for simple to complex ones to final answer like {self.get_prompt_dialect_basic(api)} in ```sql``` format to have an understanding of values in related columns.\n"
        exploration_prompt += "Each query should be different. Don't use CTEs and don't query about any SCHEMA or checking data types. You can write SELECT query only. Try to use DISTINCT. For each SQL LIMIT 100 rows.\n"

        exploration_prompt += self.get_prompt_dialect_nested(api)
                
        exploration_prompt += self.get_prompt_convert_symbols()
        
        exploration_prompt += self.get_prompt_dialect_string_matching(api)
        
        exploration_prompt += "For time-related queries, given the variety of formats, avoid using time converting functions unless you are certain of the specific format being used.\n"
        
        exploration_prompt += "When generating SQLs, be aware of quotation matching: 'Vegetarian\"; You sometimes match \' with \" which may cause an error.\n"

        exploration_prompt += f"You can only use tables in {table_struct}"
        
        exploration_prompt += self.get_prompt_knowledge()

        return exploration_prompt

    def get_self_refine_prompt(self, table_info, response_pre_txt, pre_info, task, api, format_csv, table_struct):
        refine_prompt = table_info + "Begin Exploring Related Columns\n" + response_pre_txt + "\nRefined SQLs and results:\n" + pre_info + "End Exploring Related Columns\n"

        refine_prompt += "Task: " + task + "\n"+f'\nPlease answer only one complete SQL in {api} dialect in ```sql``` format.\n'
        refine_prompt += f'Usage example: {self.get_prompt_dialect_basic(api)}\n'
        refine_prompt += f"Follow the answer format like: {format_csv}.\n"
        refine_prompt += "Here are some useful tips for answering:\n"
        
        refine_prompt += self.get_prompt_dialect_list_all_tables(table_struct, api)
        refine_prompt += self.get_prompt_fuzzy_query()

        if api == "snowflake":
            refine_prompt += "When using ORDER BY xxx DESC, add NULLS LAST to exclude null records: ORDER BY xxx DESC NULLS LAST.\n"
        refine_prompt += "When using ORDER BY, if there are duplicate values in the primary sort column, sort by an additional column as a secondary criterion.\n"

        refine_prompt += self.get_prompt_decimal_places()

        if "> 0" in format_csv:
            refine_prompt += "You need to follow the format's positive signs.\n"
        
        return refine_prompt

    def get_self_consistency_prompt(self, task, format_csv):
        self_consistency_prompt = f"Please check the answer again by reviewing {task}, reviewing Relevant Tables and Columns and Possible Conditions and then give the final SQL query. Don't output other queries. If you think the answer is right, just output the current SQL.\n" 
        self_consistency_prompt += self.get_prompt_decimal_places()
        self_consistency_prompt += f"The answer format should be like: {format_csv} The answer should match the number of rows, the column name of the format and the filled values in the format (e.g. filled year or month). Don't output extra rows or nested rows!\n"

        return self_consistency_prompt
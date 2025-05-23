from openai import OpenAI, AzureOpenAI
from utils import extract_all_blocks
import os
import sys

class GPTChat:
    def __init__(self, azure=False, model="gpt-4o", temperature=1) -> None:
        if not azure:
            if model in ["o1-preview", "o1-mini"]:
                self.client = OpenAI(
                    api_key=os.environ.get("OPENAI_API_KEY"),
                    api_version="2024-12-01-preview"
                )
            elif model in ["deepseek-reasoner"]:
                self.client = OpenAI(
                    base_url="https://api.deepseek.com",
                    api_key=os.environ.get("DS_API_KEY"),
                )                
            else: 
                self.client = OpenAI(
                    api_key=os.environ.get("OPENAI_API_KEY"),
                )
            # else:
            #     raise NotImplementedError("Unsupported API Key")
        else:
            if model in ["o1-preview", "o1-mini", "o3", "o4-mini"]:
                self.client = AzureOpenAI(
                    azure_endpoint = os.environ.get("AZURE_ENDPOINT"),
                    api_key=os.environ.get("AZURE_OPENAI_KEY"),
                    api_version="2024-12-01-preview"
                )
            else:
                self.client = AzureOpenAI(
                    azure_endpoint = os.environ.get("AZURE_ENDPOINT"),
                    api_key=os.environ.get("AZURE_OPENAI_KEY"),
                    api_version="2024-05-01-preview"
                )

        self.messages = []
        self.model = model
        self.temperature = float(temperature)

    def get_model_response(self, prompt, code_format):
        self.messages.append({"role": "user", "content": prompt})
        sql_query = []
        max_try = 0
        while not sql_query and max_try < 3:
            max_try += 1
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    temperature=self.temperature
                )
            except Exception as e:
                if "Error code" in str(e):
                    print(e)
                    sys.exit(0)
                print(e)
                return e
            choices = response.choices
            if choices:
                main_content = choices[0].message.content
                sql_query = extract_all_blocks(main_content, code_format)
            self.messages.append({"role": "assistant", "content": main_content})
            if not sql_query:
                print(f"sql_query: {sql_query}, max_try: {max_try}")
                self.messages.append({"role": "user", "content": f"Please answer in ```{code_format}``` format with one sql query."})
                continue
                
        return sql_query
    
    def get_model_response_txt(self, prompt):
        self.messages.append({"role": "user", "content": prompt})
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                temperature=self.temperature
            )
        except Exception as e:
            print(e)
            return e
        choices = response.choices
        if choices:
            main_content = choices[0].message.content

        self.messages.append({"role": "assistant", "content": main_content})
        return main_content

    def get_message_len(self):
        return sum([len(i['content']) for i in self.messages])
    
    def init_messages(self):
        self.messages = []
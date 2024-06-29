<<<<<<< Updated upstream
=======


class UnidentifiedPromptType(Exception):
    pass

class MissingPromptParams(Exception):
    pass

class PromptBuilder:
    def __init__(self, prompt_type: str):

        self.prompt_type = prompt_type
        self.prompt_template_str = ""
        self.expected_params = []

    def __prompt_type_map__(self):
        if self.prompt_type == 'extract relations':
            prompt_path = r"C:\Users\mehul\Documents\Projects - GIT\Agents\SQLCoder\APIManager\Prompts\taskExtractRelations.txt"
            self.expected_params = ['SQLQuery',]

        elif self.prompt_type == 'create data dict':
            prompt_path = r"C:\Users\mehul\Documents\Projects - GIT\Agents\SQLCoder\APIManager\Prompts\taskGenerateTableSummary.txt"

        elif self.prompt_type == 'create table summary':
            prompt_path = r"C:\Users\mehul\Documents\Projects - GIT\Agents\SQLCoder\APIManager\Prompts\taskGenerateColumnDesc.txt"

        elif self.prompt_type == 'generate data dict':
            prompt_path = r"C:\Users\mehul\Documents\Projects - GIT\Agents\SQLCoder\APIManager\Prompts\taskTemplate.txt"
            self.expected_params = ['DDLQUERY','INSERETQUERY',]

        else:
            raise UnidentifiedPromptType(f"{self.prompt_type} : Prompt type unidentified")

        with open(prompt_path,"r") as prompt_template_FObj:
            self.prompt_template_str = prompt_template_FObj.read()

    def build(self, prompt_params: dict) -> str:

        self.__prompt_type_map__()

        if not(self.expected_params == list(prompt_params.keys())):
            raise MissingPromptParams(f"""Params Dict provided missing specific params. 
            Expected: {self.expected_params} 
            Provided: {list(prompt_params.keys())}
            """)

        prompt_template_str = self.prompt_template_str

        for param, value in prompt_params.items():
            prompt_template_str = prompt_template_str.replace(f"<<{param}>>", value)

        return prompt_template_str



if __name__ == "__main__":
    print(PromptBuilder("extract relations").build({"SQLQuery":""}))


>>>>>>> Stashed changes

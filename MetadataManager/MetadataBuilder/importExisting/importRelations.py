
from APIManager.AllAPICaller import CallLLMApi
from APIManager.PromptBuilder import PromptBuilder
from MetadataManager.MetadataStore.ManageRelations import Relations
import json


class indexRelations:

    def __init__(self, mechanism="llm", service="Google"):
        self.mechanism = mechanism
        self.service = service
        self.LLMObj = CallLLMApi(service)
        self.RelationObj = Relations()
        self.PromptBuilderObj = PromptBuilder(prompt_type='extract relations')

    def __heuristic__(self, query: str):
        pass


    def __llm_based__(self, query: str):


        with open(r"C:\Users\mehul\Documents\Projects - GIT\Agents\Decompose KG from Code\pythonProject\CoderAssistants\Code\Utilities\Configs\apiTemplates\taskExtractRelations.txt", "r") as promptFObj:
            prompt_str = promptFObj.read()

        prompt_params = {"SQLQuery": query}

        prompt_str = self.PromptBuilderObj.build(prompt_params=prompt_params)

        relation_results_str = self.LLMObj.CallService(prompt_str)

        print("relation_results : ", relation_results_str)

        return json.loads(relation_results_str)

    def extract_relations(self, query: str):
        if self.mechanism == "llm":
            relations_list = self.__llm_based__(query)

        if self.mechanism == "heuristic":
            relations_list = self.__heuristic__(query)

        self.RelationObj.addRelation(relations_list)

        self.RelationObj.visRelations()

        return "Added Query relations"


if __name__ == "__main__":
    appendRelationsObj = indexRelations()

    with open(r"C:\Users\mehul\Documents\Projects - GIT\Agents\Decompose KG from Code\pythonProject\CoderAssistants\sampleFiles\NorthWinds\DataRelations.SQL", "r") as DRFobj:
        appendRelationsObj.extract_relations(DRFobj.read())


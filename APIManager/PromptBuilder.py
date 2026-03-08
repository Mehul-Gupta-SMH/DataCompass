import pathlib

_PROMPTS_DIR = pathlib.Path(__file__).parent / "Prompts"


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
            prompt_path = _PROMPTS_DIR / "taskExtractRelations.txt"
            self.expected_params = ['SQLQuery']

        elif self.prompt_type == 'create data dict':
            prompt_path = _PROMPTS_DIR / "taskGenerateTableSummary.txt"
            self.expected_params = []

        elif self.prompt_type == 'create table summary':
            prompt_path = _PROMPTS_DIR / "taskGenerateColumnDesc.txt"
            self.expected_params = []

        elif self.prompt_type == 'generate data dict':
            prompt_path = _PROMPTS_DIR / "taskTemplate.txt"
            self.expected_params = ['DDLQUERY', 'INSERETQUERY']

        elif self.prompt_type == 'generate sql':
            prompt_path = _PROMPTS_DIR / "taskGenerateSQL.txt"
            self.expected_params = ['CONVERSATION', 'SCHEMA']

        elif self.prompt_type == 'generate spark sql':
            prompt_path = _PROMPTS_DIR / "taskGenerateSparkSQL.txt"
            self.expected_params = ['CONVERSATION', 'SCHEMA']

        elif self.prompt_type == 'generate dataframe api':
            prompt_path = _PROMPTS_DIR / "taskGenerateDataframeAPI.txt"
            self.expected_params = ['CONVERSATION', 'SCHEMA']

        elif self.prompt_type == 'generate pandas':
            prompt_path = _PROMPTS_DIR / "taskGeneratePandas.txt"
            self.expected_params = ['CONVERSATION', 'SCHEMA']

        elif self.prompt_type == 'ingest pipeline':
            prompt_path = _PROMPTS_DIR / "taskIngestPipeline.txt"
            self.expected_params = ['SQL', 'SOURCE_SCHEMAS', 'COLUMN_MAPPINGS']

        elif self.prompt_type == 'gather requirements':
            prompt_path = _PROMPTS_DIR / "taskRequirementGather.txt"
            self.expected_params = ['TABLE_DIRECTORY', 'SCHEMA', 'FETCHED_SCHEMAS', 'CONVERSATION']

        else:
            raise UnidentifiedPromptType(f"{self.prompt_type} : Prompt type unidentified")

        with open(prompt_path, "r") as prompt_template_FObj:
            self.prompt_template_str = prompt_template_FObj.read()

    def build(self, prompt_params: dict) -> str:

        self.__prompt_type_map__()

        if not (self.expected_params == list(prompt_params.keys())):
            raise MissingPromptParams(f"""Params dict provided missing specific params.
            Expected: {self.expected_params}
            Provided: {list(prompt_params.keys())}
            """)

        prompt_template_str = self.prompt_template_str

        for param, value in prompt_params.items():
            prompt_template_str = prompt_template_str.replace(f"<<{param}>>", value)

        return prompt_template_str

    @staticmethod
    def format_schema(context: dict) -> str:
        """
        Format the context dict returned by SQLBuilderSupport.getBuildComponents()
        into a structured markdown schema string for the LLM prompt.

        Args:
            context (dict): Dict with keys 'user_query', 'table_list', 'join_keys'.

        Returns:
            str: Markdown-formatted schema and question.
        """
        lines = []

        lines.append("## User Question")
        lines.append(context["user_query"].strip())
        lines.append("")

        lines.append("## Database Schema")

        has_tables = any(context["table_list"].get(k) for k in ("direct", "intermediate"))
        if not has_tables:
            lines.append("\n> No schema information was retrieved for this query. "
                         "Generate the best query you can based on the conversation context above.")

        for table_type, tables in context["table_list"].items():
            label = "direct" if table_type == "direct" else "intermediate"
            for table_name, table_data in tables.items():
                lines.append(f"\n### {table_name} [{label}]")

                description = table_data.get("description")
                if description:
                    # fetchone() returns a tuple — unpack if needed
                    if isinstance(description, tuple):
                        description = description[0]
                    lines.append(f"> {description}")

                lines.append("")
                columns = table_data.get("columns") or []
                if columns:
                    lines.append("| Column | Type | Constraints | Description |")
                    lines.append("|--------|------|-------------|-------------|")
                    for col in columns:
                        col_name = col[0] or ""
                        col_type = col[1] or ""
                        constraints = col[2] or ""
                        desc = col[3] or ""
                        lines.append(f"| {col_name} | {col_type} | {constraints} | {desc} |")
                lines.append("")

        join_keys = context.get("join_keys") or []
        if join_keys:
            lines.append("## Join Paths")
            for rel in join_keys:
                join_attrs = (rel.get("edge_attributes") or {}).get("JoinKeys", "")
                lines.append(f"- {rel['source']} → {rel['target']} via {join_attrs}")

        return "\n".join(lines)


if __name__ == "__main__":
    print(PromptBuilder("extract relations").build({"SQLQuery": ""}))

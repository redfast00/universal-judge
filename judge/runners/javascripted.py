from typing import List, Optional

from runners.config import LanguageConfig
from testplan import Context


class JavaScriptedConfig(LanguageConfig):
    """
    Configuration for the Java language in script mode.
    This does not support most features.
    TODO: system for indicating required/supported features.
    """

    def value_writer(self):
        return ""

    def needs_main(self):
        return False

    def supports_top_level_functions(self) -> bool:
        return False

    def needs_compilation(self) -> bool:
        return True

    def execution_command(self, context_id: str) -> List[str]:
        return ["java", "-cp", ".", self.context_name(context_id)]

    def file_extension(self) -> str:
        return "java"

    def compilation_command(self, files: List[str]) -> List[str]:
        return ["javac", *files]

    def submission_name(self, context_id: str, context: Context) -> Optional[str]:
        return None

    def context_name(self, context_id: str) -> str:
        return f"Context{context_id}"

    def additional_files(self) -> List[str]:
        return []

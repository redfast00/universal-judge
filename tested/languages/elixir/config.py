from pathlib import Path
from typing import List

from tested.languages.config import CallbackResult, Command, Config, Language


class Elixir(Language):


    def execution(self, config: Config, cwd: Path, file: str, arguments: List[str]) -> Command:
        return ['elixir', file, *arguments]

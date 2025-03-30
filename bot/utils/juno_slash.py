import os
from discord import app_commands

class JunoSlash:
    def __init__(self, tree: app_commands.CommandTree):
        self.path = os.path.join(os.getcwd(), "bot", "commands")
        self.tree = tree
    
    def load_commands(self, args=None):
        for file in self.get_next_command():
            try:
                class_name = "".join(word.capitalize() for word in file.split("_"))
                command = self.import_from(f"bot.commands.{file}", class_name)
                command(self.tree, args=args)
            except Exception as e:
                print(f"ERROR: {e}")
    
    def get_next_command(self):
        for file in os.listdir(self.path):
            if file not in ["__pycache__", "__init__.py"]:
                yield file[:-3]
    
    @staticmethod
    def import_from(module: str, name: str):
        module = __import__(module, fromlist=[name])
        return getattr(module, name)

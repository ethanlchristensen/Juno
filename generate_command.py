import os
import re

def validate_command_name(name):
    """Validate the command name."""
    if not name:
        return False
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', name):
        return False
    return True

def get_command_info():
    """Prompt the user for command information."""
    print("=== Discord Bot Command Generator ===")
    
    # Get command name
    while True:
        command_name = input("Enter command name (e.g. ping): ").strip().lower()
        if validate_command_name(command_name):
            break
        print("Invalid command name. Use only letters, numbers and underscores, and start with a letter.")
    
    # Get command description
    description = input("Enter command description: ").strip() or "No description provided."
    
    # Check if command has arguments
    has_args = input("Does this command have arguments? (y/n): ").strip().lower() == 'y'
    
    args = []
    if has_args:
        print("Enter command arguments (press Enter on a blank line when done):")
        print("Format: name:type:description:required (e.g. user:discord.User:The user to target:True)")
        
        while True:
            arg_input = input("> ").strip()
            if not arg_input:
                break
            
            parts = arg_input.split(':')
            if len(parts) >= 3:
                arg_name = parts[0]
                arg_type = parts[1]
                arg_desc = parts[2]
                arg_required = parts[3].lower() == 'true' if len(parts) > 3 else True
                
                args.append({
                    'name': arg_name,
                    'type': arg_type,
                    'description': arg_desc,
                    'required': arg_required
                })
            else:
                print("Invalid format. Please use name:type:description:required")
    
    return {
        'name': command_name,
        'description': description,
        'args': args
    }

def generate_command_file(command_info):
    """Generate the command file content."""
    name = command_info['name']
    description = command_info['description']
    args = command_info['args']
    
    class_name = f"{name.capitalize()}Command"
    file_name = f"{name}_command.py"
    
    # Start building the file content
    content = [
        "import discord",
        "from discord import app_commands",
        "",
        f"class {class_name}(app_commands.Command):",
        f"    def __init__(self, tree: app_commands.CommandTree, args=None):",
        f"        @tree.command(name=\"{name}\", description=\"{description}\")"
    ]
    
    # Add the command function signature
    if args:
        func_def = f"        async def {name}(interaction: discord.Interaction"
        for arg in args:
            arg_name = arg['name']
            arg_type = arg['type']
            required = arg['required']
            if required:
                func_def += f", {arg_name}: {arg_type}"
            else:
                func_def += f", {arg_name}: {arg_type} = None"
        func_def += "):"
        content.append(func_def)
    else:
        content.append(f"        async def {name}(interaction: discord.Interaction):")
    
    # Add basic function body
    content.append("            # TODO: Implement command logic")
    content.append("            await interaction.response.send_message(f\"The {name} command was executed!\")")
    
    return "\n".join(content), file_name

def save_command_file(content, file_name):
    """Save the generated command file."""
    # Ensure the commands directory exists
    commands_dir = os.path.join("bot", "commands")
    os.makedirs(commands_dir, exist_ok=True)
    
    file_path = os.path.join(commands_dir, file_name)
    
    # Check if file already exists
    if os.path.exists(file_path):
        overwrite = input(f"File {file_path} already exists. Overwrite? (y/n): ").strip().lower() == 'y'
        if not overwrite:
            print("Operation canceled.")
            return False
    
    # Write the file
    with open(file_path, 'w') as f:
        f.write(content)
    
    return file_path

def main():
    try:
        command_info = get_command_info()
        content, file_name = generate_command_file(command_info)
        
        file_path = save_command_file(content, file_name)
        if file_path:
            print(f"Command file created successfully: {file_path}")
            print(f"Don't forget to import and register your command in your bot's initialization code!")
    except KeyboardInterrupt:
        print("\nOperation canceled.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
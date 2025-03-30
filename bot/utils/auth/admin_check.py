import os
import json
import discord
from functools import wraps

def is_admin():
    """
    Decorator that checks if the user is in the ADMINS list from environment variables.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            await interaction.response.defer(ephemeral=True)
            admin_list_str = os.getenv("ADMINS", "[]")
            try:
                admin_list = json.loads(admin_list_str)
                if interaction.user.id in admin_list:
                    return await func(interaction, *args, **kwargs)
                else:
                    embed = discord.Embed()
                    embed.color = 0xFF0000
                    embed.title = "Permission Denied"
                    embed.description = "You don't have permission to use this command."
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return None
            except json.JSONDecodeError:
                print(f"Error: Failed to parse ADMINS environment variable: {admin_list_str}")
                await interaction.response.send_message("An error occurred while checking permissions.", ephemeral=True)
                return None
        return wrapper
    return decorator
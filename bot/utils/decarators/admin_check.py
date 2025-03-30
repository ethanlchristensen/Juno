import os
import json
import discord
import logging
from functools import wraps

logger = logging.getLogger(__name__)

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
                    logger.warning(f"User '{interaction.user.name}' of '{interaction.guild.name}' attempted to run an Admin command.")
                    embed = discord.Embed()
                    embed.color = 0xFF0000
                    embed.title = "Permission Denied"
                    embed.description = "You don't have permission to use this command."
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return None
            except json.JSONDecodeError:
                print(f"Error: Failed to parse ADMINS environment variable: {admin_list_str}")
                await interaction.followup.send("An error occurred while checking permissions.", ephemeral=True)
                return None
        return wrapper
    return decorator
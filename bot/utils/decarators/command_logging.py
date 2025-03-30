import logging
import inspect
import functools
from typing import Callable, Any
import discord

logger = logging.getLogger(__name__)

def log_command_usage():
    """
    Decorator that logs when a slash command is used, who used it, and with what arguments.
    To be used with Discord slash commands in both cogs and standalone functions.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Determine if this is a cog method or a standalone command
            interaction = None
            
            # For cog methods, args[0] is self and args[1] is interaction
            if len(args) >= 2 and isinstance(args[1], discord.Interaction):
                interaction = args[1]
                command_name = func.__name__
            # For standalone commands, args[0] is interaction
            elif len(args) >= 1 and isinstance(args[0], discord.Interaction):
                interaction = args[0]
                command_name = func.__name__
            
            # Log the command usage if we found an interaction
            if interaction:
                user = f"{interaction.user.name} ({interaction.user.id})"
                guild = f"{interaction.guild.name} ({interaction.guild.id})" if interaction.guild else "DM"
                args_str = ', '.join([f"{k}={repr(v)}" for k, v in kwargs.items()])
                
                logger.info(f"Command '{command_name}' executed by {user} in {guild}{ ' with args ' + args_str if args_str else ''}")
            
            # Call the original function with all original arguments
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator
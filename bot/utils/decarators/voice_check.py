import functools
import discord
from discord import app_commands
from typing import Callable, TypeVar, ParamSpec, Awaitable, cast, Any

P = ParamSpec('P')
T = TypeVar('T')

def require_voice_channel(
    ephemeral: bool = True
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    A decorator that checks if the user is in a voice channel before executing the command.
    
    Args:
        ephemeral (bool, optional): Whether the response should be ephemeral. Defaults to True.
    """
    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Find the interaction object
            interaction = next((arg for arg in args if isinstance(arg, discord.Interaction)), 
                             kwargs.get('interaction', None))
            
            if not interaction:
                # If there's no interaction, just call the original function
                return await func(*args, **kwargs)
            
            # Check if the user is in a voice channel
            if not interaction.user.voice:
                await interaction.response.send_message(
                    "You're not in a voice channel! Please join a voice channel and try again.", 
                    ephemeral=ephemeral
                )
                return cast(T, None)
            
            # If the user is in a voice channel, proceed with the command
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator
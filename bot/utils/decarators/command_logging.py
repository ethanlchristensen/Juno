import functools
import logging
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

import discord

P = ParamSpec("P")
T = TypeVar("T")

logger = logging.getLogger(__name__)


def log_command_usage() -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Decorator that logs when a slash command is used, who used it, and with what arguments.
    To be used with Discord slash commands in both cogs and standalone functions.
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Find the interaction object
            interaction = next(
                (arg for arg in args if isinstance(arg, discord.Interaction)),
                kwargs.get("interaction", None),
            )

            if interaction:
                command_name = func.__name__
                user = f"{interaction.user.name} ({interaction.user.id})"
                guild = f"{interaction.guild.name} ({interaction.guild.id})" if interaction.guild else "DM"
                args_str = ", ".join([f"{k}={repr(v)}" for k, v in kwargs.items()])

                logger.info(f"Command '{command_name}' executed by {user} in {guild}{' with args ' + args_str if args_str else ''}")

            # Call the original function with all original arguments
            return await func(*args, **kwargs)

        return wrapper

    return decorator

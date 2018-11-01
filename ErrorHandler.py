from discord.ext import commands
import os
import discord
import dotenv

dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
BOT_CHANNEL= os.environ.get('BOT_CHANNEL')
board_id = os.environ.get('BOARD_ID')

class CommandErrorHandler:
    def __init__(self, bot):
        self.bot = bot

    async def on_command_error(self, error: Exception, ctx: commands.Context):
        """The event triggered when an error is raised while invoking a command.
        ctx   : Context
        error : Exception"""

        if hasattr(ctx.command, 'on_error'):
            return

        ignored = (commands.BadArgument)
        error = getattr(error, 'original', error)

        if isinstance(error, ignored):
            return

        elif isinstance(error, commands.DisabledCommand):
            await self.bot.send_message(ctx.message.channel, '{} has been disabled.'.format(ctx.command))
            return

        elif isinstance(error, commands.NoPrivateMessage):
            try:
                await self.bot.send_message(ctx.message.author, '{} can not be used in Private Messages.'.format(ctx.command))
                return
            except discord.Forbidden:
                pass

        elif isinstance(error, commands.UserInputError):
            bot_channel = discord.utils.get(self.bot.get_all_channels(),name=BOT_CHANNEL)
            board_channel = self.bot.get_channel(board_id)
            if ctx.message.channel == board_channel :
                await self.bot.send_message(bot_channel, "Bad arguments")
            else : await self.bot.send_message(ctx.message.channel, "Bad arguments")
            return

        elif isinstance(error, commands.CommandNotFound):
            bot_channel = discord.utils.get(self.bot.get_all_channels(),name=BOT_CHANNEL)
            board_channel = self.bot.get_channel(board_id)
            if ctx.message.channel == board_channel :
                await self.bot.send_message(bot_channel, "Bad arguments")
            else : await self.bot.send_message(ctx.message.channel, "Bad arguments")
            return

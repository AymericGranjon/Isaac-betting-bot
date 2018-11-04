import os
import dotenv
from sqlalchemy import create_engine, ForeignKey
from sqlalchemy import Column, Date, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import exists

from classes import Base, Racer, Bet, Race, Better
from ErrorHandler import CommandErrorHandler
from commandBetter import CommandBetter
from commandBookmaker import CommandBookmaker, displayOpenRaces

from datetime import datetime, timedelta
import sys
from apscheduler.schedulers.asyncio  import AsyncIOScheduler
import asyncio

import discord
from discord.ext import commands

dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))  # Loading .env
db_adress = os.environ.get('DB_ADRESS')
TOKEN = os.environ.get('BOT_TOKEN')
board_id = os.environ.get('BOARD_ID')
bookmaker_role = os.environ.get('BOOKMAKER_ROLE')
BOT_CHANNEL= os.environ.get('BOT_CHANNEL')

engine = create_engine(db_adress, echo =False)
Session = sessionmaker(bind=engine)



def main() :
    scheduler = AsyncIOScheduler()
    scheduler.start()
    bot = commands.Bot(command_prefix='!')
    session = Session()
    bot.add_cog(CommandErrorHandler(bot))
    bot.add_cog(CommandBetter(bot, session))
    bot.add_cog(CommandBookmaker(bot,session,scheduler))
    Base.metadata.create_all(engine)


    @bot.event
    async def on_ready():
        print('We have logged in as {0.user}'.format(bot))
        #check is there is a new memebers since last login, and give them 500
        for member in bot.get_all_members():
            if ((not member.bot or member == bot.user) and not session.query(exists().where(Better.id == member.id)).scalar()) :
                better = Better(id = member.id, name = member.display_name, coin = 500)
                session.add(better)
        session.commit()
        board_channel = bot.get_channel(board_id)
        message = bot.logs_from(board_channel, limit =1)
        async for m in message :
            await bot.delete_message(m)
        await bot.send_message(board_channel,displayOpenRaces(session))


    @bot.event
    async def on_member_join(member) :     #add member on the db and give 500 on join
        if (not member.bot and not session.query(exists().where(Better.id == member.id)).scalar()) :
            better = Better(id = member.id, name = member.display_name, coin = 500)
            session.add(better)
        session.commit()

    @bot.event
    async def on_member_update(before, after):     #change name in the db when a user's name is changed
        if before.display_name != after.display_name :
            better = session.query(Better).get(before.id)
            better.name = after.display_name
            session.commit()

    @bot.event
    async def on_message(message) :
        str = message.content
        if message.author == bot.user:
            pass
        elif (message.channel.id == board_id) :
            await bot.delete_message(message)
        await bot.process_commands(message)

    bot.run(TOKEN)

if __name__ == '__main__':
    main()

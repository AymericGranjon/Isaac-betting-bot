import os
import dotenv
import discord
from discord.ext import commands
import sqlalchemy
from sqlalchemy import create_engine, ForeignKey
from sqlalchemy import Column, Date, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import exists
from classes import Base, Racer, Bet, Race, Better
import mysql.connector


dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))  # Loading .env
db_adress = os.environ.get('DB_ADRESS')
BOT_CHANNEL= os.environ.get('BOT_CHANNEL')
db_racing = os.environ.get('DB_RACING')

class CommandBetter:
    def __init__(self, bot, session):
        self.bot = bot
        self.session = session

    def is_channel(channel_name):
        def predicate(ctx):
            return ctx.message.channel.name == channel_name
        return commands.check(predicate)

    def getWinrateRacing(self, racer1_name, racer2_name) :
        engineR = create_engine(db_racing, echo =False)
        SessionR = sessionmaker(bind=engineR)
        sessionR = SessionR()
        query = ("""select SUM((t1.place < t2.place and t1.place!=-1) or (t1.place!=-1 and t2.place=-1)) /
(SUM((t1.place < t2.place and t1.place!=-1) or (t1.place!=-1 and t2.place=-1))
+ SUM((t1.place > t2.place and t2.place!=-1) or (t2.place!=-1 and t1.place=-1)))*100 as winrate, SUM(t1.race_id = t2.race_id) as gamePlayed
from race_participants t1, race_participants t2 where t1.user_id =(
        select id from users where username='{}'
    )
and t2.user_id = (
        select id from users where username='{}'
    )
and t1.race_id = t2.race_id;""").format(racer1_name, racer2_name)
        toReturn = sessionR.execute(query)
        sessionR.close()
        return toReturn

    @commands.command(help = "Gives the winrate of one racer over another (use R+ names)")
    @is_channel(channel_name = BOT_CHANNEL)
    async def getWinrate(self, racer1_name, racer2_name) :
        result = self.getWinrateRacing(racer1_name, racer2_name)
        result = result.first()
        await self.bot.say("""```{} placed higher than {} {}% of the time out of {} races on Racing+!```""".format(racer1_name, racer2_name, result[0], result[1]))

    @is_channel(channel_name = BOT_CHANNEL)
    @commands.command(pass_context=True,
                 help = "Get the amount of coin you or an user have")
    async def coin(self, ctx, *users) :
        # todo : support @
        if len(users) == 0 :
            better = self.session.query(Better).get(ctx.message.author.id)
            await self.bot.say('You have {:d} coins'.format(better.coin))
        else :
            for name in users :
                if self.session.query(exists().where(Better.name == name)).scalar() :
                    better =  self.session.query(Better).filter(Better.name == name).first()
                    await self.bot.say('{:s} has {:d} coins'.format(better.name, better.coin))
                else :
                    await self.bot.say("{:s} doesn't exist".format(name))


    @is_channel(channel_name = BOT_CHANNEL)
    @commands.command(pass_context=True, help = "Place a bet")
    async def bet (self, ctx, race_id, winner_name, coin) : #no check if coin is an integer
        if (not self.session.query(exists().where(Race.id == race_id)).scalar()) :
            await self.bot.say("This race doesn't exist")
            return
        race = self.session.query(Race).get(race_id)
        if not race.betsOn :
            await self.bot.say("The bets for this race are closed")
            return
        if  not (race.racer1.name == winner_name or race.racer2.name == winner_name ) :
            await self.bot.say("{} is not in this race".format(winner_name))
            return
        better =  self.session.query(Better).get(ctx.message.author.id)
        if better.coin < int(coin) :
            await self.bot.say ("You don't have enough coins. Curent balance : {}".format(better.coin))
            return
        winner = self.session.query(Racer).filter(Racer.name == winner_name).first()
        if race.racer1_id == winner.id :
            odd = race.odd1
        elif race.racer2_id == winner.id :
            odd = race.odd2
        else :
            await self.bot.say("Databese error")
            return
        bet = Bet(better_id = ctx.message.author.id, better = better, race_id = race_id, race = race, winner_id = winner.id, winner = winner, coin_bet = coin, odd = odd)
        better.coin = better.coin - int(coin)
        self.session.add(bet)
        self.session.commit()
        await self.bot.say("Bet placed")


    @is_channel(channel_name = BOT_CHANNEL)
    @commands.command(pass_context=True, help = "Get current bets")
    async def currentBets(self, ctx) :
        message = ""
        better = self.session.query(Better).get(ctx.message.author.id)
        for bet in self.session.query(Bet).filter(Bet.better_id == better.id) :
            if bet.race.ongoing == True :
                message = message + "\n" + str(bet)
        await self.bot.say("Your current bets are : ```"+message+"```")

def setup(bot):
    bot.add_cog(Better(bot))

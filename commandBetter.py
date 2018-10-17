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


dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))  # Loading .env
db_adress = os.environ.get('DB_ADRESS')

engine = create_engine(db_adress, echo =False)
Session = sessionmaker(bind=engine)
session = Session()
Base.metadata.create_all(engine)

class CommandBetter:
    def __init__(self, bot):
        self.bot = bot


    @commands.command(pass_context=True,
                 help = "Get the amount of coin you or an user have")
    async def coin(self, ctx, *users) :
        # todo : support @
        if len(users) == 0 :
            better = session.query(Better).get(ctx.message.author.id)
            await self.bot.say('You have {:d} coins'.format(better.coin))
        else :
            for name in users :
                if session.query(exists().where(Better.name == name)).scalar() :
                    better =  session.query(Better).filter(Better.name == name).first()
                    await self.bot.say('{:s} has {:d} coins'.format(better.name, better.coin))
                else :
                    await self.bot.say("{:s} doesnt exist".format(name))


    @commands.command(pass_context=True, help = "Place a bet")
    async def bet (self, ctx, race_id, winner_name, coin) : #no check if coin is an integer
        if (not session.query(exists().where(Race.id == race_id)).scalar()) :
            await self.bot.say("This race deosn't exist")
            return
        race = session.query(Race).get(race_id)
        if not race.betsOn :
            await self.bot.say("The bets for this race are closed")
            return
        if  not (race.racer1.name == winner_name or race.racer2.name == winner_name ) :
            await self.bot.say("{} is not in this race".format(winner_name))
            return
        better =  session.query(Better).get(ctx.message.author.id)
        if better.coin < int(coin) :
            await self.bot.say ("You don't have enough coins. Curent balance : {}".format(better.coin))
            return
        winner = session.query(Racer).filter(Racer.name == winner_name).first()
        if race.racer1_id == winner.id :
            odd = race.odd1
        elif race.racer2_id == winner.id :
            odd = race.odd2
        else :
            await self.bot.say("Databese error")
            return
        bet = Bet(better_id = ctx.message.author.id, better = better, race_id = race_id, race = race, winner_id = winner.id, winner = winner, coin_bet = coin, odd = odd)
        better.coin = better.coin - int(coin)
        session.add(bet)
        session.commit()
        await self.bot.say("Bet placed")


    @commands.command(pass_context=True, help = "Get current bets")
    async def currentBets(self, ctx) :
        message = ""
        better = session.query(Better).get(ctx.message.author.id)
        for bet in session.query(Bet).filter(Bet.better_id == better.id) :
            if bet.race.ongoing == True :
                message = message + "\n" + str(bet)
        await self.bot.say("Your current bets are : ```"+message+"```")

def setup(bot):
    bot.add_cog(Better(bot))

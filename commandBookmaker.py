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
board_id = os.environ.get('BOARD_ID')
board_message_id = os.environ.get('BOARD_MESSAGE_ID')
bookmaker_role = os.environ.get('BOOKMAKER_ROLE')

engine = create_engine(db_adress, echo =False)
Session = sessionmaker(bind=engine)
session = Session()
Base.metadata.create_all(engine)

class CommandBookmaker:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(help = "Add a match, open by default")
    @commands.has_role(bookmaker_role)
    async def addMatch(self, racer1_name, odd1, racer2_name, odd2) :
        if (not session.query(exists().where(Racer.name == racer1_name)).scalar()) :
            await self.bot.say("{:s} doesn't exist".format(racer1_name))
        elif (not session.query(exists().where(Racer.name == racer2_name)).scalar()) :
            await self.bot.say("{:s} doesn't exist".format(racer2_name))
        else :
            racer1 = session.query(Racer).filter(Racer.name == racer1_name).first()
            racer2 = session.query(Racer).filter(Racer.name == racer2_name).first()
            race = Race(racer1_id = racer1.id, odd1 = odd1, racer2_id = racer2.id, odd2 = odd2, ongoing = True, betsOn = True)
            session.add(race)
            session.commit()
            await self.bot.say("Race created : \n" + str(race))
            board_channel = bot.get_channel(board_id)
            board_message = await bot.get_message(board_channel, board_message_id)
            await self.bot.edit_message(board_message,displayOpenRaces())

    @commands.command(help = "Close the bets for a match")
    @commands.has_role(bookmaker_role)
    async def closeBets(self,race_id) : #Close race, todo : display  race id and Who vs Who
        if (not session.query(exists().where(Race.id == race_id)).scalar()) :
            await self.bot.say("This race deosn't exist")
            return
        race = session.query(Race).get(race_id)
        if race.betsOn == False :
            await self.bot.say("The bets are already closed for this race")
            return
        race.betsOn = False
        await self.bot.say("The bets have been closed")
        session.commit()
        board_channel = self.bot.get_channel(board_id)
        board_message = await self.bot.get_message(board_channel, board_message_id)
        await self.bot.edit_message(board_message,displayOpenRaces())


    @commands.command(help = "Open the bets for a match")
    @commands.has_role(bookmaker_role)
    async def openBets(self, race_id) : #Close bets, todo : display  race id and Who vs Who
        if (not session.query(exists().where(Race.id == race_id)).scalar()) :
            await self.bot.say("This race deosn't exist")
            return
        race = session.query(Race).get(race_id)
        if race.betsOn == True :
            await self.bot.say("The bets are already opened for this race")
            return
        race.betsOn = True
        await self.bot.say("The bets have been opened")
        session.commit()
        board_channel = self.bot.get_channel(board_id)
        board_message = await self.bot.get_message(board_channel, board_message_id)
        await self.bot.edit_message(board_message,displayOpenRaces())

    @commands.command(help = "Add a racer")
    @commands.has_role(bookmaker_role)
    async def addRacer (self, name, value) :
        racer = Racer(name = name, value = value)
        session.add(racer)
        session.commit()

    @commands.command(help = "Change the multiplier for a racer in a match")
    @commands.has_role(bookmaker_role)
    async def changeOdds (self, race_id, racer_name, odd) :
        if (not session.query(exists().where(Race.id == race_id)).scalar()) :
            await self.bot.say("This race deosn't exist")
            return
        race = session.query(Race).get(race_id)
        if race.racer1.name == racer_name :
            race.odd1 = odd
        elif race.racer1.name == racer_name :
            race.odd1 = odd
        else :
            await self.bot.say("{} is not in this race".format(racer_name))
        board_channel = bot.get_channel(board_id)
        board_message = await self.bot.get_message(board_channel, board_message_id)
        await self.bot.edit_message(board_message,displayOpenRaces())

    @commands.command(help = "Close a match and give winners their due")
    @commands.has_role(bookmaker_role)
    async def closeMatch(self, race_id, winner_name) :
        if (not session.query(exists().where(Race.id == race_id)).scalar()) :
            await self.bot.say("This race deosn't exist")
            return
        race = session.query(Race).get(race_id)
        if not race.ongoing :
            await self.bot.say("The race is already closed")
            return
        if  not (race.racer1.name == winner_name or race.racer2.name == winner_name ) :
            await self.bot.say("{} is not in this race".format(winner_name))
            return
        if race.racer1.name == winner_name :
            loser_name = race.racer2.name
        else :
            loser_name = race.racer1.name
        winner_message = ""
        for bet in session.query(Bet).filter(Bet.race_id == race_id) : #Regroup better
            if bet.winner.name == winner_name :
                better = bet.better
                better.coin = better.coin + round(bet.coin_bet*bet.odd)
                winner_message = winner_message + "* {} ({}->{}) \n".format(better.name, bet.coin_bet,round(bet.coin_bet*bet.odd)) #If a better win multiple times, group it
        if winner_message == "" :
            await self.bot.say(("```{} defeated {} ! Nobody would've guessed that !```").format(winner_name, loser_name))
        else :
            await self.bot.say(("```{} defeated {} ! Congratulations : \n" + winner_message+"```").format(winner_name, loser_name))
#        race.ongoing = False
#        race.betsOn = False
        board_channel = self.bot.get_channel(board_id)
        board_message = await self.bot.get_message(board_channel, board_message_id)
        await self.bot.edit_message(board_message,displayOpenRaces())
        session.commit()
#back up command to cancel the outcome of a race in case of someone fuck up  ?

    @commands.command(help = "Give an user coins")
    @commands.has_role(bookmaker_role)
    async def giveCoin(self, better_name, coin) :
        if not session.query(exists().where(Better.name == better_name)).scalar():
            await self.bot.say("This better doesn't exist")
            return
        better =  session.query(Better).filter(Better.name == better_name).first()
        better.coin = better.coin + int(coin)
        session.commit()

def displayOpenRaces(): #use PrettyTables
    toDisplayOn = ""
    toDisplayOff = ""
    for race in session.query(Race).filter(Race.ongoing == True):
        if race.betsOn == True :
            toDisplayOn = toDisplayOn + "\n" +  str(race)
        else :
            toDisplayOff = toDisplayOff + "\n" +  str(race)

    return "Open bets : ```"+toDisplayOn+"``` \n Closed bets : \n```" + toDisplayOff+"```"

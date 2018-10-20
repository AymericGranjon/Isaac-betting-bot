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
board_id = os.environ.get('BOARD_ID')
board_message_id = os.environ.get('BOARD_MESSAGE_ID')
bookmaker_role = os.environ.get('BOOKMAKER_ROLE')
db_racing = os.environ.get('DB_RACING')

class CommandBookmaker:
    def __init__(self, bot, session):
        self.bot = bot
        self.session = session

    def getOdd(racer1_name, racer2_name, format) :
        engineR = create_engine(db_racing, echo =False)
        SessionR = sessionmaker(bind=engineR)
        sessionR = SessionR()
        if format == "mutiple" :

        else :


    @commands.command(help = "Add a match, open by default, format mutiple by default")
    @commands.has_role(bookmaker_role)
    async def addMatch(self, racer1_name, odd1, racer2_name, odd2, *format) :
        if (not self.session.query(exists().where(Racer.name == racer1_name)).scalar()) :
            await self.bot.say("{:s} doesn't exist".format(racer1_name))
            return
        elif (not self.session.query(exists().where(Racer.name == racer2_name)).scalar()) :
            await self.bot.say("{:s} doesn't exist".format(racer2_name))
            return
        elif not (format == "diversity" or format == "multiple" or format == "seeded" or format =="unseeded") or len(format) > 1 :
            await self.bot.say("{:s} is not a valid format. Valid formats are diversity, multiple, seeded or unseeded.".format(format))
            return
        else :
            if len(format) == 0 :
                format = "multiple"
            racer1 = self.session.query(Racer).filter(Racer.name == racer1_name).first()
            racer2 = self.session.query(Racer).filter(Racer.name == racer2_name).first()
            race = Race(racer1_id = racer1.id, odd1 = getOdd(racer1.name_racing, racer2.name_racing, format), racer2_id = racer2.id, odd2 = getOdd(racer2.name_racing, racer1.name_racing ,format), ongoing = True, betsOn = True, format = format )
            self.session.add(race)
            self.session.commit()
            await self.bot.say("Race created : \n" + str(race))
            board_channel = bot.get_channel(board_id)
            board_message = await bot.get_message(board_channel, board_message_id)
            await self.bot.edit_message(board_message,displayOpenRaces(self.session))

    @commands.command(help = "Close the bets for a match")
    @commands.has_role(bookmaker_role)
    async def closeBets(self,race_id) : #Close race, todo : display  race id and Who vs Who
        if (not self.session.query(exists().where(Race.id == race_id)).scalar()) :
            await self.bot.say("This race doesnt't exist")
            return
        race = self.session.query(Race).get(race_id)
        if race.betsOn == False :
            await self.bot.say("The bets are already closed for this race")
            return
        race.betsOn = False
        await self.bot.say("The bets have been closed")
        self.session.commit()
        board_channel = self.bot.get_channel(board_id)
        board_message = await self.bot.get_message(board_channel, board_message_id)
        await self.bot.edit_message(board_message,displayOpenRaces(self.session))


    @commands.command(help = "Open the bets for a match")
    @commands.has_role(bookmaker_role)
    async def openBets(self, race_id) : #Close bets, todo : display  race id and Who vs Who
        if (not self.session.query(exists().where(Race.id == race_id)).scalar()) :
            await self.bot.say("This race doesn't exist")
            return
        race = self.session.query(Race).get(race_id)
        if race.betsOn == True :
            await self.bot.say("The bets are already opened for this race")
            return
        race.betsOn = True
        await self.bot.say("The bets have been opened")
        self.session.commit()
        board_channel = self.bot.get_channel(board_id)
        board_message = await self.bot.get_message(board_channel, board_message_id)
        await self.bot.edit_message(board_message,displayOpenRaces(self.session))

    @commands.command(help = "Add a racer")
    @commands.has_role(bookmaker_role)
    async def addRacer (self, *name) :
        if (self.session.query(exists().where(Racer.name == name[0])).scalar()) :
            await self.bot.say("This racer already exist")
            return
        if len(name) == 0 :
            await self.bot.say("Bad Arguments")
            return
        elif len(name) == 1 :
            racer = Racer(name = name[0], name_racing = name[0], name_trueskill = name[0])
        elif len(name) == 2 :
            racer = Racer(name = name[0], name_racing = name[1], name_trueskill = name[0])
        elif len(name) == 3 :
            racer = Racer(name = name[0], name_racing = name[1], name_trueskill = name[2])
        self.session.add(racer)
        self.session.commit()

    @commands.command(help = "Change a racer name on a database (Trueskill, Racing+, Betting)")
    @commands.has_role(bookmaker_role)
    async def changeName (self, name, database, new_name) :
        if (not self.session.query(exists().where(Racer.name == name)).scalar()) :
            await self.bot.say("This racer doesn't exist")
            return
        racer = self.session.query(Racer).filter(Racer.name == name).first()
        if database == "Trueskill" :
            racer.name_trueskill = new_name
        elif database == "Racing+" :
            racer.name_racing = new_name
        elif database == "Betting" :
            racer.name = new_name
        else :
            await self.bot.say("Wrong database")
        self.session.commit()

    @commands.command(help = "Change the multiplier for a racer in a match")
    @commands.has_role(bookmaker_role)
    async def changeOdds (self, race_id, racer_name, odd) :
        if (not self.session.query(exists().where(Race.id == race_id)).scalar()) :
            await self.bot.say("This race doesn't exist")
            return
        race = self.session.query(Race).get(race_id)
        if race.racer1.name == racer_name :
            race.odd1 = odd
        elif race.racer1.name == racer_name :
            race.odd1 = odd
        else :
            await self.bot.say("{} is not in this race".format(racer_name))
        board_channel = bot.get_channel(board_id)
        board_message = await self.bot.get_message(board_channel, board_message_id)
        await self.bot.edit_message(board_message,displayOpenRaces(self.session))

    @commands.command(help = "Close a match and give winners their due")
    @commands.has_role(bookmaker_role)
    async def closeMatch(self, race_id, winner_name) :
        if (not self.session.query(exists().where(Race.id == race_id)).scalar()) :
            await self.bot.say("This race deosn't exist")
            return
        race = self.session.query(Race).get(race_id)
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
        for bet in self.session.query(Bet).filter(Bet.race_id == race_id) : #Regroup better
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
        await self.bot.edit_message(board_message,displayOpenRaces(self.session))
        self.session.commit()
#back up command to cancel the outcome of a race in case of someone fuck up  ?

    @commands.command(help = "Give an user coins")
    @commands.has_role(bookmaker_role)
    async def giveCoin(self, better_name, coin) :
        if not self.session.query(exists().where(Better.name == better_name)).scalar():
            await self.bot.say("This better doesn't exist")
            return
        better =  self.session.query(Better).filter(Better.name == better_name).first()
        better.coin = better.coin + int(coin)
        self.session.commit()

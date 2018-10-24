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
import itertools
import math
import trueskill


dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))  # Loading .env
db_adress = os.environ.get('DB_ADRESS')
board_id = os.environ.get('BOARD_ID')
board_message_id = os.environ.get('BOARD_MESSAGE_ID')
bookmaker_role = os.environ.get('BOOKMAKER_ROLE')
db_racing = os.environ.get('DB_RACING')
bookmaker_channel = os.environ.get('BOOKMAKER_CHANNEL')
BOT_CHANNEL= os.environ.get('BOT_CHANNEL')
commision = 0.9 #We take 10% of the winnings, 1-commision actually

def displayOpenRaces(session): #use PrettyTables
    toDisplayOn = ""
    toDisplayOff = ""
    for race in session.query(Race).filter(Race.ongoing == True):
        if race.betsOn == True :
            toDisplayOn = toDisplayOn + "\n" +  str(race)
        else :
            toDisplayOff = toDisplayOff + "\n" +  str(race)
    if toDisplayOn == "" : toDisplayOn = " "
    if toDisplayOff == "" : toDisplayOff = " "
    return "Open bets : ```"+toDisplayOn+"``` \n Closed bets : \n```" + toDisplayOff+"```"

class CommandBookmaker:
    def __init__(self, bot, session):
        self.bot = bot
        self.session = session

    def is_channel(channel_name):
        def predicate(ctx):
            return ctx.message.channel.name == channel_name
        return commands.check(predicate)

    def getOddVs(self, racer1_name, racer2_name, format) :
        engineR = create_engine(db_racing, echo =False)
        SessionR = sessionmaker(bind=engineR)
        sessionR = SessionR()
        if format == "multiple" :
            query_racer1 = ("""select r1.seeded_trueskill_mu, r1.seeded_trueskill_sigma, r1.unseeded_trueskill_mu, r1.unseeded_trueskill_sigma, r1.diversity_trueskill_mu, r1.diversity_trueskill_sigma  from users r1 where r1.username = '{}';""").format(racer1_name)
            query_racer2 = ("""select r1.seeded_trueskill_mu, r1.seeded_trueskill_sigma, r1.unseeded_trueskill_mu, r1.unseeded_trueskill_sigma, r1.diversity_trueskill_mu, r1.diversity_trueskill_sigma  from users r1 where r1.username = '{}';""").format(racer2_name)
            racer1_trueskill = sessionR.execute(query_racer1)
            racer1_trueskill= racer1_trueskill.first()
            racer2_trueskill = sessionR.execute(query_racer2)
            racer2_trueskill= racer2_trueskill.first()
            racer1 = [[(racer1_trueskill[0]+racer1_trueskill[2]+racer1_trueskill[4])/3,(racer1_trueskill[1]+racer1_trueskill[3]+racer1_trueskill[5])/3]]
            racer2 = [[(racer2_trueskill[0]+racer2_trueskill[2]+racer2_trueskill[4])/3,(racer2_trueskill[1]+racer2_trueskill[3]+racer2_trueskill[5])/3]]

        else :
            query_racer1 = ("""select r.{}_trueskill_mu, r.{}_trueskill_sigma from users r where r.username = '{}';""").format(format,format,racer1_name)
            query_racer2 = ("""select r.{}_trueskill_mu, r.{}_trueskill_sigma from users r where r.username = '{}';""").format(format,format,racer2_name)
            racer1_trueskill = sessionR.execute(query_racer1)
            racer1_trueskill= racer1_trueskill.first()
            racer2_trueskill = sessionR.execute(query_racer2)
            racer2_trueskill= racer2_trueskill.first()
            racer1 = [[racer1_trueskill[0], racer1_trueskill[1]]]
            racer2 = [[racer2_trueskill[0], racer2_trueskill[1]]]
        delta_mu = sum(format[0] for format in racer1) - sum(format[0] for format in racer2)
        sum_sigma = sum(format[1] ** 2 for format in itertools.chain(racer1, racer2))
        size = len(racer1) + len(racer2)
        denom = math.sqrt(size * (trueskill.BETA * trueskill.BETA) + sum_sigma)
        ts = trueskill.global_env()
        sessionR.close()
        return round(1+(1/ts.cdf(delta_mu / denom) - 1)*commision,2)

    @commands.command()
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def testOdds(self, racer1_name, racer2_name, format) :
        await self.bot.say(self.getOddVs(racer1_name, racer2_name, format))
        return


    @commands.command(help = "Add a match, open by default, format mutiple by default")
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def addMatch(self, racer1_name, racer2_name, *format) :
        if len(format) == 0 :
            format = "multiple"
        else : format = format[0]
        if (not self.session.query(exists().where(Racer.name == racer1_name)).scalar()) :
            await self.bot.say("{:s} doesn't exist".format(racer1_name))
            return
        elif (not self.session.query(exists().where(Racer.name == racer2_name)).scalar()) :
            await self.bot.say("{:s} doesn't exist".format(racer2_name))
            return
        elif not (format == "diversity" or format == "multiple" or format == "seeded" or format =="unseeded") :
            await self.bot.say("{:s} is not a valid format. Valid formats are diversity, multiple, seeded or unseeded.".format(format))
            return
        else :
            racer1 = self.session.query(Racer).filter(Racer.name == racer1_name).first()
            racer2 = self.session.query(Racer).filter(Racer.name == racer2_name).first()
            race = Race(racer1_id = racer1.id, odd1 = self.getOddVs(racer1.name_racing, racer2.name_racing, format), racer2_id = racer2.id, odd2 = self.getOddVs(racer2.name_racing, racer1.name_racing ,format), ongoing = True, betsOn = True, format = format )
            self.session.add(race)
            self.session.commit()
            await self.bot.say("```Match created : \n" + str(race)+"```")
            board_channel = self.bot.get_channel(board_id)
            board_message = await self.bot.get_message(board_channel, board_message_id)
            await self.bot.edit_message(board_message,displayOpenRaces(self.session))

    @commands.command(help = "Close the bets for a match")
    @is_channel(channel_name = bookmaker_channel)
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
    @is_channel(channel_name = bookmaker_channel)
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
    @is_channel(channel_name = bookmaker_channel)
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
        await self.bot.say("{} has been added as a racer".format(racer.name))


    @commands.command(help = "Change a racer name on a database (Trueskill, Racing+, Betting)")
    @is_channel(channel_name = bookmaker_channel)
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
    @is_channel(channel_name = bookmaker_channel)
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
        board_channel = self.bot.get_channel(board_id)
        board_message = await self.bot.get_message(board_channel, board_message_id)
        await self.bot.edit_message(board_message,displayOpenRaces(self.session))

    @commands.command(help = "Close a match and give winners their due")
    @is_channel(channel_name = bookmaker_channel)
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
        board_channel = discord.utils.get(self.bot.get_all_channels(),name=BOT_CHANNEL)
        DaCream = self.session.query(Better).filter(Better.id == self.bot.user.id).first()
        for bet in self.session.query(Bet).filter(Bet.race_id == race_id) : #Regroup better
            if bet.winner.name == winner_name :
                better = bet.better
                better.coin = better.coin + round(bet.coin_bet*bet.odd)
                winner_message = winner_message + "* {} ({}->{}) \n".format(better.name, bet.coin_bet,round(bet.coin_bet*bet.odd)) #If a better win multiple times, group it
                DaCream.coin = DaCream.coin - round(bet.coin_bet*bet.odd)
        if winner_message == "" :
            await self.bot.send_message(board_channel,("```{} defeated {} ! Nobody would've guessed that !```").format(winner_name, loser_name))
        else :
            await self.bot.send_message(board_channel,("```{} defeated {} ! Congratulations : \n" + winner_message+"```").format(winner_name, loser_name))
        race.ongoing = False
        race.betsOn = False
        board_channel = self.bot.get_channel(board_id)
        board_message = await self.bot.get_message(board_channel, board_message_id)
        await self.bot.edit_message(board_message,displayOpenRaces(self.session))
        self.session.commit()
#back up command to cancel the outcome of a race in case of someone fuck up  ?

    @commands.command(help = "Give an user coins")
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def giveCoin(self, better_name, coin) :
        if not self.session.query(exists().where(Better.name == better_name)).scalar():
            await self.bot.say("This better doesn't exist")
            return
        better =  self.session.query(Better).filter(Better.name == better_name).first()
        better.coin = better.coin + int(coin)
        self.session.commit()

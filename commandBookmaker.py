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
from classes import Base, Racer, Bet, Race, Better, Tournament, Job
import mysql.connector
import itertools
import math
import trueskill
import texttable as tt
import urllib.request
import json
import dateparser
import datetime
import pytz
from tzlocal import get_localzone

dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))  # Loading .env
db_adress = os.environ.get('DB_ADRESS')
board_id = os.environ.get('BOARD_ID')
bookmaker_role = os.environ.get('BOOKMAKER_ROLE')
db_racing = os.environ.get('DB_RACING')
bookmaker_channel = os.environ.get('BOOKMAKER_CHANNEL')
BOT_CHANNEL= os.environ.get('BOT_CHANNEL')
SUMUP_CHANNEL = os.environ.get('SUMUP_CHANNEL')
commision = 0.8 #We take 20% of the winnings, 1-commision actually

async def closeBetScheduled (bot, session) :
    channel = discord.utils.get(bot.get_all_channels(),name=bookmaker_channel)
    for job in session.query(Job) :
        if (job.race.betsOn == True) and (pytz.utc.localize(job.date) <= datetime.datetime.now().astimezone(pytz.utc)) :
            job.race.betsOn = False
            await bot.send_message(channel,"```The bets have been closed for the match#{}```".format(job.race.id))
            session.delete(job)
            session.commit()
            board_channel = bot.get_channel(board_id)
            message = bot.logs_from(board_channel, limit =1)
            async for m in message :
                await bot.delete_message(m)
            await displayOpenRaces(session,bot)

async def displayOpenRaces(session,bot):
    messages = ["Open bets :"]
    for race in session.query(Race).filter(Race.ongoing == True).filter(Race.betsOn == True):
        messages.append("```" + str(race) + "```")
    messages.append("Closed bets :")
    for race in session.query(Race).filter(Race.ongoing == True).filter(Race.betsOn == False):
        messages.append("```" + str(race) + "```")
    board_channel = bot.get_channel(board_id)
    message = bot.logs_from(board_channel, limit =100)
    async for m in message :
        await bot.delete_message(m)
    count_message = 0
    message2send = ""
    for message in messages :
        if count_message == 5 :
            message2send = message2send + message
            await bot.send_message(board_channel,message2send)
            count_message = 0
            message2send = ""
        else :
            message2send = message2send + message
            count_message = count_message + 1
    if count_message != 0 :
        await bot.send_message(board_channel,message2send)


class CommandBookmaker:
    def __init__(self, bot, session):
        self.bot = bot
        self.session = session

    def is_channel(channel_name):
        def predicate(ctx):
            return ctx.message.channel.name == channel_name
        return commands.check(predicate)

    def getOddVs(self, racer1, racer2, format) :
        inTrueskill = 0
        engineR = create_engine(db_racing, echo =False)
        SessionR = sessionmaker(bind=engineR)
        sessionR = SessionR()
        contents_seeded = urllib.request.urlopen("https://isaacrankings.com/api/ratings/seeded").read()
        contents_unseeded = urllib.request.urlopen("https://isaacrankings.com/api/ratings/unseeded").read()
        contents_mixed = urllib.request.urlopen("https://isaacrankings.com/api/ratings/mixed").read()
        ts_seeded = json.loads(contents_seeded.decode('utf-8'))
        ts_unseeded = json.loads(contents_unseeded.decode('utf-8'))
        ts_mixed = json.loads(contents_mixed.decode('utf-8'))
        racer1_tournament = None
        racer2_tournament = None
        winrate_tournament = None

        if format == "multiple" :
            query_racer1 = ("""select r1.seeded_trueskill_mu, r1.seeded_trueskill_sigma, r1.unseeded_trueskill_mu, r1.unseeded_trueskill_sigma, r1.diversity_trueskill_mu, r1.diversity_trueskill_sigma  from users r1 where r1.username = '{}';""").format(racer1.name_racing)
            query_racer2 = ("""select r1.seeded_trueskill_mu, r1.seeded_trueskill_sigma, r1.unseeded_trueskill_mu, r1.unseeded_trueskill_sigma, r1.diversity_trueskill_mu, r1.diversity_trueskill_sigma  from users r1 where r1.username = '{}';""").format(racer2.name_racing)
            racer1_trueskill = sessionR.execute(query_racer1)
            racer1_trueskill= racer1_trueskill.first()
            racer2_trueskill = sessionR.execute(query_racer2)
            racer2_trueskill= racer2_trueskill.first()
            racer1_table = [[(racer1_trueskill[0]+racer1_trueskill[2]+racer1_trueskill[4])/3,(racer1_trueskill[1]+racer1_trueskill[3]+racer1_trueskill[5])/3]]
            racer2_table = [[(racer2_trueskill[0]+racer2_trueskill[2]+racer2_trueskill[4])/3,(racer2_trueskill[1]+racer2_trueskill[3]+racer2_trueskill[5])/3]]
            if (racer1.name_trueskill in ts_mixed["data"]) and (racer2.name_trueskill in ts_mixed["data"]) :
                inTrueskill = 1
                racer1_tournament = [[ts_mixed["data"][racer1.name_trueskill]["mu"],ts_mixed["data"][racer1.name_trueskill]["sigma"]]]
                racer2_tournament = [[ts_mixed["data"][racer2.name_trueskill]["mu"],ts_mixed["data"][racer2.name_trueskill]["sigma"]]]

        else :
            if format == "seeded" :
                ts_gen = ts_seeded
            else : ts_gen = ts_unseeded
            query_racer1 = ("""select r.{}_trueskill_mu, r.{}_trueskill_sigma from users r where r.username = '{}';""").format(format,format,racer1.name_racing)
            query_racer2 = ("""select r.{}_trueskill_mu, r.{}_trueskill_sigma from users r where r.username = '{}';""").format(format,format,racer2.name_racing)
            racer1_trueskill = sessionR.execute(query_racer1)
            racer1_trueskill= racer1_trueskill.first()
            racer2_trueskill = sessionR.execute(query_racer2)
            racer2_trueskill= racer2_trueskill.first()
            racer1_table = [[racer1_trueskill[0], racer1_trueskill[1]]]
            racer2_table = [[racer2_trueskill[0], racer2_trueskill[1]]]
            if (racer1.name_trueskill in ts_gen["data"]) and (racer2.name_trueskill in ts_gen["data"]) :
                inTrueskill = 1
                racer1_tournament = [[ts_gen["data"][racer1.name_trueskill]["mu"],ts_gen["data"][racer1.name_trueskill]["sigma"]]]
                racer2_tournament = [[ts_gen["data"][racer2.name_trueskill]["mu"],ts_gen["data"][racer2.name_trueskill]["sigma"]]]

        delta_mu = sum(format[0] for format in racer1_table) - sum(format[0] for format in racer2_table)
        sum_sigma = sum(format[1] ** 2 for format in itertools.chain(racer1_table, racer2_table))
        size = len(racer1_table) + len(racer2_table)
        denom = math.sqrt(size * (trueskill.BETA * trueskill.BETA) + sum_sigma)
        ts = trueskill.global_env()
        sessionR.close()
        winrate_racing = ts.cdf(delta_mu / denom)
        if not (racer1_tournament is None) :
            delta_mu = sum(format[0] for format in racer1_tournament) - sum(format[0] for format in racer2_tournament)
            sum_sigma = sum(format[1] ** 2 for format in itertools.chain(racer1_tournament, racer2_tournament))
            size = len(racer1_tournament) + len(racer2_tournament)
            denom = math.sqrt(size * (trueskill.BETA * trueskill.BETA) + sum_sigma)
            ts = trueskill.global_env()
            winrate_tournament = ts.cdf(delta_mu / denom)
            winrate = winrate_racing*0.3 + winrate_tournament*0.7
        else : winrate = winrate_racing
        #print("{} : {} {} {}".format(format, winrate, winrate_racing, winrate_tournament))
        return [round(1+(1/winrate - 1)*commision,2),inTrueskill]

    @commands.command()
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def testOdds(self, racer1_name, racer2_name, format) :
        racer1 = self.session.query(Racer).filter(Racer.name == racer1_name).first()
        racer2 = self.session.query(Racer).filter(Racer.name == racer2_name).first()
        [toOdd1,inTrueskill] = self.getOddVs(racer1, racer2, format)
        await self.bot.say(" {} {} Trueskill : {}".format(toOdd1,self.getOddVs(racer2, racer1, format)[0],inTrueskill))
        return


    @commands.command(help = "Add a match, open by default, format (optional) of the tournament by default")
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def addMatch(self, racer1_name, racer2_name, tournament, *format) :
        if (not self.session.query(exists().where(Tournament.name == tournament)).scalar()) :
            await self.bot.say("This tournament doesn't exist")
            return
        tournament = self.session.query(Tournament).filter(Tournament.name == tournament).first()
        if len(format) == 0 :
            format = tournament.format
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
        racer1 = self.session.query(Racer).filter(Racer.name == racer1_name).first()
        racer2 = self.session.query(Racer).filter(Racer.name == racer2_name).first()
        [toOdd1,inTrueskill] = self.getOddVs(racer1, racer2, format)
        race = Race(racer1_id = racer1.id, odd1 = toOdd1, racer2_id = racer2.id, odd2 = self.getOddVs(racer2, racer1 ,format)[0], ongoing = True, betsOn = True, format = format, tournament_id = tournament.id )
        self.session.add(race)
        self.session.commit()
        if inTrueskill :
            await self.bot.say("```Match created (using Trueskill): \n" + str(race)+"```")
        else :
            await self.bot.say("```Match created (not using Trueskill): \n" + str(race)+"```")
        board_channel = self.bot.get_channel(board_id)
        await displayOpenRaces(self.session,self.bot)

    @commands.command(help = "Add a tournament", aliases = ["addTourney","tourney","Tourney","tournament"])
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def addTournament(self, name, format, *challonge) :
        if self.session.query(exists().where(Tournament.name == name)).scalar() :
            await self.bot.say("A tournament with the same name already exists")
            return
        if len(challonge) == 0:
            challonge = ["None"]
        tournament = Tournament(name = name, format = format, challonge = challonge[0])
        self.session.add(tournament)
        self.session.commit()
        await self.bot.say("Tournament created : \n```" + str(tournament)+"```")

    @commands.command(help = "Change tournamment link")
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def changeLink(self, name, link) :
        if not(self.session.query(exists().where(Tournament.name == name)).scalar()) :
            await self.bot.say("This tournament doesn't exist")
            return
        tournament = self.session.query(Tournament).filter(Tournament.name == tournament).first()
        tournament.challonge = link
        await self.bot.say(str(tournament))
        self.session.commit()

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
        await displayOpenRaces(self.session,self.bot)


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
        if race.ongoing == False :
            await self.bot.say("This race is done")
            return
        race.betsOn = True
        await self.bot.say("The bets have been opened")
        self.session.commit()
        await displayOpenRaces(self.session,self.bot)

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
        await self.bot.say(str(racer))
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
        elif race.racer2.name == racer_name :
            race.odd2 = odd
        else :
            await self.bot.say("{} is not in this race".format(racer_name))
        await displayOpenRaces(self.session,self.bot)
        self.session.commit()

    @commands.command(help = "Close a match and give winners their due")
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def closeMatch(self, race_id, winner_name) :
        if (not self.session.query(exists().where(Race.id == race_id)).scalar()) :
            await self.bot.say("This race doesn't exist")
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
            race.winner = 1
        else :
            loser_name = race.racer1.name
            race.winner = 2
        winner_message = ""
        board_channel = self.bot.get_channel(board_id)
        DaCream = self.session.query(Better).filter(Better.id == self.bot.user.id).first()
        total_bet = 0
        total_paid = 0
        nb_bet = 0
        nb_bet_won = 0
        coin_bet_win = 0
        for bet in self.session.query(Bet).filter(Bet.race_id == race_id) : #Regroup better
            total_bet = total_bet + bet.coin_bet
            nb_bet = nb_bet +1
            if bet.winner.name == winner_name :
                nb_bet_won = nb_bet_won +1
                coin_bet_win = coin_bet_win + bet.coin_bet
                better = bet.better
                better.coin = better.coin + round(bet.coin_bet*bet.odd)
                winner_message = winner_message + "* {} ({}->{}) \n".format(better.name, bet.coin_bet,round(bet.coin_bet*bet.odd)) #If a better win multiple times, group it
                DaCream.coin = DaCream.coin - round(bet.coin_bet*bet.odd)
                total_paid = round(bet.coin_bet*bet.odd) + total_paid
        bot_channel = discord.utils.get(self.bot.get_all_channels(),name=BOT_CHANNEL)
        if winner_message == "" :
            await self.bot.send_message(bot_channel,("```{} defeated {} ! Nobody would've guessed that !```").format(winner_name, loser_name))
        else :
            await self.bot.send_message(bot_channel,("```{} defeated {} ! Congratulations : \n" + winner_message+"```").format(winner_name, loser_name))
        race.ongoing = False
        race.betsOn = False
        await displayOpenRaces(self.session,self.bot)
        sumup_channel = discord.utils.get(self.bot.get_all_channels(),name=SUMUP_CHANNEL)
        await self.bot.send_message(sumup_channel,"**Sum up of {}**\n```Winner : {} \nTotal coins bet :{} \n{} bets for {} ({} coins) \n{} bets for {} ({} coins) \nTotal coins paid : {} \nTotal profit : {}```".format(race, winner_name, total_bet,nb_bet_won,winner_name,coin_bet_win,nb_bet - nb_bet_won, loser_name, total_bet-coin_bet_win, total_paid, total_bet-total_paid))
        self.session.commit()

    @commands.command(help = "Cancel a match")
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def cancelMatch(self, race_id) :
        if (not self.session.query(exists().where(Race.id == race_id)).scalar()) :
            await self.bot.say("This race deosn't exist")
            return
        race = self.session.query(Race).get(race_id)
        if not race.ongoing :
            await self.bot.say("The race is already closed")
            return
        DaCream = self.session.query(Better).filter(Better.id == self.bot.user.id).first()
        totalbet = 0
        for bet in self.session.query(Bet).filter(Bet.race_id == race_id) : #Regroup better
            better = bet.better
            totalbet = totalbet + bet.coin_bet
            better.coin = better.coin + bet.coin_bet
            DaCream.coin = DaCream.coin - bet.coin_bet
        bot_channel = discord.utils.get(self.bot.get_all_channels(),name=BOT_CHANNEL)
        await self.bot.send_message(bot_channel,("```Match#{} is canceled, bet money has been refunded```").format(race.id))
        race.ongoing = False
        race.betsOn = False
        board_channel = self.bot.get_channel(board_id)
        await displayOpenRaces(self.session,self.bot)
        sumup_channel = discord.utils.get(self.bot.get_all_channels(),name=SUMUP_CHANNEL)
        await self.bot.send_message(sumup_channel,"**Sum up of {}**\n```Match#{} is canceled, {} coins have been refunded```".format(race,race.id,totalbet))
        job = self.session.query(Job).filter(Job.race_id == race_id).first()
        if job : self.session.delete(job)
        self.session.commit()
#back up command to cancel the outcome of a race in case of someone fuck up  ?

    @commands.command(help = "Link racer and better")
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def linkRacer(self, better_name, racer_name) :
        if not self.session.query(exists().where(Better.name == better_name)).scalar():
            await self.bot.say("This better doesn't exist")
            return
        if not self.session.query(exists().where(Racer.name == racer_name)).scalar():
            await self.bot.say("This better doesn't exist")
            return
        better =  self.session.query(Better).filter(Better.name == better_name).first()
        racer =  self.session.query(Racer).filter(Racer.name == racer_name).first()
        racer.better_id = better.id
        await self.bot.say("```{} (racer) has been linked to {} (better)```".format(racer.name, better.name))
        self.session.commit()

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

    @commands.command(help = "Schedule closing bet (anything dateparser can understand, google it lol)")
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def closeBetTime(self, race_id, time) :
        if (not self.session.query(exists().where(Race.id == race_id)).scalar()) :
            await self.bot.say("This match doesnt't exist")
            return
        race = self.session.query(Race).get(race_id)
        if race.betsOn == False :
            await self.bot.say("The bets are already closed for this race")
            return
        if self.session.query(exists().where(Job.race_id == race_id)).scalar() :
            job = self.session.query(Job).filter(Job.race_id == race_id).first()
            await self.bot.say("The bets for this match are already scheduled to be closed at {} UTC".format(job.date))
            return
        date = dateparser.parse(time)
        date = date.astimezone(pytz.utc)
        job = Job(date = date, race_id = race_id, race = race)
        self.session.add(job)
        self.session.commit()
        await self.bot.say("```The bets for the match#{} will be closed at {} UTC```".format(race_id,date))

    @commands.command(help = "Get scheduled jobs")
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def getJobs(self) :
        message = ""
        for job in self.session.query(Job) :
            message = message + "Match#{} : {} UTC \n".format(job.race_id,job.date)
        if message == "" : message = "No jobs are scheduled"
        await self.bot.say("```"+message+"```")

    @commands.command(help = "Cancel scheduled job")
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def cancelJob(self,race_id) :
        if not (self.session.query(exists().where(Job.race_id == race_id)).scalar()) :
            await self.bot.say("No jobs are scheduled for this match")
            return
        job = self.session.query(Job).filter(Job.race_id == race_id).first()
        self.session.delete(job)
        self.session.commit()
        await self.bot.say("Job for match#{} has been canceld".format(race_id))

    @commands.command(help = "List of all the racers")
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def racers(self) :
        await self.bot.say("Name | R+ | Trueskill | Better")
        for racer in self.session.query(Racer) :
            if racer.better :
                await self.bot.say(str(racer)+" | {}".format(racer.better.name))
            else :
                await self.bot.say(str(racer)+" | None")

    @commands.command(help = "Get a racers (Name, R+, Trueskill, Better)", aliases = ["getRacer"])
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def racer(self, racer_name) :
        racer =  self.session.query(Racer).filter(Racer.name == racer_name).first()
        if not racer :
            await self.bot.say("This racer doesnt't exist")
            return
        if racer.better :
            await self.bot.say(str(racer)+" | {}".format(racer.better.name))
        else :
            await self.bot.say(str(racer)+" | None")

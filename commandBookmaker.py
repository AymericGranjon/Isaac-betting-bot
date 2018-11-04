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
from classes import Base, Racer, Bet, Race, Better, Tournament
import mysql.connector
import itertools
import math
import trueskill
import texttable as tt



dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))  # Loading .env
db_adress = os.environ.get('DB_ADRESS')
board_id = os.environ.get('BOARD_ID')
bookmaker_role = os.environ.get('BOOKMAKER_ROLE')
db_racing = os.environ.get('DB_RACING')
bookmaker_channel = os.environ.get('BOOKMAKER_CHANNEL')
BOT_CHANNEL= os.environ.get('BOT_CHANNEL')
SUMUP_CHANNEL = os.environ.get('SUMUP_CHANNEL')
commision = 0.8 #We take 20% of the winnings, 1-commision actually

async def closeBetScheduled (race_id,bot, session) :

    channel = discord.utils.get(bot.get_all_channels(),name=bookmaker_channel)
    race = session.query(Race).get(race_id)
    race.betsOn = False
    await bot.send_message(channel,"The bets have been closed for the match#{}".format(race_id))
    session.commit()
    board_channel = bot.get_channel(board_id)
    message = bot.logs_from(board_channel, limit =1)
    async for m in message :
        await bot.delete_message(m)
    await bot.send_message(board_channel,displayOpenRaces(session))

def displayOpenRaces(session):
    open = tt.Texttable()
    open.set_max_width(0)
    open.set_precision(2)
    open.header(["Match#","Racer 1","Rate 1","Racer 2","Rate 2","Tournament","Format"])
    close = tt.Texttable()
    close.set_max_width(0)
    close.set_precision(2)
    close.header(["Match#","Racer 1","Rate 1","Racer 2","Rate 2","Tournament","Format"])
    for race in session.query(Race).filter(Race.ongoing == True):
        if race.betsOn == True :
            open.add_row([race.id,race.racer1.name,race.odd1,race.racer2.name,race.odd2,race.tournament.name,race.format])
        else :
            close.add_row([race.id,race.racer1.name,race.odd1,race.racer2.name,race.odd2,race.tournament.name,race.format])
    if open.draw() :
         open_string = open.draw()
    else : open_string = " "
    if close.draw() :
         close_string = close.draw()
    else : close_string = " "
    return "Open bets : ```"+open_string+"``` \n Closed bets : \n```" + close_string+"```"

class CommandBookmaker:
    def __init__(self, bot, session, scheduler):
        self.bot = bot
        self.session = session
        self.scheduler = scheduler

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
        race = Race(racer1_id = racer1.id, odd1 = self.getOddVs(racer1.name_racing, racer2.name_racing, format), racer2_id = racer2.id, odd2 = self.getOddVs(racer2.name_racing, racer1.name_racing ,format), ongoing = True, betsOn = True, format = format, tournament_id = tournament.id )
        self.session.add(race)
        self.session.commit()
        await self.bot.say("```Match created : \n" + str(race)+"```")
        board_channel = self.bot.get_channel(board_id)
        message = self.bot.logs_from(board_channel, limit =1)
        async for m in message :
            await self.bot.delete_message(m)
        await self.bot.send_message(board_channel,displayOpenRaces(self.session))

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
        board_channel = self.bot.get_channel(board_id)
        message =  self.bot.logs_from(board_channel, limit =1)
        async for m in message :
            await self.bot.delete_message(m)
        await self.bot.send_message(board_channel,displayOpenRaces(self.session))


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
        board_channel = self.bot.get_channel(board_id)
        message =  self.bot.logs_from(board_channel, limit =1)
        async for m in message :
            await self.bot.delete_message(m)
        await self.bot.send_message(board_channel,displayOpenRaces(self.session))

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
        elif race.racer2.name == racer_name :
            race.odd2 = odd
        else :
            await self.bot.say("{} is not in this race".format(racer_name))
        board_channel = self.bot.get_channel(board_id)
        message = self.bot.logs_from(board_channel, limit =1)
        async for m in message :
            await self.bot.delete_message(m)
        await self.bot.send_message(board_channel,displayOpenRaces(self.session))
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
        else :
            loser_name = race.racer1.name
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
        message = self.bot.logs_from(board_channel, limit =1)
        async for m in message :
            await self.bot.delete_message(m)
        if winner_message == "" :
            await self.bot.send_message(board_channel,("```{} defeated {} ! Nobody would've guessed that !```").format(winner_name, loser_name))
        else :
            await self.bot.send_message(board_channel,("```{} defeated {} ! Congratulations : \n" + winner_message+"```").format(winner_name, loser_name))
        race.ongoing = False
        race.betsOn = False
        await self.bot.send_message(board_channel,displayOpenRaces(self.session))
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
        message = self.bot.logs_from(board_channel, limit =1)
        async for m in message :
            await self.bot.delete_message(m)
        await self.bot.send_message(board_channel,displayOpenRaces(self.session))
        sumup_channel = discord.utils.get(self.bot.get_all_channels(),name=SUMUP_CHANNEL)
        await self.bot.send_message(sumup_channel,"**Sum up of {}**\n```Match#{} is canceled, {} coins have been refunded```".format(race,race.id,totalbet))
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

    @commands.command(help = "Schedule closing bet")
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
        for job in self.scheduler.get_jobs() :
            if job.args[0] == race_id :
                await self.bot.say("The bets for this match are already scheduled to be closed at {}".format(job.next_run_time.ctime()))
                return
        self.scheduler.add_job(closeBetScheduled,'date',run_date = time, args=[race_id,self.bot, self.session])
        await self.bot.say("```The bets for the match#{} will be closed at {}```".format(race_id,time))

    @commands.command(help = "Get scheduled jobs")
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def getJobs(self) :
        message = ""
        for job in self.scheduler.get_jobs() :
            message = message + "Match#{} : {} \n".format(job.args[0],job.next_run_time.ctime())
        if message == "" : message = "No jobs are scheduled"
        await self.bot.say("```"+message+"```")

    @commands.command(help = "Cancel scheduled job")
    @is_channel(channel_name = bookmaker_channel)
    @commands.has_role(bookmaker_role)
    async def cancelJob(self,race_id) :
        for job in self.scheduler.get_jobs() :
            if job.args[0] == race_id :
                job.remove()
        await self.bot.say("Schedule for match#{} canceled".format(race_id))

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
from commandBookmaker import commision, displayOpenRaces
import mysql.connector


dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))  # Loading .env
db_adress = os.environ.get('DB_ADRESS')
BOT_CHANNEL= os.environ.get('BOT_CHANNEL')
db_racing = os.environ.get('DB_RACING')
board_id = os.environ.get('BOARD_ID')
board_message_id = os.environ.get('BOARD_MESSAGE_ID')

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

    @commands.command(pass_context=True, help = "Gives the winrate of one racer over another (use R+ names)", usage = "!getWinrate <Racing+_name1> <Racing+_name2>")
    @is_channel(channel_name = BOT_CHANNEL)
    async def getWinrate(self, ctx, *racers) :
        if len(racers) == 1 :
            racer1_name = ctx.message.author.display_name
            racer2_name = racers[0]
        elif len(racers) == 2 :
            racer1_name = racers[0]
            racer2_name = racers[1]
        else :
            await self.bot.say('Bad argument')
            return
        result = self.getWinrateRacing(racer1_name, racer2_name)
        result = result.first()
        await self.bot.say("""```{} placed higher than {} {}% of the time out of {} races on Racing+!```""".format(racer1_name, racer2_name, result[0], result[1]))

    @is_channel(channel_name = BOT_CHANNEL)
    @commands.command(pass_context=True,
                 help = "Get the amount of coin you or an better have", usage = "!coin <better1> <better2> ...")
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
    @commands.command(pass_context=True, help = "Place a bet", usage = "!bet <Match#> <Winner_name> <coins_bet>")
    async def bet (self, ctx, race_id, winner_name, coin) : #no check if coin is an integer
        coin = abs(int(coin))
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
        DaCream = self.session.query(Better).filter(Better.id == self.bot.user.id).first()
        DaCream.coin = DaCream.coin + int(coin)
        self.session.add(bet)
        self.session.commit()
        await self.updateOdds(race)
        await self.bot.say("Bet placed")
        board_channel = self.bot.get_channel(board_id)
        board_message = await self.bot.get_message(board_channel, board_message_id)
        await self.bot.edit_message(board_message,displayOpenRaces(self.session))


    @is_channel(channel_name = BOT_CHANNEL)
    @commands.command(pass_context=True, help = "Get current bets")
    async def currentBets(self, ctx) :
        message = ""
        better = self.session.query(Better).get(ctx.message.author.id)
        for bet in self.session.query(Bet).filter(Bet.better_id == better.id) :
            if bet.race.ongoing == True :
                message = message + "\n" + str(bet)
        await self.bot.say("Your current bets are : ```"+message+"```")

    @is_channel(channel_name = BOT_CHANNEL)
    @commands.command(pass_context=True, help = "Top 10 richest people in the world")
    async def top(self) :
        topBetters = self.session.query(Better).order_by(Better.coin.desc()).limit(10)
        toplist = ""
        for better in topBetters :
            toplist =  toplist + better.name +" ({} coins) \n".format(better.coin)
        await self.bot.say("The top betters are : ```{}```".format(toplist))

    async def updateOdds(self, race) :
        matchBets = self.session.query(Bet).filter(Bet.race_id == race.id)
        nbBetUpdate = 10
        nbCoinUpdate = 3500
        totalCoin = 0
        totalPayoutRacer1 = 0
        totalPayoutRacer2 = 0
        maxDiff = 0.05
        nbBet = 0
        for bet in matchBets : #Moyenne exponentielle ?
            nbBet = nbBet + 1
            totalCoin = totalCoin + bet.coin_bet
            totalPayoutRacer1 = totalPayoutRacer1 +  bet.coin_bet*bet.odd*(bet.winner_id == race.racer1_id)
            totalPayoutRacer2 = totalPayoutRacer2 +  bet.coin_bet*bet.odd*(bet.winner_id == race.racer2_id)
            lastBet = bet

        if nbBet%nbBetUpdate == 0 or totalCoin%nbCoinUpdate < lastBet.coin_bet :
            winRate1 =  1/((race.odd1 -1)/commision + 1)
            winRate2 = 1/((race.odd2 -1)/commision + 1)
            if abs(totalPayoutRacer1/totalCoin - winRate1) > maxDiff :
                if (race.odd1 +0.2*(1/((totalPayoutRacer1/totalCoin -1)/commision + 1)))/1.2 >=1.05 :
                    race.odd1 = round((race.odd1 +0.2*(1/((totalPayoutRacer1/totalCoin -1)/commision + 1)))/1.2,2)
                else : race.odd1 = 1.05
            if abs(totalPayoutRacer2/totalCoin - winRate2) > maxDiff :
                if (race.odd2 +0.2*(1/((totalPayoutRacer2/totalCoin -1)/commision + 1)))/1.2 >=1.05 :
                    race.odd2 = round((race.odd2 +0.2*(1/((totalPayoutRacer2/totalCoin -1)/commision + 1)))/1.2,2)
                else : race.odd2 = 1.05
            self.session.commit()

def setup(bot):
    bot.add_cog(Better(bot))

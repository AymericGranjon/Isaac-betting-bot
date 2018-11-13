import os
import re
import dotenv
import discord
import math
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
from discord.utils import get
from sqlalchemy import func


dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))  # Loading .env
db_adress = os.environ.get('DB_ADRESS')
BOT_CHANNEL= os.environ.get('BOT_CHANNEL')
db_racing = os.environ.get('DB_RACING')
board_id = os.environ.get('BOARD_ID')
bookmaker_channel = os.environ.get('BOOKMAKER_CHANNEL')
BOT_CHANNEL= os.environ.get('BOT_CHANNEL')
BET_HISTORY = os.environ.get('BET_HISTORY')

class CommandBetter:
    def __init__(self, bot, session):
        self.bot = bot
        self.session = session

    def is_channel(**channel_name):
        def predicate(ctx):
            return ctx.message.channel.name in channel_name['channel_name']
        return commands.check(predicate)

    def getWinrateRacing(self, racer1_name, racer2_name) :
        engineR = create_engine(db_racing, echo =False)
        SessionR = sessionmaker(bind=engineR)
        sessionR = SessionR()
        query = ("""select SUM((t1.place < t2.place and t1.place!=-1) or (t1.place!=-1 and t2.place=-1))*100/SUM(t1.race_id = t2.race_id) as winrate, SUM(t1.race_id = t2.race_id) as gamePlayed
from race_participants t1, race_participants t2 where t1.user_id =(
        select id from users where username= '{}'
    )
and t2.user_id = (
        select id from users where username='{}'
    )
and t1.race_id = t2.race_id;""").format(racer1_name, racer2_name)
        toReturn = sessionR.execute(query)
        sessionR.close()
        return toReturn

    @commands.command(pass_context=True, help = "Gives the winrate of one racer over another (use R+ names)", usage = "!winrate <Racing+_name1> <Racing+_name2>")
    @is_channel(channel_name = BOT_CHANNEL)
    async def winrate(self, ctx, *racers) :
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
                 help = "Get the amount of coin you or an better have", usage = "!coin <better1> <better2> ...",
                 aliases = ["coins","c"])
    async def coin(self, ctx, *users) :
        if len(users) == 0 :
            better = self.session.query(Better).get(ctx.message.author.id)
            if better.coin == 0 :
                await self.bot.say("0 coins you fucking degenerate")
            else :
                await self.bot.say('You have {:d} coins'.format(better.coin))
        else :
            for name in users :
                if self.session.query(exists().where(Better.name == name)).scalar() :
                    better =  self.session.query(Better).filter(Better.name == name).first()
                    await self.bot.say('{:s} has {:d} coins'.format(better.name, better.coin))
                else :
                    await self.bot.say("{:s} doesn't exist".format(name))


    @is_channel(channel_name = [BOT_CHANNEL,"betting-board"])
    @commands.command(pass_context=True, help = "Place a bet", usage = "!bet <Match#> <Winner_name> <coins_bet>")
    async def bet (self, ctx, race_id, winner_name, coin) : #no check if coin is an integer
        bot_channel = discord.utils.get(self.bot.get_all_channels(),name=BOT_CHANNEL)
        race_id = re.search(r'\d+$', race_id)
        if race_id == None :
            await self.bot.send_message(bot_channel,"This race doesn't exist")
            return
        race_id = int(race_id.group())
        if (not self.session.query(exists().where(Race.id == race_id)).scalar()) :
            await self.bot.send_message(bot_channel,"This race doesn't exist")
            return
        race = self.session.query(Race).get(race_id)
        if not race.betsOn :
            await self.bot.send_message(bot_channel,"The bets for this race are closed")
            return
        if  not (race.racer1.name.lower() == winner_name.lower() or race.racer2.name.lower() == winner_name.lower() ) :
            await self.bot.send_message(bot_channel,"{} is not in this race".format(winner_name))
            return
        better =  self.session.query(Better).get(ctx.message.author.id)
        pikaO = get(self.bot.get_all_emojis(), name='pikaO')
        if (better.id == race.racer1.better_id or better.id == race.racer2.better_id) :
            await self.bot.send_message(bot_channel,"{} just tried to bet on their own race {}".format(better.name,pikaO))
            return
        punOko = get(self.bot.get_all_emojis(), name='PunOko')
        if coin.isdigit() == False :
            await self.bot.send_message(bot_channel,"Stop trying to break me {}".format(punOko))
            return
        if  int(coin) <= 0 :
            await self.bot.send_message(bot_channel,"Stop trying to break me {}".format(punOko))
            return
        if (better.coin - int(coin) <0) :
            await self.bot.send_message(bot_channel,"You don't have enough coins. Current balance : {}".format(better.coin))
            return
        winner = self.session.query(Racer).filter(func.lower(Racer.name) == func.lower(winner_name)).first()
        if race.racer1_id == winner.id :
            odd = race.odd1
        elif race.racer2_id == winner.id :
            odd = race.odd2
        else :
            await self.bot.send_message(bot_channel,"Database error")
            return
        bet = Bet(better_id = ctx.message.author.id, better = better, race_id = race_id, race = race, winner_id = winner.id, winner = winner, coin_bet = coin, odd = odd)
        better.coin = better.coin - int(coin)
        DaCream = self.session.query(Better).filter(Better.id == self.bot.user.id).first()
        DaCream.coin = DaCream.coin + int(coin)
        self.session.add(bet)
        self.session.commit()
        await self.updateOdds(race)
        await self.bot.send_message(bot_channel,"```{} just bet {} coin that {} will win match#{}```".format(better.name,bet.coin_bet,winner.name,bet.race_id))
        board_channel = self.bot.get_channel(board_id)
        bet_history_channel = discord.utils.get(self.bot.get_all_channels(),name=BET_HISTORY)
        await self.bot.send_message(bet_history_channel,"```{} just bet {} coin that {} will win match#{} at {} rate```".format(better.name,bet.coin_bet,winner.name,bet.race_id,bet.odd))
        await displayOpenRaces(self.session,self.bot)


    @is_channel(channel_name = BOT_CHANNEL)
    @commands.command(pass_context=True, help = "Get current bets", aliases = ["bets", "Bets", "currentbets"])
    async def currentBets(self, ctx) :
        message = ""
        better = self.session.query(Better).get(ctx.message.author.id)
        for bet in self.session.query(Bet).filter(Bet.better_id == better.id) :
            if bet.race.ongoing == True :
                message = message + "\n" + str(bet)
        if message == "" : message = "You have no bet placed"
        await self.bot.say("Your current bets are : ```"+message+"```")

    @is_channel(channel_name = BOT_CHANNEL)
    @commands.command(pass_context=True, help = "Top richest people in the world")
    async def top(self) :
        bets = self.session.query(Bet)
        betters = self.session.query(Better)
        top = [[],[]]
        toplist = ""
        for better in betters :
            coins = better.coin
            for bet in self.session.query(Bet).filter(Bet.better == better) :
                race = bet.race
                if race.ongoing == True :
                    coins = coins + bet.coin_bet
            if int(better.id) != int(self.bot.user.id) :
                if len(top[0]) == 0 :
                    top = [[better.name],[coins]]
                elif len(top[0]) < 10 :
                    top[0].append(better.name)
                    top[1].append(coins)
                elif min(top[1]) <= coins :
                    index_min = min(range(len(top[1])), key=top[1].__getitem__)
                    top[0][index_min] = better.name
                    top[1][index_min] = coins
        while len(top[0]) != 0 :
            index_max = max(range(len(top[1])), key=top[1].__getitem__)
            toplist =  toplist + top[0][index_max] +" ({} coins) \n".format(top[1][index_max])
            del top[0][index_max]
            del top[1][index_max]
        await self.bot.say("The top betters are : ```{}```".format(toplist))

    @is_channel(channel_name = BOT_CHANNEL)
    @commands.command(pass_context=True, help = "Top poorest people in the world", aliases = ["losers"])
    async def bottom(self) :
        bets = self.session.query(Bet)
        betters = self.session.query(Better)
        top = [[],[]]
        toplist = ""
        for better in betters :
            coins = better.coin
            for bet in self.session.query(Bet).filter(Bet.better == better) :
                race = bet.race
                if race.ongoing == True :
                    coins = coins + bet.coin_bet
            if int(better.id) != int(self.bot.user.id) :
                if len(top[0]) == 0 :
                    top = [[better.name],[coins]]
                elif len(top[0]) < 10 :
                    top[0].append(better.name)
                    top[1].append(coins)
                elif max(top[1]) >= coins :
                    index_min = max(range(len(top[1])), key=top[1].__getitem__)
                    top[0][index_min] = better.name
                    top[1][index_min] = coins
        while len(top[0]) != 0 :
            index_max = min(range(len(top[1])), key=top[1].__getitem__)
            toplist =  toplist + top[0][index_max] +" ({} coins) \n".format(top[1][index_max])
            del top[0][index_max]
            del top[1][index_max]
        await self.bot.say("The top losers are : ```{}```".format(toplist))

    async def updateOdds(self, race) :
        matchBets = self.session.query(Bet).filter(Bet.race_id == race.id)
        nbBetUpdate = 10
        nbCoinUpdate = 3500
        totalCoin = 0
        totalBetRacer1 = 1
        totalBetRacer2 = 1
        maxDiff = 0.05
        nbBet = 0
        for bet in matchBets : #Moyenne exponentielle ?
            nbBet = nbBet + 1
            totalCoin = totalCoin + bet.coin_bet
            totalBetRacer1 = totalBetRacer1 +  bet.coin_bet*(bet.winner_id == race.racer1_id)
            totalBetRacer2 = totalBetRacer2 +  bet.coin_bet*(bet.winner_id == race.racer2_id)
            lastBet = bet

        if nbBet%nbBetUpdate == 0 or totalCoin%nbCoinUpdate < lastBet.coin_bet :
            winRate1 =  1/((race.odd1 -1)/commision + 1)
            winRate2 = 1/((race.odd2 -1)/commision + 1)
            if abs(totalBetRacer1/totalCoin - winRate1) > maxDiff :
                if  abs(max(min(round((race.odd1 +0.2*(1+(1/(totalBetRacer1/totalCoin) - 1)*commision))/1.2,2),10),1.05) - race.odd1) <= 2 :
                    race.odd1 = max(min(round((race.odd1 +0.2*(1+(1/(totalBetRacer1/totalCoin) - 1)*commision))/1.2,2),10),1.05)
                else : race.odd1 = race.odd1 + math.copysign(1,max(min(round((race.odd1 +0.2*(1+(1/(totalBetRacer1/totalCoin) - 1)*commision))/1.2,2),10),1.05) - race.odd1)*2
            if abs(totalBetRacer2/totalCoin - winRate2) > maxDiff :
                if  abs(max(min(round((race.odd2 +0.2*(1+(1/(totalBetRacer2/totalCoin) - 1)*commision))/1.2,2),10),1.05) - race.odd2) <= 2 :
                    race.odd2 = max(min(round((race.odd2 +0.2*(1+(1/(totalBetRacer2/totalCoin) - 1)*commision))/1.2,2),10),1.05)
                else : race.odd2 = race.odd2 + math.copysign(1,max(min(round((race.odd2 +0.2*(1+(1/(totalBetRacer2/totalCoin) - 1)*commision))/1.2,2),10),1.05) - race.odd2)*2
            race.odd1 = round(min(max(race.odd1,1.05),10),2)
            race.odd2 = round(min(max(race.odd2,1.05),10),2)
            self.session.commit()

    @is_channel(channel_name = BOT_CHANNEL)
    @commands.command(pass_context=True, help = "10 last bets", aliases = ["pastbets", "past"])
    async def pastBets(self, ctx) :
        list = ""
        better =  self.session.query(Better).get(ctx.message.author.id)
        bets = self.session.query(Bet).join(Bet.race).filter(Bet.better_id == better.id).filter(Race.ongoing == False).order_by(Bet.id.desc()).limit(10)
        for bet in bets :
            if bet.race.tournament :
                list = list + "Match#{} : {} vs {} on {} for {}, {} coins on {} at {} \n".format(bet.race_id, bet.race.racer1.name,bet.race.racer2.name,bet.race.format,bet.race.tournament.name, bet.coin_bet, bet.winner.name, bet.odd)
            else :
                list = list + "Match#{} : {} vs {} on {}, {} coins on {} at {} \n".format(bet.race_id, bet.race.racer1.name,bet.race.racer2.name,bet.race.format, bet.coin_bet, bet.winner.name, bet.odd)
        await self.bot.say("Your last 10 bets are : ```" + list + "```")

    @is_channel(channel_name = BOT_CHANNEL)
    @commands.command(pass_context=True, help = "How good are you ?", aliases = ["howgood", "howGood","Howgood","howgoodiam"])
    async def howGoodIAm(self, ctx) :
        better = self.session.query(Better).get(ctx.message.author.id)
        won = 0
        lost = 0
        profit = 0
        coin_lost = 0
        coin_won =0
        for bet in self.session.query(Bet).filter(Bet.better_id == better.id) :
            if (bet.winner_id == bet.race.racer1_id and bet.race.winner == 1) or (bet.winner_id == bet.race.racer2_id and bet.race.winner == 2) :
                won = won + 1
                coin_won = coin_won + round(bet.coin_bet*bet.odd) - bet.coin_bet
            elif (bet.winner_id == bet.race.racer1_id and bet.race.winner == 2) or (bet.winner_id == bet.race.racer2_id and bet.race.winner == 1) :
                lost = lost + 1
                coin_lost = coin_lost + bet.coin_bet
        profit = coin_won - coin_lost
        if (won+lost == 0) :
            winrate = 0
        else :
            winrate = round(won*100/(won+lost),2)
        await self.bot.say("```You won {}/{} bets ({}%) and have a results of {} coins ({} won, {} lost)```".format(won,won+lost,winrate,profit,coin_won,coin_lost))
